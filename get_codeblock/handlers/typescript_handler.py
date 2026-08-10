"""TypeScript/JavaScript language handler for get_codeblock."""

from ..core import read_lines, resolve


class TypeScriptHandler:
    """Handles TypeScript/JS code block detection using brace matching."""

    def __init__(self):
        self.language = "typescript"

    def get_blocks(self, file_path, line_num):
        lines = read_lines(file_path)
        blocks = []
        self._scan_braces(lines, blocks)

        containing = [b for b in blocks if b['start'] <= line_num <= b['end']]
        containing.sort(key=lambda b: b['level'])

        seen_levels = set()
        result = []
        for b in containing:
            if b['level'] not in seen_levels:
                seen_levels.add(b['level'])
                result.append(b)

        if not result or result[0]['level'] != 0:
            result.insert(0, {
                'start': 1,
                'end': len(lines),
                'level': 0,
                'type': 'file'
            })

        return result

    def _scan_braces(self, lines, blocks):
        stack = []

        for i, line in enumerate(lines):
            stripped = line.strip()

            if stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*'):
                continue

            open_count = stripped.count('{')
            close_count = stripped.count('}')

            for j in range(open_count):
                block_type = self._detect_block_type(lines, i)
                stack.append((i + 1, block_type))

            for _ in range(close_count):
                if stack:
                    start_line, block_type = stack.pop()
                    blocks.append({
                        'start': start_line,
                        'end': i + 1,
                        'level': len(stack),
                        'type': block_type
                    })

    def _detect_block_type(self, lines, line_idx):
        line = lines[line_idx].strip()

        if 'function' in line or '=>' in line:
            return 'function'
        if 'class' in line or 'interface' in line or 'enum' in line:
            return 'class'

        if any(kw in line for kw in ['if', 'for', 'while', 'switch', 'try']):
            return 'control_flow'

        return 'block'
