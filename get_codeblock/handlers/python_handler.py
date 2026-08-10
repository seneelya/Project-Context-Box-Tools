"""Python language handler for get_codeblock."""

import ast
import sys
from ..core import read_file_lines, resolve_block_query


class PythonHandler:
    """Handles Python code block detection using AST parsing."""

    def __init__(self):
        self.language = "python"

    def _parse_ast(self, file_path):
        """Parse Python file and return AST."""
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        return ast.parse(source)

    def get_code_blocks(self, file_path, line_num):
        """Get all code blocks containing the specified line.

        Args:
            file_path: Path to the Python file
            line_num: 1-indexed line number

        Returns:
            List of block dicts sorted outermost-first, each with keys:
            start, end, level, type
        """
        lines = read_file_lines(file_path)
        tree = self._parse_ast(file_path)

        # Collect all block nodes (functions, classes, if/for/while/etc.)
        blocks = []
        self._collect_blocks(tree, blocks, indent_level=0)

        # Filter blocks that contain line_num
        containing = []
        for block in blocks:
            if block['start'] <= line_num <= block['end']:
                containing.append(block)

        # Sort by level (outermost first)
        containing.sort(key=lambda b: b['level'])

        # Deduplicate: keep only one block per level
        seen_levels = set()
        result = []
        for b in containing:
            if b['level'] not in seen_levels:
                seen_levels.add(b['level'])
                result.append(b)

        # Always include file-level block (outermost)
        if not result or result[0]['level'] != 0:
            result.insert(0, {
                'start': 1,
                'end': len(lines),
                'level': 0,
                'type': 'file'
            })

        return result

    def _collect_blocks(self, node, blocks, indent_level=0):
        """Recursively collect all blocks from AST."""
        # Check if this node is a block type
        block_type = None
        if isinstance(node, ast.FunctionDef):
            block_type = 'function'
        elif isinstance(node, ast.ClassDef):
            block_type = 'class'
        elif isinstance(node, (ast.If, ast.For, ast.While, ast.Try, ast.With)):
            block_type = 'control_flow'

        if block_type:
            blocks.append({
                'start': node.lineno,
                'end': self._get_end_line(node),
                'level': indent_level,
                'type': block_type
            })

        # Recurse into child nodes
        for child in ast.iter_child_nodes(node):
            self._collect_blocks(child, blocks, indent_level + 1)

    def _get_end_line(self, node):
        """Get the last line number of a node."""
        max_line = node.lineno
        for child in ast.walk(node):
            if hasattr(child, 'lineno'):
                max_line = max(max_line, child.lineno)
        return max_line

    def handle_query(self, args):
        """Handle a query command."""
        lines = read_file_lines(args.file)
        blocks = self.get_code_blocks(args.file, args.line)

        if not blocks:
            print("Error: No blocks found", file=sys.stderr)
            return None

        # Resolve query
        block = resolve_block_query(blocks, args.query, is_query=True)
        if block is None:
            print("Error: No block found", file=sys.stderr)
            return None

        # Output block text (byte-for-byte from file)
        output = ""
        for i in range(block["start"] - 1, min(block["end"], len(lines))):
            output += lines[i]

        return output

    def handle_level(self, args):
        """Handle a level command."""
        lines = read_file_lines(args.file)
        blocks = self.get_code_blocks(args.file, args.line)

        if not blocks:
            print("Error: No blocks found", file=sys.stderr)
            return None

        # Default: show current block level and bounds (innermost block)
        if args.level is None:
            block = blocks[-1]  # innermost block
            level = block["level"]
            start = block["start"]
            end = block["end"] - 1 if block["end"] > 0 else args.line
            print(f"{level} {start} {end}")
            return

        # Resolve level query
        block = resolve_block_query(blocks, args.level)
        if block is None:
            print("Error: No block found", file=sys.stderr)
            return None

        # Format output: level from_line to_line
        level = block["level"]
        start = block["start"]
        end = block["end"] - 1 if block["end"] > 0 else args.line

        return f"{level} {start} {end}"

    def run(self):
        """Run the Python handler with parsed CLI arguments."""
        from ..core import parse_args
        args = parse_args()

        if args.query is not None:
            return self.handle_query(args)
        else:
            return self.handle_level(args)


if __name__ == "__main__":
    handler = PythonHandler()
    output = handler.run()
    if output is not None:
        print(output)
