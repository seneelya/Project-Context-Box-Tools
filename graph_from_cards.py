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

Виды карты (--view): tree (по дереву каталогов, ДЕФОЛТ) | depth (0=листья→точки входа).
Ось --edges: out (только '→') | in (только '←') | inout (обе стороны, ДЕФОЛТ).
Плотность --verbose: 0 (только модули+связи) | 1 (с описаниями, ДЕФОЛТ).
Фокус: --file PATH [--hops N]; health: --cycles; coverage: --discrepancies.

Использование:
    python graph_from_cards.py [--project-root PATH] [--view tree|depth]
                               [--edges out|in|inout] [--verbose 0|1]
    python graph_from_cards.py [--file <path> [--hops N]]     # фокус-срез (радиус только с --file)
    python graph_from_cards.py --cycles                       # циклы A → B → C → A
    python graph_from_cards.py --discrepancies [--group-by kind|package|card]
                                                              # свод «карта vs реальность»
Карточки по умолчанию в <project-root>/__map/ (корень: флаг > CONFIG__TOOLS > cwd).
"""

import argparse
import json
import re
import sys
from collections import namedtuple
from pathlib import Path

import CARD_FORMAT as cf

try:
    import termstyle
except ImportError:                         # утилиты нет -> работаем без краски, не падаем
    class termstyle:                        # noqa: N801 (shim под именем модуля)
        @staticmethod
        def md(text):
            return text

_DASH = re.compile(r"\s+[—–-]\s+")   # legacy "# name — summary" separator


def resolve_project_root(cli_value):
    """Корень проекта для card-тулов (`__map/` не существует «относительно cwd»).
    Общий резолвер для тесно связанного семейства `graph_from_cards`/`validate_cards`/
    `check_cards_freshness` (не для всего пакета — generic-тулы резолвят иначе, см.
    __dev/vision/Vision01__path-and-flag-conventions.md).

    - не задан -> неявно `CONFIG__TOOLS.PROJECT_ROOT`, со sanity-check: резолвленный корень
      обязан быть предком папки, где лежит сам тул — иначе это протухший/чужой конфиг, отказ,
      а не тихая работа не пойми над чем;
    - `"@"` -> то же самое, явно, БЕЗ проверки — пользователь осознанно так решил;
    - литеральный путь -> буквально, без проверки.
    """
    if cli_value is not None and str(cli_value) != "@":
        return Path(cli_value).resolve()

    cfg_root = None
    try:
        import CONFIG__TOOLS
        cfg_root = getattr(CONFIG__TOOLS, "PROJECT_ROOT", None) or None
    except Exception:
        pass

    if str(cli_value) == "@":
        if cfg_root is None:
            sys.stderr.write("Error: --project-root @ requires CONFIG__TOOLS.PROJECT_ROOT, "
                              "but it isn't set.\n")
            sys.exit(2)
        return Path(cfg_root).resolve()

    # cli_value is None: неявный путь — с проверкой на вменяемость.
    if cfg_root is None:
        return Path.cwd()
    root_abs = Path(cfg_root).resolve()
    here = Path(__file__).resolve().parent
    if not (here == root_abs or root_abs in here.parents):
        sys.stderr.write(
            f"Error: CONFIG__TOOLS.PROJECT_ROOT ({root_abs}) doesn't contain this tool ({here}) "
            f"— looks like a stale or foreign config. Pass --project-root explicitly "
            f"(a path, or @ to force this value anyway).\n")
        sys.exit(2)
    return root_abs


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


def file_zone(graph, center, depth):
    """Фокус-срез вокруг center: downstream (что тянет) + upstream (кто тянет), <= depth."""
    nodes = graph["nodes"]
    rdeps = _reverse(nodes)
    deps = {i: n["deps"] for i, n in nodes.items()}
    down = _bfs(center, deps, depth)
    up = _bfs(center, rdeps, depth)
    return {"center": center, "depth": depth, "down": down, "up": up, "rdeps": rdeps}


def format_file_zone(graph, z, verbose=1):
    nodes, rdeps = graph["nodes"], z["rdeps"]
    c = z["center"]

    def line(i):
        s = nodes[i]["summary"]
        return f"{i} — {s}" if verbose >= 1 and s and not cf.is_agent_directive(s) else i

    out = [f"# file: {c}  (hops {z['depth']}; {len(z['down'])} downstream, {len(z['up'])} upstream)",
           _orient_file(verbose), ""]
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


def _fmt_cycle(cyc):
    """Цепочка цикла с обрамляющими стрелками — показывает, что она замыкается: → A → B → A →."""
    return "→ " + " → ".join(cyc) + " →"


def format_cycles(nodes, cycles):
    out = ["# cycles (circular internal dependencies)", _ORIENT_CYCLES, ""]
    if not cycles:
        out.append("(none — graph is acyclic)")
        return "\n".join(out)
    for cyc in sorted(cycles, key=lambda c: (len(c), c)):
        out.append(_fmt_cycle(cyc))
    out += ["", f"total: {len(cycles)} cycle(s)"]
    return "\n".join(out)


# --- structured views: packages / layers -------------------------------------

def _top_pkg(nid):
    """Верхний пакет узла: '_engine/...' -> '_engine/', корневой файл -> '(root)'."""
    return nid.split("/", 1)[0] + "/" if "/" in nid else "(root)"


def _rel_to(dep, pkg):
    """Путь зависимости относительно пакета (тише); в layers pkg='(root)' -> полный."""
    if pkg == "(root)":
        return dep
    return dep[len(pkg):] if dep.startswith(pkg) else dep


def _cycle_nodes(nodes):
    s = set()
    for cyc in find_cycles(nodes):
        s.update(cyc)
    return s


def _summ(nodes, i, verbose=1):
    if verbose < 1:                        # --verbose 0: только модули+связи, без описаний
        return ""
    s = nodes[i]["summary"]
    return f" — {s}" if s and not cf.is_agent_directive(s) else ""


def _seg(arrow, ids, pkg):
    """Одна сторона рёбер. 1 элемент -> '→ name' (без ×, без скобок);
    ≥2 -> '→ ×N (a · b · c)' (× считает перечисленные в скобках). Симметрично для → и ←."""
    names = [_rel_to(d, pkg) for d in ids]
    if len(names) == 1:
        return f"{arrow} {names[0]}"
    return f"{arrow} ×{len(names)} (" + " · ".join(names) + ")"


def _edge_bits(i, nodes, rdeps, pkg, edges):
    """Строка рёбер узла: '→' (uses, out/inout) и/или '←' (used-by, in/inout)."""
    bits = []
    if edges in ("out", "inout") and nodes[i]["deps"]:
        bits.append(_seg("→", nodes[i]["deps"], pkg))
    if edges in ("in", "inout") and rdeps[i]:
        bits.append(_seg("←", rdeps[i], pkg))
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


def components(nodes):
    """Связные компоненты по НЕОРИЕНТИРОВАННЫМ import-рёбрам, крупные первыми.

    Зачем: в одном дереве законно живут независимые части — второй плагин, или
    JS-фронтенд к нашему же питон-бэкенду. Между ними НЕТ import-ребра, и его
    не должно быть: их связь — рантайм-контракт (тип события, REST-путь), а не
    импорт. Выдумывать такое ребро в графе значило бы показывать догадку как
    факт. Поэтому мы не соединяем компоненты, а НАЗЫВАЕМ их — чтобы «так и
    задумано» отличалось от «связь потерялась».
    """
    adj = {i: set() for i in nodes}
    for i, n in nodes.items():
        for d in n["deps"]:
            if d in adj:
                adj[i].add(d)
                adj[d].add(i)
    seen, comps = set(), []
    for start in sorted(nodes):
        if start in seen:
            continue
        stack, comp = [start], []
        seen.add(start)
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for nxt in sorted(adj[cur]):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        comps.append(sorted(comp))
    return sorted(comps, key=lambda c: (-len(c), c[0]))


def _comp_label(comp):
    """Компонент -> 'top_pkg+top_pkg (N)' — по каким верхним пакетам он лежит."""
    pkgs = []
    for nid in comp:
        p = _top_pkg(nid)
        if p not in pkgs:
            pkgs.append(p)
    return f"{'+'.join(pkgs)} ({len(comp)})"


def _comp_labels(comps):
    """Метки компонентов, гарантированно РАЗЛИЧИМЫЕ.

    Два компонента внутри одного пакета дают одинаковую метку
    ('self_delegate/ (2)' и 'self_delegate/ (1)'), и вывод читается как
    дубликат. Совпавшим дописываем представителя.
    """
    labels = [_comp_label(c) for c in comps]
    seen = {}
    for lb in labels:
        seen[lb] = seen.get(lb, 0) + 1
    return [f"{lb} [{c[0]}]" if seen[lb] > 1 else lb for lb, c in zip(labels, comps)]


def split_components(nodes):
    """(связные части из >1 модуля, одиночные модули без рёбер).

    Разделение осознанное: НЕСКОЛЬКО СВЯЗНЫХ ЧАСТЕЙ — это про архитектуру
    (отдельный плагин, JS-фронтенд к этому же бэкенду), а одиночный файл без
    рёбер — просто ни с чем не связанный файл (скрипт, индекс пакета). Сваливать
    их в один счётчик значит превращать полезное наблюдение в шум: у нас так
    вышло «4 компонента» там, где независимых частей две.
    """
    comps = components(nodes)
    multi = [c for c in comps if len(c) > 1]
    singles = [c[0] for c in comps if len(c) == 1]
    return multi, singles


def _slices(graph, disp_label):
    """Общий хвост всех видов: hotspots + cycles + unresolved."""
    nodes, indeg = graph["nodes"], graph["indeg"]
    multi, singles = split_components(nodes)
    out = ["", "## hotspots"]
    ep = [f"{i} ← ×{indeg[i]}" for i in sorted(nodes, key=lambda i: (-indeg[i], i)) if indeg[i] > 0][:8]
    out.append("- most depended-on: " + (" · ".join(ep) if ep else "(none)"))
    # Листья — предлагаемый ПОРЯДОК ЧТЕНИЯ, поэтому при нескольких независимых
    # частях один общий список врёт: он подсовывает файлы чужой части как начало
    # чтения нашей. Разносим по частям; одиночные файлы идут отдельной строкой,
    # потому что они и лист, и корень одновременно — в порядке чтения им не место.
    if len(multi) > 1:
        labels = _comp_labels(multi)
        out.append(f"- independent parts: {len(multi)} — " + " · ".join(labels))
        for c, lb in zip(multi, labels):
            cl = sorted(i for i in c if not nodes[i]["deps"])
            out.append(f"- leaves in {lb}: " + (" · ".join(cl) if cl else "(none)"))
    else:
        leaves = sorted(i for i, n in nodes.items()
                        if not n["deps"] and i not in set(singles))
        out.append("- leaves (no deps): " + (" · ".join(leaves) if leaves else "(none)"))
    if singles:
        out.append(f"- isolated files ({len(singles)}, no import edge either way): "
                   + " · ".join(sorted(singles)))

    cycles = find_cycles(nodes)
    out += ["", f"## cycles ({len(cycles)})"]
    out += (["- " + _fmt_cycle(c) for c in sorted(cycles, key=lambda c: (len(c), c))]
            if cycles else ["(none — acyclic)"])

    if graph["unresolved"]:
        out += ["", "## unresolved from-file refs (normalize to a card path)"]
        out += [f'- "{raw}" (in {nid})' for nid, raw in sorted(set(graph["unresolved"]))]
    return out


# «Как читать эту карту» — мета-шапка под H1 каждого режима (термстайл красит '>' серым).
# Анатомия записи — единая, чтобы не расходилась между видами; строка entry зависит от --verbose.
_EDGES = ("> edges:  → what it imports · ← what imports it · ×N before (…) = list length "
          "(shown only when >1) · ⟲ = in a cycle")
_SEP = "> ---"


def _entry_line(verbose):
    return ("> entry:  - <module> — <one-line summary from the module's card>" if verbose >= 1
            else "> entry:  - <module>   (summaries hidden at --verbose 0; --verbose 1 to show)")


# «other views» — ТОЛЬКО альтернативные режимы карты (исключаем текущий). --edges/--verbose/--file
# это ФИЛЬТРЫ вывода, а не режимы — они идут отдельной строкой «filters».
_VIEW_OPTS = [
    ("depth", "--view depth (by dependency depth: 0=leaves)"),
    ("tree", "--view tree (group by directory tree)"),
    ("cycles", "--cycles (circular deps)"),
    ("discrepancies", "--discrepancies (map vs source)"),
]
_FILTERS_MAP = ("> filters:      --edges out|in|inout (which links) · --verbose 0|1 (hide/show summaries) · "
                "--file PATH (focus one module)")


def _other_views(current):
    return "> other views:  " + " · ".join(lbl for key, lbl in _VIEW_OPTS if key != current)


def _nav(current, filters=_FILTERS_MAP):
    """Нижний блок шапки: разделитель + (опц.) фильтры + другие режимы.
    '> ---' отделяет «как читать структуру» от «чем управлять выводом»."""
    parts = [_SEP]
    if filters:
        parts.append(filters)
    parts.append(_other_views(current))
    return "\n".join(parts)


def _orient_tree(verbose):
    return _entry_line(verbose) + "\n" + _EDGES + "\n" + _nav("tree")


def _orient_depth(verbose):
    return ("> depth: 0 = leaves (import nothing internal), higher = closer to entry points\n"
            + _entry_line(verbose) + "\n" + _EDGES + "\n" + _nav("depth"))


def _orient_file(verbose):
    return ("> read: focus around one file — downstream (what it needs) + upstream (who needs it), within --hops\n"
            + _entry_line(verbose) + "\n"
            + _nav("file", "> filters:      --hops N (hops from the file) · --verbose 0|1 (hide/show summaries)"))


_ORIENT_CYCLES = ("> read: each line is a circular import chain — arrows wrap front & back to show it loops\n"
                  + _nav("cycles", None))
_ORIENT_DISCR = ("> read: card↔source gaps — orphan (card, no source) · pending (source, no card) · "
                 "unresolved (dep points nowhere)\n"
                 + _nav("discrepancies", "> filters:      --group-by kind|package|card"))


def format_tree(graph, disp, edges, verbose=1):
    nodes, rdeps, cyc = graph["nodes"], _reverse(graph["nodes"]), _cycle_nodes(graph["nodes"])
    out = [f"# map — {len(nodes)} modules · tree (by directory) · auto-gathered from {disp}",
           _orient_tree(verbose), ""]
    pkgs = {}
    for i in nodes:
        pkgs.setdefault(_top_pkg(i), []).append(i)
    for pkg in sorted(pkgs):
        members = sorted(pkgs[pkg])
        out.append(f"## {pkg} ({len(members)})")
        for i in members:
            label = _rel_to(i, pkg)
            out.append(f"- **{label}**{' ⟲' if i in cyc else ''}{_summ(nodes, i, verbose)}")
            eb = _edge_bits(i, nodes, rdeps, pkg, edges)
            if eb:
                out.append(f"  {eb}")
        out.append("")
    return "\n".join(out + _slices(graph, disp))


def format_depth(graph, disp, edges, verbose=1):
    nodes, rdeps, cyc = graph["nodes"], _reverse(graph["nodes"]), _cycle_nodes(graph["nodes"])
    layers = _compute_layers(nodes)
    out = [f"# map — {len(nodes)} modules · depth (0=leaves) · auto-gathered from {disp}",
           _orient_depth(verbose), ""]
    for l in sorted(layers):
        members = sorted(layers[l])
        out.append(f"## depth {l} ({len(members)})")
        for i in members:
            out.append(f"- **{i}**{' ⟲' if i in cyc else ''}{_summ(nodes, i, verbose)}")
            eb = _edge_bits(i, nodes, rdeps, "(root)", edges)  # слои cross-cutting -> пути полные
            if eb:
                out.append(f"  {eb}")
        out.append("")
    return "\n".join(out + _slices(graph, disp))


# --- discrepancies digest: "map vs reality" ----------------------------------
# СБОР и ПОДАЧА разделены нарочно: collect_* отдаёт плоский типизированный список,
# group_by + _DISCR_KEYS решают КАК его резать. Новую ось группировки добавить =
# дописать одну строку в _DISCR_KEYS; переставить — сменить --group-by. Формат не трогаем.

Discrepancy = namedtuple("Discrepancy", "kind card ref pkg detail")


def collect_discrepancies(graph, project_root):
    """Плоский список расхождений карты и дерева исходников (БЕЗ группировки):
    - orphan     — карточка есть, исходника нет;
    - pending    — dep-ссылка на реальный исходник, у которого ещё нет карточки;
    - unresolved — dep-ссылка не легла ни на карточку, ни на существующий исходник."""
    items = []
    nodes = graph["nodes"]
    for nid in sorted(nodes):                       # orphan: карта без исходника
        if project_root is not None and not (project_root / nid).exists():
            items.append(Discrepancy("orphan", nid, None, _top_pkg(nid),
                                     "card without source file"))
    for nid, raw in sorted(set(graph["unresolved"])):   # pending / unresolved
        parts = raw.split()
        tok = (parts[0] if parts else raw).strip().lstrip("./")
        if project_root is not None and (project_root / tok).exists():
            items.append(Discrepancy("pending", nid, raw, _top_pkg(nid),
                                     "dep on a source file that has no card yet"))
        else:
            items.append(Discrepancy("unresolved", nid, raw, _top_pkg(nid),
                                     "dep ref matches neither a card nor a source file"))
    return items


def group_by(items, key):
    """items -> {key_value: [items]} (dict сохраняет порядок первого появления ключа)."""
    out = {}
    for it in items:
        out.setdefault(key(it), []).append(it)
    return out


# реестр осей группировки — добавить ось = одна строка здесь
_DISCR_KEYS = {
    "kind": lambda d: d.kind,
    "package": lambda d: d.pkg,
    "card": lambda d: d.card,
}
_DISCR_ORDER = {"orphan": 0, "pending": 1, "unresolved": 2}   # осмысленный порядок вместо алфавита


def format_discrepancies(items, group="kind", note=None):
    kinds = ("orphan", "pending", "unresolved")
    counts = {k: sum(1 for d in items if d.kind == k) for k in kinds}
    head = (f"# discrepancies — {len(items)} total "
            f"({counts['orphan']} orphan · {counts['pending']} pending · {counts['unresolved']} unresolved)")
    # `note` — НАБЛЮДЕНИЕ, а не расхождение (сейчас: карта из нескольких
    # независимых компонентов). Осознанно НЕ типизированная находка: несколько
    # компонентов — законная архитектура, а не дефект, и превращать её в
    # находку значило бы навсегда убрать «none (map matches reality)» с
    # здорового полиглотного проекта и раздуть счётчики. Поэтому строка идёт
    # рядом со сводкой и не участвует в подсчёте.
    if not items:
        return "# discrepancies — none (map matches reality)" + (f"\n{note}" if note else "")

    keyfn = _DISCR_KEYS.get(group, _DISCR_KEYS["kind"])
    grouped = group_by(items, keyfn)
    # порядок групп: для kind — смысловой, иначе алфавит
    gkeys = (sorted(grouped, key=lambda k: _DISCR_ORDER.get(k, 99)) if group == "kind"
             else sorted(grouped))
    out = [head] + ([note] if note else []) + [_ORIENT_DISCR, ""]
    for g in gkeys:
        rows = grouped[g]
        out.append(f"## {g} ({len(rows)})")
        for d in sorted(rows, key=lambda d: (d.card, d.ref or "")):
            tag = "" if group == "kind" else f"[{d.kind}] "   # не дублируем ось-заголовок
            ref = f' → "{d.ref}"' if d.ref else ""
            out.append(f"- {tag}{d.card}{ref} — {d.detail}")
        out.append("")
    return "\n".join(out).rstrip()


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
    ap.add_argument("--file", metavar="PATH", default=None,
                    help="фокус-срез вокруг файла: что он тянет (downstream) + кто тянет его (upstream)")
    ap.add_argument("--hops", type=int, default=1,
                    help="радиус среза в рёбрах от --file (по умолч. 1; работает только с --file)")
    ap.add_argument("--cycles", action="store_true",
                    help="детекция циклических зависимостей, вывод цепочками A → B → C → A")
    ap.add_argument("--discrepancies", action="store_true",
                    help="свод «карта vs реальность»: orphan (карта без исходника) + "
                         "pending (исходник без карточки) + unresolved (ссылка в никуда)")
    ap.add_argument("--group-by", choices=["kind", "package", "card"], default="kind",
                    help="ось группировки свода --discrepancies (по умолч. kind)")
    ap.add_argument("--view", choices=["tree", "depth"], default="tree",
                    help="структура карты: tree (по дереву каталогов, дефолт) | depth (0=листья→точки входа)")
    ap.add_argument("--edges", choices=["out", "in", "inout"], default="inout",
                    help="какие рёбра печатать: out (только '→') | in (только '←') | "
                         "inout (обе стороны, дефолт)")
    ap.add_argument("--verbose", type=int, default=1, metavar="N",
                    help="0 = только модули и связи (описания скрыты) | 1 = с описаниями (дефолт)")
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
        print(termstyle.md(format_cycles(graph["nodes"], find_cycles(graph["nodes"]))))
        return

    if args.discrepancies:
        items = collect_discrepancies(graph, resolve_project_root(args.project_root))
        multi, _singles = split_components(graph["nodes"])
        # Наблюдение, не находка (см. format_discrepancies). В --json НЕ кладём:
        # там контракт — плоский список расхождений, и объект другой природы
        # сломал бы любого читателя. Одиночные файлы этой строки НЕ вызывают:
        # они не архитектура, а просто несвязанные файлы (см. split_components).
        note = (f"> note: the map has {len(multi)} independent parts — "
                + " · ".join(_comp_labels(multi))
                + ". No import edge between them; if that is by design (a separate "
                  "plugin, a JS front end to this backend) their link is a runtime "
                  "contract, not an import — document it and link both cards' Doc links."
                ) if len(multi) > 1 else None
        if args.json:
            print(json.dumps([d._asdict() for d in items], ensure_ascii=False, indent=2))
        else:
            print(termstyle.md(format_discrepancies(items, group=args.group_by, note=note)))
        return

    if args.file:
        center = _resolve_id(graph["nodes"], args.file)
        if not center:
            print(f"--file: '{args.file}' — no such card (need a root-relative path or a unique basename)",
                  file=sys.stderr)
            sys.exit(1)
        z = file_zone(graph, center, max(1, args.hops))
        if args.json:
            print(json.dumps({"center": center, "depth": z["depth"],
                              "downstream": sorted(z["down"]), "upstream": sorted(z["up"])},
                             ensure_ascii=False, indent=2))
        else:
            print(termstyle.md(format_file_zone(graph, z, args.verbose)))
        return

    if args.json:
        print(json.dumps({"nodes": graph["nodes"], "unresolved": graph["unresolved"]},
                         ensure_ascii=False, indent=2))
        return

    disp = cards_dir.as_posix()   # полный путь к папке карточек (видно, откуда собрана карта)
    if args.view == "depth":
        print(termstyle.md(format_depth(graph, disp, args.edges, args.verbose)))
    else:
        print(termstyle.md(format_tree(graph, disp, args.edges, args.verbose)))


if __name__ == "__main__":
    main()
