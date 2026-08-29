#!/usr/bin/env python3
"""make_interface_card.py — штемпель карточки: ОДНА команда -> готовый .md-скелет карточки, где
ФАКТИЧЕСКИЕ секции заполнены детерминированно, а прозаические — строки-ДИРЕКТИВЫ
`<|Agent: … |>`, которые ЛЛМ дописывает, прочитав исходник.

Ничего нового не анализирует — ОРКЕСТРИРУЕТ три факта:
  - объявленная поверхность + сигнатуры   <- единый источник:
        Python  → show_pyfile_api.collect (ast — точные типы параметров),
        TS/JS   → get_codeblock declarations (структурные заголовки блоков),
        (C# — позже; сейчас только факты потребления/зависимостей).
  - потреблённая поверхность               <- find_code_usage downstream
    (кто РЕАЛЬНО импортит символы цели; вскрывает leaked-private и dead surface).
  - зависимости самой цели                 <- find_code_usage --incoming (резолв в файлы).

Формат — из CARD_FORMAT.py (единый контракт). Мультиязычно: объявления берутся из
языко-агностичного `declarations`, факты потребления/зависимостей уже мультиязычны.

Использование:
    python make_interface_card.py <file> --project-root PATH
"""

import argparse
import difflib
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import CARD_FORMAT as cf
from graph_from_cards import _cells, _is_sep


_LANG = {".py": "python", ".ts": "typescript", ".tsx": "typescript",
         ".js": "typescript", ".jsx": "typescript", ".cs": "csharp"}


def _lang(file):
    return _LANG.get(os.path.splitext(file)[1].lower(), "python")


# The LLM fills prose; the stamp keeps the machine FACT line and the agent DIRECTIVE line
# separate so line-based patch edits never collide (the fact is editable too — just a line).
# Все директивы строятся через cf.agent() -> единый маркер `<|Agent: … |>` (детект в CARD_FORMAT).
DIRECTIVE_DESC = cf.agent("replace with a concise, sufficient one-liner — what it does and its role; or delete this line if trivial")
DIRECTIVE_SUMMARY = cf.agent("replace with a concise one-line summary — what this file is and does")
DIRECTIVE_HOWITWORKS = cf.agent("describe the actual mechanism/flow after reading the source; keep it precise — do NOT generalize a per-case detail to \"each/every\" unless it holds for all")
DIRECTIVE_WHY = cf.agent("why?")

# H4 declaration kind -> H3 subsection label (order below drives emission order).
_KIND_H3 = {"function": "Functions", "class": "Classes", "interface": "Interfaces",
            "enum": "Enums", "type": "Types", "namespace": "Namespaces",
            "const": "Constants", "let": "Constants", "var": "Constants",
            "struct": "Classes", "record": "Classes"}
_H3_ORDER = ["Functions", "Classes", "Interfaces", "Enums", "Types", "Constants", "Namespaces"]


# --- fact producers ----------------------------------------------------------

def _cis_setup(project_root, file):
    """Mirror of test/check.py: resolve target names + handler for import_search."""
    from find_code_usage.core import resolve_target_names
    from find_code_usage.handlers import get_handler
    _t, target_names = resolve_target_names(file, None, "", project_root)
    file_arg = file if os.path.isabs(file) else os.path.join(project_root, file)
    target_abs = os.path.abspath(file_arg)
    lang = _lang(file)
    handler = get_handler(lang)
    if lang == "csharp" and hasattr(handler, "_extract_namespace"):
        ns = handler._extract_namespace(target_abs)
        if ns:
            target_names.add(ns)
            parts = ns.split(".")
            for i in range(1, len(parts)):
                target_names.add(".".join(parts[:i]))
    return project_root, target_names, target_abs, lang, handler


def consumers_of(project_root, file):
    """{symbol: [(consumer_rel, kind, [lines])]} — who really imports the target's symbols."""
    from find_code_usage.core import scan_downstream
    pr, target_names, target_abs, lang, handler = _cis_setup(project_root, file)
    data, _dyn = scan_downstream(pr, handler, target_names, target_abs, lang, True, [], False)
    out = defaultdict(list)
    for consumer, syms in data.items():
        for sym, info in syms.items():
            out[sym].append((consumer, info["kind"], info["lines"]))
    for sym in out:
        out[sym].sort()
    return dict(out)


def deps_of(project_root, file):
    """(resolved, externals): the target's own upstream imports resolved to files."""
    from find_code_usage.core import scan_incoming
    from find_code_usage.resolvers import get_resolver
    pr, target_names, target_abs, lang, handler = _cis_setup(project_root, file)
    resolver = get_resolver(lang)
    resolved, externals, _usages, _stats = scan_incoming(resolver, target_abs, pr, handler=handler, verbose=False)
    return resolved, externals


def _resolve_sibling_signature(target_abs, module, level, name):
    """Best-effort signature of a re-exported `name` from a relative import
    `from <dots><module> import name` — resolve to a sibling .py and read its ast (Python)."""
    if level <= 0:
        return None
    base = Path(target_abs).parent
    for _ in range(level - 1):
        base = base.parent
    parts = module.split(".") if module else []
    cand = base.joinpath(*parts)
    for p in (cand.with_suffix(".py"), cand / "__init__.py"):
        if p.is_file():
            try:
                import show_pyfile_api
                return show_pyfile_api.collect(p).get("all_defs", {}).get(name)
            except Exception:
                return None
    return None


# --- declared surface (single source, per language) --------------------------

def _decl_backend():
    """DECL_BACKEND from CONFIG__TOOLS: 'auto' | 'treesitter' | 'regex' (default 'auto')."""
    try:
        import CONFIG__TOOLS
        return getattr(CONFIG__TOOLS, "DECL_BACKEND", "auto")
    except Exception:
        return "auto"


# Per-language tree-sitter backend module + the pip package that supplies its grammar.
_TS_BACKEND = {
    "typescript": ("get_codeblock.handlers.ts_treesitter", "tree-sitter-typescript"),
    "csharp": ("get_codeblock.handlers.cs_treesitter", "tree-sitter-c-sharp"),
}
_WARNED = set()   # warn once per (language) per process


def _warn_fallback(lang, pkg, forced):
    if lang in _WARNED:
        return
    _WARNED.add(lang)
    how = "DECL_BACKEND=treesitter but its grammar is missing" if forced else \
          "high-fidelity tree-sitter backend not installed"
    sys.stderr.write(
        f"[make_interface_card] WARNING: {how} for {lang} - running in the REGEX FALLBACK "
        f"(lower-fidelity signatures). For a full parse install:  "
        f"pip install tree-sitter {pkg}   (or set CONFIG__TOOLS.DECL_BACKEND='regex' to silence)\n"
    )


def _declarations(lang, src):
    """Declared surface for a brace language via DECL_BACKEND (tree-sitter or regex).

    Emits a one-time stderr WARNING when `auto`/`treesitter` wanted tree-sitter but the
    grammar isn't installed, so an agent knows results are the lower-fidelity fallback.
    """
    backend = _decl_backend()
    mod_name, pkg = _TS_BACKEND[lang]
    if backend in ("treesitter", "auto"):
        try:
            import importlib
            ts = importlib.import_module(mod_name)
            if ts.available():
                return ts.declarations(src)
            _warn_fallback(lang, pkg, forced=(backend == "treesitter"))
        except Exception as e:
            sys.stderr.write(f"[make_interface_card] WARNING: tree-sitter backend for {lang} failed ({e}); using regex.\n")
    from get_codeblock.handlers import get_handler
    return get_handler(lang).declarations(src.splitlines(keepends=True))


def _declared(project_root, file, lang):
    """Language-agnostic declared surface. Returns:
      {docstring_first, exports:[{name,kind,signature,methods}], all_defs:{name:sig},
       reexports:[{name,source[,module,level]}]}
    Python via show_pyfile_api(ast) — precise param types; TS/JS via get_codeblock declarations.
    """
    empty = {"docstring_first": None, "exports": [], "all_defs": {}, "reexports": []}
    target_abs = file if os.path.isabs(file) else os.path.join(project_root, file)

    if lang == "python":
        import show_pyfile_api
        c = show_pyfile_api.collect(Path(target_abs))
        exports = [{"name": f["name"], "kind": "function", "signature": f["signature"], "methods": []}
                   for f in c["functions"]]
        exports += [{"name": cl["name"], "kind": "class", "signature": cl["name"], "methods": cl["methods"]}
                    for cl in c["classes"]]
        all_defs = dict(c["all_defs"])
        for g in c["module_globals"]:
            all_defs.setdefault(g, g)
        reexports = [{"name": nm, "source": "." * imp["level"] + imp["module"],
                      "module": imp["module"], "level": imp["level"]}
                     for imp in c["import_froms"] if imp["level"] >= 1 for nm in imp["names"]]
        return {"docstring_first": c["docstring_first"], "exports": exports,
                "all_defs": all_defs, "reexports": reexports}

    if lang == "typescript":
        try:
            src = open(target_abs, encoding="utf-8", errors="replace").read()
        except OSError:
            return empty
        decls = _declarations("typescript", src)
        exports, all_defs, reexports = [], {}, []
        for d in decls:
            if d["kind"] == "reexport":
                reexports.append({"name": d["name"], "source": d["reexport_from"]})
                continue
            all_defs[d["name"]] = d["signature"]
            if d["exported"]:
                exports.append({"name": d["name"], "kind": d["kind"],
                                "signature": d["signature"], "methods": []})
        return {"docstring_first": None, "exports": exports, "all_defs": all_defs, "reexports": reexports}

    if lang == "csharp":
        try:
            src = open(target_abs, encoding="utf-8", errors="replace").read()
        except OSError:
            return empty
        exports, all_defs = [], {}
        for d in _declarations("csharp", src):
            all_defs[d["name"]] = d["signature"]
            if d["exported"]:
                exports.append({"name": d["name"], "kind": d["kind"],
                                "signature": d["signature"], "methods": d.get("methods", [])})
        return {"docstring_first": None, "exports": exports, "all_defs": all_defs, "reexports": []}

    return empty  # unknown language — declared surface TBD; facts still come from import_search


# --- formatting --------------------------------------------------------------

def _consumers_fact(sym, consumers):
    """A plain, generated fact line: who really imports `sym`."""
    c = consumers.get(sym)
    if not c:
        return "consumers 0"
    return f"consumers {len(c)}: " + ", ".join(f for f, _k, _ln in c)


# --- merge: сохранить прозу человека, освежить факты -------------------------
# Проза висит на КЛЮЧЕ-имени (символа/секции), не на позиции и не на сигнатуре —
# поэтому переезд заголовков и смена сигнатуры прозу не роняют. Незаполненный слот =
# строка-директива `<|Agent: … |>`; её мы прозой не считаем.

def _is_ph(line):
    """True, если строка — незаполненная директива агенту (`<|Agent: … |>`, терпит легаси)."""
    return cf.is_agent_directive(line)


# Слова-обёртки языка, которые могут стоять ПЕРЕД именем в сигнатуре ("function foo",
# "async def foo", "public static void Foo", "class Widget"). Имя ищем не угадыванием
# по "первому слову" (ломается на любой обёртке), а по ПОЗИЦИИ: токен перед первой `(`
# (вызываемое — функция/метод), иначе токен перед первым `=` (присвоение), иначе — то,
# что останется после отбрасывания слева известных слов этого языка (класс/интерфейс/
# голый Python). Новый язык — новая копия набора, ничего в логике не меняется.
_DECORATORS = {
    "python": ("async",),
    "typescript": ("export", "default", "declare", "async", "function", "class",
                   "interface", "enum", "type", "namespace", "abstract", "public",
                   "private", "protected", "readonly", "static", "const", "let", "var"),
    "csharp": ("public", "private", "protected", "internal", "static", "virtual",
               "override", "sealed", "abstract", "async", "readonly", "partial",
               "new", "class", "interface", "struct", "enum", "record", "const"),
}
_IDENT_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
_TRAILING_IDENT_RE = re.compile(r"([A-Za-z_$][A-Za-z0-9_$]*)\s*$")


def _strip_decorators(text, lang):
    """Срезает слева известные служебные слова ЭТОГО языка, пока не упрёмся в то, что
    декоратором не является — остаток начинается с настоящего имени объявления."""
    words = _DECORATORS.get(lang, ())
    s = text
    while True:
        m = _IDENT_RE.match(s)
        if not m or m.group(0) not in words:
            return s
        s = s[m.end():].lstrip()


def _name_before(text, sep):
    """Идентификатор непосредственно перед первым вхождением sep, если он там есть."""
    i = text.find(sep)
    if i == -1:
        return None
    m = _TRAILING_IDENT_RE.search(text[:i])
    return m.group(1) if m else None


def _h4_raw_text(h4_line):
    """'#### `foo(x) -> y`  ← .bar' -> 'foo(x) -> y' — сырой текст сигнатуры без decor'а H4."""
    e = h4_line.strip()[4:].strip()
    # Сначала вырезаем код-спан по ЗАКРЫВАЮЩЕМУ бэктику. strip("`") этого не
    # умеет: он кусает только у самых концов строки, а у ре-экспорта после
    # закрывающего бэктика стоит "← .module" — и бэктик приклеивался к имени
    # ('delegate_core`'). Ключ переставал совпадать с эмиссией, и проза такой
    # записи ТЕРЯЛАСЬ на каждой перештамповке, заменяясь свежей директивой.
    if e.startswith("`"):
        rest = e[1:]
        e = rest.split("`", 1)[0] if "`" in rest else rest
    e = e.strip().strip("`").strip()
    return e.lstrip("\\").lstrip("*").lstrip("\\").strip()


def _entry_key(h4_line, lang=None):
    """'#### `foo(x) -> y`  ← .bar' -> 'foo' (имя записи — ключ merge).

    Сигнатура — текст ДЛЯ ЧЕЛОВЕКА («function foo(x)», «public static void Foo(x)»,
    «const X = […]»), не идентификатор сам по себе. Имя ищем по позиции, а не угадыванием
    по первому слову (то ломается на любой языковой обёртке — см. REQ-004+005 design).
    """
    e = _h4_raw_text(h4_line)
    eq, paren = e.find("="), e.find("(")
    if eq != -1 and (paren == -1 or eq < paren):
        name = _name_before(e, "=")
        if name:
            return name
    if paren != -1:
        name = _name_before(e, "(")
        if name:
            return name
    stripped = _strip_decorators(e, lang)
    m = _IDENT_RE.match(stripped)
    if m:
        return m.group(0)
    return e.split("(")[0].split("=")[0].split(" ")[0].strip()  # legacy fallback, никогда не падает


_SIM_THRESHOLD = 0.6
_MARK_SIG_CHANGED = "⚠ поменялась сигнатура - "


def _mark_renamed(old_name):
    return f"⚠ похоже на переименование, было `{old_name}` - "


def _norm_name(name):
    return re.sub(r"[^A-Za-z0-9]", "", name).lower()


def _similarity(a, b):
    return difflib.SequenceMatcher(None, _norm_name(a), _norm_name(b)).ratio()


def _resolve_entry_identities(new_syms, op, report):
    """Сопоставляет новые записи (name, group, sig) со старой прозой: сначала точное имя,
    остаток — по похожести (переименование). Возвращает (resolved, renamed_from):
    resolved[name] = строки прозы (с маркером при расхождении) или None (директива);
    renamed_from = имена старых записей, забранные fuzzy-паройой (не в Salvage)."""
    old_entries = op.get("entries", {})
    resolved = {}
    used_old = set()

    for name, _group, sig in new_syms:
        old = old_entries.get(name)
        if old is None:
            resolved[name] = None
            continue
        used_old.add(name)
        desc = old["desc"]
        if desc and old.get("sig") != sig:
            desc = [_MARK_SIG_CHANGED + desc[0]] + desc[1:]
        resolved[name] = desc if desc else None

    leftover_new = [(name, group) for name, group, _sig in new_syms if resolved.get(name) is None]
    leftover_old = [nm for nm in old_entries if nm not in used_old and old_entries[nm]["desc"]]
    renamed_from = set()

    for name, group in leftover_new:
        best, best_score = None, 0.0
        for onm in leftover_old:
            if onm in renamed_from or old_entries[onm]["group"] != group:
                continue
            score = _similarity(name, onm)
            if score > best_score:
                best, best_score = onm, score
        if best is not None and best_score >= _SIM_THRESHOLD:
            desc = old_entries[best]["desc"]
            resolved[name] = [_mark_renamed(best) + desc[0]] + desc[1:]
            renamed_from.add(best)
            report["renamed"].append(f"{best} -> {name}")

    return resolved, renamed_from


def _parse_entries(body, P, lang=None):
    """H4-записи Public API -> P['entries'][name] = {'desc','block','sig','group'}."""
    entries, cur, group = [], None, None
    for ln in body:
        s = ln.strip()
        if s.startswith("### "):
            group = s[4:].strip()
            cur = None
        elif s.startswith("#### "):
            cur = {"name": _entry_key(ln, lang), "sig": _h4_raw_text(ln), "group": group, "block": [ln]}
            entries.append(cur)
        elif cur is not None:
            cur["block"].append(ln)
    for cur in entries:
        block = cur["block"]
        desc = [ln for ln in block[1:]
                if ln.strip() and not _is_ph(ln)
                and not ln.strip().startswith("consumers ")
                and not ln.lstrip().startswith("- ")]  # `- ` = метод (факт), не проза
        if cur["name"]:
            P["entries"][cur["name"]] = {"desc": desc, "block": block, "sig": cur["sig"], "group": cur["group"]}


def _cells_raw(row):
    """Как _cells, но БЕЗ снятия бэктиков — для колонок со свободной прозой.

    `_cells` снимает бэктики с каждой ячейки, и для факт-колонок (Import /
    File Path / Symbols) это верно: они всегда обёрнуты. Но `Why` — проза
    человека, и она законно НАЧИНАЕТСЯ или ЗАКАНЧИВАЕТСЯ инлайн-кодом
    (`` `old_string` ``). Прогон merge через _cells съедал этот краевой бэктик,
    и на каждой перештамповке карточка теряла по одному, пока код-спан не
    разваливался. graph_from_cards читает только факт-колонки, поэтому там
    _cells остаётся правильным — чинить надо здесь, а не у него.
    """
    return [c.strip() for c in row.strip().strip("|").split("|")]


def _parse_why(body, P):
    """Колонка `Why` таблицы Dependencies Internal -> P['why'][import] = текст."""
    data = [r for r in body if r.strip().startswith("|") and not _is_sep(_cells(r))]
    if len(data) < 2:
        return
    header = [cf.canon(c) for c in _cells(data[0])]
    if "Import" not in header or "Why" not in header:
        return
    imp_i, why_i = header.index("Import"), header.index("Why")
    for r in data[1:]:
        cells = _cells(r)
        raw = _cells_raw(r)
        if max(imp_i, why_i) >= len(cells):
            continue
        imp = cells[imp_i].strip().strip("`").strip()
        # Индексируем по backtick-снятой версии, а ЗНАЧЕНИЕ берём из сырой:
        # ключ — факт, значение — проза.
        why = raw[why_i].strip() if why_i < len(raw) else cells[why_i].strip()
        if imp and why and not _is_ph(why) and why != cf.EMPTY:
            P["why"][imp] = why


def _parse_old_prose(text, lang=None):
    """Проза человека из существующей карточки, по ключу-имени. -> dict слотов."""
    lines = text.splitlines()
    P = {"summary": None, "entries": {}, "why": {}, "ext_note": [], "sections": {}}

    h1 = next((i for i, ln in enumerate(lines)
               if ln.strip().startswith("# ") and not ln.strip().startswith("## ")), None)
    if h1 is not None:
        for ln in lines[h1 + 1:]:
            s = ln.strip()
            if s.startswith("## "):
                break
            if not s or s.startswith("docstring 1st line:") or _is_ph(ln):
                continue
            P["summary"] = s
            break

    secs, cur = [], None
    for ln in lines:
        if ln.strip().startswith("## "):
            cur = [ln.strip()[3:].strip(), []]
            secs.append(cur)
        elif cur is not None:
            cur[1].append(ln)

    for raw, body in secs:
        name = cf.canon(raw)
        if name == "Public API":
            _parse_entries(body, P, lang)
        elif name == "Dependencies Internal":
            _parse_why(body, P)
        elif name == "Dependencies External":
            note = [ln for ln in body if ln.strip() and not _is_ph(ln)
                    and ln.strip() not in (cf.EMPTY, "external imports:")
                    and not ln.strip().startswith(("import ", "from "))]
            if note:
                P["ext_note"] = note
        elif name.startswith("Salvage"):
            keep = [ln for ln in body if ln.strip()]
            if keep:
                P["sections"]["Salvage"] = keep
        elif name in ("How it works", "Doc links", "Discrepancies", "Package layout"):
            keep = [ln for ln in body if ln.strip() and not _is_ph(ln)
                    and ln.strip() != cf.EMPTY
                    and not ln.strip().startswith("known submodules (re-exported from):")]
            if keep:
                P["sections"][name] = keep
    return P


_SALVAGE_H2 = "Salvage (снято при re-stamp — перенеси нужное выше или удали)"


def build_card(project_root, file, old_prose=None, report=None):
    lang = _lang(file)
    fname = os.path.basename(file)
    is_pkg = cf.is_package(fname)

    consumers = consumers_of(project_root, file)
    resolved, externals = deps_of(project_root, file)
    declared = _declared(project_root, file, lang)
    target_abs = file if os.path.isabs(file) else os.path.join(project_root, file)

    op = old_prose or {"summary": None, "entries": {}, "why": {}, "ext_note": [], "sections": {}}
    if report is None:
        report = {}
    for k in ("preserved_entries", "new_entries", "salvaged", "renamed"):
        report.setdefault(k, [])
    report.setdefault("kept_sections", [])
    report.setdefault("merged", old_prose is not None)

    # ---- Public API: собрать ВСЕ новые записи (имя/группа/сигнатура) ДО рендера строк —
    # identity-resolution (точное имя -> fuzzy на переименование, REQ-004+005 design) должна
    # видеть картину целиком, а не решать по одной записи за раз в порядке вывода. -----------
    by_h3 = defaultdict(list)
    for e in declared["exports"]:
        by_h3[_KIND_H3.get(e["kind"], "Objects")].append(e)

    new_syms = [(e["name"], h3, e["signature"])
                for h3 in _H3_ORDER + ["Objects"] for e in by_h3.get(h3, [])]
    placed = {name for name, _, _ in new_syms}

    reexport_sigs = {}
    if is_pkg:
        for r in declared["reexports"]:
            sig = None
            if lang == "python" and "module" in r:
                sig = _resolve_sibling_signature(target_abs, r["module"], r["level"], r["name"])
            reexport_sigs[r["name"]] = sig if sig else r["name"]
            new_syms.append((r["name"], "Re-exports", reexport_sigs[r["name"]]))
            placed.add(r["name"])

    # Consumed internals: symbols DEFINED here that other files really import but that are
    # not part of the declared/exported surface — the leaked interface. Intersecting with
    # "defined here" drops reverse-index false-positives.
    defined_here = set(declared["all_defs"])
    leftover = sorted(s for s in consumers if s not in placed and s in defined_here)
    leftover_sigs = {sym: (declared["all_defs"].get(sym) or sym) for sym in leftover}
    new_syms += [(sym, cf.CONSUMED_SUBSECTION, leftover_sigs[sym]) for sym in leftover]

    resolved_desc, renamed_from = _resolve_entry_identities(new_syms, op, report)
    emitted = set()   # все имена записей, вписанных в НОВУЮ карточку (для Salvage)

    lines = [f"# {fname}", ""]

    def emit_desc(name):
        """Однострочник записи: старая проза по имени/похожести, иначе директива (+отчёт)."""
        emitted.add(name)
        desc = resolved_desc.get(name)
        if desc:
            lines.extend(desc)
            report["preserved_entries"].append(name)
        else:
            lines.append(DIRECTIVE_DESC)
            if old_prose is not None:
                report["new_entries"].append(name)

    def prose_section(title, default):
        """Секция-проза целиком: старое тело по ключу-секции, иначе плейсхолдер."""
        lines.append(f"## {title}")
        lines.append("")
        kept = op["sections"].get(title)
        if kept:
            lines.extend(kept)
            report["kept_sections"].append(title)
        else:
            lines.append(default)

    # Summary: проза (первая непустая строка после H1) — сохраняем; docstring-подсказка — факт.
    if op["summary"]:
        lines.append(op["summary"])
        report["kept_sections"].append("summary")
    else:
        lines.append(DIRECTIVE_SUMMARY)
    if declared["docstring_first"]:
        lines.append(f"docstring 1st line: {declared['docstring_first']}")
    lines.append("")

    # ---- Package layout (package/facade only) ----
    if is_pkg:
        srcs = sorted({r["source"] for r in declared["reexports"]})
        lines.append("## Package layout")
        lines.append("")
        if srcs:
            lines.append("known submodules (re-exported from): " + ", ".join(srcs))
        pl = op["sections"].get("Package layout")
        if pl:
            lines.extend(pl)
            report["kept_sections"].append("Package layout")
        else:
            lines.append(cf.agent("one line per submodule — what it holds"))
        lines.append("")

    # ---- Public API ----
    lines.append("## Public API")
    lines.append("")

    for h3 in _H3_ORDER + ["Objects"]:
        group = by_h3.get(h3)
        if not group:
            continue
        lines.append(f"### {h3}")
        for e in group:
            lines.append(f"#### `{e['signature']}`")
            lines.append(_consumers_fact(e["name"], consumers))
            emit_desc(e["name"])
            for m in e.get("methods", []):
                lines.append(f"    - `{m['signature']}`")
        lines.append("")

    # Re-exports (facade only): names surfaced onward from sibling modules.
    if is_pkg and declared["reexports"]:
        lines.append("### Re-exports")
        for r in declared["reexports"]:
            lines.append(f"#### `{reexport_sigs.get(r['name'], r['name'])}`  ← {r['source']}")
            lines.append(_consumers_fact(r["name"], consumers))
            emit_desc(r["name"])
        lines.append("")

    if leftover:
        lines.append(f"### {cf.CONSUMED_SUBSECTION}")
        for sym in leftover:
            lines.append(f"#### `{leftover_sigs[sym]}`")
            lines.append(_consumers_fact(sym, consumers))
            emit_desc(sym)
        lines.append("")

    if not (any(by_h3.values()) or (is_pkg and declared["reexports"]) or leftover):
        lines.append("(none)")
        lines.append("")

    # ---- Dependencies Internal ----
    lines.append("## Dependencies Internal")
    lines.append("")
    if resolved:
        lines.append("| Import | File Path | Symbols | Why | Kind |")
        lines.append("|---|---|---|---|---|")
        for r in resolved:
            syms = ", ".join(f"`{s}`" for s in r["symbols"]) if r["symbols"] else ""
            key = os.path.basename(r["file"]).rsplit(".", 1)[0]
            why = op["why"].get(key, DIRECTIVE_WHY)
            lines.append(f"| `{key}` | `{r['file']}` | {syms} | {why} | normal |")
    else:
        lines.append(cf.EMPTY)
    lines.append("")

    # ---- Dependencies External ----
    lines.append("## Dependencies External")
    lines.append("")
    det = [d for d in sorted(set(externals)) if "__future__" not in d]  # drop `from __future__ …` noise
    if det:
        lines.append("external imports:")
        lines.extend(det)
        if op["ext_note"]:
            lines.extend(op["ext_note"])
            report["kept_sections"].append("Dependencies External")
        else:
            lines.append(cf.agent("optional — one line ONLY if a lib above is non-obvious; else DELETE this line (do NOT edit the import list)"))
    else:
        lines.append(cf.EMPTY)
    lines.append("")

    # ---- prose-only sections ----
    prose_section("How it works", DIRECTIVE_HOWITWORKS)
    lines.append("")
    prose_section("Doc links", cf.EMPTY)
    lines.append("")
    prose_section("Discrepancies", cf.agent("docstring vs code contradictions; else write (none)"))

    # ---- Salvage: проза записей, которых в коде больше нет (не теряем молча) ----
    old_salv = op["sections"].get("Salvage", [])
    orphans = [nm for nm, e in op["entries"].items()
               if nm not in emitted and nm not in renamed_from and e["desc"]]
    if old_salv or orphans:
        lines.append("")
        lines.append(f"## {_SALVAGE_H2}")
        lines.append("")
        if old_salv:
            lines.extend(old_salv)
        for nm in orphans:
            lines.extend(op["entries"][nm]["block"])
            report["salvaged"].append(nm)

    # Нумерация — ПОСЛЕДНИМ шагом, над готовым текстом: одна точка вместо счётчика,
    # протянутого через каждое место emit'а, и по построению покрывает любую
    # директиву, включая протащенную merge'ем из старой карточки.
    return cf.number_directives("\n".join(lines) + "\n")


def _card_path(project_root_abs, file_rel):
    """__map/<path>.md для файла (root-relative), с сохранением расширения исходника."""
    return os.path.join(project_root_abs, "__map", file_rel + ".md")


def _stamp_to_file(project_root_abs, file_rel, out_path, force, discard_prose=False):
    """Штемпелит один файл В out_path. На существующей карточке — MERGE (если не --force).
    `--force` на карточке с непустой прозой без `discard_prose` НЕ пишет — возвращает 'blocked'
    (REQ-004: force — дешёвый флаг из мышечной памяти, а стирает дорогую человеческую прозу).
    Возвращает (status, report): status ∈ {'new','merged','forced','blocked'}."""
    old_prose = None
    existed = os.path.exists(out_path)
    if existed:
        try:
            old_prose = _parse_old_prose(open(out_path, encoding="utf-8").read(), _lang(file_rel))
        except OSError:
            old_prose = None
    if force and old_prose and not discard_prose and _prose_blocks(old_prose):
        return "blocked", {"prose_blocks": _prose_blocks(old_prose)}
    if force:
        old_prose = None  # настоящий force: не мерджим, даже если распарсили выше для guard'а
    report = {}
    card = build_card(project_root_abs, file_rel, old_prose, report)
    out_dir = os.path.dirname(os.path.abspath(out_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(card)
    return ("merged" if old_prose is not None else ("forced" if existed else "new")), report


def _print_merge_delta(out, report):
    """stderr-дельта merge: что сохранено / что переименовано / что дописать / что разобрать."""
    ne, sv, pe, ks = (report["new_entries"], report["salvaged"],
                      report["preserved_entries"], report["kept_sections"])
    rn = report.get("renamed", [])
    sys.stderr.write(f"[make_interface_card] merged {out}\n")
    sys.stderr.write(f"  prose kept: {len(pe)} entries" + (f" + {', '.join(ks)}" if ks else "") + "\n")
    if rn:
        sys.stderr.write(f"  RENAMED — matched by similarity, verify: {', '.join(rn)}\n")
    if ne:
        sys.stderr.write(f"  NEW — fill prose: {', '.join(ne)}\n")
    if sv:
        sys.stderr.write(f"  SALVAGED — removed from code, moved to '## Salvage': {', '.join(sv)}\n")
    if not ne and not sv and not rn:
        sys.stderr.write("  facts refreshed; no new or removed entries\n")


def _prose_blocks(op):
    """Сколько прозных блоков реально заполнено (не пусто, не директива) — считает guard --force."""
    n = sum(1 for e in op.get("entries", {}).values() if e["desc"])
    if op.get("summary"):
        n += 1
    return n + len(op.get("why", {})) + len(op.get("sections", {}))


def _config_lang_testdirs():
    lang, test_dirs = "python", []
    try:
        import CONFIG__TOOLS
        lang = getattr(CONFIG__TOOLS, "LANGUAGE", "python") or "python"
        test_dirs = list(getattr(CONFIG__TOOLS, "TEST_DIRS", []) or [])
    except Exception:
        pass
    return lang, test_dirs


def _normalize_langs(value):
    """LANGUAGE (скаляр ИЛИ список) / --language -> список канонных языков.

    Полиглотный репозиторий — норма, а не край: у нас питон-плагин и его же
    JS-фронтенд лежат в ОДНОМ дереве. Разбор карточки и так пофайловый
    (`_lang(file)` смотрит на расширение), одноязычным был только выбор того,
    ЧТО попадёт в массовый проход. Скаляр продолжает работать как раньше.
    `"all"` = все известные языки.
    """
    if isinstance(value, str):
        items = [p.strip() for p in value.replace(",", " ").split()]
    elif isinstance(value, (list, tuple, set)):
        items = [str(p).strip() for p in value]
    else:
        items = []
    known = set(_LANG.values())
    out, seen = [], set()
    for it in items:
        if not it:
            continue
        low = it.lower()
        if low == "all":
            return sorted(known)
        # Синонимы, которыми язык называют в CLI других тулов пакета.
        low = {"ts": "typescript", "js": "typescript", "tsx": "typescript",
               "cs": "csharp", "py": "python"}.get(low, low)
        if low in known and low not in seen:
            seen.add(low)
            out.append(low)
    return out


def _lang_extensions(lang):
    """Расширения одного языка ИЛИ списка языков. Неизвестное -> все известные."""
    langs = _normalize_langs(lang)
    if not langs:
        return set(_LANG)   # неизвестный/пустой язык -> все известные расширения
    exts = {e for e, l in _LANG.items() if l in langs}
    return exts or set(_LANG)


def _stamp_all(project_root_abs, force, language=None, discard_prose=False):
    """BULK: штемпелит ВСЕ исходники под project-root в __map/.

    Языки: `language` (CLI) если задан, иначе CONFIG__TOOLS.LANGUAGE — и то и
    другое принимает список/через запятую/`all`.
    """
    from find_code_usage.core import collect_files, rel_path
    lang, test_dirs = _config_lang_testdirs()
    selected = language if language else lang
    langs = _normalize_langs(selected)
    exts = _lang_extensions(selected)
    files = collect_files(project_root_abs, exts, test_dirs=test_dirs, tests_only=False)
    # Печатаем ЯЗЫКИ, а не только расширения: молчаливый пропуск JS-файлов в
    # питон-проекте — ровно то, из-за чего эта опция и появилась. Пусть видно,
    # по какому набору шли, даже когда всё нашлось.
    sys.stderr.write(f"[make_interface_card] --all: languages={langs or 'ALL'} "
                     f"exts={sorted(exts)}\n")
    if not files:
        sys.stderr.write(f"[make_interface_card] --all: no {sorted(exts)} files under {project_root_abs}\n")
        return 0
    counts = {"new": 0, "merged": 0, "forced": 0, "blocked": 0, "error": 0}
    for abs_path in files:
        rel = rel_path(abs_path, project_root_abs)
        try:
            status, rep = _stamp_to_file(project_root_abs, rel, _card_path(project_root_abs, rel),
                                          force, discard_prose)
            counts[status] += 1
            if status == "blocked":
                sys.stderr.write(f"  BLOCKED {rel}: has prose ({rep['prose_blocks']} blocks); "
                                  f"add --discard-prose to confirm --force here\n")
        except Exception as e:  # один битый файл не должен валить весь проход
            counts["error"] += 1
            sys.stderr.write(f"  ERROR {rel}: {e}\n")
    sys.stderr.write(
        f"[make_interface_card] --all: {len(files)} files -> {counts['new']} new, "
        f"{counts['merged']} merged, {counts['forced']} forced, {counts['blocked']} blocked, "
        f"{counts['error']} errors\n")
    return 1 if (counts["error"] or counts["blocked"]) else 0


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Card stamp: fact-filled card skeleton for a file", add_help=False)
    ap.add_argument("-h", "--help", action="help", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    ap.add_argument("file", nargs="?", help="target source file (root-relative or absolute); omit with --all")
    ap.add_argument("--project-root", type=str, default=".", help="project root for the reverse index")
    ap.add_argument("--out", type=str, default=None,
                    help="write the card to this file (default: print to stdout)")
    ap.add_argument("--force", action="store_true",
                    help="discard the existing card and write a FRESH stamp "
                         "(default on an existing card is MERGE — refresh facts, keep prose). "
                         "On a card that already has prose, also requires --discard-prose.")
    ap.add_argument("--discard-prose", action="store_true",
                    help="confirms --force on a card that already has filled-in prose "
                         "(without it, --force on such a card is REFUSED, exit 2 — see REQ-004)")
    ap.add_argument("--all", action="store_true",
                    help="BULK maintainer pre-stamp: stamp EVERY source file under --project-root "
                         "(by --language, else CONFIG__TOOLS.LANGUAGE) each to __map/<path>.md. Skips "
                         ".git/__pycache__/__map/__HQ/.venv/node_modules/... and CONFIG__TOOLS.TEST_DIRS. "
                         "Existing cards MERGE (facts refreshed, prose kept); add --force to reset them. "
                         "Ignores <file> and --out. One-shot way to seed/refresh a whole tree's card skeletons.")
    ap.add_argument("--language", type=str, default=None,
                    help="--all only: which languages to stamp, overriding CONFIG__TOOLS.LANGUAGE. "
                         "Comma/space separated, or 'all'. Accepts python/typescript/csharp and the "
                         "short forms py/ts/js/tsx/cs (js and tsx are the typescript handler). "
                         "A POLYGLOT repo is the reason this exists: with a scalar LANGUAGE the bulk "
                         "pass silently skipped every file of the other language.")
    args = ap.parse_args()

    project_root_abs = os.path.abspath(args.project_root)

    if args.all:
        return _stamp_all(project_root_abs, args.force, args.language, args.discard_prose)

    if not args.file:
        ap.error("either a <file> argument or --all is required")

    out = args.out
    if not out:
        # Без --out — просто печать штемпеля в stdout (без merge: файла-цели нет).
        print(build_card(project_root_abs, args.file, None, {}))
        return 0

    status, report = _stamp_to_file(project_root_abs, args.file, out, args.force, args.discard_prose)
    if status == "blocked":
        n = report["prose_blocks"]
        sys.stderr.write(
            f"[make_interface_card] REFUSED: {out} has prose ({n} filled blocks); "
            f"--force would discard it silently. Merge is the default — drop --force. "
            f"To reset anyway: --force --discard-prose\n")
        return 2
    elif status == "merged":
        _print_merge_delta(out, report)
    elif status == "forced":
        sys.stderr.write(f"[make_interface_card] wrote {out} (--force: fresh stamp, prior prose discarded)\n")
    else:
        sys.stderr.write(f"[make_interface_card] wrote {out}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
