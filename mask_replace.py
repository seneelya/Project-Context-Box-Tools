import argparse
import glob
import os
import re
import sys
from pathlib import Path

# Minimal safe builtins for -m expressions (no __import__, no open, no exec).
# Only string ops, numeric helpers, and type checks.
_SAFE_BUILTINS = {
    "len": len,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "min": min,
    "max": max,
    "abs": abs,
    "isinstance": isinstance,
    "type": type,
}

# Decode a small set of backslash escapes in -r/-m find/with args, so the CLI can
# insert newlines/tabs (e.g. -r " — " "\n"). The -m match EXPRESSION is left raw.
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", "0": "\0"}


def _decode_escapes(s):
    return re.sub(r"\\(.)", lambda m: _ESCAPES.get(m.group(1), m.group(0)), s)


def process_file(filepath, replacements, warned_expressions):
    with open(filepath, "r", encoding="utf-8", newline="") as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        current_line = line
        for repl in replacements:
            if repl["type"] == "simple":
                if repl["find"] in current_line:
                    current_line = current_line.replace(repl["find"], repl["with"])
            elif repl["type"] == "matched":
                _eval_env = {
                    "__builtins__": _SAFE_BUILTINS,
                    "line": current_line,
                    "re": re,
                }
                try:
                    match_result = eval(repl["match_expr"], _eval_env)
                except Exception as e:
                    expr = repl["match_expr"]
                    if expr not in warned_expressions:
                        print(f"Warning: expression error '{expr}' ({e}) — skipping this rule.", file=sys.stderr)
                        warned_expressions.add(expr)
                    continue

                if match_result and repl["find"] in current_line:
                    current_line = current_line.replace(repl["find"], repl["with"])

        new_lines.append(current_line)

    with open(filepath, "w", encoding="utf-8", newline="") as f:
        f.writelines(new_lines)


def main():
    parser = argparse.ArgumentParser(
        description="Batch find-and-replace in files matching a mask.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:

  Simple replace across all matches:
    %(prog)s path/to/folder "*.md" -r "old text" "new text"

  Recurse into subfolders (-R):
    %(prog)s path/to/cards "*.md" -R -r "old text" "new text"

  Replace only in lines that match a Python expression:
    %(prog)s path/to/folder "*.md" -m 'line.startswith("## Dependencies")' "Dependencies" "DEPS"

  Replace when line contains X but NOT Y:
    %(prog)s path/to/folder "*.txt" -m '"foo" in line and "bar" not in line' "foo" "baz"

  Transform line for matching (strip spaces), replace in original:
    %(prog)s path/to/folder "*.md" -m 'line.replace(" ", "") == "|Импортирует|"' "Импортирует" "Imports"

Notes:
  - The expression is evaluated as Python with two builtins available: `line` (current string) and `re` module.
  - Multiple -r or -m can be specified; rules are applied in the exact order they appear on the command line.
  - In find/with, backslash escapes \\n \\t \\r \\\\ are decoded (insert newlines/tabs); the -m expression is left raw.
""",
    )

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    # Parse positional args only first, then manually scan argv for -r/-m to preserve CLI order.
    _pos_parser = argparse.ArgumentParser(add_help=False)
    _pos_parser.add_argument("folder")
    _pos_parser.add_argument("mask")
    _known, _rest = _pos_parser.parse_known_args()

    # Rebuild args dict so rest of code can use args.folder / args.mask.
    class Args:
        folder = _known.folder
        mask = _known.mask
        replace = []
        match = []

    args = Args()

    # Build replacement list preserving command-line order
    replacements = []
    recursive = False

    # Scan remaining argv for -r/-m in command-line order
    i = 0
    while i < len(_rest):
        tok = _rest[i]
        if tok in ("-r", "--replace"):
            if i + 2 >= len(_rest):
                parser.error(f"-{tok} requires exactly 2 arguments")
            find_text, with_text = _decode_escapes(_rest[i + 1]), _decode_escapes(_rest[i + 2])
            args.replace.append((find_text, with_text))
            replacements.append({"type": "simple", "find": find_text, "with": with_text})
            i += 3
        elif tok in ("-m", "--match"):
            if i + 3 >= len(_rest):
                parser.error(f"-{tok} requires exactly 3 arguments")
            expr = _rest[i + 1]
            find_text, with_text = _decode_escapes(_rest[i + 2]), _decode_escapes(_rest[i + 3])
            args.match.append((expr, find_text, with_text))

            # Validate expression upfront instead of spamming per-line warnings
            _eval_env = {
                "__builtins__": _SAFE_BUILTINS,
                "line": "",
                "re": re,
            }
            try:
                eval(expr, _eval_env)
            except SyntaxError as e:
                parser.error(f"Invalid Python expression in -m '{expr}': {e}")
            except Exception:
                pass  # Runtime errors with empty string are OK (depends on line content)

            replacements.append({
                "type": "matched",
                "match_expr": expr,
                "find": find_text,
                "with": with_text,
            })
            i += 4
        elif tok in ("-R", "--recursive"):
            recursive = True
            i += 1
        elif tok == "-h" or tok == "--help":
            parser.print_help()
            sys.exit(0)
        else:
            parser.error(f"unrecognized argument: '{tok}'")

    if not args.replace and not args.match:
        parser.error("Specify at least one replacement (-r or -m).")

    # Resolve file list (-R walks subfolders too)
    if recursive:
        pattern = os.path.join(args.folder, "**", args.mask)
        files = sorted(str(p) for p in Path(args.folder).rglob(args.mask) if p.is_file())
    else:
        pattern = os.path.join(args.folder, args.mask)
        files = sorted(glob.glob(pattern))

    if not files:
        print(f"No files matched: {pattern}", file=sys.stderr)
        sys.exit(1)

    print(f"Processing {len(files)} file(s):")
    warned_expressions = set()
    for fpath in files:
        process_file(fpath, replacements, warned_expressions)
        print(f"  {fpath}")


if __name__ == "__main__":
    main()
