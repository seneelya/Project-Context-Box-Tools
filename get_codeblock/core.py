"""Core CLI logic for get_codeblock."""

import argparse
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Get code block containing a line.")
    parser.add_argument("--file", required=True)
    parser.add_argument("--line", type=int, required=True)
    parser.add_argument("--level", type=int, default=None)
    parser.add_argument("--query", type=int, default=None)
    return parser.parse_args()


def read_lines(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return f.readlines()


def resolve(blocks, n, is_query=False):
    """Resolve block query.
    
    blocks: list sorted outermost-first [0=outermost, N=innermost]
    """
    if not blocks:
        return None
    
    if is_query:
        if n > 0:
            return blocks[min(n - 1, len(blocks) - 1)]
        elif n == 0:
            return blocks[-1]
        else:
            # Negative: relative to innermost, going up
            # -1 = parent, -2 = grandparent, etc.
            idx = len(blocks) - 1 + n
            return blocks[0] if idx < 0 else blocks[idx]
    else:
        if n == 0:
            return blocks[-1]
        elif n > 0:
            idx = len(blocks) - 1 - n
            return blocks[0] if idx < 0 else blocks[idx]
        else:
            idx = len(blocks) + n
            return blocks[-1] if idx < 0 else blocks[idx]


def main():
    args = parse_args()
    
    try:
        lines = read_lines(args.file)
    except FileNotFoundError:
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)
    
    if args.line < 1 or args.line > len(lines):
        print(f"Error: Line {args.line} out of range (1-{len(lines)})", file=sys.stderr)
        sys.exit(1)
    
    ext = Path(args.file).suffix.lower()
    lang_map = {'.py': 'python', '.ts': 'typescript', '.js': 'typescript', '.cs': 'csharp'}
    language = lang_map.get(ext, 'python')
    
    from get_codeblock.handlers import get_handler
    handler = get_handler(language)
    blocks = handler.get_blocks(args.file, args.line)
    
    if not blocks:
        print("Error: No blocks found", file=sys.stderr)
        sys.exit(1)
    
    if args.query is not None:
        block = resolve(blocks, args.query, is_query=True)
        for i in range(block["start"] - 1, min(block["end"], len(lines))):
            sys.stdout.write(lines[i])
    else:
        block = resolve(blocks, args.level if args.level is not None else 0)
        start = block["start"]
        end = block["end"] - 1 if block["end"] > 0 else args.line
        print(f"{block['level']} {start} {end}")


if __name__ == "__main__":
    main()
