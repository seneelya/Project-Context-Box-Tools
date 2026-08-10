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
        return containing

    def _scan_braces(self, lines, blocks):
        stack = []  # [(start_line, block_type), ...]

        for i, line in enumerate(lines):
            stripped = line.strip()

            if stripped.startswith('//'):
                continue
            if stripped.startswith('/*') or stripped.startswith('*'):
                # Skip multi-line comments
                while i < len(lines) and '*/' not in lines[i]:
                    i += 1
                continue

            # Track braces character by character
            in_string = False
            string_char = None
            in_comment = False

            for ch_idx in range(len(stripped)):
                ch = stripped[ch_idx]

                # Skip escaped chars
                if in_string and ch == '\\':
                    continue

                # Handle strings
                if not in_comment and (ch == '"' or ch == "'") and ch != string_char:
                    if not in_string:
                        in_string = True
                        string_char = ch
                    elif ch == string_char:
                        in_string = False
                        string_char = None
                    continue

                if in_string:
                    continue

                # Handle line comments
                if ch == '/' and ch_idx + 1 < len(stripped) and stripped[ch_idx + 1] == '/':
                    break

                # Handle block comment start
                if ch == '/' and ch_idx + 1 < len(stripped) and stripped[ch_idx + 1] == '*':
                    in_comment = True
                    continue

                if in_comment:
                    if ch == '*' and ch_idx + 1 < len(stripped) and stripped[ch_idx + 1] == '/':
                        in_comment = False
                    continue

                if ch == '{':
                    # Skip if this is an import/export statement
                    line = lines[i].strip()
                    if 'import' in line or 'export' in line:
                        continue

                    block_level = len(stack)
                    block_type = self._detect_block_type(lines, i)
                    stack.append((i + 1, block_type, block_level))

                elif ch == '}':
                    if stack:
                        start_line, block_type, block_level = stack.pop()
                        blocks.append({
                            'start': start_line,
                            'end': i + 1,
                            'level': block_level,
                            'type': block_type
                        })

    def _detect_block_type(self, lines, line_idx):
        line = lines[line_idx].strip().lower()

        if 'function' in line or '=>' in line:
            return 'function'
        if 'class' in line or 'interface' in line or 'enum' in line:
            return 'class'

        if any(kw in line for kw in ['if ', 'if(', 'for ', 'for(', 'while ', 'while(',
                                       'switch ', 'switch(', 'try ', 'try{']):
            return 'control_flow'

        return 'block'
