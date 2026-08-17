"""Shared tree-sitter block engine for brace languages (C/C++, C#).

The traversal + level logic is identical across brace languages; only the set of
node-type names differs. Each language supplies a `LangSpec` (grammar loader +
node-type sets) and gets outline / get_blocks / line_level for free by
subclassing `TSBlockHandler`.

Block model (see cpp_handler for the full rationale):
  * A block is any node with a brace-delimited body -> a foldable region.
  * TRANSPARENT containers (namespace / extern "C") are shown in --outline but
    do NOT add a nesting level to their members.
  * Preamble comments directly above a block are glued onto its start.
  * Preprocessor lines, usings, forward-decls and plain fields are leaves.

Level rule (matches editor-fold numbering):
  level(row) = 1 + count of NON-transparent block bodies STRICTLY containing the
  row (strict -> the `{` line and `}` line belong to the outer level).
"""


class LangSpec:
    """Node-type configuration for one brace language."""

    def __init__(self, name, load_language, *, body_types, transparent_parents,
                 named_def, container, control, scope_body, cut_extra=()):
        self.name = name
        self._load_language = load_language
        self.body_types = frozenset(body_types)
        self.transparent_parents = frozenset(transparent_parents)
        self.named_def = frozenset(named_def)
        self.container = frozenset(container)
        self.control = frozenset(control)
        self.scope_body = scope_body           # bare `{}` statement-block type
        self.cut_at = self.body_types | frozenset(cut_extra)
        self.body_owners = self.named_def | self.control
        self._parser = None

    def parser(self):
        if self._parser is None:
            try:
                from tree_sitter import Parser
                lang = self._load_language()
            except ImportError as e:
                raise ImportError(
                    f"{self.name} support needs tree-sitter: pip install "
                    f"tree-sitter <grammar> (present in the project venv/system python)"
                ) from e
            self._parser = Parser(lang)
        return self._parser


def _walk(node):
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        stack.extend(reversed(n.children))


def _source_bytes(lines):
    return "".join(lines).encode("utf-8")


class TreeSitterBlockHandler:
    """Mixin providing outline/get_blocks/line_level from a LangSpec.

    Subclasses set the class attribute SPEC = <LangSpec>.
    """

    SPEC = None

    # -- tree helpers -----------------------------------------------------

    def _root(self, source_bytes):
        return self.SPEC.parser().parse(source_bytes).root_node

    def _bodies(self, root):
        """(start_row, end_row, transparent) for every brace body."""
        sp = self.SPEC
        out = []
        for n in _walk(root):
            if n.type in sp.body_types:
                transparent = (n.parent is not None
                               and n.parent.type in sp.transparent_parents)
                out.append((n.start_point[0], n.end_point[0], transparent))
        return out

    @staticmethod
    def _level_of_row(row, bodies):
        return 1 + sum(1 for sr, er, tr in bodies if not tr and sr < row < er)

    def _has_body(self, node):
        return any(c.type in self.SPEC.body_types for c in node.children)

    def _is_standalone_scope(self, node):
        sp = self.SPEC
        return (node.type == sp.scope_body
                and node.parent is not None
                and node.parent.type not in sp.body_owners)

    def _label(self, node, source_bytes):
        """Header text: everything up to the body / init-list."""
        cut = node.end_byte
        for c in node.children:
            if c.type in self.SPEC.cut_at:
                cut = c.start_byte
                break
        text = source_bytes[node.start_byte:cut].decode("utf-8", "replace")
        return " ".join(text.split()).rstrip('{').rstrip().rstrip(':').rstrip()

    @staticmethod
    def _comment_rows(root):
        rows = set()
        for n in _walk(root):
            if n.type == 'comment':
                for r in range(n.start_point[0], n.end_point[0] + 1):
                    rows.add(r)
        return rows

    @staticmethod
    def _preamble_start(start_row, comment_rows, lines):
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

    def _preamble_owner(self, nodes, row, comment_rows, lines):
        """The ladder node whose preamble (comments directly above it) includes
        `row`, i.e. preamble_start(node) <= row < node.start. None if the row is
        a comment that documents nothing (trailing/detached). If several nodes
        qualify (a comment above a block that is itself the first line of an outer
        block), pick the nearest one below the row = the block it actually
        annotates."""
        owners = [n for n in nodes
                  if self._preamble_start(n.start_point[0], comment_rows, lines)
                  <= row < n.start_point[0]]
        if not owners:
            return None
        return min(owners, key=lambda n: n.start_point[0])

    def _ladder_nodes(self, root):
        sp = self.SPEC
        out = []
        for n in _walk(root):
            t = n.type
            if t in sp.named_def and self._has_body(n):
                out.append(n)
            elif t in sp.control:
                out.append(n)
            elif self._is_standalone_scope(n):
                out.append(n)
        return out

    def _outline_nodes(self, root):
        sp = self.SPEC
        out = []
        for n in _walk(root):
            t = n.type
            if (t in sp.container or t in sp.named_def) and self._has_body(n):
                out.append(n)
        return out

    # -- public API (mirrors PythonHandler) -------------------------------

    def outline(self, lines, max_level=None):
        source = _source_bytes(lines)
        root = self._root(source)
        bodies = self._bodies(root)
        comment_rows = self._comment_rows(root)

        nodes = self._outline_nodes(root)
        nodes.sort(key=lambda n: (n.start_point[0], -n.end_point[0]))

        out = []
        for n in nodes:
            level = self._level_of_row(n.start_point[0], bodies)
            if max_level and level > max_level:
                continue
            start = self._preamble_start(n.start_point[0], comment_rows, lines)
            out.append({
                'level': level,
                'text': self._label(n, source),
                'start': start + 1,
                'end': n.end_point[0] + 1,
            })
        return out

    def line_level(self, lines, idx):
        if idx < 0 or idx >= len(lines):
            return 1
        root = self._root(_source_bytes(lines))
        return self._level_of_row(idx, self._bodies(root))

    def get_blocks(self, file_path, target_line):
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        if not lines or target_line < 1 or target_line > len(lines):
            return []

        root = self._root(_source_bytes(lines))
        bodies = self._bodies(root)
        comment_rows = self._comment_rows(root)
        row = target_line - 1

        nodes = self._ladder_nodes(root)
        containing = [n for n in nodes
                      if n.start_point[0] <= row <= n.end_point[0]]

        # Landing on a preamble comment: it documents the block directly below it,
        # so it belongs to THAT block, not to whatever encloses the gap between
        # blocks (a class, a body). Mirror outline's gluing: if the row sits in a
        # node's preamble region [preamble_start .. node.start), treat that node as
        # the innermost containing block. An inner comment can't document the class.
        if row in comment_rows:
            owner = self._preamble_owner(nodes, row, comment_rows, lines)
            if owner is not None and owner not in containing:
                containing.append(owner)

        if not containing:
            return self._nearest(nodes, row, bodies, comment_rows, lines)

        containing.sort(key=lambda n: (n.start_point[0], -n.end_point[0]))

        result = []
        for i, n in enumerate(containing):
            level = self._level_of_row(n.start_point[0], bodies)
            start = n.start_point[0]
            if i == len(containing) - 1:  # glue preamble onto innermost only
                start = self._preamble_start(start, comment_rows, lines)
            result.append({
                'level': level,
                'start': start + 1,
                'end': n.end_point[0] + 1,
            })
        return result

    def _nearest(self, nodes, row, bodies, comment_rows, lines):
        below = [n for n in nodes if n.start_point[0] >= row]
        above = [n for n in nodes if n.end_point[0] <= row]
        chosen = None
        if below:
            chosen = min(below, key=lambda n: n.start_point[0] - row)
        if above:
            a = min(above, key=lambda n: row - n.end_point[0])
            if chosen is None or (row - a.end_point[0]) < (chosen.start_point[0] - row):
                chosen = a
        if chosen is None:
            return []
        level = self._level_of_row(chosen.start_point[0], bodies)
        start = self._preamble_start(chosen.start_point[0], comment_rows, lines)
        return [{
            'level': level,
            'start': start + 1,
            'end': chosen.end_point[0] + 1,
        }]
