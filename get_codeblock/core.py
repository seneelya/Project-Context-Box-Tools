"""Core CLI logic for get_codeblock."""

import os
import sys
from pathlib import Path


def normalize_path(p):
    """Normalize path separators to forward slashes."""
    if not p:
        return p
    return p.replace('\\', '/')


def is_absolute_path(p):
    """Check if path is absolute (Unix or Windows style)."""
    if Path(p).is_absolute():
        return True
    # Handle Windows drive letters like C:/ or Y:/ on non-Windows systems
    return bool(p and len(p) >= 2 and p[1] == ':')


def load_config():
    """Load tools_config.py if available."""
    try:
        from tools_config import PROJECT_ROOT
        return {'PROJECT_ROOT': PROJECT_ROOT}
    except ImportError:
        return None


def parse_args():
    """Manually parse command line arguments from sys.argv."""
    config = load_config()
    default_root = config['PROJECT_ROOT'] if config else None

    tokens = sys.argv[1:]

    file_path = None
    line_num = None
    level = None
    query = None
    project_root = default_root

    i = 0
    while i < len(tokens):
        token = tokens[i]

        if token == '--file' and i + 1 < len(tokens):
            file_path = tokens[i + 1]
            i += 2
        elif token == '--line' and i + 1 < len(tokens):
            try:
                line_num = int(tokens[i + 1])
            except ValueError:
                print(f"Error: --line requires an integer value", file=sys.stderr)
                sys.exit(1)
            i += 2
        elif token == '--level' and i + 1 < len(tokens):
            try:
                level = int(tokens[i + 1])
            except ValueError:
                print(f"Error: --level requires an integer value", file=sys.stderr)
                sys.exit(1)
            i += 2
        elif token == '--query' and i + 1 < len(tokens):
            try:
                query = int(tokens[i + 1])
            except ValueError:
                print(f"Error: --query requires an integer value", file=sys.stderr)
                sys.exit(1)
            i += 2
        elif token in ('--project-root', '--project_root') and i + 1 < len(tokens):
            value = tokens[i + 1]
            # Check for Windows CMD quoting issue: trailing backslash escapes quote, swallowing next args
            if ' --' in value or '--line' in value or '--file' in value or '--level' in value or '--query' in value:
                print(f"Error: --project-root incorrect: {value}", file=sys.stderr)
                sys.exit(1)
            
            project_root = value
            i += 2
        elif token == '--help':
            root_info = f'Current PROJECT_ROOT="{default_root}"\n\n' if default_root else ''
            print("get_codeblock.py")
            print("Search or query exact code block from given line at given depth.")
            print(f"Usage: get_codeblock.py --file PATH --line N [--level LEVEL] [--query Q]\n{root_info}Full help with --help")
            sys.exit(0)
        else:
            # Unknown argument, skip it
            i += 1

    # Normalize paths (handle both \ and / on Windows/Linux)
    if file_path:
        file_path = normalize_path(file_path)
    if project_root:
        project_root = normalize_path(project_root)

    # No arguments or missing required ones: show usage hint
    if not file_path and not line_num:
        root_info = f'Current PROJECT_ROOT="{default_root}"\n\n' if default_root else ''
        print("get_codeblock.py")
        print("Search or query exact code block from given line at given depth.")
        print(f"Usage: get_codeblock.py --file PATH --line N [--level LEVEL] [--query Q]\n{root_info}Full help with --help")
        sys.exit(0)

    if not file_path or line_num is None:
        print("Error: the following arguments are required: --file, --line", file=sys.stderr)
        sys.exit(1)

    return {
        'file': file_path,
        'line': line_num,
        'level': level,
        'query': query,
        'project_root': project_root
    }, config


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
    print(f"[DEBUG] main() started", file=sys.stderr)
    
    try:
        args, config = parse_args()
        print(f"[DEBUG] parse_args returned: {args}", file=sys.stderr)
    except Exception as e:
        print(f"[DEBUG] parse_args crashed: {type(e).__name__}: {e}", file=sys.stderr)
        raise

    # Resolve file path: relative paths are joined with --root (or config PROJECT_ROOT)
    file_path = args['file']
    if not is_absolute_path(file_path) and args.get('project_root'):
        resolved = str(Path(args['project_root']) / file_path)
        if Path(resolved).exists():
            file_path = resolved
    
    try:
        lines = read_lines(file_path)
    except FileNotFoundError:
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)
    
    line_num = args['line']
    if line_num < 1 or line_num > len(lines):
        print(f"Error: Line {line_num} out of range (1-{len(lines)})", file=sys.stderr)
        sys.exit(1)
    
    ext = Path(file_path).suffix.lower()
    lang_map = {'.py': 'python', '.ts': 'typescript', '.js': 'typescript', '.cs': 'csharp'}
    language = lang_map.get(ext, 'python')
    
    from get_codeblock.handlers import get_handler
    handler = get_handler(language)
    blocks = handler.get_blocks(file_path, line_num)
    
    if not blocks:
        print("Error: No blocks found", file=sys.stderr)
        sys.exit(1)
    
    if args.get('query') is not None:
        block = resolve(blocks, args['query'], is_query=True)
        for i in range(block["start"] - 1, min(block["end"], len(lines))):
            sys.stdout.write(lines[i])
    else:
        level_or_default = args.get('level') if args.get('level') is not None else 0
        block = resolve(blocks, level_or_default)
        start = block["start"]
        end = block["end"] - 1 if block["end"] > 0 else line_num
        print(f"Block level: {block['level']}  from: {start} to: {end}  lines")


if __name__ == "__main__":
    main()
