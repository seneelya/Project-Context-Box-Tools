#!/usr/bin/env python3
"""get_codeblock reads a non-UTF-8 file (cp1251 / cp1252) instead of dying on UnicodeDecodeError:
same rows, readable letters, a note in the File: header. Synthetic files only."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

from get_codeblock.physical_lines import decode_source, read_lines, read_source

GCB = os.path.join(TOOLS_DIR, "get_codeblock.py")

PY_TEXT = "# Привет, мир\n\ndef f():\n    return \"строка\"\n\n\ndef g():\n    return 2\n"
MD_TEXT = "# Guide — start\n\nText.\n\n## Part two\n\nMore café text.\n"
CPP_TEXT = "// Комментарий к функции\nint f(int x) {\n  return x; // ещё\n}\n\nint g() { return 1; }\n"


def gcb(*args):
    r = subprocess.run([sys.executable, GCB, *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout


def test_decode_picks_the_code_page():
    assert decode_source(PY_TEXT.encode("utf-8")) == (PY_TEXT, None)
    assert decode_source(PY_TEXT.encode("cp1251")) == (PY_TEXT, "cp1251")
    assert decode_source(MD_TEXT.encode("cp1252")) == (MD_TEXT, "cp1252")


def test_rows_and_bytes_stay_in_place_with_crlf():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d, "a.py")
        p.write_bytes(PY_TEXT.replace("\n", "\r\n").encode("cp1251"))
        lines = read_lines(str(p))
        assert len(lines) == 8 and lines[0] == "# Привет, мир\r\n"
        assert read_source(str(p)).decode("utf-8") == "".join(lines)


def test_gcb_on_cp1251_python_cpp_and_cp1252_markdown():
    with tempfile.TemporaryDirectory() as d:
        py = Path(d, "a.py")
        py.write_bytes(PY_TEXT.encode("cp1251"))
        out = gcb("--file", str(py), "--line", "3", "--query")
        assert "not UTF-8, read as cp1251" in out and "# Привет, мир" in out and "строка" in out, out
        md = Path(d, "a.md")
        md.write_bytes(MD_TEXT.encode("cp1252"))
        out = gcb("--file", str(md), "--outline")
        assert "Guide — start" in out and "Part two" in out, out
        cpp = Path(d, "a.cpp")
        cpp.write_bytes(CPP_TEXT.encode("cp1251"))
        out = gcb("--file", str(cpp), "--line", "2", "--query")
        assert "not UTF-8, read as cp1251" in out and "// Комментарий к функции" in out, out
        assert "BLOCK : 1-4" in out, out
        utf = Path(d, "u.py")
        utf.write_text(PY_TEXT, encoding="utf-8")
        assert "not UTF-8" not in gcb("--file", str(utf), "--line", "3", "--query")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"ok   {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
