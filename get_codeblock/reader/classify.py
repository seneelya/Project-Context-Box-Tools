"""Backend-agnostic .0-классификатор (Vision02/03) на протоколе.

Ровно та же механика, что в handlers/dot_classify.py, но работает через `Spec`+
`RNode`, не зная про tree-sitter. Порт — чтобы доказать, что классификатор
отвязывается от backend'а (шаг к core2 docx/pdf).
"""

import os

from .ir import Block, Role
from .registry import resolve


class Classifier:
    def __init__(self, spec):
        self.spec = spec

    def classify(self, scope, level, depth):
        """Классифицировать прямых детей scope на уровне `level`. depth>0 —
        рекурсивно раскрыть тела landmark-ов на уровень глубже."""
        out = []
        run = None   # filler-полоса: [kind, start, end, count]

        def flush():
            nonlocal run
            if run is not None:
                out.append(Block(Role.FILLER, run[0], run[1], run[2], level, count=run[3]))
                run = None

        for child in scope.children():
            s = child.start_row + 1
            e = child.end_row + 1
            frame = self.spec.unwrap_frame(child)
            defn = None if frame is not None else self.spec.unwrap_def(child)

            if frame is None and defn is None:            # filler
                kind = self.spec.filler_kind(child)
                if run is not None and run[0] == kind:
                    run[2] = e
                    run[3] += 1
                else:
                    flush()
                    run = [kind, s, e, 1]
                continue

            flush()

            if frame is not None:                         # рамка: дети всплывают (тот же level)
                entry = Block(Role.FRAME, frame.type, s, e, level, name=self.spec.name(frame))
                body = self.spec.body(frame)
                scope2 = body if body is not None else frame
                entry.children = self.classify(scope2, level, depth)
                out.append(entry)
            else:                                         # landmark: имя от внешнего узла (с export/deco)
                entry = Block(Role.LANDMARK, defn.type, s, e, level, name=self.spec.name(child))
                if depth > 0:
                    body = self.spec.body(child)
                    if body is not None:
                        entry.children = self.classify(body, level + 1, depth - 1)
                out.append(entry)

        flush()
        return out


def classify_file(path, depth=0):
    ext = os.path.splitext(path)[1]
    backend, spec = resolve(ext)
    with open(path, 'rb') as f:
        src = f.read()
    root = backend.root(src)
    return Classifier(spec).classify(root, level=1, depth=depth)


def render(blocks, marker='#'):
    lines = []

    def walk(items, indent):
        pad = '  ' * indent
        for b in items:
            rng = f"[{b.start}-{b.end}]"
            if b.role is Role.LANDMARK:
                body = f"L{b.level}  {rng:>10}  {b.name}"
            elif b.role is Role.FRAME:
                body = f".   {rng:>10}  {b.name}"
            else:
                tag = f"~{b.kind}" + (f" x{b.count}" if b.count > 1 else "")
                body = f"    {rng:>10}  {tag}"
            if b.description:                       # обогащение от Analyzer, если было
                body += f"   « {b.description} »"
            lines.append(f"{marker}{pad}{body}")
            if b.children:
                walk(b.children, indent + 1)

    walk(blocks, 0)
    return "\n".join(lines)


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
