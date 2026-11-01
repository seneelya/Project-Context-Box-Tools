"""Byte-preserving GLSL extension masks; source returned to callers stays original."""
import re


_PROTECTED = re.compile(
    rb'//(?:\\\r?\n|[^\r\n])*'
    rb'|/\*[\s\S]*?(?:\*/|\Z)'
    rb'|"(?:\\[\s\S]|[^"\\])*(?:"|\\?\Z)'
    rb"|'(?:\\[\s\S]|[^'\\])*(?:'|\\?\Z)"
)


def _code_view(source):
    """Hide comments/strings from recognition, keeping byte offsets and line endings."""
    return _PROTECTED.sub(lambda m: bytes(c if c in (10, 13) else 32 for c in m[0]), source)


def _blank(out, source, code, start, end):
    for i in range(start, end):
        if source[i] not in (10, 13) and source[i] == code[i]:
            out[i] = 32  # protected text is untouched, including inside a matched span


def _attribute_end(code, start):
    stack = []
    close = {41: 40, 93: 91, 125: 123}
    i = start + 2
    while i < len(code):
        c = code[i]
        if c in (59, 123, 125):
            return None  # an attribute cannot contain statements or a block
        if not stack and code[i:i + 2] == b']]':
            return i + 2
        if c in (40, 91, 123):
            stack.append(c)
        elif c in close:
            if not stack or stack.pop() != close[c]:
                return None
        i += 1
    return None  # malformed/unfinished attributes stay visible to the grammar


def _type_end(code, start):
    """Conservative scalar argument list. Ambiguous ungrouped operators stay raw."""
    stack, count, arg = [], 1, start + 1
    close = {41: 40, 93: 91}
    i = arg
    while i < len(code):
        c = code[i]
        if c in (59, 123, 125):
            return None  # never hide statements/blocks as type arguments
        if not stack:
            if c == 62:
                return (i + 1, count) if code[arg:i].strip() else None
            if c == 44:
                if not code[arg:i].strip():
                    return None
                count += 1
                arg = i + 1
            if c in (60, 59, 123, 125, 61) or code[i:i + 2] in (b'&&', b'||'):
                return None
        if c in (40, 91):
            stack.append(c)
        elif c in close:
            if not stack or stack.pop() != close[c]:
                return None
        i += 1
    return None


def preprocess_bytes(source, *, type_parameters=None):
    """Blank extension syntax for parsing only; offsets/CR/LF/protected text stay exact."""
    if b'[[' not in source and (not type_parameters or b'<' not in source):
        return source
    code = _code_view(source)
    out = bytearray(source)
    cursor = 0
    while True:
        start = code.find(b'[[', cursor)
        if start < 0:
            break
        end = _attribute_end(code, start)
        if end is not None:
            _blank(out, source, code, start, end)
        cursor = end if end is not None else start + 2
    if type_parameters:
        code = _code_view(bytes(out))
        names = b'|'.join(re.escape(name.encode('ascii')) for name in type_parameters)
        for match in re.finditer(rb'\b(' + names + rb')\s*<', code):
            # A member expression is not a type-name position.
            if code[:match.start()].rstrip().endswith(b'.'):
                continue
            start = match.end() - 1
            found = _type_end(code, start)
            if found is None:
                continue
            end, count = found
            minimum, maximum = type_parameters[match[1].decode('ascii')]
            if count < minimum or (maximum is not None and count > maximum):
                continue
            tail = code[end:].lstrip()
            if not re.match(rb'(?:[A-Za-z_][A-Za-z_0-9]*|\()', tail):
                continue  # declaration/parameter/return type or constructor only
            _blank(out, source, code, start, end)
    return bytes(out)
