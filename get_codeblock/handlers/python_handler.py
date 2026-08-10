"""Python language handler for get_codeblock."""

import ast
from ..core import read_lines


class PythonHandler:
    """Handles Python code block detection using AST parsing."""

    def __init__(self):
        self.language = "python"

    def get_blocks(self, file_path, line_num):
        """Get all code blocks containing the specified line.

        Returns:
            List of block dicts sorted outermost-first.
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        tree = ast.parse(source)
        lines = source.splitlines(keepends=True)

        blocks = []
        self._collect(tree, blocks, 0)

        containing = [b for b in blocks if b['start'] <= line_num <= b['end']]
        containing.sort(key=lambda b: b['level'])

        # Deduplicate per level
        seen = set()
        result = []
        for b in containing:
            if b['level'] not in seen:
                seen.add(b['level'])
                result.append(b)

        if not result or result[0]['level'] != 0:
            result.insert(0, {'start': 1, 'end': len(lines), 'level': 0, 'type': 'file'})

        return result

    def _collect(self, node, blocks, level):
        """Recursively collect all code blocks from AST."""
        btype = None
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            btype = 'function'
        elif isinstance(node, ast.ClassDef):
            btype = 'class'
        elif isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While,
                                ast.Try, ast.With, ast.AsyncWith)):
            btype = 'control_flow'

        if btype:
            blocks.append({
                'start': node.lineno,
                'end': self._last_line(node),
                'level': level,
                'type': btype
            })

        # Children of a block are at level+1, otherwise same level
        child_level = level + 1 if btype else level
        for child in ast.iter_child_nodes(node):
            self._collect(child, blocks, child_level)

    def _last_line(self, node):
        max_line = node.lineno
        for child in ast.walk(node):
            if hasattr(child, 'lineno'):
                max_line = max(max_line, child.lineno)
        return max_line
