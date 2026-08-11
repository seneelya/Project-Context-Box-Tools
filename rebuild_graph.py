#!/usr/bin/env python3
"""Плоская топология проекта из карточек __map/ («вторая компиляция»).

Из каждой карточки достаёт: id (root-relative путь исходника = путь карточки без
`.md`), однострочную сводку (из H1 `# name<ext> — summary`) и depends_on (колонка
"From file" таблицы "Internal dependencies"). Выдаёт СКУПОЙ плоский текст: модули
со сводками и зависимостями + производные срезы (точки входа, листья). Агент
грузит это один раз и дальше рассуждает сам — impact/chain/layers в уме.

Колонка "From file" детектится по имени заголовка (англ. "From file" или
рус. "Из файла"), так что тул работает и на старых карточках. Ссылки, которые не
удалось сопоставить карточке, честно выводятся в конце (сигнал к нормализации).

Использование:
    python rebuild_graph.py [--cards-dir PATH] [--json]
По умолчанию карточки в <project>/__map/ (скрипт в __HQ/tools/).
"""

import argparse
import json
import re
import sys
from pathlib import Path

import card_format as cf

_DASH = re.compile(r"\s+[—–-]\s+")   # legacy "# name — summary" separator


def _cells(row):
    """'| a | b | c |' -> ['a','b','c'] (снятые бэктики/пробелы)."""
    return [c.strip().strip("`").strip() for c in row.strip().strip("|").split("|")]


def _is_sep(cells):
    return bool(cells) and all(c and set(c) <= set("-: ") for c in cells)


def parse_card(path, cards_dir):
    """-> {'id', 'summary', 'deps_raw': [<File Path строки>]}. Держит и новую форму
    (сводка на 2-й строке), и легаси (`# name — summary`)."""
    node_id = path.relative_to(cards_dir).as_posix()[:-3]  # без '.md'
    summary = ""
    name_seen = False
    deps_raw = []
    in_deps = False
    col_idx = 1
    header_seen = False

    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not name_seen and s.startswith("# ") and not s.startswith("## "):
            name_seen = True
            head = s[2:].strip()
            if _DASH.search(head):                       # легаси: "# name — summary"
                summary = _DASH.split(head, 1)[1].strip()
            continue
        if name_seen and not summary and s and not s.startswith("#"):
            summary = s                                  # новая форма: сводка на след. строке
        if s.startswith("## "):
            in_deps = cf.canon(s[3:].strip()) == "Dependencies Internal"
            header_seen = False
            continue
        if in_deps and s.startswith("|"):
            cells = _cells(line)
            if _is_sep(cells):
                continue
            if not header_seen:                          # строка заголовка таблицы
                header_seen = True
                for i, c in enumerate(cells):
                    if cf.canon(c) == cf.EDGE_COLUMN:
                        col_idx = i
                        break
                continue
            if col_idx < len(cells):
                val = cells[col_idx]
                if val and not cf.is_empty(val):
                    deps_raw.append(val)
    return {"id": node_id, "summary": summary, "deps_raw": deps_raw}


def build_graph(cards_dir):
    """-> {'nodes': {id: {summary, deps:[id]}}, 'indeg': {id:int}, 'unresolved': [(id, raw)]}."""
    # карточка = '<name>.<ext>.md' (в stem есть точка); отсекает отчёты вроде _cards_summary_report.md
    cards = [p for p in cards_dir.rglob("*.md") if "." in p.stem]
    parsed = {}
    for p in cards:
        c = parse_card(p, cards_dir)
        parsed[c["id"]] = c

    ids = set(parsed)
    by_base = {}
    for i in ids:
        by_base.setdefault(i.split("/")[-1], []).append(i)

    nodes = {}
    unresolved = []
    for nid, c in parsed.items():
        deps = set()
        for raw in c["deps_raw"]:
            tok = raw.split()[0] if raw.split() else raw   # отбросить " (lazy)" и пр.
            tok = tok.strip().lstrip("./")
            if tok in ids:
                deps.add(tok)
                continue
            cand = by_base.get(tok.split("/")[-1], [])
            if len(cand) == 1:
                deps.add(cand[0])
            else:
                unresolved.append((nid, raw))
        deps.discard(nid)
        nodes[nid] = {"summary": c["summary"], "deps": sorted(deps)}

    indeg = {i: 0 for i in nodes}
    for n in nodes.values():
        for d in n["deps"]:
            if d in indeg:
                indeg[d] += 1
    return {"nodes": nodes, "indeg": indeg, "unresolved": unresolved}


def format_text(graph, cards_dir_display):
    nodes, indeg, unresolved = graph["nodes"], graph["indeg"], graph["unresolved"]
    out = [f"# map: {len(nodes)} modules (dir={cards_dir_display})", "", "## modules"]
    for i in sorted(nodes):
        n = nodes[i]
        out.append(f"{i} — {n['summary']}" if n["summary"] else i)
        if n["deps"]:
            out.append(f"    -> {', '.join(n['deps'])}")

    ep = [f"{i} ({indeg[i]})" for i in sorted(nodes, key=lambda i: (-indeg[i], i)) if indeg[i] > 0][:8]
    out += ["", "## entry points (most depended-on)", ", ".join(ep) if ep else "(none)"]

    leaves = sorted(i for i, n in nodes.items() if not n["deps"])
    out += ["", "## leaves (no internal deps)", ", ".join(leaves) if leaves else "(none)"]

    if unresolved:
        out += ["", "## unresolved from-file refs (normalize to a card path)"]
        out += [f'  "{raw}" (in {nid})' for nid, raw in sorted(set(unresolved))]
    return "\n".join(out)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # карт-сводки бывают с юникодом (→, кириллица)
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Flat project topology from __map/ cards")
    ap.add_argument("--cards-dir", type=Path, default=None, help="карточки (по умолч. <project>/__map/)")
    ap.add_argument("--json", action="store_true", help="выдать граф как JSON вместо плоского текста")
    args = ap.parse_args()

    cards_dir = args.cards_dir.resolve() if args.cards_dir else (Path.cwd() / "__map")
    if not cards_dir.exists():
        print(f"cards dir not found: {cards_dir}", file=sys.stderr)
        sys.exit(1)

    graph = build_graph(cards_dir)
    if not graph["nodes"]:
        print(f"no cards in {cards_dir}")
        sys.exit(0)

    if args.json:
        print(json.dumps({"nodes": graph["nodes"], "unresolved": graph["unresolved"]},
                         ensure_ascii=False, indent=2))
    else:
        try:
            disp = cards_dir.relative_to(cards_dir.parent).as_posix()
        except ValueError:
            disp = str(cards_dir)
        print(format_text(graph, disp))


if __name__ == "__main__":
    main()
