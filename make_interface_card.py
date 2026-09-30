#!/usr/bin/env python3
"""make_interface_card.py — штемпель карточки: ОДНА команда -> готовый .md-скелет карточки, где
ФАКТИЧЕСКИЕ секции заполнены детерминированно, а прозаические — строки-ДИРЕКТИВЫ
`<|Agent: … |>`, которые ЛЛМ дописывает, прочитав исходник.

Ничего нового не анализирует — ОРКЕСТРИРУЕТ три факта:
  - объявленная поверхность + сигнатуры   <- единый источник:
        Python  → show_pyfile_api.collect (ast — точные типы параметров),
        TS/JS/C# → get_codeblock declarations (структурные заголовки блоков);
        какой язык чем — реестр `stamp_langs/` (модуль на язык, форма — его CONTRACT.md).
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
import seam_scanner
import stamp_langs
from graph_from_cards import (_cells, _is_sep, escape_cell, load_config_at, resolve_cards_dir,
                              resolve_project_root, split_cells)


TOOL_NAME = "make_interface_card"


def _is_absolute_path(p):
    """Check if path is absolute (Unix or Windows style) — same helper as get_codeblock's, kept
    local rather than shared (tools stay independent of each other on purpose, see DECISIONS.md).
    Matters because this tool and its CONFIG__TOOLS.py routinely run mixed Windows/docker-Linux."""
    if Path(p).is_absolute():
        return True
    return bool(p and len(p) >= 2 and p[1] == ':')


def _load_logging_config():
    """Best-effort read of the opt-in call-logging config from CONFIG__TOOLS.py.

    Returns (enabled, log_dir, base). `base` anchors a relative LOG_DIR: config schema >= 2 ->
    this tool's own __HQ (Vision08: our paths hang off the HQ, which may live outside the
    sources); older configs -> PROJECT_ROOT, as before. enabled is False whenever CONFIG__TOOLS.py
    is missing, doesn't list this tool, or anything else about reading it goes wrong — logging
    must never be why the tool fails to run."""
    try:
        import CONFIG__TOOLS as c
        schema = getattr(c, "CONFIG_SCHEMA_VERSION", 1) or 1
        base = Path(__file__).resolve().parent.parent if schema >= 2 else c.PROJECT_ROOT
        return TOOL_NAME in (c.LOG_ENABLED_TOOLS or []), c.LOG_DIR, base
    except Exception:
        return False, None, None


def _log_call(record):
    """Append one JSONL diagnostic line for this invocation (argv/status/exit_code/duration/
    error — never a card's actual content). No-op unless this tool is listed in
    CONFIG__TOOLS.LOG_ENABLED_TOOLS. Swallows every error: a logging failure must never affect
    the tool's real behavior or exit code. Same mechanism as get_codeblock's (see its core.py) —
    kept as its own copy, not a shared module, for the same independence reason as above."""
    try:
        enabled, log_dir, project_root = _load_logging_config()
        if not enabled:
            return
        import json
        import time as _time
        log_dir = log_dir or "."
        # Relative LOG_DIR is anchored to the HQ (schema >= 2) or PROJECT_ROOT (older configs),
        # never the process's cwd — this tool is routinely invoked from arbitrary directories.
        base = Path(project_root) if project_root and not _is_absolute_path(log_dir) else None
        log_path = (base / log_dir if base else Path(log_dir)) / f"{TOOL_NAME}.log.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        record.setdefault("ts", _time.strftime("%Y-%m-%dT%H:%M:%S"))
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _lang(file):
    """Канонное имя языка файла — по реестру `stamp_langs`. Незнакомое расширение —
    ValueError, а НЕ молча python (раньше `.h` ушёл бы в Python-разбор)."""
    lang = stamp_langs.for_file(file)
    if lang is None:
        raise ValueError(f"no stamp language for '{os.path.splitext(file)[1] or file}' "
                         f"(known: {' '.join(sorted(stamp_langs.all_extensions()))})")
    return lang.NAME


# The LLM fills prose; the stamp keeps the machine FACT line and the agent DIRECTIVE line
# separate so line-based patch edits never collide (the fact is editable too — just a line).
# Все директивы строятся через cf.agent() -> единый маркер `<|Agent: … |>` (детект в CARD_FORMAT).
DIRECTIVE_DESC = cf.agent("write short does+role, or remove")
DIRECTIVE_SUMMARY = cf.agent("replace with a concise one-line summary — what this file is and does")
DIRECTIVE_HOWITWORKS = cf.agent("describe the actual mechanism/flow after reading the source; keep it precise — do NOT generalize a per-case detail to \"each/every\" unless it holds for all")
DIRECTIVE_WHY = cf.agent("why?")

# H4 declaration kind -> H3 subsection label (order below drives emission order).
_KIND_H3 = {"function": "Functions", "class": "Classes", "interface": "Interfaces",
            "enum": "Enums", "type": "Types", "namespace": "Namespaces",
            "const": "Constants", "let": "Constants", "var": "Constants",
            "struct": "Classes", "record": "Classes", "macro": "Macros"}
_H3_ORDER = ["Functions", "Classes", "Interfaces", "Enums", "Types", "Constants", "Macros", "Namespaces"]


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
    target_names |= stamp_langs.get(lang).extra_target_names(handler, target_abs)
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


# --- declared surface (single source, per language) --------------------------

def _declared(project_root, file, lang):
    """Объявленная поверхность — от модуля языка в `stamp_langs` (форма dict'а заморожена в
    `stamp_langs/CONTRACT.md`): {docstring_first, exports:[{name,kind,signature,methods}],
    all_defs:{name:sig}, reexports:[{name,source[,…]}]}."""
    target_abs = file if os.path.isabs(file) else os.path.join(project_root, file)
    return stamp_langs.get(lang).declared_surface(project_root, target_abs)


# --- formatting --------------------------------------------------------------

def _consumers_fact(sym, consumers):
    """Generated fact lines: who really imports `sym` — one consumer per line (Plan02 pt.1),
    so two branches each adding a different new consumer add two different LINES instead of
    both rewriting the same single comma-joined line (guaranteed git conflict otherwise)."""
    c = consumers.get(sym)
    if not c:
        return ["consumers 0"]
    return [f"consumers {len(c)}:"] + [f"- {f}" for f, _k, _ln in c]


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
# голый Python). Набор слов — `DECORATORS` модуля языка в `stamp_langs`.
_IDENT_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
_TRAILING_IDENT_RE = re.compile(r"([A-Za-z_$][A-Za-z0-9_$]*)\s*$")


def _strip_decorators(text, lang):
    """Срезает слева известные служебные слова ЭТОГО языка, пока не упрёмся в то, что
    декоратором не является — остаток начинается с настоящего имени объявления."""
    mod = stamp_langs.get(lang)
    words = mod.DECORATORS if mod else ()
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
    mod = stamp_langs.get(lang)
    if mod is not None:
        own = mod.entry_key(e)     # language knows its own signature shapes (C++: typedef/#define)
        if own:
            return own
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
                and not ln.strip().startswith("condition: ")   # C/C++ `#if` fact (Plan08)
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
    return [c.strip() for c in split_cells(row)]


def _parse_why(body, P):
    """LEGACY: колонка `Why` таблицы In-Project Dependencies -> P['why'][import] = текст.

    Kept as a one-way migration bridge (Plan02 pt.3): a NEW-format table has no `Why`
    column at all, so `"Why" not in header` makes this a safe no-op on already-migrated
    cards — no need to tell old/new apart before calling it."""
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


def _parse_why_section(body, P):
    """NEW: bullet list under '### Why these imports are used...' -> P['why'][import] = текст
    (Plan02 pt.3). Safe no-op on a legacy body that has no such H3 at all — `in_why` just
    never turns True. Writes into the SAME dict as `_parse_why`; the two never actually
    collide in practice, a card is either still table-Why (legacy) or already has this
    section (migrated), never both meaningfully at once."""
    in_why = False
    for ln in body:
        s = ln.strip()
        if s.startswith("### "):
            in_why = s[4:].strip().lower().startswith("why")
            continue
        if not in_why or not s.startswith("- "):
            continue
        item = s[2:]
        if " — " not in item:
            continue
        key, why = item.split(" — ", 1)
        key, why = key.strip().strip("`").strip(), why.strip()
        if key and why and not _is_ph(why) and why != cf.EMPTY:
            P["why"][key] = why


def _parse_old_prose(text, lang=None):
    """Проза человека из существующей карточки, по ключу-имени. -> dict слотов."""
    lines = text.splitlines()
    # Card-format version marker (Plan02 pt.0) is stamped as the file's LAST line, but
    # nothing about its POSITION is load-bearing for parsing — strip it out of `lines`
    # globally, before any section splitting, so no individual section parser (summary,
    # Discrepancies, Salvage, whichever happens to be physically last) needs its own
    # special-case to avoid swallowing it as content.
    lines = [ln for ln in lines if not cf.is_version_comment(ln)]
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
        elif name == "In-Project Dependencies":
            _parse_why(body, P)          # legacy table-Why column (no-op on new-format tables)
            _parse_why_section(body, P)  # new bullet-list Why (no-op on legacy bodies)
        elif name == "External Dependencies":
            # "(none)" is kept here too (not filtered like it used to be): the note's own
            # directive now says "else write (none)" (REQ-009 — "DELETE this line" left no
            # trace, so merge couldn't tell "agent said nothing applies" from "agent never
            # looked" and kept reinserting the directive on every re-stamp).
            note = [ln for ln in body if ln.strip() and not _is_ph(ln)
                    and ln.strip() != "external imports:"
                    and not ln.strip().startswith(("import ", "from "))]
            if note:
                P["ext_note"] = note
        elif name.startswith("Salvage"):
            keep = [ln for ln in body if ln.strip()]
            if keep:
                P["sections"]["Salvage"] = keep
        elif name == "Package layout":
            # The fact ("known submodules (re-exported from):" + its own "- mod" bullets,
            # Plan02 pt.2) has to be told apart from human prose that may ALSO be bullet-shaped
            # (this section's own instructed style is "one line per submodule"), so content
            # alone can't disambiguate a "- " line. Signal used instead: whether the header
            # line has content right after its colon — legacy inline ("...from): a, b") does,
            # new bullet form ("...from):" alone, list follows) doesn't; only in the latter
            # case do we know it's safe to skip the following "- " run as fact, not prose.
            body2 = body
            for i, ln in enumerate(body):
                s = ln.strip()
                if s.startswith("known submodules (re-exported from):"):
                    rest = s[len("known submodules (re-exported from):"):].strip()
                    if rest:
                        body2 = body[i + 1:]          # legacy inline — one line, nothing more to skip
                    else:
                        j = i + 1
                        while j < len(body) and body[j].lstrip().startswith("- "):
                            j += 1
                        body2 = body[j:]              # new bullet form — skip the whole run
                    break
            keep = [ln for ln in body2 if ln.strip() and not _is_ph(ln)]
            if keep:
                P["sections"]["Package layout"] = keep
        elif name == cf.RUNTIME_SEAMS_SECTION:
            # Whole section is human/agent prose (Vision07 — the stamp cannot reconstruct a
            # runtime connection from source), preserved as-is. The ONE fact line in it — the
            # contract note — is filtered here and re-stamped fresh on every render, same
            # treatment as the version marker.
            keep = [ln for ln in body if ln.strip() and not cf.is_seam_contract_line(ln)]
            if keep:
                P["sections"][cf.RUNTIME_SEAMS_SECTION] = keep
        elif name in ("How it works", "Doc links", "Discrepancies"):
            # Discrepancies' own directive instructs "else write (none)" — that literal answer
            # IS the agent's deliberate, filled-in verdict, not an unfilled slot (REQ-009). Every
            # other section here never gets told to write cf.EMPTY as a real answer, so for them
            # a bare "(none)" still means "nothing kept" as before.
            drop_empty_marker = name != "Discrepancies"
            keep = [ln for ln in body if ln.strip() and not _is_ph(ln)
                    and (not drop_empty_marker or ln.strip() != cf.EMPTY)]
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
            sig = stamp_langs.get(lang).reexport_signature(target_abs, r)
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
            lines.append("known submodules (re-exported from):")
            lines.extend(f"- {s}" for s in srcs)
            # Blank line is the boundary the parser uses to stop skipping "- " lines as fact
            # (Plan02 pt.2) — the instructed prose style for this section ("one line per
            # submodule") is itself bullet-shaped, so content alone can't tell our fact
            # bullets apart from a human's own; position (before/after this blank) can.
            lines.append("")
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
            if e.get("cond"):
                lines.append(f"condition: {e['cond']}")
            lines.extend(_consumers_fact(e["name"], consumers))
            emit_desc(e["name"])
            for m in e.get("methods", []):
                lines.append(f"    - `{m['signature']}`")
        lines.append("")

    # Re-exports (facade only): names surfaced onward from sibling modules.
    if is_pkg and declared["reexports"]:
        lines.append("### Re-exports")
        for r in declared["reexports"]:
            lines.append(f"#### `{reexport_sigs.get(r['name'], r['name'])}`  ← {r['source']}")
            lines.extend(_consumers_fact(r["name"], consumers))
            emit_desc(r["name"])
        lines.append("")

    if leftover:
        lines.append(f"### {cf.CONSUMED_SUBSECTION}")
        for sym in leftover:
            lines.append(f"#### `{leftover_sigs[sym]}`")
            lines.extend(_consumers_fact(sym, consumers))
            emit_desc(sym)
        lines.append("")

    if not (any(by_h3.values()) or (is_pkg and declared["reexports"]) or leftover):
        lines.append("(none)")
        lines.append("")

    # ---- In-Project Dependencies ----
    # Plan02 pt.3: table is FACT-ONLY now (no Why column) — one row per SYMBOL, not per file,
    # so two branches adding different symbols imported from the same file add two different
    # table LINES instead of both rewriting the same joined-Symbols cell (guaranteed conflict
    # otherwise). Why moves to its own bullet list below, keyed by import — a human's prose
    # never again requires reproducing the whole row (facts) just to append one description.
    lines.append("## In-Project Dependencies")
    lines.append("")
    if resolved:
        lines.append("| Import | File Path | Symbols | Kind |")
        lines.append("|---|---|---|---|")
        seen_keys = []  # first-seen order, deduped — drives the Why list below
        for r in resolved:
            key = os.path.basename(r["file"]).rsplit(".", 1)[0]
            if key not in seen_keys:
                seen_keys.append(key)
            kind = escape_cell(r.get("kind") or "normal")   # C/C++: conditional(<#if>)
            if r["symbols"]:
                for s in r["symbols"]:
                    lines.append(f"| `{key}` | `{r['file']}` | `{s}` | {kind} |")
            else:
                lines.append(f"| `{key}` | `{r['file']}` |  | {kind} |")
        lines.append("")
        lines.append("### Why these imports are used (one line per import — free text)")
        for key in seen_keys:
            why = op["why"].get(key, DIRECTIVE_WHY)
            lines.append(f"- `{key}` — {why}")
    else:
        lines.append(cf.EMPTY)
    lines.append("")

    # ---- External Dependencies ----
    lines.append("## External Dependencies")
    lines.append("")
    det = [d for d in sorted(set(externals)) if "__future__" not in d]  # drop `from __future__ …` noise
    if det:
        lines.append("external imports:")
        lines.extend(det)
        if op["ext_note"]:
            lines.extend(op["ext_note"])
            report["kept_sections"].append("External Dependencies")
        else:
            lines.append(cf.agent("one line ONLY if a lib above is non-obvious; else write (none) (do NOT edit the import list)"))
    else:
        lines.append(cf.EMPTY)
    lines.append("")

    # ---- language fact sections (C/C++: ## Build facts) — pure fact, rebuilt every stamp;
    # the parser drops them (unknown to _parse_old_prose), so nothing stale survives a merge.
    for title, body in stamp_langs.get(lang).fact_sections(project_root, target_abs, declared):
        lines.append(f"## {title}")
        lines.append("")
        lines.extend(body)
        lines.append("")

    # ---- prose-only sections ----
    prose_section("How it works", DIRECTIVE_HOWITWORKS)
    lines.append("")
    prose_section("Doc links", cf.EMPTY)
    lines.append("")
    prose_section("Discrepancies", cf.agent("docstring vs code contradictions; else write (none)"))

    # ---- Runtime seams (optional; Plan03/Vision07) ----
    # Never created empty and never carries a directive — the stamp cannot reconstruct a runtime
    # connection from source, so once written the table is pure human/agent prose, kept as-is
    # except the contract line (a fact, refreshed like the version marker). If the section is
    # absent, the detector only ever produces a HINT (report["seam_hint"]) — never a section,
    # never a directive (same anti-pattern lesson as REQ-009: an empty placeholder that comes
    # back on every stamp devalues "awaiting agent" as a status).
    seams = op["sections"].get(cf.RUNTIME_SEAMS_SECTION)
    if seams:
        lines.append("")
        lines.append(f"## {cf.RUNTIME_SEAMS_SECTION}")
        lines.append("")
        lines.append(cf.seam_contract_line())
        lines.append("")
        lines.extend(seams)
        report["kept_sections"].append(cf.RUNTIME_SEAMS_SECTION)
    elif seam_scanner.scan(target_abs):
        report["seam_hint"] = True

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

    # Card-format version — ALWAYS the literal last line (Plan02 pt.0): which contract
    # version wrote this exact file, readable without opening any other tool's source.
    lines.append("")
    lines.append(cf.version_comment())

    # Нумерация — ПОСЛЕДНИМ шагом, над готовым текстом: одна точка вместо счётчика,
    # протянутого через каждое место emit'а, и по построению покрывает любую
    # директиву, включая протащенную merge'ем из старой карточки.
    return cf.number_directives("\n".join(lines) + "\n")


def _card_path(cards_dir, file_rel):
    """<cards_dir>/<path>.md для файла (root-relative), с сохранением расширения исходника.
    cards_dir — из общего резолвера card-тулов (Vision08: --cards-dir > MAP_DIR > <root>/__map)."""
    return os.path.join(str(cards_dir), file_rel + ".md")


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


def _config_lang_testdirs(project_root):
    """LANGUAGE/TEST_DIRS from the TARGET project's CONFIG__TOOLS (REQ-007), not from whatever
    `CONFIG__TOOLS.py` happens to sit next to this script."""
    mod = load_config_at(project_root)
    if mod is None:
        return "python", []
    lang = getattr(mod, "LANGUAGE", "python") or "python"
    test_dirs = list(getattr(mod, "TEST_DIRS", []) or [])
    return lang, test_dirs


def _seams_help_text():
    """Full Runtime seams contract — this is what the card's contract-note line points to
    (Vision07: the ONE source of truth for the format, not a separate doc file that can rot)."""
    return "\n".join([
        "Runtime seams — machine-readable table for connections the import graph can't see",
        "(dynamic load by path, a separate process, a shared file/store, an event bus).",
        "",
        f"Section: '## {cf.RUNTIME_SEAMS_SECTION}' — OPTIONAL, only when there is something to",
        "describe. The stamp never creates it empty and never edits an existing one, except the",
        "contract-note line above the table (refreshed every stamp, like the version marker).",
        "",
        f"Columns: {' | '.join(cf.SEAM_COLUMNS)}",
        "",
        "Kind (channel) — closed vocabulary; direction suffix required only where ambiguous:",
        "  by-path            dynamic load of a module/file by a COMPUTED path, same process",
        "                     (spec_from_file_location, require(computed), reflection)",
        "  process            launches/controls a SEPARATE OS process (subprocess.run, os.system,",
        "                     child_process.spawn) — a second row on the same target if there's",
        "                     also a real data exchange after launch",
        "  http               network call (REST or any transport)",
        "  file:reads         shared persistent storage (file / db row / in-memory store)",
        "  file:writes        (direction is NOT implied by whose card this is — state it)",
        "  file:reads+writes",
        "  event:emits        pub/sub, event bus, websocket",
        "  event:listens",
        "",
        "Shape (independent axis — any Kind can be any Shape):",
        "  dependent   disappearance of the target breaks the CONSUMING side",
        "  equal       breaks BOTH sides (shared contract/format, neither is more \"main\")",
        "  reference   breaks NOTHING — just loses context/observability for a human",
        "",
        "Who writes the row: the dependent/consuming side (same convention as normal imports —",
        "the graph computes the reverse edge itself; don't hand-write it on the target's card too).",
        "",
        "Example:",
        "| Target | Symbol | Kind | Shape | Why |",
        "|---|---|---|---|---|",
        "| `promo_engine.py` | `apply_discount` | by-path | dependent | loaded by feature flag; "
        "signature must match |",
        "",
        "See: <file> --info-seams   — scan one file for suspected dynamic-connection patterns",
        "     (grep-based hint only; Kind/Shape/Why are always the agent's call, not the tool's).",
    ])


def _config_stamp_dirs(project_root):
    """STAMP_DIRS from the TARGET project's config (Plan08): the zone `--all` stamps by default."""
    mod = load_config_at(project_root)
    return list(getattr(mod, "STAMP_DIRS", []) or []) if mod else []


def _in_zone(rel, zone):
    """rel (root-relative, '/') inside one of the zone subpaths? Empty zone = whole root."""
    if not zone:
        return True
    rel = rel.replace("\\", "/")
    for z in zone:
        z = z.replace("\\", "/").strip("/")
        if not z or rel == z or rel.startswith(z + "/"):
            return True
    return False


def _stamp_all(project_root_abs, force, language=None, discard_prose=False, record=None, cards_dir=None,
               paths=None):
    """BULK: штемпелит ВСЕ исходники под project-root в cards_dir (обычно __map/).

    Языки: `language` (CLI) если задан, иначе CONFIG__TOOLS.LANGUAGE — и то и
    другое принимает список/через запятую/`all`.

    `paths` — ЗОНА штемпелевания (Plan08): подпути от корня; не задано -> CONFIG__TOOLS.STAMP_DIRS,
    пусто -> весь корень. Зона ограничивает ТОЛЬКО то, каким файлам пишутся карточки: связи (кто
    включает / кого включает / кто использует) по-прежнему считаются по ВСЕМУ корню.

    `record` (опционально) — dict логирования вызова (см. `_log_call`): если дан, сюда кладутся
    `all_files`/`all_counts`/`all_seam_hints` — та же сводка, что печатается в stderr, только
    структурированно, для последующего анализа по накопленным логам, а не для этого одного вызова.
    """
    from find_code_usage.core import collect_files, rel_path
    if cards_dir is None:
        cards_dir = os.path.join(project_root_abs, "__map")
    lang, test_dirs = _config_lang_testdirs(project_root_abs)
    selected = language if language else lang
    langs = stamp_langs.normalize(selected)
    exts = stamp_langs.extensions(selected)
    files = collect_files(project_root_abs, exts, test_dirs=test_dirs, tests_only=False)
    zone = list(paths) if paths else _config_stamp_dirs(project_root_abs)
    if zone:
        files = [f for f in files if _in_zone(rel_path(f, project_root_abs), zone)]
        sys.stderr.write(f"[make_interface_card] --all: zone={zone} (links still resolved over the whole root)\n")
    # Печатаем ЯЗЫКИ, а не только расширения: молчаливый пропуск JS-файлов в
    # питон-проекте — ровно то, из-за чего эта опция и появилась. Пусть видно,
    # по какому набору шли, даже когда всё нашлось.
    sys.stderr.write(f"[make_interface_card] --all: languages={langs or 'ALL'} "
                     f"exts={sorted(exts)}\n")
    if not files:
        sys.stderr.write(f"[make_interface_card] --all: no {sorted(exts)} files under {project_root_abs}\n")
        if record is not None:
            record["all_files"] = 0
        return 0
    counts = {"new": 0, "merged": 0, "forced": 0, "blocked": 0, "error": 0}
    seam_hints = []
    for abs_path in files:
        rel = rel_path(abs_path, project_root_abs)
        try:
            status, rep = _stamp_to_file(project_root_abs, rel, _card_path(cards_dir, rel),
                                          force, discard_prose)
            counts[status] += 1
            if status == "blocked":
                sys.stderr.write(f"  BLOCKED {rel}: has prose ({rep['prose_blocks']} blocks); "
                                  f"add --discard-prose to confirm --force here\n")
            if rep.get("seam_hint"):
                seam_hints.append(rel)
        except Exception as e:  # один битый файл не должен валить весь проход
            counts["error"] += 1
            sys.stderr.write(f"  ERROR {rel}: {e}\n")
    sys.stderr.write(
        f"[make_interface_card] --all: {len(files)} files -> {counts['new']} new, "
        f"{counts['merged']} merged, {counts['forced']} forced, {counts['blocked']} blocked, "
        f"{counts['error']} errors\n")
    if seam_hints:
        sys.stderr.write(
            f"[make_interface_card] --all: suspected dynamic connections (grep detector) in: "
            f"{', '.join(seam_hints)} — see '<file> --info-seams' for detail\n")
    if record is not None:
        record["all_files"] = len(files)
        record["all_counts"] = counts
        record["all_seam_hints"] = seam_hints
    return 1 if (counts["error"] or counts["blocked"]) else 0


def main():
    """Thin logging wrapper around `_main_impl` (the actual CLI, unchanged below). Kept separate
    on purpose: logging must never touch/risk the real logic, only observe argv in and
    status/exit_code/error/duration out (never a card's actual content — see `_log_call`)."""
    import time as _time
    t0 = _time.time()
    record = {"tool": TOOL_NAME, "card_format_version": cf.VERSION, "argv": sys.argv[1:]}
    exit_code = 0
    try:
        exit_code = _main_impl(record)
        return exit_code
    except SystemExit as e:
        exit_code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        raise
    except BaseException as e:
        exit_code = 1
        record["error"] = f"{type(e).__name__}: {e}"
        raise
    finally:
        record["exit_code"] = exit_code if isinstance(exit_code, int) else 0
        record["duration_ms"] = round((_time.time() - t0) * 1000, 2)
        _log_call(record)


def _main_impl(record):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Card stamp: fact-filled card skeleton for a file", add_help=False)
    ap.add_argument("-h", "--help", action="help", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    ap.add_argument("file", nargs="?", help="target source file (or use --file); omit with --all")
    ap.add_argument("--file", dest="file_opt", type=str, default=None,
                     help="target source file — alias for the positional <file>, same thing")
    ap.add_argument("--project-root", type=str, default=None,
                     help="project root (also base for a relative <file>/--file). Not given -> "
                          "implicitly CONFIG__TOOLS.PROJECT_ROOT of this tool's own __HQ (must "
                          "exist). '@' -> same, explicitly, unchecked. Literal path -> used as given.")
    ap.add_argument("--out", type=str, default=None,
                    help="write the card to this file (default: print to stdout)")
    ap.add_argument("--cards-dir", type=str, default=None,
                    help="card folder for --all (and for a single <file> without --out: writes "
                         "<cards-dir>/<file>.md). Default for --all: root from config -> "
                         "CONFIG__TOOLS.MAP_DIR (relative to __HQ), no key -> <root>/__map; "
                         "explicit --project-root -> <root>/__map.")
    ap.add_argument("--force", action="store_true",
                    help="discard the existing card and write a FRESH stamp "
                         "(default on an existing card is MERGE — refresh facts, keep prose). "
                         "On a card that already has prose, also requires --discard-prose.")
    ap.add_argument("--discard-prose", action="store_true",
                    help="confirms --force on a card that already has filled-in prose "
                         "(without it, --force on such a card is REFUSED, exit 2 — see REQ-004)")
    ap.add_argument("--all", action="store_true",
                    help="BULK maintainer pre-stamp: stamp EVERY source file under --project-root "
                         "(by --language, else CONFIG__TOOLS.LANGUAGE) each to <cards>/<path>.md (see --cards-dir). Skips "
                         ".git/__pycache__/__map/__HQ/.venv/node_modules/... and CONFIG__TOOLS.TEST_DIRS. "
                         "Existing cards MERGE (facts refreshed, prose kept); add --force to reset them "
                         "(cards with prose additionally need --discard-prose, else they're skipped as "
                         "'blocked' and the run exits 1). Ignores <file> and --out. One-shot way to "
                         "seed/refresh a whole tree's card skeletons.")
    ap.add_argument("--path", action="append", default=None, metavar="SUBDIR",
                    help="--all only: stamp only files under this root-relative subpath (repeatable; "
                         "default CONFIG__TOOLS.STAMP_DIRS, empty = whole root). Only WHERE cards are "
                         "written — edges and consumers are still resolved over the whole root.")
    ap.add_argument("--language", type=str, default=None,
                    help="--all only: which languages to stamp, overriding CONFIG__TOOLS.LANGUAGE. "
                         "Comma/space separated, or 'all'. Accepts python/typescript/csharp and the "
                         "short forms py/ts/js/tsx/cs (js and tsx are the typescript handler). "
                         "A POLYGLOT repo is the reason this exists: with a scalar LANGUAGE the bulk "
                         "pass silently skipped every file of the other language.")
    ap.add_argument("--help-seams", action="store_true",
                    help="print the full Runtime seams contract (columns, Kind/Shape vocab, "
                         "examples) and exit — no file needed. This is what the card's "
                         "contract-note line points to.")
    ap.add_argument("--info-seams", action="store_true",
                    help="with <file>/--file: scan it for suspected dynamic-connection patterns "
                         "(grep detector) and print line numbers — does not write a card, does "
                         "not decide Kind/Shape/Why (that's the agent's call).")
    args = ap.parse_args()

    if args.help_seams:
        record["mode"] = "help-seams"
        print(_seams_help_text())
        return 0

    project_root_abs = str(resolve_project_root(args.project_root))
    target_file = args.file_opt if args.file_opt is not None else args.file

    if args.info_seams:
        record["mode"] = "info-seams"
        if not target_file:
            ap.error("--info-seams requires a <file> argument (or --file)")
        target_abs = target_file if os.path.isabs(target_file) else os.path.join(project_root_abs, target_file)
        hits = seam_scanner.scan(target_abs)
        record["info_seams_hits"] = len(hits)
        if not hits:
            print(f"[make_interface_card] --info-seams {target_file}: no suspected dynamic-connection patterns found")
        else:
            print(f"[make_interface_card] --info-seams {target_file}: {len(hits)} suspected line(s)")
            for line_no, label, snippet in hits:
                print(f"  L{line_no}  {label}  {snippet}")
        return 0

    if args.all:
        record["mode"] = "all"
        cards_dir = resolve_cards_dir(args.cards_dir, args.project_root, project_root_abs)
        paths = [p for arg in (args.path or []) for p in arg.split(",") if p.strip()]
        return _stamp_all(project_root_abs, args.force, args.language, args.discard_prose, record, cards_dir,
                          paths or None)

    if not target_file:
        ap.error("either a <file> argument (or --file), or --all is required")
    if stamp_langs.for_file(target_file) is None:
        sys.stderr.write(f"[make_interface_card] REFUSED: no stamp language for {target_file} "
                         f"(known extensions: {' '.join(sorted(stamp_langs.all_extensions()))})\n")
        return 2

    out = args.out
    if not out and args.cards_dir:
        rel = os.path.relpath(os.path.abspath(os.path.join(project_root_abs, target_file)), project_root_abs)
        out = _card_path(os.path.abspath(args.cards_dir), rel.replace(os.sep, "/"))
    if not out:
        # Без --out — просто печать штемпеля в stdout (без merge: файла-цели нет).
        record["mode"] = "preview"
        report = {}
        print(build_card(project_root_abs, target_file, None, report))
        if report.get("seam_hint"):
            record["seam_hint"] = True
            sys.stderr.write(
                f"  suspected dynamic connections (grep detector) — see '{target_file} --info-seams' for detail\n")
        return 0

    record["mode"] = "stamp"
    status, report = _stamp_to_file(project_root_abs, target_file, out, args.force, args.discard_prose)
    record["status"] = status
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
    if report.get("seam_hint"):
        record["seam_hint"] = True
        sys.stderr.write(
            f"  suspected dynamic connections (grep detector) — see '{target_file} --info-seams' for detail\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
