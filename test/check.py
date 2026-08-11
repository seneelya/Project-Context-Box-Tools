#!/usr/bin/env python3
"""Golden checker for codebase_import_search + get_codeblock.

Compares live tool output on the `test/` fixtures against the oracle in `test/expected.py`
(the values a human verified by hand). Run from anywhere:

    py test/check.py            # full grouped report (for human review)
    py test/check.py --fails    # only mismatches + summary (for quick regression runs)

Exit code 0 = all match, 1 = at least one mismatch.
"""

import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
for p in (_TOOLS, _HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

from get_codeblock.core import get_line_levels

_LANG = {".py": "python", ".ts": "typescript", ".js": "typescript",
         ".cs": "csharp", ".md": "markdown", ".markdown": "markdown"}


# --- live tool runners over a fixture ---------------------------------------

def levels_for(fixture_file, lines):
    return get_line_levels(os.path.join(_HERE, fixture_file), list(lines))


def _cis_setup(root, file):
    from codebase_import_search.core import resolve_target_names
    from codebase_import_search.handlers import get_handler
    project_root = os.path.join(_HERE, root)
    _t, target_names = resolve_target_names(file, None, "", project_root)
    file_arg = file if os.path.isabs(file) else os.path.join(project_root, file)
    target_abs = os.path.abspath(file_arg)
    lang = _LANG.get(os.path.splitext(file)[1].lower(), "python")
    handler = get_handler(lang)
    if lang == "csharp" and hasattr(handler, "_extract_namespace"):
        ns = handler._extract_namespace(target_abs)
        if ns:
            target_names.add(ns)
            parts = ns.split(".")
            for i in range(1, len(parts)):
                target_names.add(".".join(parts[:i]))
    return project_root, target_names, target_abs, lang, handler


def downstream(root, file):
    from codebase_import_search.core import scan_downstream
    project_root, target_names, target_abs, lang, handler = _cis_setup(root, file)
    data, _dyn = scan_downstream(project_root, handler, target_names, target_abs, lang, True, [], False)
    return {f: sorted(syms.keys()) for f, syms in data.items()}


def incoming(root, file):
    from codebase_import_search.core import scan_incoming
    from codebase_import_search.resolvers import get_resolver
    project_root, target_names, target_abs, lang, handler = _cis_setup(root, file)
    resolver = get_resolver(lang)
    resolved, _ext, _usages, _stats = scan_incoming(resolver, target_abs, project_root)
    return {r["file"]: r["symbols"] for r in resolved}


# --- comparison --------------------------------------------------------------

def main():
    only_fails = "--fails" in sys.argv
    import expected as exp

    passed = failed = 0

    def line(s):
        if not only_fails:
            print(s)

    line("== LEVELS (file / line = level) ==")
    for fixture, cases in exp.LEVELS.items():
        got = levels_for(fixture, [ln for ln, _w, _s in cases])
        line(f"\n[{fixture}]")
        for ln, want, snip in cases:
            g = got.get(ln)
            ok = g == want
            passed += ok
            failed += not ok
            if ok:
                line(f"  ok   line {ln:>4} = level {want}   # {snip}")
            else:
                print(f"  FAIL {fixture} line {ln} = level {want}  <-- got {g}   # {snip}")

    line("\n== IMPORTS (target -> {file: [symbols]}) ==")
    for name, spec in exp.IMPORTS.items():
        runner = downstream if spec["mode"] == "downstream" else incoming
        got = runner(spec["root"], spec["file"])
        line(f"\n[{name}]  {spec['mode']} {spec['file']}")
        for f, want_syms in spec["expect"].items():
            got_syms = got.get(f)
            ok = got_syms == want_syms
            passed += ok
            failed += not ok
            if ok:
                line(f"  ok   {f}: {want_syms}")
            else:
                print(f"  FAIL {name} :: {f}\n         want {want_syms}\n         got  {got_syms}")

    print(f"\n{'-'*50}\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
