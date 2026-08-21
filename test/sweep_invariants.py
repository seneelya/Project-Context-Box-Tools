#!/usr/bin/env python3
"""Fuzz get_blocks (LADDER mode) over every line of many files and flag invariant breaks.

The tool promises (reader/CONTRACT.md invariants 6-7) that the ladder returned for a line
is a clean nest of blocks that ALL contain that line. This sweep pokes real files line by
line through the same entry point the CLI uses (Reader.get_blocks) and reports where that
breaks. It is read-only.

Checks per (file, line):
  * CONTAIN   (HIGH) — a returned rung does NOT span the line (start <= line <= end). This
                       is invariant #7: "выданный блок обязан содержать строку".
  * NEST      (MED)  — ladder is not a clean outer->inner nest (outer must contain inner and
                       sit at a strictly shallower level).
  * CRASH     (HIGH) — get_blocks raised.
  * EMPTY     (INFO) — no ladder for a non-blank line in a file that has blocks elsewhere.

Usage:
    py test/sweep_invariants.py [ROOT ...] [--step N] [--max-lines M] [--max-bytes B]
                                [--show K] [--quiet]

ROOT defaults to this test/ directory (small, fast). Point it at a big checkout (e.g. a
Hermes source tree) to stress it: `py test/sweep_invariants.py Y:\\Hermess\\...\\SRC`.
--step N samples every Nth line (default 1 = all lines; get_blocks re-reads the file per
call, so N>1 is the speed knob on huge trees). Exit code 1 if any HIGH violation is found.
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
    from get_codeblock.reader import address, registry
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

    address.resolve = fast_resolve  # address.py did `from .registry import resolve`

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


def sweep_file(path, step, max_lines):
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
        # invariant #7: every rung contains the line
        for b in blocks:
            if not (b["start"] <= line <= b["end"]):
                viol.append((line, "CONTAIN",
                             f"rung [{b['start']}-{b['end']}] lvl{b.get('level')} "
                             f"{(b.get('label') or '')[:50]!r} excludes line"))
        # blocks come outermost->innermost. Two failure modes, different severity:
        #   RANGE (HIGH) — outer does not span inner: the ladder ranges are broken.
        #   LEVEL (LOW)  — ranges nest fine but levels don't strictly increase (e.g. a
        #                  try_statement wrapper and its catch branch both land at the same
        #                  depth). Cosmetic/modeling, not a containment break.
        for outer, inner in zip(blocks, blocks[1:]):
            if not (outer["start"] <= inner["start"] and inner["end"] <= outer["end"]):
                viol.append((line, "RANGE",
                             f"[{outer['start']}-{outer['end']}]/lvl{outer['level']} does not "
                             f"span [{inner['start']}-{inner['end']}]/lvl{inner['level']}"))
            elif outer["level"] >= inner["level"]:
                viol.append((line, "LEVEL",
                             f"[{outer['start']}-{outer['end']}]/lvl{outer['level']} then nested "
                             f"[{inner['start']}-{inner['end']}]/lvl{inner['level']} — level not deeper"))
    # downgrade EMPTY to noise if the file genuinely has no blocks at all
    if not saw_any_block:
        viol = [v for v in viol if v[1] != "EMPTY"]
    return checked, viol


SEVERITY = {"CONTAIN": "HIGH", "CRASH": "HIGH", "OPEN": "HIGH", "RANGE": "HIGH",
            "LEVEL": "LOW", "EMPTY": "INFO"}


def main():
    ap = argparse.ArgumentParser(description="Fuzz get_blocks ladder invariants over a tree.")
    ap.add_argument("roots", nargs="*", default=[_HERE], help="files/dirs to sweep (default: test/)")
    ap.add_argument("--step", type=int, default=1, help="check every Nth line (default 1)")
    ap.add_argument("--max-lines", type=int, default=0, help="cap lines checked per file (0=all)")
    ap.add_argument("--max-bytes", type=int, default=5_000_000, help="skip files larger than this")
    ap.add_argument("--show", type=int, default=20, help="max violations to print per file")
    ap.add_argument("--quiet", action="store_true", help="only the final summary")
    args = ap.parse_args()

    roots = args.roots or [_HERE]
    totals = {"files": 0, "lines": 0}
    counts = {k: 0 for k in SEVERITY}
    bad_files = 0

    for path in iter_files(roots):
        try:
            if os.path.getsize(path) > args.max_bytes:
                continue
        except OSError:
            continue
        checked, viol = sweep_file(path, max(1, args.step), args.max_lines)
        totals["files"] += 1
        totals["lines"] += checked
        for _ln, kind, _d in viol:
            counts[kind] = counts.get(kind, 0) + 1
        if viol:
            bad_files += 1
            if not args.quiet:
                rel = os.path.relpath(path, os.path.commonpath(roots) if len(roots) > 1 else roots[0])
                print(f"\n########## {rel}  ({checked} lines checked)")
                for line, kind, detail in viol[:args.show]:
                    print(f"  [{SEVERITY.get(kind, '?'):4}] {kind:8} line {line}: {detail}")
                if len(viol) > args.show:
                    print(f"  … +{len(viol) - args.show} more")

    high = counts["CONTAIN"] + counts["CRASH"] + counts["OPEN"] + counts["RANGE"]
    print("\n" + "-" * 50)
    print(f"swept {totals['files']} files, {totals['lines']} line-probes; {bad_files} files with findings")
    print(f"  HIGH  CONTAIN={counts['CONTAIN']} RANGE={counts['RANGE']} CRASH={counts['CRASH']} OPEN={counts['OPEN']}")
    print(f"  LOW   LEVEL={counts['LEVEL']}")
    print(f"  INFO  EMPTY={counts['EMPTY']}")
    sys.exit(1 if high else 0)


if __name__ == "__main__":
    main()
