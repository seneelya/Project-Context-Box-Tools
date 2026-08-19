"""Backend-agnostic .0-классификатор (Vision02/03) на протоколе.

Ровно та же механика, что в handlers/dot_classify.py, но работает через `Spec`+
`RNode`, не зная про tree-sitter. Порт — чтобы доказать, что классификатор
отвязывается от backend'а (шаг к core2 docx/pdf).
"""

import os

from .ir import Block, Role
from .registry import resolve


def _first_comment_line(nodes, cap=60):
    """Первая СОДЕРЖАТЕЛЬНАЯ строка комментов полосы — для подписи блока (преамбула).
    Декоративные строки-разделители (`#====`, `----`, `____`, `####`, `***` …)
    пропускаем: язык-независимо — содержательная строка содержит хотя бы одну БУКВУ
    (буквы и есть текст, разделители — только пунктуация). Обрезаем длинное; '…' если
    в полосе есть ещё строки."""
    lines = []
    for n in nodes:
        lines.extend(n.text().splitlines())
    chosen = next((ln.strip() for ln in lines if any(ch.isalpha() for ch in ln)), None)
    if not chosen:
        return None
    multi = len(lines) > 1
    if len(chosen) > cap:
        return chosen[:cap].rstrip() + '…'
    return chosen + ' …' if multi else chosen


class Classifier:
    def __init__(self, spec):
        self.spec = spec

    def classify(self, scope, level, depth, top_filler_only=False):
        """Классифицировать прямых детей scope на уровне `level`. depth>0 —
        рекурсивно раскрыть тела landmark-ов на уровень глубже.

        top_filler_only=True (режим outline): filler-полосы показываем ТОЛЬКО на
        уровне файла (level==1). Присвоения/комменты внутри подобъектов малоинформативны
        фактом наличия — это данные для --query. Рамки не углубляют, поэтому filler в
        рамке уровня файла остаётся level==1 и показывается.

        ПРЕАМБУЛА: comment-полоса ПРЯМО над landmark'ом вливается в него — граница блока
        поднимается вверх над коммент, отдельной строкой он не показывается, а его первая
        строка дописывается в подпись блока (информативность для --query). Коммент НЕ над
        блоком (закомментированный текст) остаётся обычным filler на своём уровне."""
        out = []
        run = None       # текущая filler-полоса: [kind, start, end, nodes]
        pending = None   # удержанная comment-полоса (start, end, nodes) — вдруг ниже landmark

        def make_filler(kind, s, e, nodes):
            if top_filler_only and level > 1:              # outline: filler только на файле
                return None
            label = None
            labeler = getattr(self.spec, 'filler_label', None)   # опц. (Vision03)
            if labeler is not None:
                label = labeler(nodes)
            return Block(Role.FILLER, kind, s, e, level, name=label, count=len(nodes))

        def release_pending():
            nonlocal pending
            if pending is not None:
                blk = make_filler('comment', *pending)     # ниже не блок — коммент как есть
                if blk is not None:
                    out.append(blk)
                pending = None

        def flush():
            nonlocal run, pending
            if run is None:
                return
            kind, s, e, nodes = run
            run = None
            if kind == 'comment':
                release_pending()                          # два коммент-бэнда подряд — прежний отдать
                pending = (s, e, nodes)                     # держим: вдруг ниже landmark
                return
            release_pending()                              # не-comment полоса рвёт склейку
            blk = make_filler(kind, s, e, nodes)
            if blk is not None:
                out.append(blk)

        for child in scope.children():
            s = child.start_row + 1
            e = child.end_row + 1
            frame = self.spec.unwrap_frame(child)
            defn = None if frame is not None else self.spec.unwrap_def(child)

            if frame is None and defn is None:            # filler
                kind = self.spec.filler_kind(child)
                if run is not None and run[0] == kind:
                    run[2] = e
                    run[3].append(child)
                else:
                    flush()
                    run = [kind, s, e, [child]]
                continue

            flush()

            if frame is not None:                         # рамка: дети всплывают (тот же level)
                release_pending()                         # к рамке не клеим — коммент как есть
                entry = Block(Role.FRAME, frame.type, s, e, level, name=self.spec.name(frame))
                body = self.spec.body(frame)
                scope2 = body if body is not None else frame
                entry.children = self.classify(scope2, level, depth, top_filler_only)
                out.append(entry)
            else:                                         # landmark: имя от внешнего узла (с export/deco)
                entry = Block(Role.LANDMARK, defn.type, s, e, level, name=self.spec.name(child))
                if pending is not None:                   # ПРЕАМБУЛА: коммент над блоком вливается
                    entry.start = pending[0]
                    first = _first_comment_line(pending[2])
                    if first:
                        entry.name = f"{entry.name}  {first}"
                    pending = None
                if depth > 0:
                    body = self.spec.body(child)
                    if body is not None:
                        entry.children = self.classify(body, level + 1, depth - 1, top_filler_only)
                out.append(entry)

        flush()
        release_pending()
        return out


def classify_file(path, depth=0):
    ext = os.path.splitext(path)[1]
    backend, spec = resolve(ext)
    with open(path, 'rb') as f:
        src = f.read()
    root = backend.root(src)
    return Classifier(spec).classify(root, level=1, depth=depth)


_OUTLINE_FULL_DEPTH = 64   # раскрыть landmark'и до конца; отображение режет адаптив core.py


def outline_rows(path, deep=False):
    """Unified-outline (Vision03): `.0`-строки для адаптивного outline в core.py.
    Landmark'и раскрыты вглубь. deep=False (`--outline`) — filler только на уровне файла;
    deep=True (диагностический `--dot`) — filler на ВСЕХ раскрытых уровнях. Строки несут
    флаги frame/filler (обе рисуются точкой; в подсчёт глубины/тэлли идут только landmark'и).
    Формат строки совпадает со старым handler.outline: {level,start,end,text,frame}."""
    backend, spec = resolve(os.path.splitext(path)[1])
    with open(path, 'rb') as f:
        root = backend.root(f.read())
    tree = Classifier(spec).classify(root, level=1, depth=_OUTLINE_FULL_DEPTH,
                                     top_filler_only=not deep)
    rows = []

    def walk(items):
        for b in items:
            text = b.name if b.name else '~' + b.kind + (f' x{b.count}' if b.count > 1 else '')
            rows.append({'level': b.level, 'start': b.start, 'end': b.end, 'text': text,
                         'frame': b.role is Role.FRAME, 'filler': b.role is Role.FILLER})
            if b.children:
                walk(b.children)

    walk(tree)
    return rows


def render(blocks, marker='#'):
    """Метка = обозначение УРОВНЯ. Отступ = глубина уровня (` ` * level). Символ:
    landmark — номер уровня (`1`/`2`), frame и filler — точка (`.`, «сам уровень/скоуп»,
    а не именованное определение). Точки и числа в одной колонке — консистентно.
    Диапазоны выровнены."""
    flat = []

    def walk(items):
        for b in items:
            indent = ' ' * b.level
            if b.role is Role.LANDMARK:
                sym, content = indent + str(b.level), b.name
            elif b.role is Role.FRAME:
                sym, content = indent + '.', b.name
            else:
                sym = indent + '.'
                if b.name:                              # лейбл-оглавление полосы (Vision03)
                    content = b.name
                else:
                    content = '~' + b.kind + (f' x{b.count}' if b.count > 1 else '')
            flat.append((sym, b.start, b.end, content, b.description))
            if b.children:
                walk(b.children)

    walk(blocks)
    symw = max((len(r[0]) for r in flat), default=0)
    out = []
    for sym, s, e, content, desc in flat:
        rng = f"[{s}-{e}]"
        line = f"{marker}{sym.ljust(symw)}  {rng:>10}  {content}"
        if desc:                                    # обогащение от Analyzer, если было
            line += f"  -- {desc}"
        out.append(line)
    return "\n".join(out)


def main():
    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    args = sys.argv[1:]
    if not args:
        print("usage: python -m get_codeblock.reader.classify FILE [--depth N]")
        return
    path = args[0]
    depth = int(args[args.index('--depth') + 1]) if '--depth' in args else 0
    print(f"//.0 (reader): {path}  (depth={depth})")
    print(render(classify_file(path, depth=depth)))


if __name__ == '__main__':
    main()
