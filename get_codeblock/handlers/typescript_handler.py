"""TypeScript/JavaScript language handler for get_codeblock."""


def is_block_header(line):
    """Check if line starts a named block (function/class/interface/etc)."""
    stripped = line.strip()
    if not stripped or stripped.startswith('//'):
        return False

    # Skip single-line comments and block comment markers
    if stripped.startswith('/*') or stripped.startswith('*'):
        return False

    # Check for block-starting keywords before any '{'
    check_part = stripped.split('{')[0].strip().lower()

    keywords = {
        'function', 'class', 'interface', 'enum', 'type',
        'namespace', 'module', 'const', 'let', 'var',
        'if', 'for', 'while', 'do', 'switch', 'try', 'catch', 'finally',
    }

    return any(check_part.startswith(kw) for kw in keywords)


def get_indent(line):
    """Get indentation level (spaces/tabs converted to spaces)."""
    stripped = line.lstrip()
    indent_str = line[:len(line) - len(stripped)]
    return len(indent_str.replace('\t', '    '))


class TypeScriptHandler:

    def __init__(self):
        pass

    def get_blocks(self, file_path, target_line):
        """Get blocks containing target line.

        Returns list sorted outermost-first:
        [{'level': N, 'start': X, 'end': Y}, ...]
        Level = depth from root (1=top-level block).
        start/end = 1-indexed inclusive line numbers.
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        if not lines or target_line < 1 or target_line > len(lines):
            return []

        idx = target_line - 1

        # Find all containing brace-blocks scanning from file start to target line
        containing = self._find_containing_braces(lines, idx)

        if not containing:
            return []

        result = []
        for i, (brace_line, end) in enumerate(containing):
            level = i + 1

            # Look above brace_line for the actual header/start of this block
            header_start = self._find_block_header_start(lines, brace_line)

            result.append({
                'level': level,
                'start': header_start + 1,
                'end': end + 1,
            })

        return result

    def _find_containing_braces(self, lines, target_idx):
        """Find all open '{' blocks that contain the target line index.

        Scans from file start to target, tracking brace depth while ignoring strings/comments.
        Returns list sorted outermost-first: [(brace_line_idx, matching_close_line), ...]
        """
        stack = []  # [brace_line_idx, ...] — each open '{' pushed here

        for i in range(target_idx + 1):
            line = lines[i]
            self._scan_line_for_braces(line, stack, i)

        # Now find matching '}' for each brace in stack (outermost first = bottom of stack)
        containing = []
        for brace_line_idx in stack:
            end_line = self._find_matching_brace(lines, brace_line_idx)
            if end_line != -1:
                containing.append((brace_line_idx, end_line))

        return containing

    def _scan_line_for_braces(self, line, stack, line_idx):
        """Scan a single line for '{' and '}', updating the brace stack.

        Ignores braces inside strings, template literals, and comments.
        For '{': push its line index onto stack.
        For '}': pop one entry from stack (one-to-one matching).
        """
        i = 0
        n = len(line)

        while i < n:
            ch = line[i]

            # Skip strings
            if ch in ('"', "'"):
                quote = ch
                i += 1
                while i < n and line[i] != quote:
                    if line[i] == '\\':
                        i += 2
                    else:
                        i += 1
                i += 1
                continue

            # Skip template literals
            if ch == '`':
                i += 1
                while i < n and line[i] != '`':
                    if line[i] == '\\':
                        i += 2
                    else:
                        i += 1
                i += 1
                continue

            # Skip line comments
            if i + 1 < n and ch == '/' and line[i+1] == '/':
                break  # rest of line is comment

            # Skip block comments
            if i + 1 < n and ch == '/' and line[i+1] == '*':
                i += 2
                while i < n - 1:
                    if line[i] == '*' and line[i+1] == '/':
                        i += 2
                        break
                    i += 1
                else:
                    i = n
                continue

            # Handle braces
            if ch == '{':
                stack.append(line_idx)  # store LINE index

            elif ch == '}':
                # Pop from stack — this close brace closes whatever is on top (one-to-one)
                if stack:
                    stack.pop()

            i += 1

    def _find_matching_brace(self, lines, brace_line_idx):
        """Find the closing '}' for '{' at brace_line_idx.

        Starts scanning from the line AFTER brace_line_idx with depth=1 (the opening brace counted).
        Returns inclusive line index or -1 if not found.
        """
        depth = 1

        for i in range(brace_line_idx + 1, len(lines)):
            line = lines[i]

            j = 0
            n = len(line)

            while j < n:
                ch = line[j]

                # Skip strings
                if ch in ('"', "'"):
                    quote = ch
                    j += 1
                    while j < n and line[j] != quote:
                        if line[j] == '\\':
                            j += 2
                        else:
                            j += 1
                    j += 1
                    continue

                # Skip template literals
                if ch == '`':
                    j += 1
                    while j < n and line[j] != '`':
                        if line[j] == '\\':
                            j += 2
                        else:
                            j += 1
                    j += 1
                    continue

                # Skip line comments
                if j + 1 < n and ch == '/' and line[j+1] == '/':
                    break

                # Skip block comments
                if j + 1 < n and ch == '/' and line[j+1] == '*':
                    j += 2
                    while j < n - 1:
                        if line[j] == '*' and line[j+1] == '/':
                            j += 2
                            break
                        j += 1
                    else:
                        j = n
                    continue

                # Handle braces
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        return i

                j += 1

        return -1

    def _find_block_header_start(self, lines, brace_line_idx):
        """Find the earliest header/start line for a block whose '{' is at brace_line_idx.

        Looks upward from brace_line to find:
        - The keyword/function/class declaration that owns this brace
        - Attached comments above that declaration

        Returns line index (0-based).
        """
        current = brace_line_idx
        brace_indent = get_indent(lines[brace_line_idx])

        # If '{' is on its own line or at end of a declaration line, check that line first
        stripped = lines[current].strip()
        if stripped == '{':
            # Go up to find the actual header (skip blanks)
            current -= 1
            while current >= 0 and not lines[current].strip():
                current -= 1

        if current < 0 or current >= brace_line_idx:
            return brace_line_idx

        # Find where this block's declaration starts (could be multi-line)
        header_start = self._find_declaration_start(lines, current)

        # Include attached comments above the declaration
        preamble_start = self._collect_preamble(lines, header_start)

        return preamble_start

    def _find_declaration_start(self, lines, start_idx):
        """Find the beginning of a declaration that ends at or near start_idx.

        Handles multi-line declarations like:
          public async function foo<T>(
              x: T
          ): Promise<void> {

        Returns earliest line index of this declaration.
        """
        current = start_idx
        brace_indent = get_indent(lines[start_idx])

        while current > 0:
            prev_line = lines[current - 1].strip()
            prev_indent = get_indent(lines[current - 1])

            # Stop at blank lines (separators) or block headers above us
            if not prev_line:
                break

            if is_block_header(prev_line) and prev_indent <= brace_indent:
                break

            # Continuation of same declaration (same or deeper indent, non-header)
            current -= 1

        return current

    def _collect_preamble(self, lines, header_idx):
        """Find earliest comment/docblock attached above the header.

        Returns index of first preamble line, or header_idx if none."""
        if header_idx == 0:
            return header_idx

        start = header_idx
        i = header_idx - 1

        while i >= 0:
            content = lines[i].strip()

            # Blank lines separate — skip them but don't count as preamble boundary
            if not content:
                i -= 1
                continue

            # Block comment ending or single-line comment attached above
            if (content.startswith('//') or
                    content.endswith('*/') or
                    content.startswith('*')):
                start = i
                i -= 1
            else:
                break

        return start

