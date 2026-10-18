"""Python ast-backend для ридера (фолбек, Vision02).

Когда `tree_sitter_python` не установлен, `.0` для Python идёт через stdlib `ast`
(есть всегда, ноль зависимостей). Функционал НЕПОЛНЫЙ — у ast нет комментариев
(нет `~comment`-полос), декоратор схлопнут в `def`/`class`. Реестр при откате
громко зовёт `pip install tree_sitter_python`.

Тот же контракт Backend/RNode/Spec — classify/render не меняются.
"""

import ast

from ...physical_lines import split_lines

_SCOPE = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
_DEF_TYPES = {'FunctionDef', 'AsyncFunctionDef', 'ClassDef'}


class AstNode:
    """Узел stdlib-ast под протокол RNode. children() = тело scope (module/def/class)."""
    __slots__ = ('_n', '_lines')

    def __init__(self, node, lines):
        self._n = node
        self._lines = lines

    @property
    def type(self):
        return type(self._n).__name__

    @property
    def start_row(self):
        return (getattr(self._n, 'lineno', 1) or 1) - 1

    @property
    def end_row(self):
        return (getattr(self._n, 'end_lineno', None) or getattr(self._n, 'lineno', 1)) - 1

    def children(self):
        body = getattr(self._n, 'body', None)
        if isinstance(self._n, _SCOPE) and isinstance(body, list):
            return [AstNode(c, self._lines) for c in body]
        return []

    def text(self):
        return self._header()

    def field(self, name):
        """Just the fields name_resolver reads: a def/class's `name`, an assignment's `left`
        (a plain-name target). Without them the resolver fell back to the display label
        (`def target()`) as the declared name, so `--name target` was never exact (review R07)."""
        n = self._n
        if name == 'name' and type(n).__name__ in _DEF_TYPES:
            return _Ident(n.name)
        if name == 'left':
            t = n.targets[0] if isinstance(n, ast.Assign) and len(n.targets) == 1 else \
                n.target if isinstance(n, ast.AnnAssign) else None
            if isinstance(t, ast.Name):
                return _Ident(t.id)
        return None

    def _header(self):
        """Заголовок def/class — строки от начала до первого тела-стейтмента."""
        s = self.start_row
        body = getattr(self._n, 'body', None)
        if isinstance(self._n, _SCOPE) and body:
            e = body[0].lineno - 1
        else:
            e = self.end_row + 1
        raw = "".join(self._lines[s:e])
        return " ".join(raw.split()).rstrip(':').rstrip()


class _Ident:
    """A bare identifier as an RNode leaf (what tree-sitter's `name`/`left` field holds)."""
    __slots__ = ('_s',)
    type = 'identifier'

    def __init__(self, s):
        self._s = s

    def text(self):
        return self._s

    def field(self, name):
        return None

    def children(self):
        return []


class PythonAstBackend:
    def root(self, source):
        src = source.decode('utf-8', 'replace')
        lines = split_lines(src)
        tree = ast.parse(src)          # SyntaxError пробрасывается — ast не error-tolerant
        return AstNode(tree, lines)


class PythonAstSpec:
    """Декоратор Python-ast: def/class = landmark, прочее = filler. Рамок нет."""

    def unwrap_frame(self, node):
        return None

    def unwrap_def(self, node):
        return node if node.type in _DEF_TYPES else None

    def role(self, node):
        return 'landmark' if node.type in _DEF_TYPES else 'filler'

    def body(self, node):
        return node if node.type in _DEF_TYPES and node.children() else None

    def name(self, node):
        return node.text()

    def filler_kind(self, node):
        from ..profiles.presets import IMPORT_KINDS
        if node.type in IMPORT_KINDS:
            return 'import'                 # огрубляем: Import и ImportFrom → одна полоса
        return node.type

    def filler_label(self, nodes):
        """Минимальный лейблер для ast-фолбека: импорты и присваивания по имени
        (ast остаточный — глубоко не разбираем, полный режим = tree-sitter)."""
        from ..label import band_label
        return band_label(nodes, _ast_name_of)


def _ast_name_of(node):
    n = node._n
    if isinstance(n, ast.ImportFrom):
        return n.module or '.'
    if isinstance(n, ast.Import):
        return n.names[0].name if n.names else None
    if isinstance(n, ast.Assign):
        t = n.targets[0] if n.targets else None
        return getattr(t, 'id', None)
    if isinstance(n, ast.AnnAssign):
        return getattr(n.target, 'id', None)
    return None
