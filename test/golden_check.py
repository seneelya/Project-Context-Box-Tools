#!/usr/bin/env python3
"""Golden-output regression for get_codeblock: run REAL invocations against the
calibration fixtures in test/, diff the raw stdout against a saved reference file
in test/golden/. check.py/sweep_invariants.py verify hand-picked structural facts
(a level, a range) — this verifies the exact rendered TEXT, catching format
regressions (column drift, wording changes, marker glyphs, ...) that those two
never touch directly.

Usage (run from __HQ/tools/):
  py test/golden_check.py              # compare all cases against test/golden/*.txt
  py test/golden_check.py NAME         # compare only one named case
  py test/golden_check.py --record     # (re)write ALL golden files from current output
  py test/golden_check.py --record NAME  # (re)write just one

A mismatch reports the COUNT of differing lines and their line numbers (not a full
diff dump) — see HowTo__Test-get_codeblock.md for when to add a case and how to
review a --record before committing it (a record is a claim "this output is now
correct", not just "this is what came out").
"""
import subprocess
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent.parent
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"

# (name, args) — args exactly as you'd type them after get_codeblock.py. Keep fixtures
# SMALL (test/Edge, test/pythonSRC/backends/rerank_driver.py, ...) — a golden file is
# meant to be eyeballed in a diff, not scrolled through.
CASES = [
    ("survey_merged_tree", ["--file", "test/csharpSRC2/Core/Settings.cs", "--line", "75,239,253"]),
    ("survey_header_hit", ["--file", "test/Edge/Edge.py", "--line", "54,38"]),
    ("outline_batch_merge", ["--file", "test/csharpSRC2/Core/Settings.cs", "--outline",
                              "--line", "245,395", "--ancestor-level", "0,1"]),
    ("query_merge_touching", ["--file", "test/Edge/Edge.py", "--line", "51,45",
                               "--query", "--level", "-1"]),
    ("query_real_gap_stays_separate", ["--file", "test/Edge/Edge.py", "--line", "51,45", "--query"]),
    ("query_error_isolation", ["--file", "test/pythonSRC/backends/rerank_driver.py",
                                "--line", "49,99999", "--query"]),
    ("outline_single_python", ["--file", "test/pythonSRC/backends/rerank_driver.py", "--outline"]),
    ("outline_markdown", ["--file", "test/mdSRC/capture.py.md", "--outline"]),
    ("single_line_typescript", ["--file", "test/tsSRC/src/analyzer.ts", "--line", "41"]),
    ("single_line_csharp_query", ["--file", "test/csharpSRC/Core/GlobalStopWatchInstance.cs",
                                   "--line", "12", "--query"]),
    ("focus_outline_object", ["--file", "test/Edge/Edge.py", "--line", "38", "--outline"]),
    ("focus_outline_named_parent", ["--file", "test/Edge/Edge.py", "--line", "45",
                                     "--ancestor-level", "1", "--outline"]),
]


def run(args):
    """Real subprocess call — not an import — so this exercises the actual CLI path
    (argv parsing, non-tty stdout) exactly as a human or another tool would invoke it."""
    result = subprocess.run(
        [sys.executable, "get_codeblock.py", *args],
        cwd=TOOLS_DIR, capture_output=True, text=True, encoding="utf-8",
    )
    return result.stdout


def golden_path(name):
    return GOLDEN_DIR / f"{name}.txt"


def record(names):
    GOLDEN_DIR.mkdir(exist_ok=True)
    for name, args in CASES:
        if names and name not in names:
            continue
        actual = run(args)
        golden_path(name).write_text(actual, encoding="utf-8")
        print(f"recorded {name} ({len(actual.splitlines())} lines)")


def check(names):
    cases = [c for c in CASES if not names or c[0] in names]
    if not cases:
        print(f"no case matches {names!r}", file=sys.stderr)
        return 1

    failed = 0
    for name, args in cases:
        gp = golden_path(name)
        if not gp.exists():
            print(f"MISSING golden/{name}.txt -- run: py test/golden_check.py --record {name}")
            failed += 1
            continue

        actual_lines = run(args).splitlines()
        expected_lines = gp.read_text(encoding="utf-8").splitlines()
        width = max(len(actual_lines), len(expected_lines))
        bad = [i + 1 for i in range(width)
               if i >= len(actual_lines) or i >= len(expected_lines)
               or actual_lines[i] != expected_lines[i]]

        if bad:
            failed += 1
            print(f"FAIL {name}: {len(bad)} line(s) differ (of {width}): {bad}")
        else:
            print(f"ok   {name}")

    print(f"\n{len(cases) - failed}/{len(cases)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    args = sys.argv[1:]
    do_record = "--record" in args
    names = [a for a in args if a != "--record"]
    sys.exit(record(names) or 0 if do_record else check(names))
