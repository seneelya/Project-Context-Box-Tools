#!/usr/bin/env python3
"""Tests for split_monster.py — see Plan04__split_monster.md (Пункт 5) for the checklist this
covers. Fixtures are small inline JS snippets, not hermes-filetools itself."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # test/
TOOLS_DIR = os.path.dirname(SCRIPT_DIR)                  # __HQ/tools/
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

import split_monster as sm

TOOL_PATH = os.path.join(TOOLS_DIR, "split_monster.py")

FIXTURE_JS = """\
import { unrelated } from './x.js';

function helperOne() {
  return 1;
}

function helperTwo() {
  return helperOne() + 1;
}

const CONST_A = 42;
"""


def _write_fixture(tmp_dir, name="monster.js", content=FIXTURE_JS):
    path = Path(tmp_dir) / name
    path.write_text(content, encoding="utf-8")
    return str(path)


def run_cli(*args):
    cmd = [sys.executable, TOOL_PATH] + list(args)
    # split_monster.py forces UTF-8 stdout (Windows console codepages choke on Cyrillic
    # otherwise) — decode the same way here, not via the locale-default codepage.
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        print("stdout:", result.stdout)
        print("stderr:", result.stderr)
    return result


# --------------------------------------------------------------------------- cut()

def test_cut_returns_exact_block_text():
    with tempfile.TemporaryDirectory() as d:
        path = _write_fixture(d)
        block = sm.cut(path, 3)  # `function helperOne() {`
        assert block.text.splitlines()[0].strip() == "function helperOne() {"
        assert block.text.splitlines()[-1].strip() == "}"
        assert block.start == 3
        assert block.end == 5


# --------------------------------------------------------------------------- monster.write

def test_write_without_apply_creates_nothing(capsys):
    with tempfile.TemporaryDirectory() as d:
        src = _write_fixture(d)
        target = str(Path(d) / "out.js")
        block = sm.cut(src, 3)
        sm.monster.write(target, [block], [])
        assert not Path(target).exists()
        out = capsys.readouterr().out
        assert "dry-run" in out


def test_write_with_apply_restores_source_order(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        src = _write_fixture(d)
        target = str(Path(d) / "out.js")
        b1 = sm.cut(src, 3)  # helperOne — earlier in source
        b2 = sm.cut(src, 7)  # helperTwo — later in source
        monkeypatch.setattr(sys, "argv", ["split_monster", "--apply"])
        # pass in REVERSE order on purpose — write() must restore source order regardless
        sm.monster.write(target, [b2, b1], [sm.add_import("import { x } from './x.js';")])
        text = Path(target).read_text(encoding="utf-8")
        assert text.index("helperOne") < text.index("helperTwo")
        assert text.count("import { x } from './x.js';") == 1


def test_write_second_batch_goes_before_existing_body(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        src = _write_fixture(d)
        target = str(Path(d) / "out.js")
        monkeypatch.setattr(sys, "argv", ["split_monster", "--apply"])

        b1 = sm.cut(src, 3)
        sm.monster.write(target, [b1], [sm.add_import("import { a } from './a.js';")])

        b2 = sm.cut(src, 7)
        sm.monster.write(target, [b2], [sm.add_import("import { a } from './a.js';"),
                                        sm.add_import("import { b } from './b.js';")])

        text = Path(target).read_text(encoding="utf-8")
        assert text.index("helperTwo") < text.index("helperOne")
        assert text.count("import { a } from './a.js';") == 1
        assert text.count("import { b } from './b.js';") == 1


# --------------------------------------------------------------------------- monster.cut

def test_monster_cut_removes_exact_ranges(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        src = _write_fixture(d)
        monkeypatch.setattr(sys, "argv", ["split_monster", "--apply"])
        block = sm.cut(src, 3)
        sm.monster.cut(src, [block])
        remaining = Path(src).read_text(encoding="utf-8")
        assert "function helperOne" not in remaining
        assert "function helperTwo" in remaining


def test_monster_cut_rejects_mismatched_source():
    with tempfile.TemporaryDirectory() as d:
        src = _write_fixture(d)
        block = sm.cut(src, 3)
        try:
            sm.monster.cut("some/other/file.js", [block])
            assert False, "expected ValueError"
        except ValueError:
            pass


# --------------------------------------------------------------------------- CLI: --investigate stub

def test_investigate_is_a_documented_stub_not_a_crash():
    with tempfile.TemporaryDirectory() as d:
        src = _write_fixture(d)
        result = run_cli("--file", src, "--investigate")
        assert result.returncode != 0
        assert "не реализован" in result.stderr
        assert "v1" in result.stderr


def test_investigate_does_not_require_split_or_out_script():
    # would previously fail argparse's own required-arg check before reaching our code
    result = run_cli("--file", "irrelevant.js", "--investigate")
    assert "the following arguments are required" not in result.stderr


def test_help_mentions_investigate_is_unbuilt():
    result = run_cli("--help")
    assert result.returncode == 0
    assert "--investigate" in result.stdout
    assert "НЕ РЕАЛИЗОВАНО" in result.stdout


# --------------------------------------------------------------------------- --generate CLI

def test_generate_produces_tagged_layered_script():
    with tempfile.TemporaryDirectory() as d:
        src = _write_fixture(d)
        out_script = str(Path(d) / "move.py")
        result = run_cli(
            "--file", src,
            "--split", "3", str(Path(d) / "target.js"),
            "--out-script", out_script,
        )
        assert result.returncode == 0
        text = Path(out_script).read_text(encoding="utf-8")
        assert "#1" in text
        assert "cut(" in text
        assert "monster.write(" in text
        assert "monster.cut(" in text
        # code line carries only code + tag — no mixed-in description
        code_line = [l for l in text.splitlines() if l.strip().startswith("c01 = cut(")][0]
        assert code_line.rstrip().endswith("#1")
        assert "helperOne" not in code_line  # descriptive text lives on the line ABOVE


def test_generate_hint_finds_cross_reference():
    with tempfile.TemporaryDirectory() as d:
        src = _write_fixture(d)
        out_script = str(Path(d) / "move.py")
        run_cli(
            "--file", src,
            "--split", "3", str(Path(d) / "target.js"),  # helperOne, referenced by helperTwo
            "--out-script", out_script,
        )
        text = Path(out_script).read_text(encoding="utf-8")
        assert "best-effort" in text
        assert "helperOne" in text  # the hint names the block being cross-referenced


def test_generated_script_runs_and_moves_the_block():
    with tempfile.TemporaryDirectory() as d:
        src = _write_fixture(d)
        target = str(Path(d) / "target.js")
        out_script = str(Path(d) / "move.py")
        run_cli("--file", src, "--split", "3", target, "--out-script", out_script)

        preview = subprocess.run([sys.executable, out_script], capture_output=True, text=True)
        assert preview.returncode == 0
        assert not Path(target).exists()

        applied = subprocess.run(
            [sys.executable, out_script, "--apply"], capture_output=True, text=True
        )
        assert applied.returncode == 0, applied.stderr
        assert Path(target).exists()
        assert "function helperOne" in Path(target).read_text(encoding="utf-8")
        assert "function helperOne" not in Path(src).read_text(encoding="utf-8")
