"""C# language handler for get_codeblock."""

from ..core import read_lines, resolve


class CSharpHandler:
    """Handles C# code block detection using brace matching + #region."""

    def __init__(self):
        self.block_keywords = [
            'class', 'struct', 'interface', 'enum', 'namespace',
            'public', 'private', 'protected', 'internal',
            'void', 'static', 'async', 'sealed', 'abstract',
            'partial', 'readonly', 'const', 'event', 'delegate',
        ]

    def get_blocks(self, file_path, line_num):
        lines = read_lines(file_path)
        blocks = []
        self._scan_blocks(lines, blocks)

        containing = [b for b in blocks if b['start'] <= line_num <= b['end']]
        containing.sort(key=lambda b: b['level'])
        return containing

    def _scan_blocks(self, lines, blocks):
        """Scan for code blocks using brace matching and #region."""
        stack = []

        for i, line in enumerate(lines):
            stripped = line.strip()

            if stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*'):
                continue

            # Handle #region blocks
            if stripped.startswith('#region'):
                region_name = stripped[8:].strip() if stripped.startswith('#region ') else stripped[7:].strip()
                stack.append((i + 1, 'region', region_name))
            elif stripped == '#endregion':
                if stack and stack[-1][1] == 'region':
                    start_line, _, name = stack.pop()
                    blocks.append({
                        'start': start_line,
                        'end': i + 1,
                        'level': len(stack),
                        'type': 'region',
                        'name': name
                    })

            # Handle { } blocks
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

    def _detect_block_type(self, lines, idx):
        """Detect block type from line content."""
        line = lines[idx].strip()

        if line.startswith('//') or line.startswith('/*'):
            return 'comment'

        for kw in self.block_keywords:
            if line.startswith(kw + ' ') or line.startswith(kw + '('):
                return kw

        return 'block'

    def extract(self, file_path, start_line, end_line):
        """Extract text from file."""
        lines = read_lines(file_path)
        return '\n'.join(lines[start_line - 1:end_line])
