"""TypeScript/JavaScript language handler for get_codeblock."""

import re


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


_BRACELESS_KW = ('if', 'else', 'for', 'while', 'do', 'foreach')


def _is_braceless_control(stripped):
    """A control header whose body is the next statement (no '{' on this line)."""
    if '{' in stripped or stripped.endswith(';') or stripped.endswith(','):
        return False
    for kw in _BRACELESS_KW:
        if stripped == kw or stripped.startswith(kw + ' ') or stripped.startswith(kw + '('):
            return True
    return False


class TypeScriptHandler:

    def __init__(self):
        pass

    def line_level(self, lines, idx):
        """Logical nesting level of ONE line (0-based idx), 1-based.

        level = 1 + enclosing block BODIES. For brace languages a body is the region
        inside a matching {...}; the header (up to and including '{') sits at the
        parent's level, so a leading '}' counts against the parent too. Brace-less
        control bodies (if/for/while/else with no '{') are recovered via indentation.
        Root = 1 (0 is reserved for --level addressing, never a real depth).
        """
        if idx < 0 or idx >= len(lines):
            return 1
        stack = []
        for i in range(idx):
            self._scan_line_for_braces(lines[i], stack, i)
        depth = len(stack)
        content = lines[idx].lstrip()
        if content.startswith('}'):
            depth = max(depth - 1, 0)  # a closing brace belongs to the parent level
        return depth + 1 + self._braceless_bonus(lines, idx)

    def _braceless_bonus(self, lines, idx):
        """Extra levels from brace-less control headers governing this line by indent."""
        bonus = 0
        cur_indent = get_indent(lines[idx])
        j = idx - 1
        while j >= 0:
            s = lines[j].strip()
            if not s or s.startswith('//') or s.startswith('*') or s.startswith('/*'):
                j -= 1
                continue
            ind = get_indent(lines[j])
            if ind < cur_indent and _is_braceless_control(s):
                bonus += 1
                cur_indent = ind
                j -= 1
                continue
            break
        return bonus

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

    # -- declared surface (for card_api) --------------------------------------

    def declarations(self, lines):
        """Top-level declarations (structural TS/JS heuristics) — the declared surface.

        Returns a list of dicts, in file order:
          {name, kind, exported, reexport_from, signature, start, end}
        kind ∈ function|class|interface|enum|type|const|let|var|namespace|reexport.
        `exported` = the line carries `export`. `reexport_from` set for
        `export … from "x"` (barrel). `signature` = the header, multi-line joined and
        cut at `{`/`;`. start/end are 1-indexed. Depth-0 only (nested members excluded).
        """
        out = []
        stack = []
        for i in range(len(lines)):
            depth_before = len(stack)
            s = lines[i].strip()
            if depth_before == 0 and s and not s.startswith(('//', '*', '/*')):
                d = self._parse_decl(lines, i)
                if d:
                    out.append(d)
            self._scan_line_for_braces(lines[i], stack, i)
        return out

    def _parse_decl(self, lines, i):
        s = lines[i].strip()
        # re-export: `export {a, b} from '...'`  |  `export * (as X)? from '...'`
        m = re.match(r'export\s+(?:type\s+)?(\*(?:\s+as\s+[\w$]+)?|\{[^}]*\})\s*from\s*["\']([^"\']+)["\']', s)
        if m:
            return {'name': m.group(1).strip(), 'kind': 'reexport', 'exported': True,
                    'reexport_from': m.group(2), 'signature': s.rstrip(';'),
                    'start': i + 1, 'end': i + 1}
        exported = bool(re.match(r'export\b', s))
        core = re.sub(r'^(?:export\s+|default\s+|declare\s+|abstract\s+|async\s+)+', '', s)
        m = re.match(r'(function|class|interface|enum|namespace|module|type|const|let|var)\b\s*\*?\s*([A-Za-z_$][\w$]*)', core)
        if not m:
            return None
        sig, end = self._decl_signature(lines, i, m.group(1))
        return {'name': m.group(2), 'kind': m.group(1), 'exported': exported,
                'reexport_from': None, 'signature': sig, 'start': i + 1, 'end': end}

    # kinds whose first depth-0 `{` opens a BODY (cut the signature there);
    # the rest (type/const/let/var) keep braces as part of the value/type up to `;`.
    _BLOCK_BODIED = {'function', 'class', 'interface', 'enum', 'namespace', 'module'}

    def _decl_signature(self, lines, i, kind):
        """Signature of a declaration starting at line i, scanning char-by-char across
        lines with bracket-depth + string/comment awareness. Returns (signature, end_line).

        - block-bodied kinds → stop at the first depth-0 `{` (the body opener);
        - value/type kinds    → run to the depth-0 `;` (type/object braces are part of the
          signature and are NOT cut); an arrow body `=> {` still stops the scan.
        """
        block = kind in self._BLOCK_BODIED
        value_binding = kind in ('const', 'let', 'var')
        out, depth, j = [], 0, i
        seen_colon = False   # a depth-0 `:` = a type annotation on a value binding
        stop = False
        while j < len(lines) and j < i + 40 and not stop:
            line = lines[j]
            k, n = 0, len(line)
            while k < n:
                ch = line[k]
                if ch in ('"', "'", '`'):                       # string / template literal
                    q = ch; out.append(ch); k += 1
                    while k < n and line[k] != q:
                        out.append(line[k]); k += 2 if line[k] == '\\' else 1
                    if k < n:
                        out.append(line[k]); k += 1
                    continue
                if ch == '/' and k + 1 < n and line[k + 1] == '/':   # line comment
                    break
                if ch == '/' and k + 1 < n and line[k + 1] == '*':   # block comment
                    k += 2
                    while k < n - 1 and not (line[k] == '*' and line[k + 1] == '/'):
                        k += 1
                    k += 2
                    continue
                if ch in '([':
                    depth += 1
                elif ch in ')]':
                    depth -= 1
                elif ch == '{':
                    if depth == 0:
                        tail = ''.join(out).rstrip()
                        if block or tail.endswith('=>'):        # body opener → stop
                            stop = True
                            break
                    depth += 1                                   # type/object literal brace
                elif ch == '}':
                    depth -= 1
                elif ch == ';' and depth == 0:
                    stop = True
                    break
                elif ch == ':' and depth == 0 and value_binding:
                    seen_colon = True                            # entering the type annotation
                elif ch == '=' and depth == 0 and value_binding and seen_colon:
                    # A typed binding `const x: T = impl` — the declared TYPE is the signature;
                    # drop the `= impl` initializer. Skip `=>`, `==`, `>=`, `<=`, `!=`.
                    nxt = line[k + 1] if k + 1 < n else ''
                    prev = out[-1] if out else ''
                    if nxt not in ('>', '=') and prev not in ('=', '<', '>', '!'):
                        stop = True
                        break
                out.append(ch)
                k += 1
            out.append(' ')
            j += 1
        sig = ' '.join(''.join(out).split()).rstrip(';').strip()
        return sig, j

