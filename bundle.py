#!/usr/bin/env python3
"""Сборщик контекста: полная карточка цели + Public API её зависимостей — одним блоком.

Экономит ВЫЗОВЫ (action economy): вместо N чтений карточек агент делает один
вызов, а тул сам стягивает нужные карточки, режет из зависимостей только Public
API и склеивает. Толстый слой (API) тянется по требованию; тонкую топологию даёт
`rebuild_graph`.

Зависимости берутся из графа (`rebuild_graph.build_graph`) — колонка "From file".
`--depth N` разворачивает транзитивно (по умолчанию 1 — прямые зависимости).

Использование:
    python bundle.py <file> [--cards-dir PATH] [--depth N]
Пример: python bundle.py capture.py
По умолчанию карточки в <project>/__map/ (скрипт в __HQ/tools/).
"""

import argparse
import sys
from pathlib import Path

import card_format as cf
from rebuild_graph import build_graph  # соседний модуль в __HQ/tools/


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
    ap = argparse.ArgumentParser(description="Bundle a file's card + its deps' Public API")
    ap.add_argument("target", help="файл (root-relative), напр. capture.py или _engine/embed.py")
    ap.add_argument("--cards-dir", type=Path, default=None)
    ap.add_argument("--depth", type=int, default=1, help="глубина транзитивных зависимостей (по умолч. 1)")
    args = ap.parse_args()

    cards_dir = args.cards_dir.resolve() if args.cards_dir else (Path.cwd() / "__map")
    if not cards_dir.exists():
        print(f"cards dir not found: {cards_dir}", file=sys.stderr)
        sys.exit(1)

    tid, tpath = _find_card(cards_dir, args.target)
    if tid is None:
        print(f"no card for '{args.target}' under {cards_dir}", file=sys.stderr)
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

    print(f"# bundle: {tid}  (depth={args.depth}, {len(order)} deps)")
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
