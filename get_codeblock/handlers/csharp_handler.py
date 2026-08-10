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
        stack = []  # [(start_line, block_type)]
        in_multiline_comment = False

        for i, line in enumerate(lines):
            stripped = line.strip()

            if stripped.startswith('//'):
                continue

            # Handle multi-line comments
            if in_multiline_comment:
                if '*/' in stripped:
                    in_multiline_comment = False
                continue
            if stripped.startswith('/*'):
                if '*/' not in stripped:
                    in_multiline_comment = True
                continue

            # Handle #region blocks
            if stripped.startswith('#region'):
                region_name = stripped[8:].strip() if stripped.startswith('#region ') else stripped[7:].strip()
                stack.append((i + 1, 'region', region_name))
            elif stripped == '#endregion':
                if stack and len(stack[-1]) > 2 and stack[-1][1] == 'region':
                    start_line, _, name = stack.pop()
                    blocks.append({
                        'start': start_line,
                        'end': i + 1,
                        'level': len(stack),
                        'type': 'region',
                        'name': name
                    })

            # Handle { } blocks character by character
            in_string = False
            string_char = None

            for ch_idx in range(len(stripped)):
                ch = stripped[ch_idx]

                # Skip escaped chars
                if in_string and ch == '\\\\':
                    continue

                # Handle strings
                if (ch == '"' or ch == "'") and not in_string:
                    in_string = True
                    string_char = ch
                    continue
                if in_string and ch == string_char:
                    in_string = False
                    string_char = None
                    continue

                if in_string:
                    continue

                # Skip line comments after strings
                if ch == '/' and ch_idx + 1 < len(stripped) and stripped[ch_idx + 1] == '/':
                    break

                if ch == '{':
                    block_type = self._detect_block_type(lines, i)
                    stack.append((i + 1, block_type))

                elif ch == '}':
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
