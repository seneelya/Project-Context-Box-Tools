"""tree-sitter backend для ридера (core1).

Три вещи:
  * TSNode        — тонкая обёртка tree-sitter-узла под протокол RNode (+ пара
                    helper'ов для нарезки заголовка, которых нет в минимальном RNode).
  * TSBackend     — парсер: байты → корневой TSNode (поверх LangSpec.parser()).
  * TreeSitterSpec — тонкий ДВИЖОК: роль/имя/тело/обёртки узла. Общая логика; весь
                    язык-нюанс приходит ДАННЫМИ из TSProfile (profiles/<lang>.py):
                    extra-frames и binder/value-типы промоушена. Наборы структурных
                    node-типов — из LangSpec профиля (не дублируем).
"""


_LABEL_CAP = 350   # max chars in a landmark/frame header label (cursor_feedback__gcb.md #4) —
                   # above the longest real multi-kwarg Python signature in the golden fixtures
                   # (267 chars), comfortably below a "many DI params" C# primary-constructor
                   # header (300-800+ chars), which is what the complaint was about.


class TSNode:
    """Обёртка tree-sitter-узла под RNode. Дополнительно несёт start_byte/helpers
    для нарезки заголовка — TreeSitterSpec ими пользуется (RNode это не требует)."""
    __slots__ = ('_n', '_src', '_rules')

    def __init__(self, node, src, rules=None):
        self._n = node
        self._src = src
        self._rules = rules or {}

    def _wrap(self, node):
        return TSNode(node, self._src, self._rules)

    def _flattened(self):
        rules = self._rules.get('flatten', {})
        if self._n.type not in rules:
            return False
        missing_field = rules[self._n.type]
        return missing_field is None or self._n.child_by_field_name(missing_field) is None

    def _inline_comment(self):
        if self._n.type in self._rules.get('inline_comments', ()):
            line_start = self._src.rfind(b'\n', 0, self._n.start_byte) + 1
            if self._src[line_start:self._n.start_byte].strip():
                return True
        return False

    @property
    def type(self):
        for child_type, alias in self._rules.get('aliases', {}).get(self._n.type, ()):
            if any(c.type == child_type for c in self._n.named_children):
                return alias
        return self._n.type

    @property
    def start_row(self):
        if self._n.type in self._rules.get('body_span_from_parent', ()) and self._n.parent is not None:
            return self._n.parent.start_point[0]
        return self._n.start_point[0]

    @property
    def end_row(self):
        if self._n.type in self._rules.get('body_span_from_parent', ()) and self._n.parent is not None:
            return self._n.parent.end_point[0]
        if (self._n.type in self._rules.get('exclusive_end', ())
                and self._n.end_point[1] == 0 and self._n.end_point[0] > self.start_row):
            return self._n.end_point[0] - 1
        return self._n.end_point[0]

    def children(self):
        if not self._rules:
            return [TSNode(c, self._src) for c in self._n.named_children]
        out = []
        for c in self._n.named_children:
            child = self._wrap(c)
            if child._inline_comment():
                continue  # source stays on its owner's physical line; no separate preamble/rung
            out.extend(child.children() if child._flattened() else [child])
        return out

    def text(self):
        return self._src[self._n.start_byte:self._n.end_byte].decode('utf-8', 'replace')

    def field(self, name):
        c = self._n.child_by_field_name(name)
        if c is not None:
            return self._wrap(c)
        for path in self._rules.get('fields', {}).get(self.type, {}).get(name, ()):
            cur = self
            for kind in path:
                cur = next((ch for ch in cur.children() if ch.type == kind), None)
                if cur is None:
                    break
            if cur is not None:
                return cur
        return None

    def parent(self):
        p = self._n.parent
        while p is not None and self._wrap(p)._flattened():
            p = p.parent
        return self._wrap(p) if p is not None else None

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
    def __init__(self, langspec, node_rules=None):
        self._langspec = langspec
        self._node_rules = node_rules

    def root(self, source):
        if self._langspec.preprocess is not None:
            source = self._langspec.preprocess(source)
        node = self._langspec.parser().parse(source).root_node
        return TSNode(node, source, self._node_rules)


class TreeSitterSpec:
    """Движок Spec поверх TSProfile. Реализует протокол Spec на TSNode; язык-нюанс —
    из профиля (frame-типы, binder/value-типы промоушена)."""

    def __init__(self, profile):
        self.profile = profile
        self.ls = profile.langspec
        self.frame_types = self.ls.transparent_parents | profile.extra_frames

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
        node на 1-2 уровня вглубь (const/let/export const, поле класса, pair, x = ...).
        Наборы binder/value-типов — из профиля (пусто → правило неактивно для языка)."""
        binders = self.profile.binders
        value_types = self.profile.value_types
        if not binders:
            return None
        stack = [(node, 0)]
        while stack:
            n, d = stack.pop()
            if d > 2:
                continue
            if n.type in binders:
                val = n.field('value') or n.field('right')
                if val is not None and val.type in value_types:
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
        # A FRAME's body is its own child (namespace/extern "C" -> declaration_list); never
        # unwrap into a definition inside it: `#ifdef X` wrapping exactly one function made
        # unwrap_def find that function and return ITS body — the map lost the function and
        # listed its locals at file level. A bodiless frame (`#ifdef`) -> None: the frame
        # itself is the scope (Classifier / _containing_chain).
        d = node if node.type in self.frame_types else (self.unwrap_def(node) or node)
        for c in d.children():
            if c.type in self.ls.body_types:
                return c
        return None

    def name(self, node):
        body = self.body(node)
        raw = node.head_before(body) if body is not None else node.first_line()
        text = " ".join(raw.split()).rstrip('{').rstrip(':').rstrip()
        # A header can run to hundreds of chars (C# primary-constructor DI param lists are
        # the reported case, but any language can produce one) — cap it for outline/ladder
        # display. Display-only: `--query` on the SAME range still returns the untruncated
        # source, so nothing is actually lost, just not dumped into a landmark label.
        if len(text) > _LABEL_CAP:
            text = text[:_LABEL_CAP].rstrip() + ' …'
        return text

    def filler_kind(self, node):
        from ..profiles.presets import IMPORT_KINDS
        if node.type in IMPORT_KINDS:
            return 'import'                 # огрубляем: import и from-import → одна полоса
        if node.type == 'expression_statement':
            kids = node.children()
            if len(kids) == 1 and kids[0].type in ('string', 'concatenated_string'):
                return 'docstring'
        # A `preprocess`-masked comment (opt-in, LangSpec.is_synthetic_comment) is NOT a
        # real comment — it's a statement standing in disguise (css_handler.py's SCSS
        # `$var:` mask). Give it a kind other than 'comment' so Classifier's preamble-glue
        # ('comment'-kind runs pend and attach to the NEXT landmark) never absorbs it into
        # the following rule's range — cursor_feedback__gcb.md #5 residual, fixed 2026-09-13.
        if (node.type == 'comment' and self.ls.is_synthetic_comment is not None
                and self.ls.is_synthetic_comment(node.text())):
            return 'masked'
        return node.type

    def filler_label(self, nodes):
        """Заголовок filler-полосы: список имён (импорты/привязки). См. reader/label.py."""
        from ..label import band_label, ts_name_of
        if not self.profile.node_rules:
            return band_label(nodes, ts_name_of)
        def name_of(node):
            kinds = self.profile.node_rules.get('declarators', ())
            names = [c.field('name').text() for c in node.children()
                     if c.type in kinds and c.field('name') is not None]
            return ', '.join(names) if names else ts_name_of(node)
        return band_label(nodes, name_of)
