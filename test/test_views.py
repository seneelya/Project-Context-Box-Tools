"""get_codeblock/views.py: every CLI mode as data + its picture, and `block_range`.
Run: python test/test_views.py"""
import io
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

from get_codeblock import views

_PASS = _FAIL = 0


def check(name, cond):
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(".", end="", flush=True)
    else:
        _FAIL += 1
        print(f"\nFAIL: {name}")


def _tmp(d, fname, text):
    p = os.path.join(d, fname)
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return p


PY = """import os


# helper comment
def a():
    x = 1
    if x:
        y = 2
        z = 3
    return x


def b():
    for i in range(3):
        print(i)
    return 0
"""

# One long function: a short read from inside it cannot reach its end.
PY_BIG = "def big():\n" + "".join(f"    v{i} = {i}\n" for i in range(60)) + "    return 0\n"

MD = """# Title

Intro line.

## First

one
two
three

## Second

four
five
"""

TS = """// greeting
export function greet(name: string): string {
  const s = `hi ${name}`;
  return s;
}

export function twice(n: number): number {
  if (n > 0) {
    return n * 2;
  }
  return 0;
}
"""

TXT = """First paragraph line one.
First paragraph line two.

Second paragraph line one.
Second paragraph line two.
Second paragraph line three.

Third paragraph.
"""


def _cli(*args):
    """The CLI's stdout, in-process through `_main_impl` (not `main`: that one also writes
    the call log, and a test run must not land in the real usage log)."""
    from get_codeblock import core
    old_argv, old_out = sys.argv, sys.stdout
    sys.argv, sys.stdout = ["get_codeblock.py"] + list(args), io.StringIO()
    code = 0
    try:
        core._main_impl()
    except SystemExit as e:
        code = e.code or 0
    finally:
        out, sys.argv, sys.stdout = sys.stdout.getvalue(), old_argv, old_out
    return code, out


def _fwd(p):
    """The CLI shows the path it opened with forward slashes; views show it as given."""
    return p.replace("\\", "/")


def test_open_source(d):
    py = _tmp(d, "a.py", PY)
    src = views.open_source(py)
    check("open: lines", len(src.lines) == 16)
    check("open: py comment wrapper", src.c("x") == "#x")
    check("open: md comment wrapper", views.open_source(_tmp(d, "m.md", MD)).c("x") == "<!-- x -->")
    try:
        views.open_source(_tmp(d, "x.log", "a\nb\n"))
        check("open: .log refused", False)
    except views.UnsupportedFormat as e:
        check("open: .log refused by name", "'.log'" in str(e))
    try:
        views.open_source(os.path.join(d, "missing.py"))
        check("open: missing file", False)
    except FileNotFoundError:
        check("open: missing file", True)


def test_pictures_equal_cli(d):
    """The picture of every view is byte-for-byte the CLI's stdout (pipe, not a tty)."""
    py, md = _fwd(_tmp(d, "a.py", PY)), _fwd(_tmp(d, "m.md", MD))
    for path in (py, md):
        src = views.open_source(path)
        text = views.as_text(views.render_outline(views.outline_view(src), src))
        check(f"outline == cli ({os.path.basename(path)})", text == _cli("--file", path, "--outline")[1])
    src = views.open_source(py)
    text = views.as_text(views.render_ladder(views.ladder_view(src, [8, 15]), src))
    check("ladder == cli", text == _cli("--file", py, "--line", "8,15")[1])
    view = views.query_view(src, [8], [0], force=True)
    text = views.as_text(views.render_query(view, src, numbered=True))
    check("query == cli", text == _cli("--file", py, "--line", "8", "--query", "--force", "--numbered")[1])
    view = views.outline_batch_view(src, [8, 15], [-1, -1])
    text = views.as_text(views.render_outline_batch(view, src))
    check("outline batch == cli",
          text == _cli("--file", py, "--line", "8,15", "--ancestor-level", "1", "--outline")[1])


def test_views_are_data(d):
    src = views.open_source(_tmp(d, "a.py", PY))
    ov = views.outline_view(src)
    check("outline rows are dicts with ranges",
          [(r['start'], r['end'], r['text']) for r in ov['rows'] if not r['filler']]
          == [(4, 10, "def a()  # helper comment"), (13, 16, "def b()")])
    q = views.query_view(src, [8, 9], [0, 0], force=True)
    check("query runs: one block, two hits", [(r['start'], r['end']) for r in q['runs']] == [(7, 9)])
    check("query: no note with force", q['note'] is None and q['errors'] == [])
    q = views.query_view(src, [8], [0])
    check("query: escalation leaves a note", q['note'] is not None and "escalated" in q['note'])
    q = views.query_view(src, [99], [0], force=True)
    check("query: out of range is an error, not a raise", q['runs'] == [] and len(q['errors']) == 1)
    lv = views.ladder_view(src, [8])
    hits = [r for r in lv['rows'] if r['kind'] == 'hit']
    check("ladder: hit row carries the source line", hits and hits[0]['text'] == "y = 2")
    try:
        views.outline_view(src, line=99)
        check("outline: line out of range raises", False)
    except ValueError:
        check("outline: line out of range raises", True)


def test_block_range(d):
    py = views.open_source(_tmp(d, "a.py", PY))
    r = views.block_range(py, 6, 4)          # asked 6-9: inside a(), `if` 7-9
    check("py: both ends snap to a()", (r['from'], r['to'], r['cut']) == (4, 10, None))
    r = views.block_range(py, 14, 2)         # asked 14-15: the `for` in b()
    check("py: a small read stays inside", (r['from'], r['to'], r['cut']) == (13, 16, None))
    big = views.open_source(_tmp(d, "big.py", PY_BIG))
    r = views.block_range(big, 20, 10)       # asked 20-29 deep inside a 62-line function
    # `cut` = the INNERMOST block around the end: here the run of assignments 2-61
    check("py big: cut by line, block named", (r['from'], r['to'], r['cut']) == (20, 29, [2, 61]))
    md = views.open_source(_tmp(d, "m.md", MD))
    r = views.block_range(md, 7, 2)          # asked 7-8 in "## First"
    check("md: snaps to the section", (r['from'], r['to'], r['cut']) == (5, 10, None))
    ts = views.open_source(_tmp(d, "t.ts", TS))
    r = views.block_range(ts, 9, 2)          # asked 9-10: inside `if` of twice()
    check("ts: snaps to twice()", (r['from'], r['to'], r['cut']) == (7, 12, None))
    r = views.block_range(ts, 3, 2)          # asked 3-4 inside greet(), comment glued above
    check("ts: head takes the glued comment", (r['from'], r['to']) == (1, 5))
    txt = views.open_source(_tmp(d, "p.txt", TXT))
    r = views.block_range(txt, 5, 2)         # asked 5-6 in the second paragraph
    # start: the paragraph 4-6; end: the OUTERMOST rung within tol is the file root 1-8
    check("txt: paragraph start, outermost end", (r['from'], r['to'], r['cut']) == (4, 8, None))
    for bad in ((0, 5), (99, 5), (3, 0)):
        try:
            views.block_range(py, *bad)
            check(f"block_range{bad} raises", False)
        except ValueError:
            check(f"block_range{bad} raises", True)


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as d:
        test_open_source(d)
        test_pictures_equal_cli(d)
        test_views_are_data(d)
        test_block_range(d)
    print("\n" + "-" * 50)
    print(f"{_PASS} passed, {_FAIL} failed")
    sys.exit(1 if _FAIL else 0)
