"""Адресация на reader-движке (Vision04) — brace-языки.

ОДИН структурный движок «какой блок на строке N» для tree-sitter brace-языков
(ts/tsx/cs/cpp/css): `get_blocks` (лестница объемлющих блоков) и `line_level`
(глубина строки). Порт handlers/_treesitter_blocks на протокол RNode+Spec —
тот же grammar, те же границы, что и у `.0`-outline (склейка преамбулы общая),
но набор рунгов адресации БОГАЧЕ карты: сюда входят braced-control (`for`/`if`)
и standalone-тела (arrow/`{…}`/object/array), а transparent-рамки (namespace/
extern "C") прозрачны для уровня — как в старом `_level_of_row`.

Python/Markdown идут своим (отступным/бesparser) путём — Reader делегирует их
существующим хендлерам, пока они не обёрнуты в backend (см. CONTEXT_RESTORE ⭐).
"""

import os

from .registry import resolve


# brace-семейство: reader-нативная адресация. Python (отступной) и Markdown
# (беsparser) НАМЕРЕННО исключены — идут своим хендлером до обёртки в backend.
_BRACE_EXTS = frozenset({
    '.ts', '.js', '.tsx', '.jsx', '.cs',
    '.cpp', '.cc', '.cxx', '.c++', '.hpp', '.hh', '.hxx', '.h', '.c',
    '.scss', '.sass', '.css',
})


def supports(path):
    """Есть ли reader-нативная адресация для расширения (только brace-язык с langspec)."""
    ext = os.path.splitext(path)[1].lower()
    if ext not in _BRACE_EXTS:
        return False
    try:
        _, spec = resolve(ext)
    except Exception:
        return False
    ls = getattr(spec, 'ls', None)
    return ls is not None and hasattr(ls, 'control') and hasattr(ls, 'body_types')


# -- обход дерева -----------------------------------------------------------

def _has_body(node, ls):
    return any(c.type in ls.body_types for c in node.children())


def _is_standalone_body(node, parent, ls):
    """brace-тело без своего заголовка (arrow-тело, голый `{}`, многострочный
    object/array-литерал) — foldable-регион без имени. ТОЛЬКО многострочный."""
    if node.type not in ls.body_types:
        return False
    if node.end_row <= node.start_row:
        return False
    if parent is None:
        return False
    return (parent.type not in ls.body_owners
            and parent.type not in ls.transparent_parents)


def _collect(root, ls):
    """Один обход: рунги адресации (node, parent) + все brace-тела (sr,er,transparent)."""
    blocks, bodies = [], []

    def walk(node, parent):
        t = node.type
        if t in ls.body_types:
            transparent = parent is not None and parent.type in ls.transparent_parents
            bodies.append((node.start_row, node.end_row, transparent))
        if (t in ls.named_def or t in ls.control) and _has_body(node, ls):
            blocks.append((node, parent))
        elif _is_standalone_body(node, parent, ls):
            blocks.append((node, parent))
        for c in node.children():
            walk(c, node)

    walk(root, None)
    return blocks, bodies


def _level_of_row(row, bodies):
    """Как старый: 1 + число НЕпрозрачных тел, СТРОГО содержащих строку (0-based)."""
    return 1 + sum(1 for sr, er, tr in bodies if not tr and sr < row < er)


# -- преамбула-склейка (общая семантика с outline) --------------------------

def _comment_rows(root):
    """Строки, покрытые ИСКЛЮЧИТЕЛЬНО комментами (лист-узлы). Код на строке рвёт склейку."""
    comment_rows, code_rows = set(), set()

    def walk(n):
        ch = n.children()
        if not ch:                                    # лист
            rows = range(n.start_row, n.end_row + 1)
            (comment_rows if n.type == 'comment' else code_rows).update(rows)
        for c in ch:
            walk(c)

    walk(root)
    return comment_rows - code_rows


def _preamble_start(start_row, comment_rows, lines):
    """Поднять начало над коммент-преамбулой (комменты/пустые прямо над блоком). 0-based."""
    first = start_row
    r = start_row - 1
    while r >= 0:
        if not lines[r].strip():
            r -= 1
            continue
        if r in comment_rows:
            first = r
            r -= 1
            continue
        break
    return first


def _preamble_owner(blocks, row, comment_rows, lines):
    owners = [n for n, _ in blocks
              if _preamble_start(n.start_row, comment_rows, lines) <= row < n.start_row]
    if not owners:
        return None
    return min(owners, key=lambda n: n.start_row)


# -- label ------------------------------------------------------------------

def _block_label(node, parent, spec):
    ls = spec.ls
    if node.type in ls.named_def or node.type in ls.control:
        return spec.name(node)
    ptype = parent.type if parent is not None else ''
    if node.type in ('object', 'object_pattern'):
        return "{…} object"
    if node.type in ('array', 'array_pattern'):
        return "[…] array"
    if 'arrow' in ptype:
        return "() => {…}"
    return "{…} block"


def _bounds(node, parent, bodies, comment_rows, lines, spec):
    return {
        'level': _level_of_row(node.start_row, bodies),
        'start': _preamble_start(node.start_row, comment_rows, lines) + 1,
        'end': node.end_row + 1,
        'label': _block_label(node, parent, spec),
    }


def _read_lines(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.readlines()


# -- публичный API (зеркалит хендлер) ---------------------------------------

def get_blocks(path, target_line):
    lines = _read_lines(path)
    if not lines or target_line < 1 or target_line > len(lines):
        return []
    backend, spec = resolve(os.path.splitext(path)[1])
    root = backend.root("".join(lines).encode("utf-8"))
    blocks, bodies = _collect(root, spec.ls)
    comment_rows = _comment_rows(root)
    row = target_line - 1

    containing = [(n, p) for n, p in blocks if n.start_row <= row <= n.end_row]

    if row in comment_rows:                            # тычок в преамбулу → её блок
        owner = _preamble_owner(blocks, row, comment_rows, lines)
        if owner is not None and all(owner is not n for n, _ in containing):
            containing.append(next((n, p) for n, p in blocks if n is owner))

    if not containing:
        return _nearest(blocks, row, bodies, comment_rows, lines, spec)

    containing.sort(key=lambda np: (np[0].start_row, -np[0].end_row))
    return [_bounds(n, p, bodies, comment_rows, lines, spec) for n, p in containing]


def _nearest(blocks, row, bodies, comment_rows, lines, spec):
    below = [(n, p) for n, p in blocks if n.start_row >= row]
    above = [(n, p) for n, p in blocks if n.end_row <= row]
    chosen = None
    if below:
        chosen = min(below, key=lambda np: np[0].start_row - row)
    if above:
        a = min(above, key=lambda np: row - np[0].end_row)
        if chosen is None or (row - a[0].end_row) < (chosen[0].start_row - row):
            chosen = a
    if chosen is None:
        return []
    n, p = chosen
    return [_bounds(n, p, bodies, comment_rows, lines, spec)]


def line_level(path, idx):
    lines = _read_lines(path)
    if idx < 0 or idx >= len(lines):
        return 1
    backend, spec = resolve(os.path.splitext(path)[1])
    root = backend.root("".join(lines).encode("utf-8"))
    _, bodies = _collect(root, spec.ls)
    return _level_of_row(idx, bodies)
