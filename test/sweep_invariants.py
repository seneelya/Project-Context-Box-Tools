#!/usr/bin/env python3
"""Fuzz get_blocks (LADDER mode) over every line of many files and flag invariant breaks.

The tool promises (reader/CONTRACT.md invariants 6-7) that the ladder returned for a line
is a clean nest of blocks that ALL contain that line. This sweep pokes real files line by
line through the same entry point the CLI uses (Reader.get_blocks) and reports where that
breaks. It is read-only.

Checks per (file, line):
  * CONTAIN   (HIGH) — a returned rung does NOT span the line (start <= line <= end). This
                       is invariant #7: "выданный блок обязан содержать строку".
  * RANGE     (HIGH) — ladder is not a clean outer->inner nest (outer must span inner). A
                       real containment/bounds bug.
  * SIBLING   (INFO) — same level, no nesting, but outer.end == line == inner.start: two
                       sibling control clauses sharing one physical brace line (`} else {`,
                       `} catch (e) {`). Both legitimately touch the line — not a bug, an
                       inherently ambiguous boundary (CONTRACT invariant #8).
  * LEVEL     (LOW)  — ranges nest fine but levels don't strictly increase (try/catch
                       sibling-wrapper quirk). Cosmetic, not a containment break.
  * CRASH     (HIGH) — get_blocks raised.
  * EMPTY     (INFO) — no ladder for a non-blank line in a file that has blocks elsewhere.
  * QUERY     (HIGH) — only with `--check-query`: `get_codeblock(query=True)` (the CORE API,
                       what `--query`/other tools actually call) returned text that does NOT
                       contain the probed line's real content at the right row. Exercises
                       `resolve()` (the invariant #8 ambiguity climb) and the text slice —
                       neither is touched by the plain ladder checks above.

Usage:
    py test/sweep_invariants.py [ROOT ...] [--file F] [--step N] [--max-lines M]
                                [--max-bytes B] [--show K] [--show-info] [--quiet]
                                [--check-query] [--write-level]

ROOT defaults to this test/ directory (small, fast). Point it at a big checkout (e.g. a
Hermes source tree) to stress it: `py test/sweep_invariants.py Y:\\Hermess\\...\\SRC`.
--file F sweeps exactly that one file (shorthand for a single-file ROOT, useful when you
want to eyeball one specific file without touching the roots list). --step N samples every
Nth line (default 1 = all lines; get_blocks re-reads the file per call, so N>1 is the speed
knob on huge trees). --write-level additionally writes an eyeball-review copy of each swept
file (level-number + flag prefix on every line, see `write_level_map`) into test/ — never
next to the source. Exit code 1 if any HIGH violation is found.
"""
import argparse
import functools
import os
import sys
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from get_codeblock.reader.reader import Reader  # noqa: E402


def _speed_up():
    """get_blocks re-resolves the backend (reloads the grammar!) and re-parses the file on
    EVERY line — O(lines^2) per file, unusable over a big tree. Here in the TEST harness we
    memoize (a) resolve by extension and (b) the parse by file content. The computed ladder
    is byte-identical (parsing is deterministic); we only skip redundant work. Production is
    untouched — it calls get_blocks once per invocation, so this lives in the sweep only."""
    from get_codeblock.reader import address, classify, registry
    orig_resolve = registry.resolve

    @functools.lru_cache(maxsize=256)
    def fast_resolve(ext):
        backend, spec = orig_resolve(ext)
        orig_root, cache = backend.root, {}

        def root(src):
            key = hash(src)
            if key not in cache:
                cache[key] = orig_root(src)
            return cache[key]

        backend.root = root
        return backend, spec

    # Both address.py and classify.py did `from .registry import resolve` — each holds its
    # OWN name binding, so patching `registry.resolve` alone wouldn't reach either. Point
    # BOTH at the SAME cached wrapper: filler_container_at (invariant #9's get_blocks
    # fallback) calls classify.resolve on every top-level/frame-level line with no
    # addressable rung — without this, that path reparses the WHOLE file from scratch on
    # every such line (a fresh, unpatched backend each time), turning any file with many
    # imports/comments/docstring lines back into the O(lines²) blowup this function exists
    # to kill.
    address.resolve = fast_resolve
    classify.resolve = fast_resolve

    # get_blocks also re-walks the whole tree per line (_collect, _comment_rows). Those are
    # pure functions of the (now cached, stable) root, so memoize them by id(root).
    def _memo_by_root(fn):
        cache = {}

        @functools.wraps(fn)
        def wrapper(root, *rest):
            key = id(root)
            if key not in cache:
                cache[key] = fn(root, *rest)
            return cache[key]
        return wrapper

    address._collect = _memo_by_root(address._collect)
    address._comment_rows = _memo_by_root(address._comment_rows)

    # The indentation (.py) path re-reads the file on EVERY line via a bare open(). Shadow
    # that module's `open` with a per-path readlines cache — kills the O(lines) I/O per line.
    import builtins
    from get_codeblock.handlers import python_handler
    read_cache = {}

    class _CachedFile:
        def __init__(self, lines):
            self._lines = lines

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def readlines(self):
            # Return the SAME list object every time (not a copy): python_handler caches its
            # in-string mask keyed on `lines is lines`, so a stable object lets that O(lines)
            # scan run once per file instead of once per probed line.
            return self._lines

    def cached_open(path, *a, **k):
        key = os.path.abspath(path)
        if key not in read_cache:
            with builtins.open(path, *a, **k) as f:
                read_cache[key] = f.readlines()
        return _CachedFile(read_cache[key])

    python_handler.open = cached_open

    # find_body_end / find_containing_blocks are the O(lines) scans get_blocks reruns for the
    # SAME headers on every probed line — the real O(lines^2) cost. They're pure functions of
    # (lines content, args); with lines now a stable object we memoize by (id(lines), args).
    def _memo_by_lines(fn):
        cache = {}

        @functools.wraps(fn)
        def wrapper(lines, *rest, **kw):
            key = (id(lines), rest, tuple(sorted(kw.items())))
            if key not in cache:
                cache[key] = fn(lines, *rest, **kw)
            return cache[key]
        return wrapper

    python_handler.find_body_end = _memo_by_lines(python_handler.find_body_end)
    python_handler.find_containing_blocks = _memo_by_lines(python_handler.find_containing_blocks)


_speed_up()

# Authoritative set of extensions the tool addresses (mirrors test/check.py _LANG).
SUPPORTED = {".py", ".ts", ".js", ".tsx", ".jsx", ".scss", ".sass", ".css", ".cs",
             ".md", ".markdown", ".cpp", ".cc", ".cxx", ".c++", ".hpp", ".hh", ".hxx",
             ".h", ".c"}
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".mypy_cache",
             ".pytest_cache", "secret", "parity"}


def iter_files(roots):
    for root in roots:
        if os.path.isfile(root):
            yield root
            continue
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
            for f in files:
                if os.path.splitext(f)[1].lower() in SUPPORTED:
                    yield os.path.join(dirpath, f)


def _tag(b, lines):
    """Human-readable stand-in for a rung: its label (`try`, `if (def.coerce)`, …) if it
    has one, else the raw source text of its own start line. Lets a human judge a finding
    from the report alone — no need to open the file to see WHAT the colliding rungs are."""
    lbl = (b.get("label") or "").strip()
    if lbl:
        return lbl[:40]
    return lines[b["start"] - 1].strip()[:40]


def line_kinds(blocks, line, lines):
    """Classify one probed line's ladder into findings: [(kind, detail)]. Shared by the
    invariant sweep (`sweep_file`) and the eyeball level-map (`write_level_map`) so the two
    never drift into judging the same ladder differently.

    kinds, worst-first: CONTAIN/RANGE (HIGH, real bugs) — SIBLING (INFO, shared brace
    boundary, not a bug, see CONTRACT invariant #8) — LEVEL (LOW, try/catch cosmetic tie)."""
    out = []
    for b in blocks:
        if not (b["start"] <= line <= b["end"]):
            out.append(("CONTAIN", f"rung [{b['start']}-{b['end']}] lvl{b.get('level')} "
                                    f"{_tag(b, lines)!r} excludes line"))
    for outer, inner in zip(blocks, blocks[1:]):
        nests = outer["start"] <= inner["start"] and inner["end"] <= outer["end"]
        o = f"[{outer['start']}-{outer['end']}]/lvl{outer['level']} {_tag(outer, lines)!r}"
        i = f"[{inner['start']}-{inner['end']}]/lvl{inner['level']} {_tag(inner, lines)!r}"
        if not nests:
            if (outer["level"] == inner["level"]
                    and outer["end"] == line and inner["start"] == line):
                out.append(("SIBLING", f"{o} meets {i} at the hit line — shared brace "
                                        f"boundary, not a nesting break"))
            else:
                out.append(("RANGE", f"{o} does not span {i}"))
        elif outer["level"] >= inner["level"]:
            out.append(("LEVEL", f"{o} then nested {i} — level not deeper"))
    return out


def query_violation(path, line, lines):
    """Cross-check the CORE API's default `--query` (level 0): `get_codeblock(path, line,
    query=True)['text']` — the same function other tools will soon call directly (Vision04:
    get_codeblock as the structural-core provider) — must actually CONTAIN the probed line's
    real content at the right row. This exercises `resolve()` (the invariant #8 ambiguity
    climb) and the text slice, neither of which the ladder checks above touch (they only
    look at raw `get_blocks()` rungs, never the resolved/queried text a caller would get).
    Returns a detail string, or None if consistent."""
    from get_codeblock.core import get_codeblock
    try:
        result = get_codeblock(path, line_num=line, level=0, query=True)
    except Exception as e:  # noqa: BLE001
        return f"get_codeblock(query=True) raised: {e!r}"
    start, end, text = result["start"], result["end"], result["text"]
    if not (start <= line <= end):
        return f"query block [{start}-{end}] does not contain line {line}"
    rows = text.splitlines(keepends=True)
    idx = line - start
    if not (0 <= idx < len(rows)):
        return f"query block [{start}-{end}] text has {len(rows)} row(s), line {line} is row {idx} (out of range)"
    got = rows[idx].rstrip("\r\n")
    want = lines[line - 1].rstrip("\r\n")
    if got != want:
        return f"query block [{start}-{end}] row {idx} is {got!r}, real file line {line} is {want!r}"
    return None


def sweep_file(path, step, max_lines, check_query=False):
    """Return (checked, [violation]) for one file. violation = (line, kind, detail)."""
    try:
        lines = open(path, encoding="utf-8", errors="replace").readlines()
    except OSError as e:
        return 0, [(0, "OPEN", repr(e))]
    n = len(lines)
    if n == 0:
        return 0, []
    reader = Reader.open(path, lines)
    hi = min(n, max_lines) if max_lines else n
    viol = []
    checked = 0
    saw_any_block = False
    for line in range(1, hi + 1, step):
        # Only poke NON-BLANK lines: a blank line genuinely between blocks legitimately
        # belongs to no block, so "not contained" there is expected, not a bug.
        if not lines[line - 1].strip():
            continue
        checked += 1
        try:
            blocks = reader.get_blocks(path, line)
        except Exception as e:  # noqa: BLE001 — a crash on any line is itself a finding
            viol.append((line, "CRASH", f"{e!r} | {traceback.format_exc().splitlines()[-1]}"))
            continue
        if blocks:
            saw_any_block = True
        else:
            viol.append((line, "EMPTY", "no ladder for a non-blank line"))
            continue
        for kind, detail in line_kinds(blocks, line, lines):
            viol.append((line, kind, detail))
        if check_query:
            detail = query_violation(path, line, lines)
            if detail is not None:
                viol.append((line, "QUERY", detail))
    # downgrade EMPTY to noise if the file genuinely has no blocks at all
    if not saw_any_block:
        viol = [v for v in viol if v[1] != "EMPTY"]
    return checked, viol


def write_level_map(path, out_dir):
    """Write an eyeball-review copy of `path` with a fixed `START-END | LVL<flag>| ` prefix
    on every line:
      * START-END — the innermost RUNG containing the line (from `get_blocks`, its ladder
        entry, NOT the whole file) — so you can see exactly which block get_blocks thinks
        owns this line, not just a number.
      * LVL       — real depth (`line_level`: 1 + enclosing bodies). It counts nesting, so
        a plain statement gets the SAME depth as a sibling `if`/`for` header at the same
        indent — unlike a rung's own `level` field, which only bumps on lines that open
        their OWN nested block (a bare assignment right after `if:`/`for:` headers at
        identical indentation would misleadingly show one level shallower — the real
        `docker.py` case: `normalized = {}` at the same indent as `if`/`for` siblings).
      * <flag>    — ' ' normally, '*' if the sweep would flag this line as a SIBLING
        (shared brace boundary — `} else {`, `} catch (e) {`: two blocks legitimately meet
        here, expected), '!' if it would flag anything worse (CONTAIN/RANGE/LEVEL).

    Both columns are padded to the widest value actually seen in the file, so every line
    lines up in one clean table — nothing to eyeball-align by hand.

    Output goes to `out_dir` (not next to the source) so review copies always land in one
    place — nothing to hunt for afterwards."""
    try:
        lines = open(path, encoding="utf-8", errors="replace").readlines()
    except OSError as e:
        return None, repr(e)
    reader = Reader.open(path, lines)
    n = len(lines)
    rows = []  # (start, end, level, flag, raw_line)
    for i in range(1, n + 1):
        try:
            blocks = reader.get_blocks(path, i)
        except Exception:
            blocks = []
        try:
            level = reader.line_level(lines, i - 1)
        except Exception:
            level = 1
        flag = " "
        if blocks:
            kinds = {k for k, _ in line_kinds(blocks, i, lines)}
            if kinds & {"CONTAIN", "RANGE", "LEVEL", "CRASH"}:
                flag = "!"
            elif "SIBLING" in kinds:
                flag = "*"
        b = blocks[-1] if blocks else None
        start, end = (b["start"], b["end"]) if b else (i, i)
        rows.append((start, end, level, flag, lines[i - 1]))

    span_w = max(len(f"{s}-{e}") for s, e, _l, _f, _r in rows) if rows else 1
    lvl_w = max(len(str(lv)) for _s, _e, lv, _f, _r in rows) if rows else 1
    out = []
    for start, end, level, flag, raw in rows:
        if not raw.endswith("\n"):
            raw += "\n"
        span = f"{start}-{end}".rjust(span_w)
        lvl = str(level).rjust(lvl_w)
        out.append(f"{span} | {lvl}{flag}| {raw}")
    out_path = os.path.join(out_dir, f"LEVELMAP_{os.path.basename(path)}.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.writelines(out)
    return out_path, None


SEVERITY = {"CONTAIN": "HIGH", "CRASH": "HIGH", "OPEN": "HIGH", "RANGE": "HIGH", "QUERY": "HIGH",
            "LEVEL": "LOW", "SIBLING": "INFO", "EMPTY": "INFO"}


def main():
    ap = argparse.ArgumentParser(description="Fuzz get_blocks ladder invariants over a tree.")
    ap.add_argument("roots", nargs="*", default=[_HERE], help="files/dirs to sweep (default: test/)")
    ap.add_argument("--step", type=int, default=1, help="check every Nth line (default 1)")
    ap.add_argument("--max-lines", type=int, default=0, help="cap lines checked per file (0=all)")
    ap.add_argument("--max-bytes", type=int, default=5_000_000, help="skip files larger than this")
    ap.add_argument("--show", type=int, default=20, help="max violations to print per file")
    ap.add_argument("--quiet", action="store_true", help="only the final summary")
    ap.add_argument("--show-info", action="store_true",
                     help="also itemize INFO findings (SIBLING/EMPTY) per file — noisy, "
                          "default output only itemizes HIGH/LOW (the actionable ones)")
    ap.add_argument("--file", dest="file", help="sweep only this one file (overrides roots)")
    ap.add_argument("--check-query", action="store_true",
                     help="also cross-check get_codeblock(query=True) (the CORE API `--query` "
                          "uses/will be embedded by other tools) against the real file text — "
                          "not just get_blocks()' raw ranges. Slower (one extra full API call "
                          "per line); off by default")
    ap.add_argument("--write-level", action="store_true",
                     help="also write an eyeball-review copy of each swept file with a "
                          "level-number/flag prefix on every line (see write_level_map "
                          "docstring); written next to this script (test/), never next to "
                          "the source, so nothing to hunt for afterwards")
    args = ap.parse_args()

    roots = [args.file] if args.file else (args.roots or [_HERE])
    totals = {"files": 0, "lines": 0}
    counts = {k: 0 for k in SEVERITY}
    bad_files = 0

    for path in iter_files(roots):
        try:
            if os.path.getsize(path) > args.max_bytes:
                continue
        except OSError:
            continue
        checked, viol = sweep_file(path, max(1, args.step), args.max_lines, args.check_query)
        totals["files"] += 1
        totals["lines"] += checked
        for _ln, kind, _d in viol:
            counts[kind] = counts.get(kind, 0) + 1
        if args.write_level:
            out_path, err = write_level_map(path, _HERE)
            if err:
                print(f"  [write-level failed for {path}: {err}]")
            else:
                print(f"  level map written: {out_path}")
        # INFO findings (SIBLING/EMPTY) are expected structural noise, not bugs — they'd
        # otherwise bury the HIGH/LOW findings under a wall of text on real codebases full
        # of `} else {`. Itemize only HIGH/LOW by default; --show-info opts into the rest.
        itemizable = viol if args.show_info else [v for v in viol if SEVERITY.get(v[1]) != "INFO"]
        if itemizable:
            bad_files += 1
            if not args.quiet:
                rel = os.path.relpath(path, os.path.commonpath(roots) if len(roots) > 1 else roots[0])
                print(f"\n########## {rel}  ({checked} lines checked)")
                for line, kind, detail in itemizable[:args.show]:
                    print(f"  [{SEVERITY.get(kind, '?'):4}] {kind:8} line {line}: {detail}")
                if len(itemizable) > args.show:
                    print(f"  … +{len(itemizable) - args.show} more")

    high = counts["CONTAIN"] + counts["CRASH"] + counts["OPEN"] + counts["RANGE"] + counts["QUERY"]
    print("\n" + "-" * 50)
    print(f"swept {totals['files']} files, {totals['lines']} line-probes; "
          f"{bad_files} files with HIGH/LOW findings")
    print(f"  HIGH  CONTAIN={counts['CONTAIN']} RANGE={counts['RANGE']} CRASH={counts['CRASH']} "
          f"OPEN={counts['OPEN']} QUERY={counts['QUERY']}")
    print(f"  LOW   LEVEL={counts['LEVEL']}")
    print(f"  INFO  SIBLING={counts['SIBLING']} EMPTY={counts['EMPTY']}   "
          "(expected noise -- shared close/open brace boundaries; use --show-info to itemize)")
    sys.exit(1 if high else 0)


if __name__ == "__main__":
    main()
