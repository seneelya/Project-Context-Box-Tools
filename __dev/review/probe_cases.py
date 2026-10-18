"""Independent exploratory reproductions; only temporary source files are modified."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from get_codeblock import views
from get_codeblock.core import get_codeblock
from get_codeblock.name_resolver import declarations, resolve_name


def cli(path, *args):
    code = "from get_codeblock import core; core._log_call = lambda *a: None; core.main()"
    p = subprocess.run([sys.executable, "-c", code, "--file", str(path), *args],
                       cwd=ROOT, capture_output=True, encoding="utf-8",
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    return dict(rc=p.returncode, stdout=p.stdout, stderr=p.stderr)


def main():
    out = {}
    with tempfile.TemporaryDirectory(prefix="gcb-review-") as tmp:
        d = Path(tmp)

        p = d / "decorated.py"
        p.write_text("@decorator(\n    option=True,\n)\ndef target():\n    return 42\n", encoding="utf-8")
        src = views.open_source(str(p))
        out["multiline_decorator"] = dict(
            outline=src.handler.outline(src.lines),
            query=get_codeblock(str(p), 4, level=1, query=True),
            decorator_line=get_codeblock(str(p), 1, query=True))

        p = d / "qualified.ts"
        p.write_text("class A {\n  foo() {\n    return 1;\n  }\n}\nclass B {\n  foo() {\n    return 2;\n  }\n}\n", encoding="utf-8")
        out["qualified_glob"] = dict(
            exact=resolve_name(str(p), "A.foo").__dict__,
            glob=resolve_name(str(p), "A.foo*").__dict__)
        from get_codeblock.reader.backends.treesitter import TSBackend
        from get_codeblock.core import get_line_levels
        original_root = TSBackend.root
        calls = []

        def counted_root(self, source):
            calls.append(len(source))
            return original_root(self, source)

        TSBackend.root = counted_root
        try:
            src = views.open_source(str(p))
            view = views.query_view(src, [2, 3, 7], [0, 0, 0], force=True)
            query_calls = len(calls)
            calls.clear()
            get_line_levels(str(p), [2, 3, 7])
            out["batch_parse_count"] = dict(anchors=3, query_root_calls=query_calls,
                                            line_level_root_calls=len(calls))
        finally:
            TSBackend.root = original_root

        p = d / "multiple.ts"
        p.write_text("export const FIRST = 1, SECOND = 2;\n", encoding="utf-8")
        out["multiple_declarations"] = dict(declarations=declarations(str(p)),
                                            second=cli(p, "--name", "SECOND", "--force"))

        p = d / "fenced.md"
        p.write_text("# Real\n````markdown\n```\n# Fake inside code\n````\n## Actual\nbody\n", encoding="utf-8")
        src = views.open_source(str(p))
        out["long_fence"] = src.handler.outline(src.lines)

        p = d / "heading.md"
        p.write_text("# Getting started\nInstall the application.\n", encoding="utf-8")
        out["markdown_heading_name"] = cli(p, "--name", "Getting started", "--force")

        p = d / "fallback.py"
        p.write_text("VALUE = 42\ndef target():\n    return VALUE\n", encoding="utf-8")
        fallback = os.environ.get("GCB_REVIEW_FALLBACK_PYTHON")
        if fallback:
            r = subprocess.run([fallback, str(ROOT / "get_codeblock.py"), "--file", str(p),
                                "--name", "target", "--force"], capture_output=True,
                               encoding="utf-8", env=dict(os.environ, PYTHONIOENCODING="utf-8"))
            out["fallback_name"] = dict(rc=r.returncode, stdout=r.stdout, stderr=r.stderr)

        p = d / "unicode.md"
        p.write_text("# First\ntext\u2028continued\n## Second\nbody\n", encoding="utf-8")
        src = views.open_source(str(p))
        out["unicode_lines"] = dict(lines=src.lines, outline=src.handler.outline(src.lines),
                                    query=get_codeblock(str(p), 3, level=0, query=True))

        p = d / "snapshot.py"
        p.write_text("def old():\n    return 1\n", encoding="utf-8")
        src = views.open_source(str(p))
        p.write_text("# new version\n\ndef new():\n    return 999\n", encoding="utf-8")
        v = views.query_view(src, [1], [0], force=True)
        out["snapshot"] = dict(lines=src.lines, view=v,
                                rendered=views.as_text(views.render_query(v, src)))

        p = d / "errors.py"
        p.write_text("def ok():\n    return 1\n", encoding="utf-8")
        out["invalid_lines"] = dict(
            survey=cli(p, "--line", "1,999"),
            outline=cli(p, "--line", "1,999", "--outline"),
            query=cli(p, "--line", "1,999", "--query", "--force"),
            empty_arg=cli(p, ""))

        p = d / "crlf.py"
        p.write_bytes(b"def target():\r\n    return 1\r\n")
        out["crlf"] = dict(raw=p.read_bytes().decode(), query=get_codeblock(str(p), 1, query=True))

        p = d / "one_line.py"
        p.write_text("def first(): return 1\ndef second():\n    return 2\n", encoding="utf-8")
        src = views.open_source(str(p))
        out["one_line_def"] = dict(outline=src.handler.outline(src.lines),
                                   query=get_codeblock(str(p), 1, level=1, query=True))

        p = d / "body.sh"
        p.write_text("build() {\n  echo hi\n}\n", encoding="utf-8")
        src = views.open_source(str(p))
        out["shell_depth"] = dict(outline=src.handler.outline(src.lines),
                                  rungs=src.handler.get_blocks(str(p), 2))

        p = d / "scalar.yaml"
        p.write_text("message: |\n  hello\nnext: 42\n", encoding="utf-8")
        src = views.open_source(str(p))
        out["yaml_scalar"] = dict(outline=src.handler.outline(src.lines),
                                   rungs=src.handler.get_blocks(str(p), 3),
                                   query=get_codeblock(str(p), 3, query=True))

    out["confirmed"] = {
        "R01": out["multiline_decorator"]["query"]["start"] != 1,
        "R02": out["snapshot"]["view"]["runs"][0]["end"] > len(out["snapshot"]["lines"]),
        "R03": max(r["end"] for r in out["unicode_lines"]["outline"]) > len(out["unicode_lines"]["lines"]),
        "R04": any(r["text"] == "Fake inside code" for r in out["long_fence"]),
        "R05": any(h.name == "B.foo" for h in out["qualified_glob"]["glob"]["hits"]),
        "R06": out["multiple_declarations"]["second"]["rc"] == 2,
        "R07": "no exact" in out["markdown_heading_name"]["stdout"],
        "R08": out["crlf"]["query"]["text"] != out["crlf"]["raw"],
        "R09": out["invalid_lines"]["survey"]["rc"] == 0 and out["invalid_lines"]["outline"]["rc"] == 0,
        "R10": "IndexError" in out["invalid_lines"]["empty_arg"]["stderr"],
    }
    dest = Path(__file__).resolve().parent / "validation" / "probes.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2,
                              default=lambda obj: obj.__dict__), encoding="utf-8")
    print(dest)
    print(json.dumps(out["confirmed"]))


if __name__ == "__main__":
    main()
