"""Core CLI logic for get_codeblock."""

import os
import sys
from pathlib import Path

# Bump on any change that affects OUTPUT FORMAT (columns, labels, flag semantics) —
# gcb now has real external consumers (Hermes agents), so the CLI contract is no
# longer a private implementation detail. See CONTRACT.md for what's covered.
VERSION = "0.3.1"


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
    """Load CONFIG__TOOLS.py if available."""
    try:
        from CONFIG__TOOLS import PROJECT_ROOT
        return {'PROJECT_ROOT': PROJECT_ROOT}
    except ImportError:
        return None


def parse_args():
    """Manually parse command line arguments from sys.argv."""
    config = load_config()
    default_root = config['PROJECT_ROOT'] if config else None

    tokens = sys.argv[1:]

    file_path = None
    line_list = None       # --line, always a list once given (len 1 == the old scalar)
    level_list_raw = None  # --level, as given (before array-broadcast against --line)
    ancestor_list_raw = None  # --ancestor-level, as given (before broadcast; wins over --level)
    query = False  # flag, no value needed
    outline = False  # flag: print the file's structural outline (no --line needed)
    numbered = False  # flag: prefix --query code lines with absolute line numbers
    dot = False  # flag: reader .0 universal map (IR: landmarks + filler-полосы + frames)
    depth = 0    # for --dot: how many landmark levels to expand
    project_root = default_root

    i = 0
    while i < len(tokens):
        token = tokens[i]

        if token == '--file' and i + 1 < len(tokens):
            file_path = tokens[i + 1]
            i += 2
        elif token == '--line' and i + 1 < len(tokens):
            # Batch coordinates: --line 1827,606,867 resolves all of them in one file
            # parse (grep hands you many at once). A single number is just a 1-element
            # array — no behavior change for the existing single-line callers.
            try:
                line_list = [int(t) for t in tokens[i + 1].split(',')]
            except ValueError:
                print(f"Error: --line requires an integer or comma-separated integers", file=sys.stderr)
                sys.exit(1)
            i += 2
        elif token == '--level' and i + 1 < len(tokens):
            try:
                level_list_raw = [int(t) for t in tokens[i + 1].split(',')]
            except ValueError:
                print(f"Error: --level requires an integer or comma-separated integers", file=sys.stderr)
                sys.exit(1)
            i += 2
        elif token == '--query':
            query = True
            i += 1
        elif token == '--outline':
            outline = True
            i += 1
        elif token == '--dot':
            dot = True
            i += 1
        elif token == '--depth' and i + 1 < len(tokens):
            try:
                depth = int(tokens[i + 1])
            except ValueError:
                print("Error: --depth requires an integer value", file=sys.stderr)
                sys.exit(1)
            i += 2
        elif token == '--numbered':
            numbered = True
            i += 1
        elif token in ('--ancestor-level', '--ancestor_level') and i + 1 < len(tokens):
            # Self-documenting relative address: N ancestors up from the block at
            # --line (0 = that block itself, 1 = parent, ...). Sugar for --level -N;
            # the underlying mechanic (negative level) is unchanged. Array-capable in
            # lockstep with --line (see _broadcast below).
            try:
                ancestor_list_raw = [int(t) for t in tokens[i + 1].split(',')]
            except ValueError:
                print("Error: --ancestor-level requires an integer or comma-separated integers >= 0", file=sys.stderr)
                sys.exit(1)
            if any(a < 0 for a in ancestor_list_raw):
                print("Error: --ancestor-level must be >= 0 (0=self, 1=parent, ...)", file=sys.stderr)
                sys.exit(1)
            i += 2
        elif token in ('--project-root', '--project_root') and i + 1 < len(tokens):
            value = tokens[i + 1]
            if ' --' in value or '--line' in value or '--file' in value or '--level' in value or '--query' in value:
                print(f"Error: --project-root incorrect: {value}", file=sys.stderr)
                sys.exit(1)
            project_root = value
            i += 2
        elif token == '--help':
            print(f"get_codeblock (gcb) v{VERSION}")
            print("Search or query an exact code block from a given line, at a given depth (--level).")
            print("")
            print("Usage:")
            print("  get_codeblock.py --file PATH                          (defaults to --outline)")
            print("  get_codeblock.py --file PATH --outline [--level MAXDEPTH]")
            print("  get_codeblock.py --file PATH --line N[,N,...] [--ancestor-level N | --level N] [--query]")
            print("")
            print("Arguments:")
            print("  --file PATH         Path to file (absolute or relative). Code + Markdown (.md).")
            print("  --outline           Print the structural map (named blocks only). No --line")
            print("                      needed. Default mode when --file is given alone. Bare = an")
            print("                      overview sized to the file; --level N caps depth (high N = all).")
            print("  --dot [--depth N]   Universal .0 map (reader): named landmarks + filler bands +")
            print("                      frames. Works on code AND markdown. --depth N expands N levels.")
            print("  --line N[,N,...]    Target line number(s), 1-based. One file parse resolves them")
            print("                      all. >1 line switches to batch mode: bare = survey (per-hit")
            print("                      ladder, dedup'd); with --outline = one merged tree; with")
            print("                      --query = per-hit body, [i/n], one bad hit won't crash the rest.")
            print("  --ancestor-level N[,N,...]  Which block at --line: N ancestors up. 0 = the innermost")
            print("                      block itself (default), 1 = its parent, 2 = grandparent, ...")
            print("  --level N[,N,...]   Absolute depth address instead: 1 = file top, 2 = one level in.")
            print("                      (With --outline, --level N caps the depth shown — not an address.)")
            print("                      Arrays broadcast against --line: one value replicates to all;")
            print("                      shorter repeats its last value; longer has its excess ignored.")
            print("  --query             Return the block TEXT (framed by anchors) instead of the ladder.")
            print("  --numbered          With --query: prefix each code line with its absolute line")
            print("                      number ('  92 | ...'). Off by default — raw text stays")
            print("                      copy/diff-safe; the range header already gives the numbers.")
            print("  --project-root PATH Root for relative paths (CLI overrides config)")
            print("")
            print("Two ways to pick a block at --line (don't mix):")
            print("  --ancestor-level N  relative — walk N blocks up from where the line lands (0=here).")
            print("  --level N           absolute — jump to depth N counted from the file top.")
            print("  Output 'Block level: K' is the block's real depth (1 = file top, deeper = higher).")
            print("")
            if default_root:
                print(f'Current PROJECT_ROOT="{default_root}"')
            sys.exit(0)
        else:
            # A silently-skipped stray token used to hide a real bug: PowerShell
            # expands an unquoted `a,b, c` (comma THEN space) into separate argv
            # entries (`a`, `b`, `c`) instead of one string — `--line` then only
            # sees its immediate next token as a 1-element array, and the rest
            # landed here and vanished, quietly falling back to single-line mode
            # instead of erroring. Fail loud instead: this token belongs to nothing.
            hint = (" (PowerShell splits an unquoted 'a,b, c' on the space after the "
                    "comma into separate arguments — quote the whole list: "
                    f"--line \"{token}\")") if token[0].isdigit() or token[0] == '-' and token[1:].isdigit() else ""
            print(f"Error: unrecognized argument: '{token}'{hint}", file=sys.stderr)
            sys.exit(1)

    # Normalize paths
    if file_path:
        file_path = normalize_path(file_path)
    if project_root:
        project_root = normalize_path(project_root)

    # --file alone (no --line, no --outline) defaults to --outline: it's the primary
    # discovery mode, and requiring the flag explicitly here would be pure friction.
    # The flag itself still works and stays documented for explicit use.
    if file_path and line_list is None and not outline and not dot:
        outline = True

    # No arguments or missing required ones: show usage hint
    if not file_path and line_list is None:
        print("Search or query an exact code block from a given line, at a given depth (--level).")
        print("Usage:")
        print("  get_codeblock.py --file PATH                          (defaults to --outline)")
        print("  get_codeblock.py --file PATH --outline [--level MAXDEPTH]")
        print("  get_codeblock.py --file PATH --line N[,N,...] [--level LEVEL] [--query]")
        print("Run with --help for full options, including --level addressing.")
        print("")
        if default_root:
            print(f"PROJECT_ROOT={default_root}")
        sys.exit(0)

    # --outline / --dot need only --file; every other mode needs --file and --line
    if not file_path or (line_list is None and not outline and not dot):
        need = "--file" if (outline or dot) else "--file, --line"
        print(f"Error: the following arguments are required: {need}", file=sys.stderr)
        sys.exit(1)

    # Array broadcast (--line 1827,606,867 with --level/--ancestor-level): one number
    # replicates across the whole array; a shorter array replicates its last value for
    # the remainder; a longer array has its excess ignored. --ancestor-level wins over
    # --level when both are given (same precedence as the old scalar code: whichever
    # was parsed decides `level`; here that's whichever list is non-None).
    n_lines = len(line_list) if line_list else 1

    def _broadcast(raw, n):
        if not raw:
            return None
        if len(raw) >= n:
            return raw[:n]
        return raw + [raw[-1]] * (n - len(raw))

    if ancestor_list_raw is not None:
        levels = [-a for a in _broadcast(ancestor_list_raw, n_lines)]
    elif level_list_raw is not None:
        levels = _broadcast(level_list_raw, n_lines)
    else:
        levels = [0] * n_lines

    return {
        'file': file_path,
        'line': line_list[0] if line_list else None,   # back-compat single-value view
        'lines': line_list,                              # full array (len 1 for scalar calls)
        'level': levels[0],                               # back-compat single-value view
        'levels': levels,                                 # full array, broadcast to len(lines)
        'query': query,
        'outline': outline,
        'numbered': numbered,
        'dot': dot,
        'depth': depth,
        'project_root': project_root
    }, config


def read_lines(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return f.readlines()


def _innermost_unambiguous_idx(blocks):
    """Index of the innermost rung whose level is held by exactly one entry.

    Sibling control clauses that share one physical brace line (`} else {`,
    `} catch (e) {`) land at the SAME level — both genuinely touch the hit line,
    and neither is "more inner" than the other. A duplicate level means "this
    line sits exactly on the shared boundary of two siblings": there is no single
    innermost block to name, so climb past the whole tied run to the nearest
    level held by one rung (their common parent)."""
    idx = len(blocks) - 1
    while idx > 0 and sum(1 for b in blocks if b['level'] == blocks[idx]['level']) > 1:
        idx -= 1
    return idx


def resolve(blocks, level):
    """Resolve block by level address.

    blocks: list sorted outermost-first [0=outermost/top-level, N-1=innermost]

    Level addressing (Vision contract):
      0   = current block (innermost UNAMBIGUOUS block containing the line;
            see `_innermost_unambiguous_idx` for the shared-brace-line case)
     -N   = N steps up from there to parent blocks
      +N  = N-th level from top of hierarchy (1=topmost, 2=next inner...)
    """
    if not blocks:
        return None

    n = level
    base = _innermost_unambiguous_idx(blocks)

    if n == 0:
        return blocks[base]

    elif n < 0:
        # Negative: relative to the unambiguous base, going up (-1=parent)
        idx = base + n
        return blocks[0] if idx < 0 else blocks[idx]

    else:
        # Positive: from top of hierarchy (1=topmost containing block)
        idx = n - 1
        return blocks[min(idx, len(blocks) - 1)]


def make_comment_delims(language):
    """(open, close) comment delimiters for the tool's own metadata lines, so those
    lines are valid comments in the target language and don't collide with its syntax.

    Markdown needs a CLOSED HTML comment `<!-- … -->` — a leading `#` would render as
    an H1 heading. The line-comment languages just get a prefix and an empty closer.
    """
    return {"python": ("#", ""), "typescript": ("//", ""), "tsx": ("//", ""),
            "csharp": ("//", ""), "cpp": ("//", ""), "css": ("//", ""),
            "markdown": ("<!-- ", " -->")}.get(language, ("#", ""))


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
    lang_map = {'.py': 'python', '.ts': 'typescript', '.js': 'typescript',
                '.tsx': 'tsx', '.jsx': 'tsx', '.cs': 'csharp',
                '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp', '.c++': 'cpp', '.hpp': 'cpp',
                '.hh': 'cpp', '.hxx': 'cpp', '.h': 'cpp', '.c': 'cpp',
                '.scss': 'css', '.sass': 'css', '.css': 'css',
                '.md': 'markdown', '.markdown': 'markdown'}
    language = lang_map.get(ext, 'python')

    # Get blocks via handler
    from get_codeblock.env_check import ensure_language
    ensure_language(language)  # raises EnvError with install instructions if deps missing
    from get_codeblock.reader.reader import Reader
    handler = Reader.open(file_path, lines, language)
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

    Designed for callers like find_code_usage that need levels for many
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
    lang_map = {'.py': 'python', '.ts': 'typescript', '.js': 'typescript',
                '.tsx': 'tsx', '.jsx': 'tsx', '.cs': 'csharp',
                '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp', '.c++': 'cpp', '.hpp': 'cpp',
                '.hh': 'cpp', '.hxx': 'cpp', '.h': 'cpp', '.c': 'cpp',
                '.scss': 'css', '.sass': 'css', '.css': 'css',
                '.md': 'markdown', '.markdown': 'markdown'}
    language = lang_map.get(ext, 'python')

    # Per-line logical level: level = 1 + enclosing block BODIES (a block header sits
    # at its parent's level). Every handler implements line_level.
    from get_codeblock.env_check import ensure_language
    ensure_language(language)  # raises EnvError with install instructions if deps missing
    from get_codeblock.reader.reader import Reader
    handler = Reader.open(file_path, lines, language)
    return {
        ln: (handler.line_level(lines, ln - 1) if 1 <= ln <= len(lines) else 1)
        for ln in line_nums
    }


def _outline_label_index(handler, lines, deep=False):
    """Full-file outline computed ONCE, indexed by (start, end). Ladder/survey rows
    read their label from here instead of the raw truncated header text — one source
    of truth for block labels, shared with outline batch (CONTRACT.md: 'label lines
    are taken exactly as outline gives them'). Missing entries (no outline support
    for this language) fall back to the raw ladder label at the call site."""
    if not hasattr(handler, 'outline'):
        return {}
    rows = handler.outline(lines, max_level=None, deep=deep) or []
    return {(r['start'], r['end']): r for r in rows}


def _render_boxed_rows(rows, emit, c):
    """CONTRACT.md boxed ladder/tree format — the ONE renderer shared by survey and
    outline batch, so both look identical (columns AND indentation computed once
    across ALL rows passed in, never per-hit/per-group). Each row is one of:
      {'kind': 'hit',   'idx': i, 'line': N, 'text': <source line>,   'indent': K}
      {'kind': 'error', 'idx': i, 'line': N, 'msg': <error text>,     'indent': K}
      {'kind': 'block', 'level': L, 'start': S, 'end': E, 'text': <label>, 'indent': K,
       'frame': bool, 'filler': bool}
    `indent` = nesting depth WITHIN this printout (0 = outermost shown), independent
    of the block's real file-depth — real depth can start anywhere (a hit ten levels
    deep still reads as a 3-row staircase, not ten). Encoded two ways: the marker
    (level number / '.'+level / arrow) is staircased across the mark column — deeper
    rows sit closer to the `|`, like nested braces — AND the label itself gets a
    synthetic `  `-per-level indent, so the block reads almost like the source's own
    nesting. A single arrow glyph marks hit/error rows: unambiguous "here's the grep
    hit", never confusable with a block's real depth number.
    """
    ARROW = '→'  # →

    def _mark(r):
        if r['kind'] in ('hit', 'error'):
            return ARROW
        if not (r.get('frame') or r.get('filler')):
            return str(r['level'])
        return '.' + (str(r['level']) if r['level'] > 1 else '')

    def _cell(r):
        if r['kind'] in ('hit', 'error'):
            return f"{r['idx']}> {r['line']}"
        return f"{r['start']}-{r['end']}"

    if not rows:
        return
    marks = [_mark(r) for r in rows]
    cells = [_cell(r) for r in rows]
    cw = max(len(x) for x in cells)
    max_indent = max(r.get('indent', 0) for r in rows)
    mark_w = max_indent + 2  # staircase field: leading (indent+1) spaces + 1-char marker
    for r, m, cell in zip(rows, marks, cells):
        text = f"ERROR: {r['msg']}" if r['kind'] == 'error' else r['text']
        indent = r.get('indent', 0)
        mark_field = (' ' * (indent + 1) + m).ljust(mark_w)
        emit(c(f"{mark_field}| {cell.rjust(cw)}| {'  ' * indent}{text}"))


def _run_survey_batch(handler, file_path, lines, line_nums, emit, c):
    """Batch survey (CONTRACT.md): every hit shows its OWN exact source line (the
    grep-hit proof, never enriched/reformatted) plus the ladder up to lvl 1, printed
    OUTERMOST FIRST so it reads top-down like the source itself — the hit's own line
    comes LAST, nested one level deeper than the block it landed in. Runs of
    consecutive hits that resolve to the identical ladder share ONE printing of it."""
    n = len(line_nums)
    emit(c(f"File: {file_path} ({len(lines)} lines) · {n} hits"))

    outline_index = _outline_label_index(handler, lines)
    all_rows = []
    group_key, group_rows, group_hits = None, None, []

    def _flush_group():
        if group_hits:
            all_rows.extend(group_rows)
            all_rows.extend(group_hits)

    for i, ln in enumerate(line_nums, start=1):
        if ln < 1 or ln > len(lines):
            _flush_group()
            group_key, group_rows, group_hits = None, None, []
            all_rows.append({'kind': 'error', 'idx': i, 'line': ln, 'indent': 0,
                              'msg': f"Line out of range (1-{len(lines)})"})
            continue

        blocks = handler.get_blocks(file_path, ln)  # outermost -> innermost
        if not blocks:
            _flush_group()
            group_key, group_rows, group_hits = None, None, []
            all_rows.append({'kind': 'error', 'idx': i, 'line': ln, 'indent': 0,
                              'msg': "No blocks found"})
            continue

        rows = []
        for depth, b in enumerate(blocks):
            o = outline_index.get((b['start'], b['end']))
            rows.append({'kind': 'block', 'level': b['level'], 'start': b['start'], 'end': b['end'],
                         'text': o['text'] if o else (b.get('label') or ''), 'indent': depth,
                         'frame': bool(o and o.get('frame')), 'filler': bool(o and o.get('filler'))})
        key = tuple((r['level'], r['start'], r['end']) for r in rows)
        # The innermost rung can already be a single-line pinpoint (e.g. a
        # `~return_statement` filler band whose start==end==the hit line itself) —
        # then it and the hit ARE the same line, not container-and-content, so the
        # hit sits at the SAME indent as that rung, not one deeper than it.
        innermost = rows[-1] if rows else None
        pinpoint = innermost is not None and innermost['start'] == innermost['end'] == ln
        hit_indent = len(rows) - 1 if pinpoint else len(rows)
        hit_row = {'kind': 'hit', 'idx': i, 'line': ln, 'indent': hit_indent,
                   'text': lines[ln - 1].strip()}

        if key == group_key:
            group_hits.append(hit_row)
        else:
            _flush_group()
            group_key, group_rows, group_hits = key, rows, [hit_row]

    _flush_group()
    _render_boxed_rows(all_rows, emit, c)


def _run_outline_batch(handler, file_path, lines, line_nums, levels, deep, emit, c):
    """Batch outline (CONTRACT.md): ONE merged, deduped tree across all hits, each
    escalated to its own broadcast --level/--ancestor-level. Same boxed renderer as
    survey — same columns, same staircase indent, same arrow glyph for error rows."""
    n = len(line_nums)
    errors = []
    merged = {}   # (start, end) -> row (first hit to surface it wins)
    order = []

    for i, (ln, lvl) in enumerate(zip(line_nums, levels), start=1):
        if ln < 1 or ln > len(lines):
            errors.append((i, ln, f"Line out of range (1-{len(lines)})"))
            continue
        rows = handler.outline(lines, max_level=None, deep=deep, focus_line=ln, focus_level=lvl)
        if not rows:
            errors.append((i, ln, "no block found at that line"))
            continue
        for r in rows:
            key = (r['start'], r['end'])
            if key not in merged:
                merged[key] = r
                order.append(key)

    mode_word = '.0' if deep else 'outline'
    emit(c(f"File: {file_path} · {mode_word} batch · {n} hits"
           + (f", {len(errors)} error(s)" if errors else "")))

    error_rows = [{'kind': 'error', 'idx': i, 'line': ln, 'indent': 0, 'msg': err}
                  for i, ln, err in errors]
    block_list = sorted((merged[k] for k in order), key=lambda r: (r['start'], -r['end']))
    base_level = min((r['level'] for r in block_list), default=0)
    block_rows = [{'kind': 'block', 'level': r['level'], 'start': r['start'], 'end': r['end'],
                   'text': r['text'], 'indent': r['level'] - base_level,
                   'frame': r.get('frame'), 'filler': r.get('filler')}
                  for r in block_list]
    _render_boxed_rows(error_rows + block_rows, emit, c)


def _run_query_batch(handler, file_path, lines, line_nums, levels, numbered, emit, c):
    """Batch query (CONTRACT.md): full block body per hit, [i/n] indexed, one bad hit
    does not crash the batch. Returns a nonzero exit code iff any hit errored."""
    n = len(line_nums)
    ok = errors = 0
    emit(c(f"File: {file_path} · query batch · {n} hits"))

    for i, (ln, lvl) in enumerate(zip(line_nums, levels), start=1):
        if ln < 1 or ln > len(lines):
            emit(c(f"[{i}/{n}] ERROR: Line {ln} out of range (1-{len(lines)})"))
            errors += 1
            continue
        blocks = handler.get_blocks(file_path, ln)
        if not blocks:
            emit(c(f"[{i}/{n}] ERROR: No blocks found at line {ln}"))
            errors += 1
            continue
        block = resolve(blocks, lvl)
        if not block:
            emit(c(f"[{i}/{n}] ERROR: Level out of range at line {ln}"))
            errors += 1
            continue

        start, end = block['start'], block['end']
        _lbl = block.get('label')
        emit(c(f"[{i}/{n}] hit {ln}"))
        emit(c(f"Block level: {block['level']} range: {start}-{end}"
               + (f"  {_lbl}" if _lbl else "")))
        last = min(end, len(lines))
        numw = len(str(last)) if numbered else 0
        for j in range(start - 1, last):
            if numw:
                sys.stdout.write(f"{j + 1:>{numw}} | ")
            sys.stdout.write(lines[j])
        if last >= 1 and not lines[last - 1].endswith("\n"):
            sys.stdout.write("\n")
        emit(c(f"Block end: {end}"))
        ok += 1

    emit(c(f"{ok} ok, {errors} error" + ("s" if errors != 1 else "")))
    return 1 if errors else 0


def main():
    # Windows-консоль (cp1251/1252) роняет print на не-ASCII (×, кириллица, emoji).
    # utf-8 + replace: не падаем; на не-utf8 консоли максимум косметический мохито.
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

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
    lang_map = {'.py': 'python', '.ts': 'typescript', '.js': 'typescript',
                '.tsx': 'tsx', '.jsx': 'tsx', '.cs': 'csharp',
                '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp', '.c++': 'cpp', '.hpp': 'cpp',
                '.hh': 'cpp', '.hxx': 'cpp', '.h': 'cpp', '.c': 'cpp',
                '.scss': 'css', '.sass': 'css', '.css': 'css',
                '.md': 'markdown', '.markdown': 'markdown'}
    language = lang_map.get(ext, 'python')

    # Preflight: if this language needs tree-sitter packages that aren't installed,
    # print exactly what to install (from requirements.txt) instead of a traceback.
    from get_codeblock.env_check import ensure_language, EnvError
    try:
        ensure_language(language)
    except EnvError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    # Preflight: is THIS extension registered at all (any profile/backend)? `language`
    # above is core.py's own best-guess mapping (defaults to 'python' for anything it
    # doesn't recognize), so it can't catch this — only `registry.resolve(ext)` knows.
    # Without this check, an unsupported extension (e.g. `.rs`, `.go`, `.yaml`) reached
    # `registry.resolve` deep inside outline/get_blocks and raised a raw `ValueError`
    # traceback instead of a clean message.
    from get_codeblock.reader.registry import resolve as _resolve_format
    try:
        _resolve_format(ext)
    except ValueError:
        print(f"Error: file format '{ext or '(no extension)'}' is not supported yet "
              "(no reader profile registered for it).", file=sys.stderr)
        sys.exit(1)

    # Единая точка входа приложения (Vision03): проверенные режимы делегируются
    # хендлеру внутри Reader (паритет), новый .0 — там же. core.py в get_handler
    # напрямую больше не ходит.
    from get_codeblock.reader.reader import Reader
    handler = Reader.open(file_path, lines, language)
    _copen, _cclose = make_comment_delims(language)
    is_tty = sys.stdout.isatty()

    def c(s):
        """Wrap one metadata line as a comment valid in the target language."""
        return f"{_copen}{s}{_cclose}"

    def emit(s):
        print(f"\033[93m{s}\033[0m" if is_tty else s)

    # One-line reminder of the two addressing scales (real depth vs --level). Console-only
    # (is_tty) — external/programmatic callers get bare block lines, nothing extra to parse.
    # Still wrapped in c() like every other line: a human may paste this straight into a
    # code file along with the block below it, and an uncommented line would break there.
    def emit_legend():
        if is_tty:
            legend_text = ("'Block level: K' = real depth (1=file top, deeper=higher). Pick a block: "
                            "--ancestor-level N = N up from here (0=this block, 1=parent) · "
                            "--level N = absolute depth from top · --query = its text.")
            print(f"\033[92m{c(legend_text)}\033[0m")

    # --outline / --dot: единый адаптивный рендер поверх `.0` IR (Vision03).
    #   --outline — чистая карта: landmark'и вглубь, filler только на уровне файла.
    #   --dot     — тот же рендер, но filler на ВСЕХ раскрытых уровнях (диагностика).
    # Глубина адаптивная (по размеру файла); --level N / --depth N — явный потолок.
    lines_batch = args.get('lines') or []
    levels_batch = args.get('levels') or []
    is_batch = len(lines_batch) > 1

    if args.get('outline') or args.get('dot'):
        deep = bool(args.get('dot'))
        mode_word = '.0' if deep else 'outline'
        if not hasattr(handler, 'outline'):
            print(f"Error: outline not supported for {language} yet", file=sys.stderr)
            sys.exit(1)
        if is_batch:
            _run_outline_batch(handler, file_path, lines, lines_batch, levels_batch,
                                deep, emit, c)
            return
        # Map mode does not take --line. If both are given the user meant to inspect a
        # line — карта ТОЛЬКО блока-цели: K-предок строки (K=--level, по умолч. внутренний).
        # Решает монстро-файлы/классы: развернуть один блок как отдельный файл, рекурсивно.
        focus_line = args.get('line')
        focus_level = args.get('level') or 0
        if focus_line is not None and (focus_line < 1 or focus_line > len(lines)):
            print(f"Error: Line {focus_line} out of range (1-{len(lines)})", file=sys.stderr)
            sys.exit(1)
        rows_all = handler.outline(lines, max_level=None, deep=deep,
                                   focus_line=focus_line, focus_level=focus_level)
        if not rows_all:
            emit(c("(no block found at that line)" if focus_line else "(no structure found)"))
            return

        per_level = {}                      # frames/filler ('.') excluded from the tally
        for r in rows_all:
            if not r.get('frame') and not r.get('filler'):
                per_level[r['level']] = per_level.get(r['level'], 0) + 1
        # Базовый уровень = РЕАЛЬНАЯ глубина корня карты: 1 для файла, глубже — в фокусе
        # (напр. метод на глубине 2). Адаптив/хедер считаем ОТ него, а не от жёсткого 1.
        # per_level пуст, когда фокус-цель сама — filler (инвариант #9: строка без landmark
        # рядом, например топ-левел assign/comment) — единственная строка НЕ landmark, тэлли
        # её не считает. Тогда база — реальный level этой самой строки, а не «1» (иначе
        # `rows` ниже отфильтровывает её же и остаётся пустым — падение на max() пустой
        # последовательности).
        base_level = min(per_level) if per_level else (rows_all[0]['level'] if rows_all else 1)
        depth = max((r['level'] for r in rows_all if not r.get('filler')), default=base_level)
        nb = per_level.get(base_level, 0)          # «вершины» на базовом уровне
        nb1 = per_level.get(base_level + 1, 0)     # следующий уровень
        total_lines = len(lines)

        # Явный потолок: --level N (outline) или --depth N (dot). Иначе адаптив.
        # В фокус-режиме --level = предок цели (не потолок глубины) → адаптив.
        explicit = None if focus_line else (
            (args['level'] if args['level'] and args['level'] > 0 else None)
            or (args['depth'] if deep and args.get('depth', 0) > 0 else None))
        if explicit:
            shown = explicit
        else:
            # Overview depth from the map's own size. Expand ONE level past base only when
            # the map stays a small fraction of the file (<=PCT) AND fits a row budget
            # (<=MAX_ROWS). With very few tops (<=TINY_TOPS) the tops say almost nothing —
            # expand anyway (the members ARE the map). Relative to base_level, not hard 1/2.
            OUTLINE_PCT, OUTLINE_MAX_ROWS, OUTLINE_TINY_TOPS = 0.15, 40, 2
            fits = (nb + nb1) <= OUTLINE_PCT * total_lines and (nb + nb1) <= OUTLINE_MAX_ROWS
            shown = (base_level + 1) if (nb1 > 0 and (fits or nb <= OUTLINE_TINY_TOPS)) else base_level

        rows = [r for r in rows_all if r['level'] <= shown]

        # Help line ALWAYS on top. Actionable hints are HUMAN guidance, not part of
        # the tool's output contract: console-only (is_tty), so programmatic callers
        # get clean block lines. Teach the mode map explicitly: here --level = depth
        # cap; --line/--query are OTHER modes (never combined with --outline).
        if is_tty:
            g, r = "\033[92m", "\033[0m"
            capflag = "--depth N" if deep else "--level N"
            cap = f"{capflag} caps depth (raise N for the full tree)" if shown < depth \
                  else f"{capflag} caps depth"
            kind = ".0 map (all levels: named + filler)" if deep else "outline (map) mode"
            hint2 = ("to read code, drop the map flag: `--line N` = block bounds at a line "
                     "· `--line N --query` = that block's text")
            print(f"{g}{c(f'{kind} · {cap}')}{r}")
            print(f"{g}{c(hint2)}{r}")

        # Header: total depth + per-level tally + what is shown. This is METADATA
        # (the overview signal) — emitted for every caller, including the API.
        tally = " ".join(f"L{lvl}={per_level[lvl]}" for lvl in sorted(per_level))
        focus_tag = f"focus line {focus_line} " if focus_line else ""
        emit(c(f"{mode_word} — {focus_tag}depth {depth}"
               + (f", {tally}" if tally else "")
               + f", showing {base_level}..{min(shown, depth)}"))

        # Pad each "<indent><marker>" so ranges line up. Named block = bare level number;
        # unnamed (frame/filler) = '.'+level ('.3' = «уровень 3, без имени»), чтобы глубина
        # была видна, но было ясно: имени тут нет, в оглавление не тащим. На уровне 1 номер
        # не пишем (он очевиден по нулевому отступу) — голая '.', чтобы оглавление не шумело.
        def _mark(r):
            if not (r.get('frame') or r.get('filler')):
                return str(r['level'])
            return '.' + (str(r['level']) if r['level'] > 1 else '')
        labels = ["  " * (r['level'] - 1) + _mark(r) for r in rows]
        width = max(len(s) for s in labels)
        for r, label in zip(rows, labels):
            emit(c(f"{label.ljust(width)} [{r['start']}-{r['end']}] {r['text']}"))
        return

    if is_batch:
        emit_legend()
        if args['query']:
            exit_code = _run_query_batch(handler, file_path, lines, lines_batch, levels_batch,
                                          args.get('numbered'), emit, c)
            if exit_code:
                sys.exit(exit_code)
            return
        else:
            _run_survey_batch(handler, file_path, lines, lines_batch, emit, c)
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
        emit_legend()
        start, end = block["start"], block["end"]  # inclusive
        # File first: the call that produced this text may not be in view when several
        # --query extractions get concatenated, so each block must self-identify its source.
        emit(c(f"File: {file_path}"))
        _lbl = block.get('label')
        emit(c(f"Block level: {block['level']} range: {start}-{end}"
               + (f"  {_lbl}" if _lbl else "")))
        last = min(end, len(lines))
        # --numbered: prefix ONLY the code lines with right-aligned absolute numbers;
        # the frame tags (File/Block level/Block end) stay clean. Off by default so the
        # raw text is copy/diff-safe.
        numw = len(str(last)) if args.get('numbered') else 0
        for i in range(start - 1, last):
            if numw:
                sys.stdout.write(f"{i + 1:>{numw}} | ")
            sys.stdout.write(lines[i])
        if last >= 1 and not lines[last - 1].endswith("\n"):
            sys.stdout.write("\n")  # ensure the footer starts on its own line at EOF
        emit(c(f"Block end: {end}"))
    else:
        # Metadata = the LADDER: every enclosing block, innermost -> outermost, so one
        # call shows all zoom options (pick a level, then --query it). Рисуем ЛЕСЕНКОЙ:
        # номер уровня отступает вправо с глубиной (внутренний — правее), диапазоны в
        # столбец; сразу видно, куда «нырять».
        emit_legend()
        ladder = list(reversed(blocks))                 # innermost -> outermost
        emit(c(f"You hit in block lvl {ladder[0]['level']}:"))
        marks = [' ' * (b['level'] - 1) + str(b['level']) for b in ladder]
        mw = max(len(m) for m in marks)
        for b, m in zip(ladder, marks):
            lbl = b.get('label') or ''
            emit(c(f"{m.ljust(mw)} [{b['start']}-{b['end']}] {lbl}".rstrip()))


if __name__ == "__main__":
    main()
