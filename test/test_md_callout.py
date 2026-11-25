"""REQ-024: a typed callout right under a markdown heading shows in the outline.
Run: python test/test_md_callout.py"""
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

from get_codeblock import views

_PASS = _FAIL = 0

DOC = """# Doc

> Plain intro quote, not a summary.

## One line

> [!info] one line

body

## Multi

> [!Note] first
> line 2
lazy line 3

after

## Long

> [!tldr] LONG

## Paragraph first

Some text.

> [!info] not first, ignored

## Plain quote

> just a quote

## Parent
### Child right away

> [!warning]
> Body of the warning.

## Fenced

> [!info] stops at
```
code
```
""".replace("LONG", " ".join(["abcdefghi"] * 30))


def check(name, cond):
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(".", end="", flush=True)
    else:
        _FAIL += 1
        print(f"\nFAIL: {name}")


def _rows(path, **kw):
    v = views.outline_view(views.open_source(path), **kw)
    return {r['text']: r.get('description') for r in v['rows']}


def test_outline(d):
    p = os.path.join(d, "doc.md")
    for nl in ("\n", "\r\n"):
        with open(p, "w", encoding="utf-8", newline="") as fh:
            fh.write(DOC.replace("\n", nl))
        r = _rows(p, level=3)
        check(f"one line {nl!r}", r["One line"] == "[info] one line")
        check(f"multi joined {nl!r}", r["Multi"] == "[note] first line 2 lazy line 3")
        long = r["Long"]
        check(f"cap 200 {nl!r}", long.startswith("[tldr] ") and long.endswith("…")
              and 190 < len(long) - len("[tldr] ") <= 201)
        check(f"paragraph first {nl!r}", r["Paragraph first"] is None)
        check(f"plain quote {nl!r}", r["Plain quote"] is None and r["Doc"] is None)
        check(f"heading then subheading {nl!r}", r["Parent"] is None)
        check(f"type on its own line {nl!r}", r["Child right away"] == "[warning] Body of the warning.")
        check(f"fence ends callout {nl!r}", r["Fenced"] == "[info] stops at")

    src = views.open_source(p)
    pic = "\n".join(t for _k, t in views.render_outline(views.outline_view(src, level=3), src))
    check("rendered after two spaces", "One line  [info] one line" in pic)
    q = "".join(views.as_text(views.render_query(views.query_view(src, [7], [0]), src)))
    check("query keeps callout in body", "[!info] one line" in q)


def test_code_untouched(d):
    p = os.path.join(d, "m.py")
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# > [!info] not markdown\ndef f():\n    return 1\n")
    v = views.outline_view(views.open_source(p))
    check("code rows have no description", all('description' not in r for r in v['rows']))


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as d:
        test_outline(d)
        test_code_untouched(d)
    print("\n" + "-" * 50)
    print(f"{_PASS} passed, {_FAIL} failed")
    sys.exit(1 if _FAIL else 0)
