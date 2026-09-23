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
        assert "split_monster API (полная палитра" in text
        assert "monster.replace" in text
        assert "переносы" in text
        assert "cut() + monster.cut()" in text
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


# --------------------------------------------------------------------------- banded blocks

BANDED_JS = """\
export const ROW_PX = 34
export const NOTE_ESTIMATE_PX = 30
export const OVERSCAN_PX = 400

function keepMe() {
  return 1;
}
"""


def test_generate_accepts_comma_separated_lines_for_one_target():
    with tempfile.TemporaryDirectory() as d:
        src = _write_md_fixture(d)
        out_script = str(Path(d) / "move.py")
        result = run_cli(
            "--file", src,
            "--split", "5,9", str(Path(d) / "merged.md"),
            "--out-script", out_script,
        )
        assert result.returncode == 0, result.stderr
        text = Path(out_script).read_text(encoding="utf-8")
        assert text.count("= replace(") == 2
        assert "MERGED_BLOCKS = [c01, c02]" in text


def test_generate_dedupes_lines_that_resolve_to_the_same_band():
    with tempfile.TemporaryDirectory() as d:
        src = _write_fixture(d, name="banded.js", content=BANDED_JS)
        out_script = str(Path(d) / "move.py")
        result = run_cli(
            "--file", src,
            "--split", "1", str(Path(d) / "target.js"),
            "--split", "2", str(Path(d) / "target.js"),  # same band as line 1 — must dedupe
            "--out-script", out_script,
        )
        assert result.returncode == 0, result.stderr
        text = Path(out_script).read_text(encoding="utf-8")
        # only ONE `= cut(...)` extraction for the banded range, not two — else monster.cut()
        # would delete the range twice ("cut(" alone also matches the cheat-sheet/monster.cut)
        assert text.count("= cut(") == 1
        assert "TARGET_BLOCKS = [c01]" in text


def test_generate_rejects_same_band_split_to_different_targets():
    with tempfile.TemporaryDirectory() as d:
        src = _write_fixture(d, name="banded.js", content=BANDED_JS)
        out_script = str(Path(d) / "move.py")
        result = run_cli(
            "--file", src,
            "--split", "1", str(Path(d) / "a.js"),
            "--split", "2", str(Path(d) / "b.js"),  # same band, DIFFERENT target — must reject
            "--out-script", out_script,
        )
        assert result.returncode != 0
        assert not Path(out_script).exists()


# --------------------------------------------------------------------------- Находка 1: imports

IMPORTS_JS = """\
import { jsx, jsxs } from 'react/jsx-runtime';
import { useState } from 'react';
import { unrelatedThing } from './other.js';

function Widget() {
  const [x] = useState(0);
  return jsx('div', {});
}

function Plain() {
  return 1;
}
"""


def test_generate_adds_needed_source_imports_for_the_target_that_uses_them():
    with tempfile.TemporaryDirectory() as d:
        src = _write_fixture(d, name="imports.js", content=IMPORTS_JS)
        out_script = str(Path(d) / "move.py")
        result = run_cli(
            "--file", src,
            "--split", "5", str(Path(d) / "widget.js"),  # Widget — uses jsx + useState
            "--out-script", out_script,
        )
        assert result.returncode == 0, result.stderr
        text = Path(out_script).read_text(encoding="utf-8")
        assert "add_import(\"import { jsx } from 'react/jsx-runtime'\")" in text
        assert "add_import(\"import { useState } from 'react'\")" in text
        # jsxs is imported by the source but never used by Widget — must NOT be proposed
        assert "jsxs" not in text
        # unrelatedThing is never used by Widget either
        assert "unrelatedThing" not in text


def test_generate_does_not_propose_imports_a_target_does_not_use():
    with tempfile.TemporaryDirectory() as d:
        src = _write_fixture(d, name="imports.js", content=IMPORTS_JS)
        out_script = str(Path(d) / "move.py")
        result = run_cli(
            "--file", src,
            "--split", "10", str(Path(d) / "plain.js"),  # Plain — uses neither import
            "--out-script", out_script,
        )
        assert result.returncode == 0, result.stderr
        text = Path(out_script).read_text(encoding="utf-8")
        # cheat-sheet mentions add_import(text) by name — only a real "= add_import(" CALL
        # (assigned to a var, same shape as everywhere else in this tool) would be a false positive
        assert "= add_import(" not in text


DEFAULT_NAMESPACE_JS = """\
import React from 'react';
import * as util from './util.js';

function Widget() {
  return React.createElement(util.thing());
}
"""


def test_generate_reconstructs_default_and_namespace_imports():
    with tempfile.TemporaryDirectory() as d:
        src = _write_fixture(d, name="dn.js", content=DEFAULT_NAMESPACE_JS)
        out_script = str(Path(d) / "move.py")
        result = run_cli(
            "--file", src,
            "--split", "4", str(Path(d) / "widget.js"),
            "--out-script", out_script,
        )
        assert result.returncode == 0, result.stderr
        text = Path(out_script).read_text(encoding="utf-8")
        assert "add_import(\"import React from 'react'\")" in text
        assert "add_import(\"import * as util from './util.js'\")" in text


# --------------------------------------------------------------------------- multi-name bands

def test_generate_marks_multi_name_bands_and_lists_every_name_for_consumers():
    with tempfile.TemporaryDirectory() as d:
        src = _write_fixture(d, name="banded.js", content=BANDED_JS)
        out_script = str(Path(d) / "move.py")
        result = run_cli(
            "--file", src,
            "--split", "1", str(Path(d) / "target.js"),
            "--split", "2", str(Path(d) / "target.js"),
            "--split", "3", str(Path(d) / "target.js"),
            "--out-script", out_script,
        )
        assert result.returncode == 0, result.stderr
        text = Path(out_script).read_text(encoding="utf-8")
        assert "# банд: 3 объявлений" in text
        assert "ROW_PX" in text and "NOTE_ESTIMATE_PX" in text and "OVERSCAN_PX" in text
        # monster.consumers() must be asked about EVERY name in the band, not just the first
        consumers_line = [l for l in text.splitlines() if l.startswith("monster.consumers(")][0]
        for name in ("ROW_PX", "NOTE_ESTIMATE_PX", "OVERSCAN_PX"):
            assert name in consumers_line


# --------------------------------------------------------------------------- Находка 2: orphans

ORPHAN_BEFORE_CONST_JS = """\
import { unrelated } from './x.js';

// rationale: this width was picked to fit five-char tool names
const TOOL_FONT = '11px monospace';

function keepMe() {
  return 1;
}
"""


def test_generate_surfaces_orphan_comment_before_a_const_as_a_candidate():
    with tempfile.TemporaryDirectory() as d:
        src = _write_fixture(d, name="orphan.js", content=ORPHAN_BEFORE_CONST_JS)
        out_script = str(Path(d) / "move.py")
        result = run_cli(
            "--file", src,
            "--split", "4", str(Path(d) / "target.js"),  # TOOL_FONT — comment does NOT glue
            "--out-script", out_script,
        )
        assert result.returncode == 0, result.stderr
        text = Path(out_script).read_text(encoding="utf-8")
        assert "# кандидат" in text
        assert "[3-3]" in text  # the comment's own line range


GLUED_COMMENT_JS = """\
import { unrelated } from './x.js';

// this rationale glues straight into the function below

function helperOne() {
  return 1;
}
"""


def test_generate_does_not_offer_a_comment_already_glued_into_its_landmark():
    with tempfile.TemporaryDirectory() as d:
        src = _write_fixture(d, name="glued.js", content=GLUED_COMMENT_JS)
        out_script = str(Path(d) / "move.py")
        result = run_cli(
            "--file", src,
            "--split", "6", str(Path(d) / "target.js"),  # helperOne — comment already IN the block
            "--out-script", out_script,
        )
        assert result.returncode == 0, result.stderr
        text = Path(out_script).read_text(encoding="utf-8")
        assert "# кандидат" not in text


MULTILINE_CONST_JS = """\
import { unrelated } from './x.js';

function helperZero() {
  return 0;
}

// rationale: multi-line object literal below
const ROLE_TONE = {
  user: 'blue',
  assistant: 'green'
}

function helperOne() {
  return 1;
}
"""


def test_generate_excludes_a_candidate_already_claimed_by_a_wider_cut():
    # get_codeblock's own cut() glues a comment into a FOLLOWING multi-line const's range
    # ([7-11]), but outline_rows' Classifier reports them as two separate rows ([7-7] and
    # [8-11]) — an exact-tuple "already claimed" check misses that the narrower row [7-7] is
    # already inside the wider claimed range, and would wrongly offer it as a free candidate
    # (real risk: a naive second cut() on it would delete an already-moved range twice).
    with tempfile.TemporaryDirectory() as d:
        src = _write_fixture(d, name="multiline.js", content=MULTILINE_CONST_JS)
        out_script = str(Path(d) / "move.py")
        result = run_cli(
            "--file", src,
            "--split", "8", str(Path(d) / "target.js"),   # ROLE_TONE — glues the comment in
            "--split", "13", str(Path(d) / "target2.js"),  # helperOne — its own separate target
            "--out-script", out_script,
        )
        assert result.returncode == 0, result.stderr
        text = Path(out_script).read_text(encoding="utf-8")
        assert "# кандидат" not in text


FIXTURE_MD = """\
# Doc Title

Preamble under H1.

## Section A

Content A

### Section A.1

Deep content

## Section B

Content B
"""


def _write_md_fixture(tmp_dir, name="monster.md", content=FIXTURE_MD):
    path = Path(tmp_dir) / name
    path.write_text(content, encoding="utf-8")
    return str(path)


def test_cut_md_heading_section_not_whole_document():
    with tempfile.TemporaryDirectory() as d:
        path = _write_md_fixture(d)
        block = sm.cut(path, 5)  # `## Section A`
        assert block.start == 5
        assert block.end == 12  # through ### A.1, before ## Section B
        assert block.text.splitlines()[0].strip() == "## Section A"
        assert "### Section A.1" in block.text
        assert "## Section B" not in block.text


def test_cut_md_h3_subsection():
    with tempfile.TemporaryDirectory() as d:
        path = _write_md_fixture(d)
        block = sm.cut(path, 9)  # `### Section A.1`
        assert block.start == 9
        assert block.text.splitlines()[0].strip() == "### Section A.1"
        assert "Deep content" in block.text
        assert any(l.strip() == "## Section A" for l in block.text.splitlines()) is False


def test_generate_md_emits_replace_and_stub_vars():
    with tempfile.TemporaryDirectory() as d:
        src = _write_md_fixture(d)
        out_script = str(Path(d) / "move.py")
        run_cli("--file", src, "--split", "5", str(Path(d) / "part.md"), "--out-script", out_script)
        text = Path(out_script).read_text(encoding="utf-8")
        assert "STUB_01 = " in text
        assert "= replace(" in text
        lines = text.splitlines()
        assert any(l.startswith("monster.replace(") for l in lines)
        assert not any(l.startswith("monster.cut(") for l in lines)
        assert "replace() + STUB_XX + monster.replace()" in text
        assert "полная палитра" in text


def test_monster_replace_leaves_stub_text(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        src = _write_md_fixture(d)
        stub = "> Moved to [A](./part.md)\n"
        r = sm.replace(src, 5, stub)
        monkeypatch.setattr(sys, "argv", ["split_monster", "--apply"])
        sm.monster.write(str(Path(d) / "part.md"), [r], [])
        sm.monster.replace(src, [r])
        remaining = Path(src).read_text(encoding="utf-8")
        assert stub.strip() in remaining
        assert "## Section A" not in remaining
        assert "Deep content" in Path(d, "part.md").read_text(encoding="utf-8")


def test_generate_and_apply_moves_md_sections():
    with tempfile.TemporaryDirectory() as d:
        src = _write_md_fixture(d)
        target_a = str(Path(d) / "part-a.md")
        target_b = str(Path(d) / "part-b.md")
        out_script = str(Path(d) / "move.py")
        result = run_cli(
            "--file", src,
            "--split", "5", target_a,
            "--split", "13", target_b,
            "--out-script", out_script,
        )
        assert result.returncode == 0, result.stderr
        applied = subprocess.run(
            [sys.executable, out_script, "--apply"], capture_output=True, text=True
        )
        assert applied.returncode == 0, applied.stderr
        assert "## Section A" in Path(target_a).read_text(encoding="utf-8")
        assert "## Section B" in Path(target_b).read_text(encoding="utf-8")
        remaining = Path(src).read_text(encoding="utf-8")
        assert "## Section A" not in remaining
        assert "## Section B" not in remaining
        assert "# Doc Title" in remaining


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
