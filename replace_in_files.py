#!/usr/bin/env python3
"""Batch find-and-replace in files matching a mask — the migration/maintenance hand."""

import argparse
import glob
import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# ---------------------------------------------------------------------------
# Safety: dangerous system paths (refuse to touch these)
# ---------------------------------------------------------------------------
_DANGEROUS_PREFIXES = [
    "/etc/", "/proc/", "/sys/", "/dev/", "/var/log", "/boot", "/usr/lib", "/lib/",
]

_DANGEROUS_WINDOWS_PREFIXES = [
    "c:\\windows", "d:\\windows", "c:\\program files",
    "c:\\programdata", "c:\\users\\default",
]

# Masks that are too broad — if used, tool runs dry-run only regardless of --apply.
_DANGEROUS_MASKS = {"*", "*.*"}

# Binary extensions to skip (refuse to modify)
_BINARY_EXTENSIONS = {
    ".exe", ".dll", ".so", ".dylib", ".bin", ".o", ".obj", ".pyc", ".pyd",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".ico", ".webp", ".svg",
    ".mp3", ".wav", ".ogg", ".flac", ".mp4", ".avi", ".mkv",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
    ".pdf", ".docx", ".xlsx", ".pptx", ".odt",
}

# ---------------------------------------------------------------------------
# Minimal safe builtins for --match expressions (no __import__, no open, no exec).
# Only string ops, numeric helpers, and type checks.
# ---------------------------------------------------------------------------
_SAFE_BUILTINS = {
    "len": len, "str": str, "int": int, "float": float, "bool": bool,
    "min": min, "max": max, "abs": abs, "isinstance": isinstance, "type": type,
}

# ---------------------------------------------------------------------------
# Decode a small set of backslash escapes in --find/--with args.
# The --match expression is left raw.
# ---------------------------------------------------------------------------
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", "0": "\0"}


def _decode_escapes(s):
    return re.sub(r"\\(.)", lambda m: _ESCAPES.get(m.group(1), m.group(0)), s)


# ---------------------------------------------------------------------------
# Safety helpers
# ---------------------------------------------------------------------------

def _is_dangerous_path(resolved_path):
    """Check if resolved path falls under known dangerous system directories."""
    path_lower = resolved_path.lower()

    for prefix in _DANGEROUS_PREFIXES:
        if path_lower.startswith(prefix.lower()):
            return True

    for prefix in _DANGEROUS_WINDOWS_PREFIXES:
        if path_lower.startswith(prefix):
            return True

    return False


def _is_in_blacklist_dir(resolved_path, blacklist_dirs):
    """Check if any component of the resolved path matches BLACKLIST_DIRS."""
    parts = Path(resolved_path).parts
    for part in parts:
        if part in blacklist_dirs:
            return True
    return False


def _is_binary_file(filepath):
    """Check if file has a binary extension that should be skipped."""
    ext = os.path.splitext(filepath)[1].lower()
    return ext in _BINARY_EXTENSIONS


def _load_config():
    """Load CONFIG__TOOLS settings from the tools directory, or use defaults."""
    config_path = os.path.join(os.path.dirname(__file__), "CONFIG__TOOLS.py")

    BLACKLIST_DIRS_DEFAULT = [".git", "__pycache__"]

    if os.path.isfile(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_code = compile(f.read(), config_path, "exec")
            safe_ns = {"__builtins__": {}}
            exec(config_code, safe_ns)

            BLACKLIST_DIRS = safe_ns.get("BLACKLIST_DIRS", BLACKLIST_DIRS_DEFAULT)
        except Exception:
            BLACKLIST_DIRS = BLACKLIST_DIRS_DEFAULT
    else:
        BLACKLIST_DIRS = BLACKLIST_DIRS_DEFAULT

    return BLACKLIST_DIRS


def _check_file_safety(filepath, blacklist_dirs):
    """Validate a resolved file path against safety rules. Returns (ok, message)."""
    if os.path.isdir(filepath):
        return False, f"SKIPPED (directory): {filepath}"

    resolved = os.path.realpath(filepath)

    if _is_dangerous_path(resolved):
        return False, f"BLOCKED: refusing to access system path: {filepath}"

    if _is_in_blacklist_dir(resolved, blacklist_dirs):
        return False, f"SKIPPED (blacklisted dir): {filepath}"

    if _is_binary_file(filepath):
        return False, f"SKIPPED (binary file): {filepath}"

    return True, None


# ---------------------------------------------------------------------------
# Core processing — applies ONE replacement rule to one file
# ---------------------------------------------------------------------------

def process_file(filepath, find_text, with_text, match_expr=None, dry_run=False, verbose=False, warned_expressions=None):
    """Apply replacement to one file. Returns (count, hit_linenos)."""
    if warned_expressions is None:
        warned_expressions = set()

    with open(filepath, "r", encoding="utf-8", newline="") as f:
        lines = f.readlines()

    count = 0
    hits = []
    new_lines = []

    for lineno, line in enumerate(lines, 1):
        current_line = line
        should_replace = False

        if match_expr is None:
            # No guard — always apply
            should_replace = True
        else:
            _eval_env = {
                "__builtins__": _SAFE_BUILTINS,
                "line": current_line,
                "re": re,
            }
            try:
                match_result = eval(match_expr, _eval_env)
            except Exception as e:
                if match_expr not in warned_expressions:
                    print(f"Warning: expression error '{match_expr}' ({e}) — skipping this rule.", file=sys.stderr)
                    warned_expressions.add(match_expr)
                continue

            should_replace = bool(match_result) and find_text in current_line

        if should_replace:
            line_hits = current_line.count(find_text)
            new_line = current_line.replace(find_text, with_text)

            count += line_hits
            hits.append((lineno, line, new_line))
            current_line = new_line

        new_lines.append(current_line)

    if not dry_run and count > 0:
        with open(filepath, "w", encoding="utf-8", newline="") as f:
            f.writelines(new_lines)

    return count, hits


# ---------------------------------------------------------------------------
# Help messages (two-level help system)
# ---------------------------------------------------------------------------

def print_short_help(prog):
    """Compact usage scheme printed when run without flags or with invalid flag."""
    YELLOW = "\033[93m"
    RESET = "\033[0m"
    print(f'''{YELLOW}Usage: {prog} (PATH or .) ("*.md": fileMask) --find "F" --with "W" [--match 'line.startswith("# ")'] (--dry-run or --apply){RESET}

Note: Default is DRY-RUN (no writes). Use --apply to make changes. Use --help for full help.''')


def print_full_help(prog):
    """Full help with examples."""
    YELLOW = "\033[93m"
    RESET = "\033[0m"
    print(f'''Batch find-and-replace in files matching a mask — the migration/maintenance hand.

{YELLOW}Usage: {prog} PATH MASK --find "F" --with "W" [--match EXPR] (--dry-run or --apply){RESET}

Arguments (required):
  PATH                  directory to scan; absolute path, relative path from current dir,
                        "." for current dir, or @ as alias for project root (from CONFIG__TOOLS)
  MASK                  file glob pattern (e.g. "*.py", "*.md")
   --find X             text/substring to find in matching files (exactly one per invocation)
   --with Y             replacement text for the preceding --find argument

Options:
  --match EXPR          guarded replace: only on lines where Python expression EXPR is true.
                        Available in EXPR: `line` (current line string), `re` module, basic builtins.
                        Example: --match 'line.startswith("##")' --find "old" --with "new"
  --recurse             recurse into subdirectories
  --dry-run             show preview of changes
  --apply               actually apply and write changes to files on disk (ignored for masks '*', '*.*')
  --verbose             enable detailed output; shows changed lines with their line numbers

Examples:

  Simple replace (dry-run by default):
    {prog} path/to/folder "*.md" --find "old" --with "new"

  Recurse into subdirectories and apply changes:
    {prog} . "*.py" --recurse --find "foo()" --with "bar()" --apply

  Guarded replace — only in lines starting with ##:
    {prog} docs "*.md" --find "Dependencies" --with "DEPS" --match 'line.startswith("##")' --apply

  Replace when line contains X but NOT Y:
    {prog} src "*.ts" --find "foo" --with "baz" --match '"foo" in line and "bar" not in line' --dry-run

Notes:
  - Default behavior is DRY-RUN — nothing is written unless you explicitly use --apply.
  - Only ONE replacement rule per invocation.
  - In --find/--with values, backslash escapes \\n \\t \\r \\\\ are decoded (insert newlines/tabs).
  - The --match expression is left as raw Python.''')



# ---------------------------------------------------------------------------
# Main CLI handler
# ---------------------------------------------------------------------------

def main():
    prog = os.path.basename(sys.argv[0])

    # Two-level help: no args or invalid flag → short help; --help → full help
    if len(sys.argv) == 1:
        print_short_help(prog)
        sys.exit(0)

    if "-h" in sys.argv or "--help" in sys.argv:
        print_full_help(prog)
        sys.exit(0)

    # Parse positional args first
    pos_parser = argparse.ArgumentParser(add_help=False)
    pos_parser.add_argument("path")
    pos_parser.add_argument("mask")

    try:
        known, rest = pos_parser.parse_known_args()
    except SystemExit:
        print(f"Error: Missing required arguments. Need PATH and MASK.", file=sys.stderr)
        print_short_help(prog)
        sys.exit(1)

    # Resolve special @ alias to PROJECT_ROOT from CONFIG__TOOLS
    if known.path == "@":
        import CONFIG__TOOLS as cfg
        folder = cfg.PROJECT_ROOT
    else:
        folder = known.path
    mask = known.mask

    # Parse long-only flags manually to give clear error messages
    find_args = []
    with_args = []
    match_expr = None
    recursive = False
    dry_run_flag = False   # explicitly set --dry-run
    apply_flag = False     # explicitly set --apply
    verbose = False

    i = 0
    while i < len(rest):
        tok = rest[i]

        if tok == "--find":
            if i + 1 >= len(rest):
                print(f"Error: --find requires an argument (text to find).", file=sys.stderr)
                sys.exit(1)
            find_args.append(_decode_escapes(rest[i + 1]))
            i += 2

        elif tok == "--with":
            if i + 1 >= len(rest):
                print(f"Error: --with requires an argument (replacement text).", file=sys.stderr)
                sys.exit(1)
            with_args.append(_decode_escapes(rest[i + 1]))
            i += 2

        elif tok == "--match":
            if i + 1 >= len(rest):
                print(f"Error: --match requires an argument (Python expression).", file=sys.stderr)
                sys.exit(1)
            match_expr = rest[i + 1]
            i += 2

        elif tok == "--recurse":
            recursive = True
            i += 1

        elif tok == "--dry-run":
            dry_run_flag = True
            i += 1

        elif tok == "--apply":
            apply_flag = True
            i += 1

        elif tok == "--verbose":
            verbose = True
            i += 1

        else:
            print(f"Error: Unrecognized argument '{tok}'.", file=sys.stderr)
            print_short_help(prog)
            sys.exit(1)

    # Validate --find / --with (exactly one each, single rule per invocation)
    if len(find_args) == 0:
        print("Error: Missing required flag '--find'. Specify the text to find.", file=sys.stderr)
        print_short_help(prog)
        sys.exit(1)

    if len(with_args) == 0:
        print("Error: Missing required flag '--with'. Specify the replacement text.", file=sys.stderr)
        print_short_help(prog)
        sys.exit(1)

    if len(find_args) > 1:
        print(f"Error: Multiple --find flags given ({len(find_args)}). Only ONE replacement rule per invocation is allowed.", file=sys.stderr)
        sys.exit(1)

    if len(with_args) > 1:
        print(f"Error: Multiple --with flags given ({len(with_args)}). Only ONE replacement rule per invocation is allowed.", file=sys.stderr)
        sys.exit(1)

    find_text = find_args[0]
    with_text = with_args[0]

    # Validate --match expression upfront (catch syntax errors early)
    if match_expr is not None:
        _eval_env = {
            "__builtins__": _SAFE_BUILTINS,
            "line": "",
            "re": re,
        }
        try:
            eval(match_expr, _eval_env)
        except SyntaxError as e:
            print(f"Error: Invalid Python expression in --match '{match_expr}': {e}", file=sys.stderr)
            sys.exit(1)
        # Runtime errors with empty string are OK (depends on actual line content)

    # Determine effective mode: --dry-run takes priority over --apply
    if dry_run_flag or not apply_flag:
        effective_dry_run = True
    else:
        effective_dry_run = False

    # Check for dangerous masks — force read-only regardless of --apply
    mask_is_dangerous = mask in _DANGEROUS_MASKS
    if mask_is_dangerous and apply_flag:
        print(f"Warning: Dangerous mask '{mask}' detected. Forcing dry-run (read-only).", file=sys.stderr)
        effective_dry_run = True

    # Load config for blacklist dirs
    blacklist_dirs = _load_config()

    # Resolve file list
    if recursive:
        files = sorted(str(p) for p in Path(folder).rglob(mask) if p.is_file())
    else:
        pattern = os.path.join(folder, mask)
        files = sorted(glob.glob(pattern))

    if not files:
        print(f"Error: No files matched the given path and mask.", file=sys.stderr)
        sys.exit(1)

    # Safety check all files upfront
    safe_files = []
    for fpath in files:
        ok, msg = _check_file_safety(fpath, blacklist_dirs)
        if not ok:
            print(msg)
        else:
            safe_files.append(fpath)

    if not safe_files:
        print("Error: No safe files to process after applying filters.", file=sys.stderr)
        sys.exit(1)

    # Run replacements
    # No header line; mode shown in the result summary below

    warned_expressions = set()
    total = 0
    changed_files = 0

    for fpath in safe_files:
        n, hits = process_file(
            fpath, find_text, with_text, match_expr,
            dry_run=effective_dry_run, verbose=verbose, warned_expressions=warned_expressions
        )
        total += n

        if n:
            changed_files += 1
            row = f"  {n:>5}  {fpath}"
            print(row)

            # Verbose mode: show the actual lines that were/would be changed
            if verbose and hits:
                for lineno, old_line, new_line in hits[:20]:
                    print(f"      [{lineno}] -{old_line.rstrip()}")
                    print(f"             +{new_line.rstrip()}")

                if len(hits) > 20:
                    print(f"      ... (+{len(hits) - 20} more replacements in this file)")

    verb = "would change" if effective_dry_run else "changed"
    mode_tag = "\033[1;93mDRY-RUN\033[0m (nothing written)" if effective_dry_run else "\033[1;32mAPPLIED\033[0m"
    print(f"{mode_tag} — {verb}: {total} replacement(s) in {changed_files} file(s)")


if __name__ == "__main__":
    main()
