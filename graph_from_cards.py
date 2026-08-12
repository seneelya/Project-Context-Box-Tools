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

Виды карты (--view): packages (по пакетам, ДЕФОЛТ) | layers (0=листья→точки входа) | flat
(плоско, легаси). Оси: --edges both|out (показывать ли '← used-by'), --paths rel|full
(пути относительно пакета или полные). Фокус: --zone FILE [--depth N]; health: --cycles.

Использование:
    python graph_from_cards.py [--project-root PATH] [--view packages|layers|flat]
                               [--edges both|out] [--paths rel|full]
    python graph_from_cards.py --zone <file> [--depth N]      # фокус-срез вокруг модуля
    python graph_from_cards.py --cycles                       # циклы A → B → C → A
Карточки по умолчанию в <project-root>/__map/ (корень: флаг > CONFIG__TOOLS > cwd).
"""

import argparse
import json
import re
import sys
from pathlib import Path

import CARD_FORMAT as cf

_DASH = re.compile(r"\s+[—–-]\s+")   # legacy "# name — summary" separator


def resolve_project_root(cli_value):
    """Корень проекта. Приоритет: CLI-флаг > CONFIG__TOOLS.PROJECT_ROOT > cwd.
    Руками заданный путь всегда ГЛАВНЕЕ конфига. (Общий резолвер для тулов.)"""
    if cli_value is not None:
        return Path(cli_value).resolve()
    try:
        import CONFIG__TOOLS
        pr = getattr(CONFIG__TOOLS, "PROJECT_ROOT", None)
        if pr and pr != ".":
            return Path(pr).resolve()
    except Exception:
        pass
    return Path.cwd()


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


def _reverse(nodes):
    """id -> отсортированный список тех, кто ЗАВИСИТ от него (обратные рёбра)."""
    rdeps = {i: [] for i in nodes}
    for i, n in nodes.items():
        for d in n["deps"]:
            if d in rdeps:
                rdeps[d].append(i)
    return {i: sorted(v) for i, v in rdeps.items()}


def _resolve_id(nodes, want):
    """Точный id, иначе уникальный базовый путь (как в build_graph). None если не нашли/неоднозначно."""
    want = want.strip().lstrip("./")
    if want in nodes:
        return want
    cand = [i for i in nodes if i.split("/")[-1] == want.split("/")[-1]]
    return cand[0] if len(cand) == 1 else None


def _bfs(start, edges, depth):
    """Множество узлов в пределах `depth` рёбер от start по edges (не включая сам start)."""
    seen, frontier = set(), {start}
    for _ in range(depth):
        nxt = set()
        for u in frontier:
            for v in edges.get(u, []):
                if v not in seen and v != start:
                    seen.add(v)
                    nxt.add(v)
        frontier = nxt
        if not frontier:
            break
    return seen


def zone(graph, center, depth):
    """Фокус-срез вокруг center: downstream (что тянет) + upstream (кто тянет), <= depth."""
    nodes = graph["nodes"]
    rdeps = _reverse(nodes)
    deps = {i: n["deps"] for i, n in nodes.items()}
    down = _bfs(center, deps, depth)
    up = _bfs(center, rdeps, depth)
    return {"center": center, "depth": depth, "down": down, "up": up, "rdeps": rdeps}


def format_zone(graph, z):
    nodes, rdeps = graph["nodes"], z["rdeps"]
    c = z["center"]

    def line(i):
        s = nodes[i]["summary"]
        return f"{i} — {s}" if s and not s.startswith("<Agent:") else i

    out = [f"# zone: {c}  (depth {z['depth']}; {len(z['down'])} downstream, {len(z['up'])} upstream)", ""]
    out += ["## center", line(c),
            f"  uses -> {', '.join(nodes[c]['deps']) or '(none)'}",
            f"  used-by <- {', '.join(rdeps[c]) or '(none)'}", ""]

    out.append(f"## downstream (what {c} transitively depends on, <={z['depth']})")
    for i in sorted(z["down"]):
        out.append(line(i))
        if nodes[i]["deps"]:
            out.append(f"    -> {', '.join(nodes[i]['deps'])}")
    if not z["down"]:
        out.append("(none)")

    out += ["", f"## upstream (what transitively depends on {c}, <={z['depth']})"]
    for i in sorted(z["up"]):
        out.append(line(i))
        if rdeps[i]:
            out.append(f"    <- {', '.join(rdeps[i])}")
    if not z["up"]:
        out.append("(none)")
    return "\n".join(out)


def find_cycles(nodes):
    """Элементарные циклы в графе зависимостей. -> [[a,b,c,a], ...] (дедуп по ротации)."""
    deps = {i: n["deps"] for i, n in nodes.items()}
    cycles, seen = [], set()

    def canon(cyc):  # cyc без замыкающего повтора; каноним ротацией от мин-элемента
        core = cyc[:-1]
        k = core.index(min(core))
        rot = tuple(core[k:] + core[:k])
        return rot

    stack, onstack = [], set()

    def dfs(u):
        stack.append(u)
        onstack.add(u)
        for v in deps.get(u, []):
            if v == u:
                continue
            if v in onstack:                       # нашли обратное ребро -> цикл
                cyc = stack[stack.index(v):] + [v]
                key = canon(cyc)
                if key not in seen:
                    seen.add(key)
                    cycles.append(list(key) + [key[0]])
            elif v not in visited:
                dfs(v)
        stack.pop()
        onstack.discard(u)
        visited.add(u)

    visited = set()
    for start in sorted(nodes):
        if start not in visited:
            dfs(start)
    return cycles


def format_cycles(nodes, cycles):
    out = ["# cycles (circular internal dependencies)"]
    if not cycles:
        return out[0] + "\n\n(none — graph is acyclic)"
    out.append("")
    for cyc in sorted(cycles, key=lambda c: (len(c), c)):
        out.append(" → ".join(cyc))
    out += ["", f"total: {len(cycles)} cycle(s)"]
    return "\n".join(out)


# --- structured views: packages / layers (flat = format_text below) ---------

def _top_pkg(nid):
    """Верхний пакет узла: '_engine/...' -> '_engine/', корневой файл -> '(root)'."""
    return nid.split("/", 1)[0] + "/" if "/" in nid else "(root)"


def _rel_to(dep, pkg, paths):
    """Путь зависимости: относительно пакета (тише) либо полный."""
    if paths == "full" or pkg == "(root)":
        return dep
    return dep[len(pkg):] if dep.startswith(pkg) else dep


def _cycle_nodes(nodes):
    s = set()
    for cyc in find_cycles(nodes):
        s.update(cyc)
    return s


def _summ(nodes, i):
    s = nodes[i]["summary"]
    return f" — {s}" if s and not s.startswith("<Agent:") else ""


def _edge_bits(i, nodes, rdeps, pkg, edges, paths):
    """Строка рёбер узла: '→ …' и (если both) '← ×N …'."""
    bits = []
    if nodes[i]["deps"]:
        bits.append("→ " + " · ".join(_rel_to(d, pkg, paths) for d in nodes[i]["deps"]))
    if edges == "both" and rdeps[i]:
        bits.append(f"← ×{len(rdeps[i])} " + " · ".join(_rel_to(d, pkg, paths) for d in rdeps[i]))
    return "   ".join(bits)


def _compute_layers(nodes):
    """Слой узла: 0 = лист (нет внутр. deps), выше = ближе к точкам входа.
    Обратные рёбра циклов игнорируются (иначе слои не определены)."""
    deps = {i: nodes[i]["deps"] for i in nodes}
    memo, stack = {}, set()

    def lvl(n):
        if n in memo:
            return memo[n]
        stack.add(n)
        best = 0
        for d in deps.get(n, []):
            if d in stack or d not in deps:   # back-edge цикла / чужой id — пропустить
                continue
            best = max(best, lvl(d) + 1)
        stack.discard(n)
        memo[n] = best
        return best

    for n in nodes:
        lvl(n)
    layers = {}
    for n, l in memo.items():
        layers.setdefault(l, []).append(n)
    return layers


def _slices(graph, disp_label):
    """Общий хвост всех видов: hotspots + cycles + unresolved."""
    nodes, indeg = graph["nodes"], graph["indeg"]
    out = ["", "## hotspots"]
    ep = [f"{i} ×{indeg[i]}" for i in sorted(nodes, key=lambda i: (-indeg[i], i)) if indeg[i] > 0][:8]
    out.append("- most depended-on: " + (" · ".join(ep) if ep else "(none)"))
    leaves = sorted(i for i, n in nodes.items() if not n["deps"])
    out.append("- leaves (no deps): " + (" · ".join(leaves) if leaves else "(none)"))

    cycles = find_cycles(nodes)
    out += ["", f"## cycles ({len(cycles)})"]
    out += (["- " + " → ".join(c) for c in sorted(cycles, key=lambda c: (len(c), c))]
            if cycles else ["(none — acyclic)"])

    if graph["unresolved"]:
        out += ["", "## unresolved from-file refs (normalize to a card path)"]
        out += [f'- "{raw}" (in {nid})' for nid, raw in sorted(set(graph["unresolved"]))]
    return out


_LEGEND = "> → uses · ← used-by(N) · ⟲ in a cycle"


def format_packages(graph, disp, edges, paths):
    nodes, rdeps, cyc = graph["nodes"], _reverse(graph["nodes"]), _cycle_nodes(graph["nodes"])
    out = [f"# map — {len(nodes)} modules · packages (dir={disp})", _LEGEND, ""]
    pkgs = {}
    for i in nodes:
        pkgs.setdefault(_top_pkg(i), []).append(i)
    for pkg in sorted(pkgs):
        members = sorted(pkgs[pkg])
        out.append(f"## {pkg} ({len(members)})")
        for i in members:
            label = _rel_to(i, pkg, paths)
            out.append(f"- **{label}**{' ⟲' if i in cyc else ''}{_summ(nodes, i)}")
            eb = _edge_bits(i, nodes, rdeps, pkg, edges, paths)
            if eb:
                out.append(f"  {eb}")
        out.append("")
    return "\n".join(out + _slices(graph, disp))


def format_layers(graph, disp, edges, paths):
    nodes, rdeps, cyc = graph["nodes"], _reverse(graph["nodes"]), _cycle_nodes(graph["nodes"])
    layers = _compute_layers(nodes)
    out = [f"# map — {len(nodes)} modules · layers 0=leaves (dir={disp})", _LEGEND, ""]
    for l in sorted(layers):
        members = sorted(layers[l])
        out.append(f"## layer {l} ({len(members)})")
        for i in members:
            out.append(f"- **{i}**{' ⟲' if i in cyc else ''}{_summ(nodes, i)}")
            eb = _edge_bits(i, nodes, rdeps, "(root)", edges, paths)  # слои cross-cutting -> пути как заданы
            if eb:
                out.append(f"  {eb}")
        out.append("")
    return "\n".join(out + _slices(graph, disp))


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
    ap = argparse.ArgumentParser(description="Flat project topology from __map/ cards", add_help=False)
    ap.add_argument("-h", "--help", action="help", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    ap.add_argument("--cards-dir", type=Path, default=None, help="карточки (по умолч. <project-root>/__map)")
    ap.add_argument("--project-root", type=Path, default=None,
                    help="корень проекта для <root>/__map. Приоритет: флаг > CONFIG__TOOLS.PROJECT_ROOT > cwd")
    ap.add_argument("--json", action="store_true", help="выдать граф как JSON вместо плоского текста")
    ap.add_argument("--zone", metavar="FILE", default=None,
                    help="фокус-срез вокруг модуля: что он тянет (downstream) + кто тянет его (upstream)")
    ap.add_argument("--depth", type=int, default=1, help="глубина зоны в рёбрах (по умолч. 1)")
    ap.add_argument("--cycles", action="store_true",
                    help="детекция циклических зависимостей, вывод цепочками A → B → C → A")
    ap.add_argument("--view", choices=["packages", "layers", "flat"], default="packages",
                    help="структура карты: packages (по пакетам, дефолт) | layers (0=листья) | flat (плоско)")
    ap.add_argument("--edges", choices=["both", "out"], default="both",
                    help="both — показывать и '← used-by' (дефолт); out — только '→ uses'")
    ap.add_argument("--paths", choices=["rel", "full"], default="rel",
                    help="rel — пути относительно пакета (тише, дефолт); full — всегда полные")
    args = ap.parse_args()

    cards_dir = args.cards_dir.resolve() if args.cards_dir else (resolve_project_root(args.project_root) / "__map")
    if not cards_dir.exists():
        print(f"cards dir not found: {cards_dir}", file=sys.stderr)
        sys.exit(1)

    graph = build_graph(cards_dir)
    if not graph["nodes"]:
        print(f"no cards in {cards_dir}")
        sys.exit(0)

    if args.cycles:
        print(format_cycles(graph["nodes"], find_cycles(graph["nodes"])))
        return

    if args.zone:
        center = _resolve_id(graph["nodes"], args.zone)
        if not center:
            print(f"zone: '{args.zone}' — no such card (need a root-relative path or a unique basename)",
                  file=sys.stderr)
            sys.exit(1)
        z = zone(graph, center, max(1, args.depth))
        if args.json:
            print(json.dumps({"center": center, "depth": z["depth"],
                              "downstream": sorted(z["down"]), "upstream": sorted(z["up"])},
                             ensure_ascii=False, indent=2))
        else:
            print(format_zone(graph, z))
        return

    if args.json:
        print(json.dumps({"nodes": graph["nodes"], "unresolved": graph["unresolved"]},
                         ensure_ascii=False, indent=2))
        return

    try:
        disp = cards_dir.relative_to(cards_dir.parent).as_posix()
    except ValueError:
        disp = str(cards_dir)
    if args.view == "packages":
        print(format_packages(graph, disp, args.edges, args.paths))
    elif args.view == "layers":
        print(format_layers(graph, disp, args.edges, args.paths))
    else:
        print(format_text(graph, disp))


if __name__ == "__main__":
    main()
