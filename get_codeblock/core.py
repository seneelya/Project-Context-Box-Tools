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
    level = 0  # default: current block
    query = False  # flag, no value needed
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
        elif token == '--query':
            query = True
            i += 1
        elif token in ('--project-root', '--project_root') and i + 1 < len(tokens):
            value = tokens[i + 1]
            if ' --' in value or '--line' in value or '--file' in value or '--level' in value or '--query' in value:
                print(f"Error: --project-root incorrect: {value}", file=sys.stderr)
                sys.exit(1)
            project_root = value
            i += 2
        elif token == '--help':
            root_info = f'Current PROJECT_ROOT="{default_root}"\n\n' if default_root else ''
            print("get_codeblock.py")
            print("Search or query exact code block from given line at given depth.")
            print("")
            print("Usage:")
            print(f"  get_codeblock.py --file PATH --line N [--level LEVEL] [--query]")
            print("")
            print("Arguments:")
            print("  --file PATH         Path to file (absolute or relative)")
            print("  --line N            Target line number (1-based)")
            print("  --level L           Block address level:")
            print("                       0   = current block containing the line (default)")
            print("                      -N   = N steps up to parent blocks")
            print("                       +N  = N-th level from top of nesting hierarchy")
            print("  --query             Return actual text of block instead of metadata")
            print(f"  --project-root PATH Root for relative paths ({root_info}CLI overrides config)")
            sys.exit(0)
        else:
            # Unknown argument, skip it
            i += 1

    # Normalize paths
    if file_path:
        file_path = normalize_path(file_path)
    if project_root:
        project_root = normalize_path(project_root)

    # No arguments or missing required ones: show usage hint
    if not file_path and line_num is None:
        root_info = f'Current PROJECT_ROOT="{default_root}"\n\n' if default_root else ''
        print("Search or query exact code block from given line at given depth.")
        print(f"Usage: get_codeblock.py --file PATH --line N [--level LEVEL] [--query]")
        print("")
        if default_root:
            print(f"PROJECT_ROOT={default_root}")
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


def resolve(blocks, level):
    """Resolve block by level address.

    blocks: list sorted outermost-first [0=outermost/top-level, N-1=innermost]

    Level addressing (Vision contract):
      0   = current block (innermost, containing the line)
     -N   = N steps up to parent blocks
      +N  = N-th level from top of hierarchy (1=topmost, 2=next inner...)
    """
    if not blocks:
        return None

    n = level

    if n == 0:
        # Current block — innermost one containing the line
        return blocks[-1]

    elif n < 0:
        # Negative: relative to innermost, going up (-1=parent)
        idx = len(blocks) - 1 + n
        return blocks[0] if idx < 0 else blocks[idx]

    else:
        # Positive: from top of hierarchy (1=topmost containing block)
        idx = n - 1
        return blocks[min(idx, len(blocks) - 1)]


def make_comment_prefix(language):
    """Return comment prefix for the given language."""
    return {"python": "#", "typescript": "//", "csharp": "//"}.get(language, "#")


def main():
    args, config = parse_args()

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

    block = resolve(blocks, args['level'])
    if not block:
        print("Error: Level out of range", file=sys.stderr)
        sys.exit(1)

    start = block["start"]
    end = block["end"]  # end is inclusive in new handler

    # Build metadata header line (valid comment for the language)
    prefix = make_comment_prefix(language)
    meta_line = f"{prefix}Block level: {block['level']} range: {start}-{end}"

    if args['query']:
        # Output metadata header as first line, then text byte-for-byte from file
        yellow = "\033[93m"  # ANSI yellow
        reset = "\033[0m"   # Reset color
        if not sys.stdout.isatty():
            print(meta_line)
        else:
            print(f"{yellow}{meta_line}{reset}")
        for i in range(start - 1, min(end, len(lines))):
            sys.stdout.write(lines[i])
    else:
        # Metadata-only output with yellow color on TTY
        yellow = "\033[93m"  # ANSI yellow
        reset = "\033[0m"   # Reset color
        if not sys.stdout.isatty():
            print(meta_line)
        else:
            print(f"{yellow}{meta_line}{reset}")


if __name__ == "__main__":
    main()
