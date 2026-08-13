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
    "c:\\windows", "d:\\windows", "c:\\program files", "c:\\programdata", "c:\\users\\default",
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
    WHITELIST_DIRS_DEFAULT = ["*"]

    if os.path.isfile(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_code = compile(f.read(), config_path, "exec")
            safe_ns = {"__builtins__": {}}
            exec(config_code, safe_ns)

            BLACKLIST_DIRS = safe_ns.get("BLACKLIST_DIRS", BLACKLIST_DIRS_DEFAULT)
            WHITELIST_DIRS = safe_ns.get("WHITELIST_DIRS", WHITELIST_DIRS_DEFAULT)
        except Exception:
            # If config fails to load, fall back to defaults silently
            BLACKLIST_DIRS = BLACKLIST_DIRS_DEFAULT
            WHITELIST_DIRS = WHITELIST_DIRS_DEFAULT
    else:
        BLACKLIST_DIRS = BLACKLIST_DIRS_DEFAULT
        WHITELIST_DIRS = WHITELIST_DIRS_DEFAULT

    return BLACKLIST_DIRS, WHITELIST_DIRS


def _check_file_safety(filepath, blacklist_dirs):
    """Validate a resolved file path against safety rules. Returns (ok, message)."""
    if os.path.isdir(filepath):
        return False, f"SKIPPED (directory): {filepath}"

    resolved = os.path.realpath(filepath)

    # Check dangerous system paths
    if _is_dangerous_path(resolved):
        return False, f"BLOCKED: refusing to access system path: {filepath}"

    # Check blacklist dirs
    if _is_in_blacklist_dir(resolved, blacklist_dirs):
        return False, f"SKIPPED (blacklisted dir): {filepath}"

    # Check binary files
    if _is_binary_file(filepath):
        return False, f"SKIPPED (binary file): {filepath}"

    return True, None


# ---------------------------------------------------------------------------
# Core processing — applies ONE replacement rule to one file
# ---------------------------------------------------------------------------

def process_file(filepath, repl_rule, warned_expressions, dry_run=False):
    """Apply a single replacement rule to one file. Returns (count, hit_linenos)."""
    with open(filepath, "r", encoding="utf-8", newline="") as f:
        lines = f.readlines()

    count = 0
    hits = []
    new_lines = []

    for lineno, line in enumerate(lines, 1):
        current_line = line
        line_hits = 0

        if repl_rule["type"] == "simple":
            if repl_rule["find"] in current_line:
                line_hits += current_line.count(repl_rule["find"])
                current_line = current_line.replace(repl_rule["find"], repl_rule["with"])

        elif repl_rule["type"] == "match":
            _eval_env = {
                "__builtins__": _SAFE_BUILTINS,
                "line": current_line,
                "re": re,
            }
            try:
                match_result = eval(repl_rule["expr"], _eval_env)
            except Exception as e:
                expr = repl_rule["expr"]
                if expr not in warned_expressions:
                    print(f"Warning: expression error '{expr}' ({e}) — skipping this rule.", file=sys.stderr)
                    warned_expressions.add(expr)
                continue

            if match_result and repl_rule["find"] in current_line:
                line_hits += current_line.count(repl_rule["find"])
                current_line = current_line.replace(repl_rule["find"], repl_rule["with"])

        if line_hits:
            count += line_hits
            hits.append(lineno)

        new_lines.append(current_line)

    if not dry_run and count > 0:
        with open(filepath, "w", encoding="utf-8", newline="") as f:
            f.writelines(new_lines)

    return count, hits


# ---------------------------------------------------------------------------
# Help messages (two-level help system)
# ---------------------------------------------------------------------------

def print_short_help(prog):
    """Ultra-compact usage scheme printed when run without flags or with invalid flag."""
    print(f"""Usage: {prog} (PATH or .) ("*.md": fileMask) --find "F" --with "W" [--match 'line.startswith("# ")'] (--dry-run or --apply)

Note: Default is DRY-RUN (no writes). Use --apply to make changes. Use --help for full help.""")


def print_full_help(prog):
    """Full help with examples."""
    print(f"""Batch find-and-replace in files matching a mask — the migration/maintenance hand.

Usage: {prog} DIR MASK --find F --with W [--match EXPR FIND WITH] [--recurse] [--dry-run | --apply]

Arguments:
  DIR                  (required) directory to scan
  MASK                 (required) file glob pattern (e.g. "*.py", "*.md")

Options:
  --find X             text/substring to find in matching files (exactly one per invocation)
  --with Y             replacement text for the preceding --find argument
  --match EXPR FIND WITH
                       guarded replace: only on lines where Python expression EXPR is true.
                       Available in EXPR: `line` (current line string), `re` module, basic builtins.
                       Example: --match 'line.startswith("##")' "old" "new"
  --recurse            recurse into subdirectories when scanning for files
  --dry-run            show preview of changes without writing to any file (DEFAULT)
  --apply              actually apply and write changes to files on disk.
                       Ignored if mask is '*' or '*.*' (those are dry-run only).
  --verbose            enable detailed output (placeholder; will be implemented later)
  -h, --help           show this full help message and exit

Safety rules:
  - Default behavior is DRY-RUN — nothing is written unless you explicitly use --apply.
  - If both --dry-run and --apply are given, --dry-run wins (safety first).
  - Masks '*' and '*.*' are considered too broad; even with --apply they run dry-run only.
  - Files under .git/, __pycache__/ are always skipped.
  - System paths (/etc/, /proc/, C:\\Windows\\, etc.) are blocked entirely.
  - Binary files (.exe, .dll, images, archives, etc.) are skipped automatically.

Examples:

  Simple replace (dry-run by default — preview first):
    {prog} path/to/folder "*.md" --find "old text" --with "new text"

  Recurse into subdirectories and apply changes:
    {prog} project_root "*.py" --recurse --find "foo()" --with "bar()" --apply

  Guarded replace — only in lines starting with ## (Markdown headings):
    {prog} docs "*.md" --match 'line.startswith("##")' "Dependencies" "DEPS" --apply

  Replace when line contains X but NOT Y:
    {prog} src "*.ts" --match '"foo" in line and "bar" not in line' "foo" "baz" --dry-run

Notes:
  - Only ONE replacement rule per invocation. For multiple replacements, run the tool multiple times
    or use a single --match expression with compound logic.
  - In --find/--with values, backslash escapes \\n \\t \\r \\\\ are decoded (insert newlines/tabs).
    The --match expression is left as raw Python.
  - Use --dry-run first to review what will change, then rerun with --apply when satisfied.""")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    prog = os.path.basename(sys.argv[0]) or "replace_in_files.py"

    # Two-level help routing: short help for no-args, full via --help
    if len(sys.argv) == 1:
        print_short_help(prog)
        sys.exit(0)

    if "-h" in sys.argv[1:] or "--help" in sys.argv[1:]:
        print_full_help(prog)
        sys.exit(0)

    # Custom parser that lets us catch and format errors cleanly (without "usage:" prefix)
    class QuietParser(argparse.ArgumentParser):
        def error(self, message):
            raise SystemExit(message)  # no "Error: " prefix here — we add it below

    pos_parser = QuietParser(add_help=False)
    pos_parser.add_argument("dir")
    pos_parser.add_argument("mask")

    try:
        known_pos, rest_args = pos_parser.parse_known_args(sys.argv[1:])
    except SystemExit as e:
        msg = str(e.args[0]) if e.args else ""
        print(f"Error: {msg}", file=sys.stderr)
        print_short_help(prog)
        sys.exit(2)

    scan_dir = os.path.abspath(known_pos.dir)
    mask = known_pos.mask

    # Load config for safety rules (after positional args are parsed)
    BLACKLIST_DIRS, WHITELIST_DIRS = _load_config()

    # Validate directory exists
    if not os.path.isdir(scan_dir):
        print(f"Error: directory does not exist: {scan_dir}", file=sys.stderr)
        sys.exit(1)

    # Parse remaining flags (long-only; only ONE replacement rule per invocation)
    find_text = None       # single --find value
    with_text = None       # single --with value
    match_expr = None      # optional --match expression
    match_find = None      # if using --match, the FIND part for that rule
    match_with = None      # if using --match, the WITH part for that rule

    recurse = False
    dry_run_flag_given = False
    apply_flag_given = False
    verbose = False

    i = 0
    while i < len(rest_args):
        tok = rest_args[i]

        if tok in ("--find", "-f"):
            if find_text is not None:
                print(f"Error: only one --find allowed per invocation", file=sys.stderr)
                sys.exit(2)
            if i + 1 >= len(rest_args):
                print(f"Error: --find requires an argument", file=sys.stderr)
                sys.exit(2)
            find_text = rest_args[i + 1]
            i += 2

        elif tok in ("--with", "-w"):
            if with_text is not None:
                print(f"Error: only one --with allowed per invocation", file=sys.stderr)
                sys.exit(2)
            if i + 1 >= len(rest_args):
                print(f"Error: --with requires an argument", file=sys.stderr)
                sys.exit(2)
            with_text = rest_args[i + 1]
            i += 2

        elif tok == "--match":
            if match_expr is not None:
                print(f"Error: only one --match allowed per invocation", file=sys.stderr)
                sys.exit(2)
            if i + 3 >= len(rest_args):
                print(f"Error: --match requires EXPR FIND WITH (3 arguments)", file=sys.stderr)
                sys.exit(1)
            match_expr = rest_args[i + 1]
            match_find = rest_args[i + 2]
            match_with = rest_args[i + 3]

            # Validate expression upfront
            eval_env = {"__builtins__": _SAFE_BUILTINS, "line": "", "re": re}
            try:
                eval(match_expr, eval_env)
            except SyntaxError as e:
                print(f"Error: invalid Python expression in --match '{match_expr}': {e}", file=sys.stderr)
                sys.exit(1)

            i += 4

        elif tok in ("--recurse", "-r"):
            recurse = True
            i += 1

        elif tok == "--dry-run":
            dry_run_flag_given = True
            i += 1

        elif tok.lower() == "--apply":
            apply_flag_given = True
            i += 1

        elif tok == "--verbose":
            verbose = True
            i += 1

        else:
            print(f"Error: unknown argument '{tok}'", file=sys.stderr)
            sys.exit(2)

    # Validate that we have exactly one replacement rule to perform
    if match_expr is not None and (find_text is not None or with_text is not None):
        print("Error: cannot mix --match with --find/--with. Use either --match EXPR FIND WITH OR --find F --with W", file=sys.stderr)
        sys.exit(2)

    if match_expr is not None:
        repl_rule = {"type": "match", "expr": match_expr, "find": _decode_escapes(match_find), "with": _decode_escapes(match_with)}
    elif find_text is not None and with_text is not None:
        repl_rule = {"type": "simple", "find": _decode_escapes(find_text), "with": _decode_escapes(with_text)}
    elif find_text is not None:
        print(f"Error: --find '{find_text}' without matching --with", file=sys.stderr)
        sys.exit(2)
    else:
        print("Error: no replacement specified. Use --find 'F' --with 'W' or --match EXPR FIND WITH")
        sys.exit(2)

    # Determine effective mode: default is dry-run; --apply enables writes; --dry-run overrides --apply
    dangerous_mask = mask in _DANGEROUS_MASKS

    if dangerous_mask and apply_flag_given:
        print(f"WARNING: mask '{mask}' is too broad — forcing dry-run (ignoring --apply).", file=sys.stderr)

    # Priority: explicit --dry-run wins over --apply; otherwise default is dry-run unless --apply given
    effective_dry_run = True  # default
    if apply_flag_given and not dangerous_mask and not dry_run_flag_given:
        effective_dry_run = False

    # Resolve file list
    if recurse:
        pattern = os.path.join(scan_dir, "**", mask)
        raw_files = sorted(str(p) for p in Path(scan_dir).rglob(mask) if p.is_file())
    else:
        pattern = os.path.join(scan_dir, mask)
        raw_files = sorted(glob.glob(pattern))

    # Filter files through safety checks
    safe_files = []
    skipped_messages = []
    blocked_count = 0

    for fpath in raw_files:
        ok, msg = _check_file_safety(fpath, BLACKLIST_DIRS)
        if not ok:
            if "BLOCKED" in msg:
                blocked_count += 1
                print(msg, file=sys.stderr)
            else:
                skipped_messages.append(msg)
        else:
            safe_files.append(fpath)

    # Report skips (if verbose or any were skipped)
    if skipped_messages and (verbose or len(skipped_messages) <= 5):
        for msg in skipped_messages[:10]:
            print(msg, file=sys.stderr)
        if len(skipped_messages) > 10:
            print(f"  ... and {len(skipped_messages) - 10} more files skipped.", file=sys.stderr)

    if blocked_count > 0:
        print(f"\nError: {blocked_count} file(s) blocked due to safety rules. Aborting.", file=sys.stderr)
        sys.exit(1)

    if not safe_files and raw_files:
        print(f"All matched files were skipped ({len(raw_files)} total). Nothing to do.", file=sys.stderr)
        sys.exit(0)

    if not safe_files:
        print(f"No files matched pattern: {pattern}", file=sys.stderr)
        sys.exit(1)

    # Run processing — single replacement rule applied across all files
    mode_label = "DRY-RUN — nothing will be written" if effective_dry_run else "Processing (applying changes)"
    print(f"{mode_label}. Scanning {len(safe_files)} file(s):")

    warned_expressions = set()
    total_replacements = 0
    changed_files_count = 0

    for fpath in safe_files:
        n, hits = process_file(fpath, repl_rule, warned_expressions, dry_run=effective_dry_run)
        total_replacements += n

        if n > 0:
            changed_files_count += 1
            row = f"      {n}  {fpath}"
            if effective_dry_run and hits:
                shown_hits = hits[:8]
                tail = f"...(+{len(hits) - len(shown_hits)})" if len(hits) > 8 else ""
                row += f"   [lines: {', '.join(str(h) for h in shown_hits)}{tail}]"
            print(row)

    # Summary line
    if effective_dry_run:
        summary = "would change:" if total_replacements > 0 else "no changes needed"
        print(f"\n{summary} {total_replacements} replacement(s) in {changed_files_count} file(s) — dry-run, nothing written")
    else:
        print(f"\nchanged: {total_replacements} replacement(s) in {changed_files_count} file(s)")


if __name__ == "__main__":
    main()
