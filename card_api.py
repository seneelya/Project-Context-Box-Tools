#!/usr/bin/env python3
"""card_api.py — штемпель карточки: ОДНА команда -> готовый .md-скелет карточки, где
ФАКТИЧЕСКИЕ секции заполнены детерминированно, а прозаические — строки-ДИРЕКТИВЫ
`<Agent: …>`, которые ЛЛМ дописывает, прочитав исходник.

Ничего нового не анализирует — ОРКЕСТРИРУЕТ три факта:
  - объявленная поверхность + сигнатуры   <- единый источник:
        Python  → py_api.collect (ast — точные типы параметров),
        TS/JS   → get_codeblock declarations (структурные заголовки блоков),
        (C# — позже; сейчас только факты потребления/зависимостей).
  - потреблённая поверхность               <- codebase_import_search downstream
    (кто РЕАЛЬНО импортит символы цели; вскрывает leaked-private и dead surface).
  - зависимости самой цели                 <- codebase_import_search --incoming (резолв в файлы).

Формат — из card_format.py (единый контракт). Мультиязычно: объявления берутся из
языко-агностичного `declarations`, факты потребления/зависимостей уже мультиязычны.

Использование:
    python card_api.py <file> --project-root PATH
"""

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import card_format as cf


_LANG = {".py": "python", ".ts": "typescript", ".tsx": "typescript",
         ".js": "typescript", ".jsx": "typescript", ".cs": "csharp"}


def _lang(file):
    return _LANG.get(os.path.splitext(file)[1].lower(), "python")


# The LLM fills prose; the stamp keeps the machine FACT line and the agent DIRECTIVE line
# separate so line-based patch edits never collide (the fact is editable too — just a line).
DIRECTIVE_DESC = "<Agent: replace with a concise, sufficient one-liner — what it does and its role; or delete this line if trivial>"
DIRECTIVE_SUMMARY = "<Agent: replace with a concise one-line summary — what this file is and does>"

# H4 declaration kind -> H3 subsection label (order below drives emission order).
_KIND_H3 = {"function": "Functions", "class": "Classes", "interface": "Interfaces",
            "enum": "Enums", "type": "Types", "namespace": "Namespaces",
            "const": "Constants", "let": "Constants", "var": "Constants",
            "struct": "Classes", "record": "Classes"}
_H3_ORDER = ["Functions", "Classes", "Interfaces", "Enums", "Types", "Constants", "Namespaces"]


# --- fact producers ----------------------------------------------------------

def _cis_setup(project_root, file):
    """Mirror of test/check.py: resolve target names + handler for import_search."""
    from codebase_import_search.core import resolve_target_names
    from codebase_import_search.handlers import get_handler
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
    from codebase_import_search.core import scan_downstream
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
    from codebase_import_search.core import scan_incoming
    from codebase_import_search.resolvers import get_resolver
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
                import py_api
                return py_api.collect(p).get("all_defs", {}).get(name)
            except Exception:
                return None
    return None


# --- declared surface (single source, per language) --------------------------

def _decl_backend():
    """DECL_BACKEND from tools_config: 'auto' | 'treesitter' | 'regex' (default 'auto')."""
    try:
        import tools_config
        return getattr(tools_config, "DECL_BACKEND", "auto")
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
        f"[card_api] WARNING: {how} for {lang} - running in the REGEX FALLBACK "
        f"(lower-fidelity signatures). For a full parse install:  "
        f"pip install tree-sitter {pkg}   (or set tools_config.DECL_BACKEND='regex' to silence)\n"
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
            sys.stderr.write(f"[card_api] WARNING: tree-sitter backend for {lang} failed ({e}); using regex.\n")
    from get_codeblock.handlers import get_handler
    return get_handler(lang).declarations(src.splitlines(keepends=True))


def _declared(project_root, file, lang):
    """Language-agnostic declared surface. Returns:
      {docstring_first, exports:[{name,kind,signature,methods}], all_defs:{name:sig},
       reexports:[{name,source[,module,level]}]}
    Python via py_api(ast) — precise param types; TS/JS via get_codeblock declarations.
    """
    empty = {"docstring_first": None, "exports": [], "all_defs": {}, "reexports": []}
    target_abs = file if os.path.isabs(file) else os.path.join(project_root, file)

    if lang == "python":
        import py_api
        c = py_api.collect(Path(target_abs))
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


def build_card(project_root, file):
    lang = _lang(file)
    fname = os.path.basename(file)
    is_pkg = cf.is_package(fname)

    consumers = consumers_of(project_root, file)
    resolved, externals = deps_of(project_root, file)
    declared = _declared(project_root, file, lang)
    target_abs = file if os.path.isabs(file) else os.path.join(project_root, file)

    placed = set()
    lines = [f"# {fname}", ""]
    # Summary slot: the directive is the parsed summary (first non-empty line after H1);
    # the docstring fact sits below as generated context the agent may adapt or delete.
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
        lines.append("<Agent: one line per submodule — what it holds>")
        lines.append("")

    # ---- Public API ----
    lines.append("## Public API")
    lines.append("")

    # exported declarations, grouped by kind -> H3
    by_h3 = defaultdict(list)
    for e in declared["exports"]:
        by_h3[_KIND_H3.get(e["kind"], "Objects")].append(e)
    for h3 in _H3_ORDER + ["Objects"]:
        group = by_h3.get(h3)
        if not group:
            continue
        lines.append(f"### {h3}")
        for e in group:
            lines.append(f"#### `{e['signature']}`")
            lines.append(_consumers_fact(e["name"], consumers))
            lines.append(DIRECTIVE_DESC)
            for m in e.get("methods", []):
                lines.append(f"    - `{m['signature']}`")
            placed.add(e["name"])
        lines.append("")

    # Re-exports (facade only): names surfaced onward from sibling modules.
    if is_pkg and declared["reexports"]:
        lines.append("### Re-exports")
        for r in declared["reexports"]:
            sig = None
            if lang == "python" and "module" in r:
                sig = _resolve_sibling_signature(target_abs, r["module"], r["level"], r["name"])
            lines.append(f"#### `{sig if sig else r['name']}`  ← {r['source']}")
            lines.append(_consumers_fact(r["name"], consumers))
            lines.append(DIRECTIVE_DESC)
            placed.add(r["name"])
        lines.append("")

    # Consumed internals: symbols DEFINED here that other files really import but that are
    # not part of the declared/exported surface — the leaked interface. Intersecting with
    # "defined here" drops reverse-index false-positives.
    defined_here = set(declared["all_defs"])
    leftover = sorted(s for s in consumers if s not in placed and s in defined_here)
    if leftover:
        lines.append(f"### {cf.CONSUMED_SUBSECTION}")
        for sym in leftover:
            sig = declared["all_defs"].get(sym)
            lines.append(f"#### `{sig if sig else sym}`")
            lines.append(_consumers_fact(sym, consumers))
            lines.append(DIRECTIVE_DESC)
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
            imp = "`" + os.path.basename(r["file"]).rsplit(".", 1)[0] + "`"
            lines.append(f"| {imp} | `{r['file']}` | {syms} | <Agent: why?> | normal |")
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
        lines.append("<Agent: keep only libs the reader may not know; else write (none)>")
    else:
        lines.append(cf.EMPTY)
    lines.append("")

    # ---- prose-only sections ----
    lines.append("## How it works")
    lines.append("")
    lines.append("<Agent: describe the mechanism after reading the source>")
    lines.append("")
    lines.append("## Doc links")
    lines.append("")
    lines.append(cf.EMPTY)
    lines.append("")
    lines.append("## Discrepancies")
    lines.append("")
    lines.append("<Agent: docstring vs code contradictions; else write (none)>")

    return "\n".join(lines) + "\n"


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Card stamp: fact-filled card skeleton for a file")
    ap.add_argument("file", help="target source file (root-relative or absolute)")
    ap.add_argument("--project-root", type=str, default=".", help="project root for the reverse index")
    ap.add_argument("--out", type=str, default=None,
                    help="write the card to this file (default: print to stdout)")
    ap.add_argument("--force", action="store_true",
                    help="with --out: overwrite the file if it already exists")
    args = ap.parse_args()

    card = build_card(os.path.abspath(args.project_root), args.file)

    if not args.out:
        print(card)
        return 0

    # --out: write to a file, but never silently clobber an existing card (it may already
    # hold hand-written prose). Refuse unless --force; the caller then merges/updates by hand.
    if os.path.exists(args.out) and not args.force:
        sys.stderr.write(
            f"[card_api] card already exists: {args.out} - NOT overwriting.\n"
            f"  It may contain filled descriptions. Either update it by hand, or re-run with "
            f"--force to replace, or omit --out to print to stdout and merge manually.\n"
        )
        return 2
    out_dir = os.path.dirname(os.path.abspath(args.out))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(card)
    sys.stderr.write(f"[card_api] wrote {args.out}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
