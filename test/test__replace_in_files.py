#!/usr/bin/env python3
"""Tests for replace_in_files.py utility. Generates fixtures, runs tool, verifies results."""

import os
import shutil
import subprocess
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # test/ directory
UTILS_DIR = os.path.dirname(SCRIPT_DIR)                  # __HQ/tools/ (one level up from test/)
FIXTURES_DIR = os.path.join(SCRIPT_DIR, "test__replace_in_files", "fixtures")

UTIL_PATH = os.path.join(UTILS_DIR, "replace_in_files.py")


def run_tool(*args, expect_ok=True):
    """Run replace_in_files.py with given args and return (stdout, stderr, code)."""
    cmd = [sys.executable, UTIL_PATH] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if expect_ok and result.returncode != 0:
        print(f"FAIL: {cmd}")
        print(f"stdout:\n{result.stdout}")
        print(f"stderr:\n{result.stderr}")
        raise AssertionError("Tool exited with non-zero code")
    return result.stdout, result.stderr, result.returncode


def setup_fixtures():
    """Create or recreate test fixture files."""
    os.makedirs(FIXTURES_DIR, exist_ok=True)

    # Top-level files
    with open(os.path.join(FIXTURES_DIR, "a.txt"), "w") as f:
        f.write("123\n345\n456\n789\n")

    with open(os.path.join(FIXTURES_DIR, "b.txt"), "w") as f:
        f.write("---\nhello world\n---\n1 123\n2 345\n---\n")

    # Subdirectory file (for --recurse tests)
    subdir = os.path.join(FIXTURES_DIR, "subdir")
    os.makedirs(subdir, exist_ok=True)

    with open(os.path.join(subdir, "c.txt"), "w") as f:
        f.write("deep content here\n123 deep match\nanother line\n")


def teardown_fixtures():
    """Remove test fixture directory."""
    if os.path.exists(FIXTURES_DIR):
        shutil.rmtree(FIXTURES_DIR)


# ============================================================================
# Test cases
# ============================================================================

def test_short_help_shows_on_no_args():
    """Running without args shows compact usage, not full help."""
    out, err, code = run_tool()
    assert "Usage: replace_in_files.py DIR MASK" in out
    assert "--help                 show full help with examples" in out


def test_full_help_shows_on_flag():
    """--help shows detailed documentation with examples."""
    out, err, code = run_tool("--help")
    assert "Batch find-and-replace" in out
    assert "Examples:" in out or "Options:" in out


def test_simple_replace_dry_run_default():
    """Default mode is dry-run — no files modified."""
    setup_fixtures()

    # Read original content
    with open(os.path.join(FIXTURES_DIR, "a.txt")) as f:
        orig = f.read()

    out, err, code = run_tool(
        FIXTURES_DIR, "*.txt", "--find", "123", "--with", "000"
    )

    # Check dry-run output
    assert "DRY-RUN" in out.upper() or "dry-run" in out.lower()
    assert "would change:" in out.lower() or "replacement(s)" in out.lower()

    # Verify file NOT modified
    with open(os.path.join(FIXTURES_DIR, "a.txt")) as f:
        after = f.read()
    assert orig == after, "Dry-run should not modify files"


def test_simple_replace_with_apply():
    """--apply actually modifies files."""
    setup_fixtures()

    run_tool(
        FIXTURES_DIR, "*.txt", "--find", "123", "--with", "000", "--apply"
    )

    # Check a.txt: 123 -> 000
    with open(os.path.join(FIXTURES_DIR, "a.txt")) as f:
        content = f.read()
    assert "000\n" in content
    assert "123\n" not in content

    # Check b.txt: "1 123" -> "1 000"
    with open(os.path.join(FIXTURES_DIR, "b.txt")) as f:
        content = f.read()
    assert "1 000" in content


def test_recurse_flag():
    """--recurse processes files in subdirectories."""
    setup_fixtures()

    run_tool(
        FIXTURES_DIR, "*.txt", "--find", "deep match", "--with", "DEEP_REPLACED",
        "--apply", "--recurse"
    )

    # c.txt in subdir should be modified
    with open(os.path.join(FIXTURES_DIR, "subdir", "c.txt")) as f:
        content = f.read()
    assert "DEEP_REPLACED" in content


def test_no_recurse_skips_subdirs():
    """Without --recurse, subdirectory files are NOT processed."""
    setup_fixtures()

    run_tool(
        FIXTURES_DIR, "*.txt", "--find", "deep match", "--with", "DEEP_REPLACED",
        "--apply"  # no --recurse
    )

    # c.txt should be unchanged
    with open(os.path.join(FIXTURES_DIR, "subdir", "c.txt")) as f:
        content = f.read()
    assert "deep match" in content


def test_match_guard():
    """--match applies replace only on lines where expression is true."""
    setup_fixtures()

    run_tool(
        FIXTURES_DIR, "*.txt",
        "--match", 'line.startswith("---")', "---", "=== ",
        "--apply"
    )

    with open(os.path.join(FIXTURES_DIR, "b.txt")) as f:
        content = f.read()

    # Only lines starting with --- should be changed to === 
    assert "=== \nhello world\n=== \n1 123\n2 345\n=== \n" == content


def test_wildcard_mask_forces_dry_run():
    """Mask '*' or '*.*' forces dry-run even with --apply."""
    setup_fixtures()

    run_tool(
        FIXTURES_DIR, "*", "--find", "123", "--with", "000", "--apply"
    )

    # a.txt should be unchanged (forced dry-run)
    with open(os.path.join(FIXTURES_DIR, "a.txt")) as f:
        content = f.read()
    assert "123\n" in content


def test_dry_run_applies_over_apply():
    """When both --dry-run and --apply are given, dry-run wins."""
    setup_fixtures()

    run_tool(
        FIXTURES_DIR, "*.txt", "--find", "123", "--with", "000",
        "--apply", "--dry-run"  # both flags
    )

    with open(os.path.join(FIXTURES_DIR, "a.txt")) as f:
        content = f.read()
    assert "123\n" in content, "dry-run should win over apply"


def test_multiple_find_with_pairs():
    """Multiple --find/--with pairs applied sequentially."""
    setup_fixtures()

    run_tool(
        FIXTURES_DIR, "*.txt",
        "--find", "hello", "--with", "hi",
        "--find", "world", "--with", "earth",
        "--apply"
    )

    with open(os.path.join(FIXTURES_DIR, "b.txt")) as f:
        content = f.read()
    assert "hi earth" in content


def test_skip_git_dir():
    """Files under .git/ directory should be skipped."""
    setup_fixtures()
    git_dir = os.path.join(FIXTURES_DIR, ".git")
    os.makedirs(git_dir)

    with open(os.path.join(git_dir, "fake.txt"), "w") as f:
        f.write("123 secret\n")

    run_tool(
        FIXTURES_DIR, "*.txt", "--find", "secret", "--with", "PUBLIC",
        "--apply", "--recurse"
    )

    # File in .git should be unchanged
    with open(os.path.join(git_dir, "fake.txt")) as f:
        content = f.read()
    assert "secret" in content


# ============================================================================
# Main runner
# ============================================================================

def main():
    tests = [
        test_short_help_shows_on_no_args,
        test_full_help_shows_on_flag,
        test_simple_replace_dry_run_default,
        test_simple_replace_with_apply,
        test_recurse_flag,
        test_no_recurse_skips_subdirs,
        test_match_guard,
        test_wildcard_mask_forces_dry_run,
        test_dry_run_applies_over_apply,
        test_multiple_find_with_pairs,
        test_skip_git_dir,
    ]

    passed = 0
    failed = []

    for test in tests:
        name = test.__name__
        try:
            setup_fixtures()
            test()
            print(f"PASS: {name}")
            passed += 1
        except Exception as e:
            print(f"FAIL: {name} — {e}")
            failed.append((name, str(e)))
        finally:
            teardown_fixtures()

    print(f"\nResults: {passed}/{len(tests)} tests passed")
    if failed:
        for name, err in failed:
            print(f"  - {name}: {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
