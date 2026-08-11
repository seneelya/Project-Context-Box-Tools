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
    outline = False  # flag: print the file's structural outline (no --line needed)
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
        elif token == '--outline':
            outline = True
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
            print("Search or query exact code block from given line at given depth.")
            print("")
            print("Usage:")
            print(f"  get_codeblock.py --file PATH --line N [--level LEVEL] [--query]")
            print(f"  get_codeblock.py --file PATH --outline [--level MAXDEPTH]")
            print("")
            print("Arguments:")
            print("  --file PATH         Path to file (absolute or relative). Code + Markdown (.md).")
            print("  --line N            Target line number (1-based)")
            print("  --level L           With --line: block address (0=current, -N=parents, +N=from top).")
            print("                      With --outline: cap the depth shown.")
            print("  --query             Return the block text (framed by anchors) instead of the ladder")
            print("  --outline           Print the file's structural TOC (named blocks only); no --line")
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

    # --outline needs only --file; every other mode needs --file and --line
    if not file_path or (line_num is None and not outline):
        need = "--file" if outline else "--file, --line"
        print(f"Error: the following arguments are required: {need}", file=sys.stderr)
        sys.exit(1)

    return {
        'file': file_path,
        'line': line_num,
        'level': level,
        'query': query,
        'outline': outline,
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


def get_codeblock(file_path: str, line_num: int = 1, level: int = 0, query: bool = False) -> dict:
    """Importable function to get code block metadata (and optionally text).

    Args:
        file_path: Path to source file (absolute or relative)
        line_num: Target line number (1-based)
        level: Block address level (0=current, -N=parents, +N=from top)
        query: If True, also return block text

    Returns dict with keys:
        level   : int — real depth level of returned block
        start   : int — start line number (1-based)
        end     : int — end line number (1-based, inclusive)
        text    : str — block content byte-for-byte (only if query=True)

    Raises:
        FileNotFoundError: file doesn't exist
        ValueError: line out of range or no blocks found
    """
    # Read file
    try:
        lines = read_lines(file_path)
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {file_path}")

    if line_num < 1 or line_num > len(lines):
        raise ValueError(f"Line {line_num} out of range (1-{len(lines)})")

    # Detect language by extension
    ext = Path(file_path).suffix.lower()
    lang_map = {'.py': 'python', '.ts': 'typescript', '.js': 'typescript', '.cs': 'csharp',
                '.md': 'markdown', '.markdown': 'markdown'}
    language = lang_map.get(ext, 'python')

    # Get blocks via handler
    from get_codeblock.handlers import get_handler
    handler = get_handler(language)
    blocks = handler.get_blocks(file_path, line_num)

    if not blocks:
        raise ValueError("No blocks found")

    # Resolve block by level address
    block = resolve(blocks, level)
    if not block:
        raise ValueError("Level out of range")

    result = {
        "level": block["level"],
        "start": block["start"],
        "end": block["end"],  # inclusive
    }

    # Optionally return text byte-for-byte from file
    if query:
        start_idx = block["start"] - 1  # to 0-based
        end_idx = min(block["end"], len(lines))
        result["text"] = "".join(lines[start_idx:end_idx])

    return result


def get_line_levels(file_path: str, line_nums: list) -> dict:
    """Efficiently get block levels for multiple lines in ONE file parse.

    Designed for callers like codebase_import_search that need levels for many
    usage lines in the same file — avoids re-parsing file N times.

    Args:
        file_path: Path to source file (absolute or relative)
        line_nums: List of target line numbers (1-based, can be unsorted/duplicates)

    Returns dict mapping each line_num -> level int (1-based; real levels are 1,2,3,...).
    A line inside no block sits at the file root = level 1 (never 0 — 0 is reserved for
    --level addressing, not a real depth):
        {18: 1, 45: 3, ...}

    Raises:
        FileNotFoundError: file doesn't exist
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {file_path}")

    if not line_nums or not lines:
        return {}

    # Detect language by extension
    ext = Path(file_path).suffix.lower()
    lang_map = {'.py': 'python', '.ts': 'typescript', '.js': 'typescript', '.cs': 'csharp',
                '.md': 'markdown', '.markdown': 'markdown'}
    language = lang_map.get(ext, 'python')

    # Per-line logical level: level = 1 + enclosing block BODIES (a block header sits
    # at its parent's level). Every handler implements line_level.
    from get_codeblock.handlers import get_handler
    handler = get_handler(language)
    return {
        ln: (handler.line_level(lines, ln - 1) if 1 <= ln <= len(lines) else 1)
        for ln in line_nums
    }


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

    ext = Path(file_path).suffix.lower()
    lang_map = {'.py': 'python', '.ts': 'typescript', '.js': 'typescript', '.cs': 'csharp',
                '.md': 'markdown', '.markdown': 'markdown'}
    language = lang_map.get(ext, 'python')

    from get_codeblock.handlers import get_handler
    handler = get_handler(language)
    prefix = make_comment_prefix(language)
    is_tty = sys.stdout.isatty()

    def emit(s):
        print(f"\033[93m{s}\033[0m" if is_tty else s)

    # --outline: the file's structural table of contents (named blocks only). --level
    # caps depth. No --line needed. Handlers expose outline() when they support it.
    if args.get('outline'):
        if not hasattr(handler, 'outline'):
            print(f"Error: outline not supported for {language} yet", file=sys.stderr)
            sys.exit(1)
        max_level = args['level'] if args['level'] and args['level'] > 0 else None
        rows = handler.outline(lines, max_level=max_level)
        if not rows:
            emit(f"{prefix}(no structure found)")
            return
        for r in rows:
            emit(f"{prefix}Block level: {r['level']} range: {r['start']}-{r['end']} — {r['text']}")
        return

    line_num = args['line']
    if line_num < 1 or line_num > len(lines):
        print(f"Error: Line {line_num} out of range (1-{len(lines)})", file=sys.stderr)
        sys.exit(1)

    blocks = handler.get_blocks(file_path, line_num)

    if not blocks:
        print("Error: No blocks found", file=sys.stderr)
        sys.exit(1)

    if args['query']:
        # Extract ONE block (chosen by --level; default 0 = innermost), framed by
        # anchor comments so several outputs can be concatenated without merging.
        block = resolve(blocks, args['level'])
        if not block:
            print("Error: Level out of range", file=sys.stderr)
            sys.exit(1)
        start, end = block["start"], block["end"]  # inclusive
        emit(f"{prefix}Block level: {block['level']} range: {start}-{end}")
        last = min(end, len(lines))
        for i in range(start - 1, last):
            sys.stdout.write(lines[i])
        if last >= 1 and not lines[last - 1].endswith("\n"):
            sys.stdout.write("\n")  # ensure the footer starts on its own line at EOF
        emit(f"{prefix}Block end: {end}")
    else:
        # Metadata = the LADDER: every enclosing block, innermost -> outermost, so one
        # call shows all zoom options (pick a level, then --query it).
        for blk in reversed(blocks):
            emit(f"{prefix}Block level: {blk['level']} range: {blk['start']}-{blk['end']}")


if __name__ == "__main__":
    main()
