"""Core CLI logic for get_codeblock."""

import argparse
import sys
from pathlib import Path


def load_config():
    """Load tools_config.py if available."""
    try:
        from tools_config import PROJECT_ROOT
        return {'PROJECT_ROOT': PROJECT_ROOT}
    except ImportError:
        return None


def parse_args():
    config = load_config()
    default_root = config['PROJECT_ROOT'] if config else None
    
    parser = argparse.ArgumentParser(description="Get code block containing a line.")
    parser.add_argument("--file", required=True)
    parser.add_argument("--line", type=int, required=True)
    parser.add_argument("--level", type=int, default=None)
    parser.add_argument("--query", type=int, default=None)
    parser.add_argument("--project_root", type=str, default=default_root)
    return parser.parse_args(), config


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
            # Level from top (1-indexed), clamp to innermost
            return blocks[min(n - 1, len(blocks) - 1)]
        elif n == 0:
            # Current block (innermost)
            return blocks[-1]
        else:
            # Negative: relative to innermost, going up
            # -1 = parent, -2 = grandparent
            idx = len(blocks) - 1 + n
            return blocks[0] if idx < 0 else blocks[idx]
    else:
        # Level mode (no --query): relative to innermost
        # 0 = current block, positive = going up, negative = same as query
        if n == 0:
            return blocks[-1]
        elif n > 0:
            # Going up from innermost
            idx = len(blocks) - 1 - n
            return blocks[0] if idx < 0 else blocks[idx]
        else:
            # Negative in level mode: same as query (going up)
            idx = len(blocks) - 1 + n
            return blocks[0] if idx < 0 else blocks[idx]


def main():
    args, config = parse_args()

    # Resolve file path: relative paths are joined with --root (or config PROJECT_ROOT)
    file_path = args.file
    if not Path(file_path).is_absolute() and args.project_root:
        resolved = str(Path(args.project_root) / file_path)
        if Path(resolved).exists():
            file_path = resolved
    
    try:
        lines = read_lines(file_path)
    except FileNotFoundError:
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)
    
    if args.line < 1 or args.line > len(lines):
        print(f"Error: Line {args.line} out of range (1-{len(lines)})", file=sys.stderr)
        sys.exit(1)
    
    ext = Path(file_path).suffix.lower()
    lang_map = {'.py': 'python', '.ts': 'typescript', '.js': 'typescript', '.cs': 'csharp'}
    language = lang_map.get(ext, 'python')
    
    from get_codeblock.handlers import get_handler
    handler = get_handler(language)
    blocks = handler.get_blocks(file_path, args.line)
    
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
