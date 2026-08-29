#!/usr/bin/env python3
"""Сборщик контекста: полная карточка цели + Public API её зависимостей — одним блоком.

Экономит ВЫЗОВЫ (action economy): вместо N чтений карточек агент делает один
вызов, а тул сам стягивает нужные карточки, режет из зависимостей только Public
API и склеивает. Толстый слой (API) тянется по требованию; тонкую топологию даёт
`graph_from_cards`.

Зависимости берутся из графа (`graph_from_cards.build_graph`) — колонка "From file".
`--depth N` разворачивает транзитивно (по умолчанию 1 — прямые зависимости).

Использование:
    python collect_card_bundle.py <file> [--cards-dir PATH] [--depth N]
Пример: python collect_card_bundle.py capture.py
По умолчанию карточки в <project>/__map/ (скрипт в __HQ/tools/).
"""

import argparse
import os
import sys
from pathlib import Path

import CARD_FORMAT as cf
from graph_from_cards import build_graph  # соседний модуль в __HQ/tools/


def _config_project_root():
    try:
        import CONFIG__TOOLS
        return getattr(CONFIG__TOOLS, "PROJECT_ROOT", None) or None
    except Exception:
        return None


def _resolve_project_root(value):
    """Card-тул: не задан -> неявно CONFIG__TOOLS.PROJECT_ROOT со sanity-check (корень обязан быть
    предком папки, где лежит сам тул); `@`/литерал -> явное решение автора вызова, без проверки.
    См. __dev/vision/Vision01__path-and-flag-conventions.md."""
    if value is None:
        cfg_root = _config_project_root()
        if cfg_root is None:
            return os.path.abspath(".")
        root_abs = os.path.abspath(cfg_root)
        here = os.path.dirname(os.path.abspath(__file__))
        if not (here == root_abs or here.startswith(root_abs + os.sep)):
            print(f"[collect_card_bundle] Error: CONFIG__TOOLS.PROJECT_ROOT ({root_abs}) doesn't "
                  f"contain this tool ({here}) — looks like a stale or foreign config. Pass "
                  f"--project-root explicitly (a path, or @ to force this value anyway).", file=sys.stderr)
            sys.exit(2)
        return root_abs
    if value == "@":
        cfg_root = _config_project_root()
        if cfg_root is None:
            print("[collect_card_bundle] Error: --project-root @ requires CONFIG__TOOLS.PROJECT_ROOT, "
                  "but it isn't set.", file=sys.stderr)
            sys.exit(2)
        return os.path.abspath(cfg_root)
    return os.path.abspath(value)


def _find_card(cards_dir, target):
    """target (root-relative id) -> (resolved_id, card_path) или (None, None)."""
    p = cards_dir / (target + ".md")
    if p.exists():
        return target, p
    base = target.split("/")[-1] + ".md"
    matches = [c for c in cards_dir.rglob("*.md") if "." in c.stem and c.name == base]
    if len(matches) == 1:
        return matches[0].relative_to(cards_dir).as_posix()[:-3], matches[0]
    return None, None


def api_slice(text):
    """H1 (имя+сводка) + секция Public API из карточки; остальное отброшено."""
    lines = text.splitlines()
    out = []
    for line in lines:
        if line.startswith("# ") and not line.startswith("## "):
            out.append(line.rstrip())
            break
    in_api = False
    for line in lines:
        s = line.strip()
        if s.startswith("## "):
            in_api = cf.canon(s[3:].strip()) == "Public API"
            if in_api:
                out.append(line.rstrip())
            continue
        if in_api:
            out.append(line.rstrip())
    return "\n".join(out).strip()


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Bundle a file's card + its deps' Public API", add_help=False)
    ap.add_argument("-h", "--help", action="help", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    ap.add_argument("target", nargs="?", help="файл (root-relative), напр. capture.py или _engine/embed.py")
    ap.add_argument("--file", dest="file_opt", default=None, help="алиас позиционного target, то же самое")
    ap.add_argument("--project-root", type=str, default=None,
                     help="корень проекта (база для <target>/--file и <root>/__map). Не задан -> "
                          "неявно CONFIG__TOOLS.PROJECT_ROOT (sanity-checked). '@' -> то же явно, "
                          "без проверки. Литерал -> буквально, без проверки.")
    ap.add_argument("--cards-dir", type=Path, default=None)
    ap.add_argument("--depth", type=int, default=1, help="глубина транзитивных зависимостей (по умолч. 1)")
    args = ap.parse_args()

    target = args.file_opt if args.file_opt is not None else args.target
    if not target:
        ap.error("target file required (positional <target> or --file)")

    project_root_abs = _resolve_project_root(args.project_root)
    cards_dir = args.cards_dir.resolve() if args.cards_dir else (Path(project_root_abs) / "__map")
    if not cards_dir.exists():
        print(f"cards dir not found: {cards_dir}", file=sys.stderr)
        sys.exit(1)

    tid, tpath = _find_card(cards_dir, target)
    if tid is None:
        print(f"no card for '{target}' under {cards_dir}", file=sys.stderr)
        sys.exit(1)

    nodes = build_graph(cards_dir)["nodes"]

    # BFS по зависимостям до глубины depth (порядок обхода, без дублей и без цели)
    seen = set()
    order = []
    frontier = [tid]
    for _ in range(max(1, args.depth)):
        nxt = []
        for x in frontier:
            for d in nodes.get(x, {}).get("deps", []):
                if d != tid and d not in seen:
                    seen.add(d)
                    order.append(d)
                    nxt.append(d)
        frontier = nxt
        if not frontier:
            break

    print(f"# collect_card_bundle: {tid}  (depth={args.depth}, {len(order)} deps)")
    print()
    print(f"===== TARGET: {tid} =====")
    print(tpath.read_text(encoding="utf-8").strip())
    for d in order:
        dp = cards_dir / (d + ".md")
        print()
        print(f"===== DEP: {d} (Public API) =====")
        if dp.exists():
            sl = api_slice(dp.read_text(encoding="utf-8"))
            print(sl if sl else "(no Public API section)")
        else:
            print("(card missing)")


if __name__ == "__main__":
    main()
