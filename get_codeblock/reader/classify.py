"""Backend-agnostic .0-классификатор (Vision02/03) на протоколе.

Ровно та же механика, что в handlers/dot_classify.py, но работает через `Spec`+
`RNode`, не зная про tree-sitter. Порт — чтобы доказать, что классификатор
отвязывается от backend'а (шаг к core2 docx/pdf).
"""

import os
import re

from .ir import Block, Role
from .profiles.presets import NAME_TYPES
from .registry import resolve


# Признаки лицензионного блока — язык-независимо (по содержимому коммента, не по языку).
_LICENSE_RE = re.compile(
    r'SPDX-License-Identifier'
    r'|Copyright\s*(\(c\)|©|\d{4})'
    r'|Licensed under\b'
    r'|Permission is hereby granted'
    r'|Redistribution and use'
    r'|All rights reserved'
    r'|GNU (General|Lesser) Public License'
    r'|Apache License|MIT License|BSD [0-9-]*Clause',
    re.IGNORECASE)


def _comment_band_label(nodes):
    """Метка comment-полосы: `license block` если распознан лицензионный блок, иначе
    первая СОДЕРЖАТЕЛЬНАЯ строка (декоративные разделители пропускаются). Язык-независимо."""
    text = "\n".join(n.text() for n in nodes)
    if _LICENSE_RE.search(text):
        return 'license block'
    return _first_comment_line(nodes)


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

    def classify(self, scope, level, depth, top_filler_only=False, skip_leaf_names=False):
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
            if kind == 'comment':                          # коммент-полоса: 1-я значимая строка / license
                label = _comment_band_label(nodes)
            else:
                labeler = getattr(self.spec, 'filler_label', None)   # опц. (Vision03)
                label = labeler(nodes) if labeler is not None else None
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
            # Рамка без тела рекурсит СВОИ дети, среди которых её токен-имя (guard
            # `#ifndef NAME` → identifier, C#-namespace → qualified_name). Это не контент —
            # отсеваем, иначе имя рамки утекает отдельной filler-строкой `~identifier`.
            if skip_leaf_names and child.type in NAME_TYPES:
                continue
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
                # у рамки без тела дети = её собственные узлы (вкл. токен-имя) → отсеиваем его
                entry.children = self.classify(scope2, level, depth, top_filler_only,
                                               skip_leaf_names=(body is None))
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


def _is_focus_block(spec, node):
    """Узел-цель для фокуса = именованный блок (landmark) или прозрачная рамка."""
    return spec.unwrap_def(node) is not None or spec.unwrap_frame(node) is not None


def _owning_block(spec, children, line):
    """Focus-блок среди `children`, которому принадлежит `line` — С УЧЁТОМ ПРЕАМБУЛЫ:
    если строка попала на doc/коммент прямо над блоком (только комменты/пусто между),
    она принадлежит этому блоку (как в склейке). Иначе — блок, чей диапазон её содержит."""
    pre = None   # начало непрерывного коммент-рана перед текущим focus-блоком
    for ch in children:
        s, e = ch.start_row + 1, ch.end_row + 1
        if _is_focus_block(spec, ch):
            lo = pre if pre is not None else s     # диапазон + его преамбула
            if lo <= line <= e:
                return ch
            pre = None
        elif ch.type == 'comment':
            if pre is None:
                pre = s                            # старт коммент-рана (преамбула следующего блока)
        else:
            pre = None                             # код рвёт преамбулу
    return None


def _containing_chain(root, spec, line):
    """Цепочка объемлющих ИМЕНОВАННЫХ блоков строки `line`, внешний→внутренний. Спуск по
    reader-дереву (корректно, в отличие от старого get_blocks). Backend-agnostic."""
    chain, cur, guard = [], root, 0
    while guard < 512:
        guard += 1
        nxt = _owning_block(spec, cur.children(), line)
        if nxt is None:
            break
        chain.append(nxt)
        body = spec.body(nxt)
        if body is None:
            break
        cur = body
    return chain


def _pick_focus(chain, level):
    """Выбор цели из цепочки по --level (как core.resolve): 0=внутренний, +1=верхний (от файла),
    -N=на N вверх от внутреннего."""
    if not chain:
        return None
    if level == 0:
        return chain[-1]
    if level < 0:
        idx = len(chain) - 1 + level
        return chain[0] if idx < 0 else chain[idx]
    return chain[min(level - 1, len(chain) - 1)]


def _focus_head(spec, node, level):
    """Block-заголовок цели на её РЕАЛЬНОЙ файловой глубине `level` (не ре-базируем в 1 —
    иначе хедер/отступ врут о глубине). Тело раскрывается с level+1."""
    frame = spec.unwrap_frame(node)
    s, e = node.start_row + 1, node.end_row + 1
    if frame is not None:
        return Block(Role.FRAME, frame.type, s, e, level, name=spec.name(frame))
    return Block(Role.LANDMARK, spec.unwrap_def(node).type, s, e, level, name=spec.name(node))


def outline_rows(path, deep=False, focus_line=None, focus_level=0):
    """Unified-outline (Vision03): `.0`-строки для адаптивного outline в core.py.
    Landmark'и раскрыты вглубь. deep=False (`--outline`) — filler только на уровне файла;
    deep=True (диагностический `--dot`) — filler на ВСЕХ раскрытых уровнях. Строки несут
    флаги frame/filler (обе рисуются точкой; в подсчёт глубины/тэлли идут только landmark'и).
    Формат строки совпадает со старым handler.outline: {level,start,end,text,frame}.

    focus_line задан → карта ТОЛЬКО блока-цели (K-предок строки, K=focus_level): цель на
    уровне 1, её тело — вглубь. Решает монстро-классы: развернуть один блок как отдельный файл."""
    backend, spec = resolve(os.path.splitext(path)[1])
    with open(path, 'rb') as f:
        root = backend.root(f.read())
    clf = Classifier(spec)
    if focus_line is not None:
        chain = _containing_chain(root, spec, focus_line)
        target = _pick_focus(chain, focus_level)
        if target is None:
            tree = []
        else:
            base = chain.index(target) + 1     # РЕАЛЬНАЯ глубина цели в файле (не 1)
            head = _focus_head(spec, target, base)
            body = spec.body(target)
            if body is not None:
                head.children = clf.classify(body, level=base + 1, depth=_OUTLINE_FULL_DEPTH,
                                             top_filler_only=not deep)
            tree = [head]
    else:
        tree = clf.classify(root, level=1, depth=_OUTLINE_FULL_DEPTH, top_filler_only=not deep)
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
            dot = '.' + (str(b.level) if b.level > 1 else '')   # '.N' (N≥2); на уровне 1 голая '.'
            if b.role is Role.LANDMARK:
                sym, content = indent + str(b.level), b.name
            elif b.role is Role.FRAME:
                sym, content = indent + dot, b.name
            else:
                sym = indent + dot                      # '.N' — уровень без имени
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
