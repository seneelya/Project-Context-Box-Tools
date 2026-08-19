"""«.0» — универсальный классификатор scope (Vision02).

Один языконезависимый проход над tree-sitter-корнем: берём прямых детей scope и
раскладываем по РОЛЯМ (таблица ролей — единственное языкозависимое место):

  * landmark — именованное определение (class/func; в итерации 2 + именованные
    константы). Раскрываем ПОИМЁННО, не сливаем. Это «разделы и главы».
  * filler   — imports / comments / голые стейтменты. Сливаем подряд идущие
    одного типа в ПОЛОСУ (граница = смена типа). Это «вставки/реклама».
  * frame    — прозрачная рамка (namespace / extern "C" / decorated). Глубины не
    добавляет: её именованные дети ВСПЛЫВАЮТ на текущий уровень (маркер «.»).

Ядро рекурсивно: classify(scope) над любым узлом-scope. depth>0 — раскрываем тела
landmark-ов на уровень глубже («.1», «.2»...). Продукт нужен один — «.0», но
механика та же на всех уровнях (Vision02).

Не дубль движка: используем `LangSpec` из `_treesitter_blocks`. Python входит в ту
же семью через tree-sitter-python (fallback на stdlib `ast` — отдельно, не здесь).
"""

from ._treesitter_blocks import LangSpec, _walk  # noqa: F401  (_walk for future use)


# --------------------------------------------------------------- language specs

def _load_python_language():
    import tree_sitter_python
    from tree_sitter import Language
    return Language(tree_sitter_python.language())


# Python через tree-sitter (не отступной python_handler). Наборы под грамматику
# tree-sitter-python: module(root) -> statements; тело def/class = `block`.
PY_TS_SPEC = LangSpec(
    "Python(ts)",
    _load_python_language,
    body_types={'block'},
    transparent_parents=set(),          # в Python нет namespace-рамок; decorated — особый случай
    named_def={'function_definition', 'class_definition'},
    container=set(),
    control={'if_statement', 'for_statement', 'while_statement',
             'with_statement', 'try_statement', 'match_statement'},
    scope_body='block',
)


def _spec_for_ext(ext):
    ext = ext.lower()
    if ext == '.py':
        return PY_TS_SPEC
    if ext in ('.cpp', '.cc', '.cxx', '.hpp', '.h', '.hh', '.c'):
        from .cpp_handler import CPP_SPEC
        return CPP_SPEC
    if ext in ('.ts', '.js'):
        from .typescript_handler import TS_SPEC
        return TS_SPEC
    if ext in ('.tsx', '.jsx'):
        from .typescript_handler import TSX_SPEC
        return TSX_SPEC
    if ext == '.cs':
        from .csharp_handler import CS_SPEC
        return CS_SPEC
    if ext in ('.scss', '.sass', '.css'):
        from .css_handler import CSS_SPEC
        return CSS_SPEC
    raise ValueError(f"dot_classify: нет spec для {ext}")


# ------------------------------------------------------------------- classifier

class DotEntry:
    """Один элемент классификации scope."""
    __slots__ = ('kind', 'node_type', 'name', 'start', 'end', 'level', 'count', 'children')

    def __init__(self, kind, node_type, start, end, level, name=None, count=1):
        self.kind = kind            # 'landmark' | 'filler' | 'frame'
        self.node_type = node_type
        self.name = name
        self.start = start          # 1-based
        self.end = end              # 1-based inclusive
        self.level = level
        self.count = count          # сколько узлов слито в filler-полосу
        self.children = []          # вложенная классификация (frame-всплытие / drill)


# Прозрачные рамки, которых НЕТ в общих SPEC (их менять нельзя — на них завязан
# рабочий outline/query). Классификатор знает про них локально. Ключ = spec.name.
_EXTRA_FRAME_TYPES = {
    'TypeScript': {'internal_module', 'module'},          # namespace X {} / module X {}
    'TypeScript (TSX)': {'internal_module', 'module'},
    'C/C++': {'preproc_ifdef', 'preproc_if'},             # include-guard / #if оборачивает объявления
}


class DotClassifier:
    def __init__(self, spec, source_bytes):
        self.spec = spec
        self.src = source_bytes
        self.frame_types = spec.transparent_parents | _EXTRA_FRAME_TYPES.get(spec.name, set())

    # -- helpers ----------------------------------------------------------

    def _text(self, node):
        return self.src[node.start_byte:node.end_byte].decode('utf-8', 'replace')

    def _inner_def(self, node):
        """Внутреннее именованное определение, если node ИМ является или ОБОРАЧИВАЕТ
        его одним уровнем. Покрывает прозрачные обёртки-над-одним-определением:
        `decorated_definition` (@deco def/class), `export_statement`
        (export function/class/interface). Возвращает None, если определения нет
        (обычный стейтмент, `export {re-export}`, `export const` — это filler)."""
        if node.type in self.spec.named_def:
            return node
        for c in node.named_children:                 # разворачиваем один уровень
            if c.type in self.spec.named_def:
                return c
        return None

    def _def_node(self, node):
        return self._inner_def(node) or node

    def _header(self, node):
        """Шапка узла — текст от начала до тела (как движковый `_label`): даёт
        полный заголовок `int helper(int x)` / `class Foo(Base)` и корректно
        включает декоратор для decorated_definition. Надёжнее выбора одного
        `name`-поля (в C++ имя функции спрятано в declarator)."""
        body = self._body_of(node)
        if body is not None:
            cut = body.start_byte
        else:
            # нет body-узла (inline-рамка #ifndef, однострочный record/enum): берём
            # только первую физическую строку, чтобы не всосать весь блок в лейбл.
            nl = self.src.find(b'\n', node.start_byte, node.end_byte)
            cut = nl if nl != -1 else self._def_node(node).end_byte
        txt = self.src[node.start_byte:cut].decode('utf-8', 'replace')
        return " ".join(txt.split()).rstrip('{').rstrip(':').rstrip()

    def _body_of(self, node):
        """Тело-scope узла (для рекурсии/всплытия): первый ребёнок body-типа.
        Для decorated_definition спускаемся во внутреннее определение."""
        d = self._def_node(node)
        for c in d.children:
            if c.type in self.spec.body_types:
                return c
        return None

    def _frame_node(self, node):
        """Прозрачная рамка, если node ЕЮ является или ОБОРАЧИВАЕТ её одним уровнем.
        tree-sitter оборачивает bare TS `namespace X {}` в expression_statement →
        internal_module — разворачиваем так же, как обёртку над определением."""
        if node.type in self.frame_types:
            return node
        for c in node.named_children:
            if c.type in self.frame_types:
                return c
        return None

    def _role(self, node):
        if self._frame_node(node) is not None:           # рамка проверяется первой
            return 'frame'
        if self._inner_def(node) is not None:            # определение или обёртка над ним
            return 'landmark'
        return 'filler'

    def _filler_kind(self, node):
        """Тип полосы для filler. Уточнение (Vision02): expression_statement, у
        которого единственный ребёнок-строка — это docstring, не обычный стейтмент."""
        if node.type == 'expression_statement':
            kids = node.named_children
            if len(kids) == 1 and kids[0].type in ('string', 'concatenated_string'):
                return 'docstring'
        return node.type

    # -- core (рекурсивно) -----------------------------------------------

    def classify(self, scope_node, level, depth):
        """Классифицировать прямых детей scope_node на уровне `level`.
        depth>0 — рекурсивно раскрыть тела landmark-ов на уровень глубже."""
        out = []
        run = None   # накопитель filler-полосы: [kind, start, end, count]

        def flush():
            nonlocal run
            if run is not None:
                out.append(DotEntry('filler', run[0], run[1], run[2], level, count=run[3]))
                run = None

        for child in scope_node.named_children:
            role = self._role(child)
            s = child.start_point[0] + 1
            e = child.end_point[0] + 1

            if role == 'filler':
                kind = self._filler_kind(child)
                if run is not None and run[0] == kind:
                    run[2] = e
                    run[3] += 1
                else:
                    flush()
                    run = [kind, s, e, 1]
                continue

            flush()

            if role == 'frame':
                fnode = self._frame_node(child)          # разворачиваем обёртку до рамки
                entry = DotEntry('frame', fnode.type, s, e, level,
                                 name=self._header(fnode))
                # Дети рамки ВСПЛЫВАЮТ: тот же level. У namespace тело — declaration_list
                # (body_type). У inline-рамок (#ifndef-гард) тела-узла нет — объявления
                # лежат прямыми детьми самой рамки, разворачиваем их.
                body = self._body_of(fnode)
                scope = body if body is not None else fnode
                entry.children = self.classify(scope, level, depth)
                out.append(entry)
            else:  # landmark
                entry = DotEntry('landmark', self._def_node(child).type, s, e, level,
                                 name=self._header(child))
                if depth > 0:
                    body = self._body_of(child)
                    if body is not None:
                        entry.children = self.classify(body, level + 1, depth - 1)
                out.append(entry)

        flush()
        return out


# ----------------------------------------------------------------- rendering

def render(entries, marker_comment='#'):
    """Плоский текстовый вывод. landmark -> level+имя; frame -> «.»+всплытие;
    filler -> «~тип ×N»-полоса."""
    lines = []

    def walk(items, indent):
        pad = '  ' * indent
        for e in items:
            rng = f"[{e.start}-{e.end}]"
            if e.kind == 'landmark':
                lines.append(f"{marker_comment}{pad}L{e.level}  {rng:>10}  {e.name}")
            elif e.kind == 'frame':
                lines.append(f"{marker_comment}{pad}.   {rng:>10}  {e.name}")
            else:  # filler
                tag = f"~{e.node_type}" + (f" ×{e.count}" if e.count > 1 else "")
                lines.append(f"{marker_comment}{pad}    {rng:>10}  {tag}")
            if e.children:
                walk(e.children, indent + 1)

    walk(entries, 0)
    return "\n".join(lines)


# --------------------------------------------------------------------- entry

def classify_file(path, depth=0):
    import os
    ext = os.path.splitext(path)[1]
    spec = _spec_for_ext(ext)
    with open(path, 'r', encoding='utf-8') as f:
        src = f.read()
    src_bytes = src.encode('utf-8')
    root = spec.parser().parse(src_bytes).root_node
    clf = DotClassifier(spec, src_bytes)
    return clf.classify(root, level=1, depth=depth)


def main():
    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    args = sys.argv[1:]
    if not args:
        print("usage: python dot_classify.py FILE [--depth N]")
        return
    path = args[0]
    depth = 0
    if '--depth' in args:
        depth = int(args[args.index('--depth') + 1])
    entries = classify_file(path, depth=depth)
    print(f"//.0 classification: {path}  (depth={depth})")
    print(render(entries))


if __name__ == '__main__':
    main()
