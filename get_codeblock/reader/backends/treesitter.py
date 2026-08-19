"""tree-sitter backend для ридера (core1).

Три вещи:
  * TSNode        — тонкая обёртка tree-sitter-узла под протокол RNode (+ пара
                    helper'ов для нарезки заголовка, которых нет в минимальном RNode).
  * TSBackend     — парсер: байты → корневой TSNode (поверх LangSpec.parser()).
  * TreeSitterSpec — декоратор: роль/имя/тело/обёртки узла. Весь язык-нюанс тут
                    (порт логики dot_classify на RNode). Наборы node-типов берём из
                    существующего LangSpec — не дублируем.

_EXTRA_FRAME_TYPES: прозрачные рамки, которых нет в общих LangSpec (их менять
нельзя — на них завязан рабочий outline/query). Ключ = spec.name.
"""

_EXTRA_FRAME_TYPES = {
    'TypeScript': {'internal_module', 'module'},
    'TypeScript (TSX)': {'internal_module', 'module'},
    'C/C++': {'preproc_ifdef', 'preproc_if'},
}


class TSNode:
    """Обёртка tree-sitter-узла под RNode. Дополнительно несёт start_byte/helpers
    для нарезки заголовка — TreeSitterSpec ими пользуется (RNode это не требует)."""
    __slots__ = ('_n', '_src')

    def __init__(self, node, src):
        self._n = node
        self._src = src

    @property
    def type(self):
        return self._n.type

    @property
    def start_row(self):
        return self._n.start_point[0]

    @property
    def end_row(self):
        return self._n.end_point[0]

    def children(self):
        return [TSNode(c, self._src) for c in self._n.named_children]

    def text(self):
        return self._src[self._n.start_byte:self._n.end_byte].decode('utf-8', 'replace')

    def field(self, name):
        c = self._n.child_by_field_name(name)
        return TSNode(c, self._src) if c is not None else None

    # -- TS-специфичные helper'ы (вне минимального RNode) ------------------

    def head_before(self, child):
        """Текст от начала этого узла до начала `child` — для заголовка (до тела)."""
        return self._src[self._n.start_byte:child._n.start_byte].decode('utf-8', 'replace')

    def first_line(self):
        """Первая физическая строка узла (когда тела-узла нет)."""
        nl = self._src.find(b'\n', self._n.start_byte, self._n.end_byte)
        cut = nl if nl != -1 else self._n.end_byte
        return self._src[self._n.start_byte:cut].decode('utf-8', 'replace')


class TSBackend:
    def __init__(self, langspec):
        self._langspec = langspec

    def root(self, source):
        node = self._langspec.parser().parse(source).root_node
        return TSNode(node, source)


class TreeSitterSpec:
    """Декоратор языка поверх LangSpec. Реализует протокол Spec на TSNode."""

    def __init__(self, langspec):
        self.ls = langspec
        self.frame_types = langspec.transparent_parents | _EXTRA_FRAME_TYPES.get(langspec.name, set())

    # -- разворачивание обёрток (export/decorator/expression_statement) ----

    def unwrap_frame(self, node):
        if node.type in self.frame_types:
            return node
        for c in node.children():
            if c.type in self.frame_types:
                return c
        return None

    def unwrap_def(self, node):
        if node.type in self.ls.named_def:
            return node
        for c in node.children():
            if c.type in self.ls.named_def:
                return c
        # NAME = () => {…} / NAME = function(){…} — привязка функции к имени. Старый
        # outline показывает такие через _ARROW_BINDINGS; без этого «.0» роняет
        # большинство функций JS/TS в filler. Возвращаем узел-значение (arrow/function),
        # у него блочное тело в body_types → name/body работают штатно.
        return self._arrow_binding_value(node)

    def _arrow_binding_value(self, node):
        """Значение-функция (arrow/function с блочным телом), привязанное к имени внутри
        node на 1-2 уровня вглубь (const/let/export const, поле класса, pair, x = ...)."""
        BINDERS = ('variable_declarator', 'field_definition', 'public_field_definition',
                   'pair', 'assignment_expression')
        VALUE_TYPES = ('arrow_function', 'function', 'function_expression')
        stack = [(node, 0)]
        while stack:
            n, d = stack.pop()
            if d > 2:
                continue
            if n.type in BINDERS:
                val = n.field('value') or n.field('right')
                if val is not None and val.type in VALUE_TYPES:
                    for c in val.children():                 # только блочно-телые
                        if c.type in self.ls.body_types and c.end_row > c.start_row:
                            return val
            for c in n.children():
                stack.append((c, d + 1))
        return None

    # -- контракт Spec ----------------------------------------------------

    def role(self, node):
        if self.unwrap_frame(node) is not None:
            return 'frame'
        if self.unwrap_def(node) is not None:
            return 'landmark'
        return 'filler'

    def body(self, node):
        """Scope-тело для рекурсии/всплытия: у определения/рамки — первый ребёнок
        body-типа. Разворачиваем обёртку до определения (у namespace определений
        среди ПРЯМЫХ детей нет — они в declaration_list, так что не путаемся)."""
        d = self.unwrap_def(node) or node
        for c in d.children():
            if c.type in self.ls.body_types:
                return c
        return None

    def name(self, node):
        body = self.body(node)
        raw = node.head_before(body) if body is not None else node.first_line()
        return " ".join(raw.split()).rstrip('{').rstrip(':').rstrip()

    def filler_kind(self, node):
        if node.type == 'expression_statement':
            kids = node.children()
            if len(kids) == 1 and kids[0].type in ('string', 'concatenated_string'):
                return 'docstring'
        return node.type
