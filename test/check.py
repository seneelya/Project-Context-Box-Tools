#!/usr/bin/env python3
"""Golden checker for find_code_usage + get_codeblock.

Compares live tool output on the `test/` fixtures against the oracle in `test/expected.py`
(values a human verified by hand). Run:

    py test/check.py            # full grouped report (for human review)
    py test/check.py --fails    # only mismatches + summary (quick regression run)

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
         ".tsx": "tsx", ".jsx": "tsx",
         ".cs": "csharp", ".md": "markdown", ".markdown": "markdown",
         ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".c++": "cpp",
         ".hpp": "cpp", ".hh": "cpp", ".hxx": "cpp", ".h": "cpp", ".c": "cpp"}


def _lang(file):
    return _LANG.get(os.path.splitext(file)[1].lower(), "python")


def _read(fixture):
    return open(os.path.join(_HERE, fixture), encoding="utf-8", errors="replace").readlines()


# --- get_codeblock runners ---------------------------------------------------

def levels_for(fixture, lines):
    return get_line_levels(os.path.join(_HERE, fixture), list(lines))


def outline_for(fixture, max_level=None):
    from get_codeblock.handlers import get_handler
    h = get_handler(_lang(fixture))
    if not hasattr(h, "outline"):
        return None
    rows = h.outline(_read(fixture), max_level=max_level)
    return [(r["level"], r["start"], r["end"], r["text"]) for r in rows]


def ladder_for(fixture, line):
    from get_codeblock.handlers import get_handler
    blocks = get_handler(_lang(fixture)).get_blocks(os.path.join(_HERE, fixture), line)
    return [(b["level"], b["start"], b["end"]) for b in reversed(blocks)]  # innermost→outermost (as CLI)


def query_bounds(fixture, line, level):
    from get_codeblock.handlers import get_handler
    from get_codeblock.core import resolve
    blocks = get_handler(_lang(fixture)).get_blocks(os.path.join(_HERE, fixture), line)
    b = resolve(blocks, level)
    return (b["level"], b["start"], b["end"]) if b else None


# --- find_code_usage runners -----------------------------------------

def _cis_setup(root, file):
    from find_code_usage.core import resolve_target_names
    from find_code_usage.handlers import get_handler
    project_root = os.path.join(_HERE, root)
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


def downstream(root, file):
    """{consumer_file: [symbols]} — full."""
    from find_code_usage.core import scan_downstream
    project_root, target_names, target_abs, lang, handler = _cis_setup(root, file)
    data, _dyn = scan_downstream(project_root, handler, target_names, target_abs, lang, True, [], False)
    return {f: sorted(syms.keys()) for f, syms in data.items()}


def symbol_filter(root, file, symbols):
    """downstream filtered to symbols (exact / first / last token) — {file: [syms]}."""
    from find_code_usage.report import _match
    want = set(symbols)
    out = {}
    for f, syms in downstream(root, file).items():
        kept = [s for s in syms if _match(s, want)]
        if kept:
            out[f] = kept
    return out


def incoming_detail(root, file):
    """Full incoming: resolved sources, externals, dangling, and per-source usage lines+levels in target."""
    from find_code_usage.core import scan_incoming
    from find_code_usage.resolvers import get_resolver
    project_root, target_names, target_abs, lang, handler = _cis_setup(root, file)
    resolver = get_resolver(lang)
    resolved, externals, usages, _stats = scan_incoming(resolver, target_abs, project_root, handler=handler, verbose=True)
    lv = get_line_levels(target_abs, [ln for u in usages.values() for ln in u["lines"]]) if usages else {}
    usages_flat = []   # (source_file, symbol, [lines], [levels]) — flat table, easy to verify
    dangling = []
    for sym in sorted(usages):
        u = usages[sym]
        if u["lines"]:
            usages_flat.append((u["source"], sym, u["lines"], [lv.get(ln) for ln in u["lines"]]))
        else:
            dangling.append(sym)
    usages_flat.sort()
    return {
        "resolved": {r["file"]: r["symbols"] for r in resolved},
        "external": sorted(externals),
        "dangling": sorted(dangling),
        "usages": usages_flat,
    }


def consumer_files(root, file):
    """Who imports the target — sorted file set only (symbols omitted; for big fixtures)."""
    return sorted(downstream(root, file).keys())


def incoming_sources(root, file):
    """The target's own imports resolved to sibling files — sorted file set."""
    return sorted(incoming_detail(root, file)["resolved"].keys())


def declarations_regex(root, file):
    """Declared surface via the REGEX handler (deterministic, tree-sitter-independent):
    (name, kind, exported, n_members) per top-level declaration."""
    from get_codeblock.handlers import get_handler
    lines = _read(os.path.join(root, file))
    return [(d["name"], d["kind"], d["exported"], len(d.get("methods", [])))
            for d in get_handler(_lang(file)).declarations(lines)]


# --- comparison --------------------------------------------------------------

def main():
    only_fails = "--fails" in sys.argv
    import expected as exp

    passed = failed = 0

    def line(s=""):
        if not only_fails:
            print(s)

    def check(name, want, got):
        nonlocal passed, failed
        ok = want == got
        passed += ok
        failed += not ok
        if ok:
            line(f"  ok   {name}")
        else:
            print(f"  FAIL {name}\n         want {want}\n         got  {got}")

    line("== LEVELS (line = level) ==")
    for fx, cases in getattr(exp, "LEVELS", {}).items():
        got = levels_for(fx, [ln for ln, _w, _s in cases])
        line(f"\n[{fx}]")
        for ln, want, snip in cases:
            check(f"line {ln} = {want}   # {snip}", want, got.get(ln))

    line("\n== OUTLINE (level, start, end, label) ==")
    for fx, want in getattr(exp, "OUTLINE", {}).items():
        line(f"\n[{fx}]")
        check("outline", [tuple(t) for t in want], outline_for(fx))

    line("\n== LADDER (innermost→outermost) ==")
    for c in getattr(exp, "LADDER", []):
        line(f"\n[{c['file']} :{c['line']}]")
        check("ladder", [tuple(t) for t in c["expect"]], ladder_for(c["file"], c["line"]))

    line("\n== QUERY bounds (level, start, end) ==")
    for c in getattr(exp, "QUERY", []):
        line(f"\n[{c['file']} :{c['line']} level {c['level']}]")
        check("query", tuple(c["expect"]), query_bounds(c["file"], c["line"], c["level"]))

    line("\n== IMPORTS (target → {file: [symbols]}) ==")
    for name, spec in getattr(exp, "IMPORTS", {}).items():
        runner = downstream if spec["mode"] == "downstream" else (lambda r, f: incoming_detail(r, f)["resolved"])
        got = runner(spec["root"], spec["file"])
        line(f"\n[{name}]  {spec['mode']} {spec['file']}")
        check("files→symbols", {k: list(v) for k, v in spec["expect"].items()}, got)

    line("\n== SYMBOL filter ==")
    for name, spec in getattr(exp, "SYMBOL", {}).items():
        got = symbol_filter(spec["root"], spec["file"], spec["symbol"])
        line(f"\n[{name}]  {spec['file']} --symbol {spec['symbol']}")
        check("filtered", {k: list(v) for k, v in spec["expect"].items()}, got)

    line("\n== INCOMING_DETAIL (resolved / external / dangling / usages) ==")
    for name, spec in getattr(exp, "INCOMING_DETAIL", {}).items():
        got = incoming_detail(spec["root"], spec["file"])
        line(f"\n[{name}]  incoming {spec['file']}")
        check("resolved", {k: list(v) for k, v in spec["resolved"].items()}, got["resolved"])
        check("external", list(spec["external"]), got["external"])
        check("dangling", list(spec["dangling"]), got["dangling"])
        check("usages", [tuple(t) for t in spec["usages"]], got["usages"])

    line("\n== CONSUMERS (who imports the target — file set) ==")
    for name, spec in getattr(exp, "CONSUMERS", {}).items():
        got = consumer_files(spec["root"], spec["file"])
        line(f"\n[{name}]  {spec['file']}")
        check("consumer files", list(spec["expect"]), got)

    line("\n== INCOMING_SOURCES (target's deps resolved to files) ==")
    for name, spec in getattr(exp, "INCOMING_SOURCES", {}).items():
        got = incoming_sources(spec["root"], spec["file"])
        line(f"\n[{name}]  {spec['file']}")
        check("sources", list(spec["expect"]), got)

    line("\n== DECLARATIONS (regex: name, kind, exported, n_members) ==")
    for name, spec in getattr(exp, "DECLARATIONS", {}).items():
        got = declarations_regex(spec["root"], spec["file"])
        line(f"\n[{name}]  {spec['file']}")
        check("declarations", [tuple(t) for t in spec["expect"]], got)

    print(f"\n{'-'*50}\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
