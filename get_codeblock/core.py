"""Core CLI logic for get_codeblock."""

import argparse
import sys
from pathlib import Path


def parse_args(args=None):
    parser = argparse.ArgumentParser(
        description="Get code block containing a line in a file."
    )
    parser.add_argument("--file", required=True, help="Path to the source file")
    parser.add_argument("--line", type=int, required=True, help="Line number (1-indexed)")
    parser.add_argument(
        "--level", type=int, default=None,
        help="Block level (0=current, 1=parent, -1=grandparent, etc.)"
    )
    parser.add_argument(
        "--query", type=int, default=None,
        help="Query block at level N from top (1=outermost) or relative (-N=ancestor)"
    )
    return parser.parse_args(args)


def read_file_lines(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return f.readlines()


def calculate_indent(line):
    """Calculate indentation of a line (number of leading spaces/tabs)."""
    stripped = line.lstrip(" \t")
    return len(line) - len(stripped)


def get_code_blocks_for_line(lines, line_num):
    """Get all blocks containing line_num, with their levels.
    
    Returns list of dicts: [{start, end, level, indent}, ...]
    where level=0 is outermost block, level=N is innermost.
    """
    n = len(lines)
    target_indent = calculate_indent(lines[line_num - 1])
    
    # Find all boundaries going up (lines with indent < target_indent)
    boundaries = []
    for i in range(line_num - 2, -1, -1):
        indent = calculate_indent(lines[i])
        if indent < target_indent:
            boundaries.append((i + 1, indent))
    
    # Add the line itself as the innermost block
    boundaries.append((line_num, target_indent))
    
    # Sort by start line (outermost first)
    boundaries.sort(key=lambda x: x[0])
    
    # For each boundary, find end (first line with indent <= boundary indent)
    blocks = []
    for idx, (start, indent) in enumerate(boundaries):
        end = n
        for i in range(start, n):
            if calculate_indent(lines[i]) <= indent:
                end = i
                break
        
        blocks.append({
            "start": start,
            "end": end,
            "level": idx,
            "indent": indent
        })
    
    return blocks


def resolve_block_query(blocks, level_or_query, is_query=False):
    """Resolve a block query against the list of blocks.
    
    Args:
        blocks: List of block dicts sorted by level (0=outermost).
        level_or_query: int. If positive and is_query=True, level from top. 
                       If negative, relative to current.
        is_query: True if this is --query mode, False for --level mode.
    
    Returns:
        Block dict or None.
    """
    if not blocks:
        return None

    if is_query:
        if level_or_query > 0:
            # Level from top (1-indexed), but not deeper than real level
            idx = min(level_or_query - 1, len(blocks) - 1)
            return blocks[idx]
        elif level_or_query == 0:
            # Current block (innermost)
            return blocks[-1] if blocks else None
        else:
            # Negative: relative to current (innermost)
            # -1 = parent (one level up from innermost)
            idx = len(blocks) - 1 + level_or_query
            if idx < 0:
                return blocks[0]  # Outermost if too far
            return blocks[idx]
    else:
        # Level mode (no --query):
        # 0 = real level (innermost), positive = parents going up, negative = deeper
        if level_or_query == 0:
            return blocks[-1]  # innermost = real level
        elif level_or_query > 0:
            # Going up from innermost: -1 = parent, -2 = grandparent
            idx = len(blocks) - 1 - level_or_query
            if idx < 0:
                return blocks[0]  # Outermost if too far up
            return blocks[idx]
        else:
            # Negative in level mode: going deeper (but not below innermost)
            idx = len(blocks) + level_or_query
            if idx < 0:
                return blocks[-1]  # Innermost if too far down
            return blocks[idx]


def format_output(block):
    """Format block output as 'level from_line to_line'."""
    if block is None:
        return "0 0 0"
    level = block["level"]
    start = block["start"]
    end = block["end"] - 1 if block["end"] < len(sys.stdin.readlines()) else block["end"]
    return f"{level} {start} {end}"


def main(args=None):
    parsed = parse_args(args)
    
    if not parsed.file:
        print("Error: --file is required", file=sys.stderr)
        sys.exit(1)
    
    if not parsed.line:
        print("Error: --line is required", file=sys.stderr)
        sys.exit(1)
    
    # Read file
    try:
        lines = read_file_lines(parsed.file)
    except FileNotFoundError:
        print(f"Error: File not found: {parsed.file}", file=sys.stderr)
        sys.exit(1)
    
    # Validate line number
    if parsed.line < 1 or parsed.line > len(lines):
        print(f"Error: Line {parsed.line} out of range (1-{len(lines)})", file=sys.stderr)
        sys.exit(1)
    
    # Get all blocks containing the line
    blocks = get_code_blocks_for_line(lines, parsed.line)
    
    # Query mode: output block text
    if parsed.query is not None:
        block = resolve_block_query(blocks, parsed.query)
        if block is None:
            print("Error: No block found", file=sys.stderr)
            sys.exit(1)
        
        # Output block text (byte-for-byte from file)
        for i in range(block["start"] - 1, min(block["end"], len(lines))):
            sys.stdout.write(lines[i])
        return
    
    # Level mode: output 'level from_line to_line'
    if parsed.level is None:
        # Default: show current block level and bounds
        block = blocks[-1] if blocks else None
        level = block["level"] if block else 0
        start = block["start"] if block else parsed.line
        end = block["end"] - 1 if block and block["end"] > 0 else parsed.line
        print(f"{level} {start} {end}")
        return
    
    # Resolve level query
    block = resolve_block_query(blocks, parsed.level)
    if block is None:
        print("Error: No block found", file=sys.stderr)
        sys.exit(1)
    
    # Format output: level from_line to_line
    level = block["level"]
    start = block["start"]
    end = block["end"] - 1 if block["end"] > 0 else parsed.line
    print(f"{level} {start} {end}")


if __name__ == "__main__":
    main()
