#!/usr/bin/env python3
"""card_api.py — штемпель карточки: ОДНА команда -> готовый .md-скелет карточки, где
ФАКТИЧЕСКИЕ секции заполнены детерминированно, а прозаические — заглушки `<!-- LLM: … -->`,
которые ЛЛМ дописывает, прочитав исходник.

Ничего нового не анализирует — ОРКЕСТРИРУЕТ три факта:
  - объявленный API + сигнатуры        <- py_api.collect (ast; только Python)
  - потреблённая поверхность            <- codebase_import_search downstream
    (кто РЕАЛЬНО импортит символы цели, откуда; вскрывает leaked-private и dead-public)
  - зависимости самой цели              <- codebase_import_search --incoming (резолв в файлы)

Формат — из card_format.py (единый контракт), поэтому структура карточки валидна для
validate_cards (рёбра File Path резолвятся, когда появятся карточки соседей).
Python-first: для .py — полные сигнатуры; для остальных языков секции те же, сигнатуры пустые.

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


_LANG = {".py": "python", ".ts": "typescript", ".js": "typescript", ".cs": "csharp"}


def _lang(file):
    return _LANG.get(os.path.splitext(file)[1].lower(), "python")


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
    `from <dots><module> import name` — resolve to a sibling .py and read its ast."""
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
                defs = py_api.collect(p).get("all_defs", {})
                return defs.get(name)
            except Exception:
                return None
    return None


# --- formatting --------------------------------------------------------------

def _consumed_note(sym, consumers):
    c = consumers.get(sym)
    if not c:
        return "NOT consumed anywhere (dead surface? — verify)"
    files = ", ".join(f for f, _k, _ln in c)
    return f"consumed by {len(c)}: {files}"


def _api_entry(name, signature, note):
    label = signature if signature else name
    return [f"#### `{label}`", f"<!-- LLM: одна строка. FACT: {note} -->"]


def build_card(project_root, file):
    from codebase_import_search.core import rel_path  # noqa: F401 (parity import)
    lang = _lang(file)
    fname = os.path.basename(file)
    is_pkg = cf.is_package(fname)

    consumers = consumers_of(project_root, file)
    resolved, externals = deps_of(project_root, file)

    declared = {"functions": [], "classes": [], "all_defs": {}, "module_globals": [],
                "import_froms": [], "external_imports": [], "docstring_first": None,
                "ok": lang == "python"}
    if lang == "python":
        import py_api
        target_abs = os.path.join(project_root, file) if not os.path.isabs(file) else file
        declared = py_api.collect(Path(target_abs))

    placed = set()
    lines = [f"# {fname}", ""]
    ds = declared.get("docstring_first")
    lines.append(f"<!-- LLM: одна строка-сводка — что делает модуль/пакет."
                 + (f' docstring 1-я строка: \"{ds}\"' if ds else "") + " -->")
    lines.append("")

    # ---- Package layout (package/facade only) ----
    if is_pkg:
        rels = sorted({f".{'.' * (imp['level'] - 1)}{imp['module']}"
                       for imp in declared.get("import_froms", []) if imp["level"] >= 1})
        lines.append("## Package layout")
        lines.append("")
        detected = ", ".join(rels) if rels else "(none detected)"
        lines.append(f"<!-- LLM: подмодули + одна строка на каждый. Найдены относительные импорты: {detected} -->")
        lines.append("")

    # ---- Public API ----
    lines.append("## Public API")
    lines.append("")

    if declared.get("functions"):
        lines.append("### Functions")
        for f in declared["functions"]:
            lines += _api_entry(f["name"], f["signature"], _consumed_note(f["name"], consumers))
            placed.add(f["name"])
        lines.append("")

    if declared.get("classes"):
        lines.append("### Classes")
        for c in declared["classes"]:
            note = _consumed_note(c["name"], consumers)
            lines.append(f"#### `{c['name']}`")
            lines.append(f"<!-- LLM: одна строка. FACT: {note} -->")
            for m in c["methods"]:
                lines.append(f"    - `{m['signature']}`")
            placed.add(c["name"])
        lines.append("")

    # Re-exports: ONLY for a package/facade — top-level relative imports it exposes.
    # A leaf module's relative imports are dependencies (Dependencies Internal), not re-exports.
    reexports = []
    if is_pkg:
        for imp in declared.get("import_froms", []):
            if imp["level"] >= 1:
                for nm in imp["names"]:
                    reexports.append((nm, imp["module"], imp["level"]))
    if reexports:
        lines.append("### Re-exports")
        for nm, mod, lvl in reexports:
            sig = _resolve_sibling_signature(
                os.path.join(project_root, file) if not os.path.isabs(file) else file, mod, lvl, nm)
            note = _consumed_note(nm, consumers)
            label = sig if sig else nm
            lines.append(f"#### `{label}`  ← .{mod}")
            lines.append(f"<!-- LLM: одна строка если неочевидно. FACT: {note} -->")
            placed.add(nm)
        lines.append("")

    # Consumed internals: symbols DEFINED here (def/class/module-global) that other files
    # really import, minus what's already placed — the leaked `_`-private interface + globals.
    # Intersecting with "defined here" drops reverse-index false-positives for leaf modules.
    defined_here = set(declared.get("all_defs", {})) | set(declared.get("module_globals", []))
    leftover = sorted(s for s in consumers if s not in placed and s in defined_here)
    if leftover:
        lines.append(f"### {cf.CONSUMED_SUBSECTION}")
        for sym in leftover:
            sig = declared.get("all_defs", {}).get(sym)
            label = sig if sig else sym
            lines.append(f"#### `{label}`")
            lines.append(f"<!-- LLM: одна строка. FACT: {_consumed_note(sym, consumers)} -->")
        lines.append("")

    if not (declared.get("functions") or declared.get("classes") or reexports or leftover):
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
            lines.append(f"| {imp} | `{r['file']}` | {syms} | <!--why--> | normal |")
    else:
        lines.append(cf.EMPTY)
    lines.append("")

    # ---- Dependencies External ----
    lines.append("## Dependencies External")
    lines.append("")
    ext_detected = sorted({e for e in externals})
    if ext_detected or declared.get("external_imports"):
        det = ", ".join(ext_detected) if ext_detected else ", ".join(sorted(set(declared["external_imports"])))
        lines.append(f"<!-- LLM: сторонние/stdlib, которые читателю неочевидны; иначе (none). Найдено: {det} -->")
    else:
        lines.append(cf.EMPTY)
    lines.append("")

    # ---- prose-only sections ----
    lines.append("## How it works")
    lines.append("")
    lines.append("<!-- LLM: механизм — как это работает, прочитав исходник. -->")
    lines.append("")
    lines.append("## Doc links")
    lines.append("")
    lines.append(cf.EMPTY)
    lines.append("")
    lines.append("## Discrepancies")
    lines.append("")
    lines.append("<!-- LLM: docstring ↔ код противоречия; иначе (none). -->")

    return "\n".join(lines) + "\n"


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Card stamp: fact-filled card skeleton for a file")
    ap.add_argument("file", help="target source file (root-relative or absolute)")
    ap.add_argument("--project-root", type=str, default=".", help="project root for the reverse index")
    args = ap.parse_args()

    project_root = os.path.abspath(args.project_root)
    print(build_card(project_root, args.file))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
