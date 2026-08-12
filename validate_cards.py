#!/usr/bin/env python3
"""Валидатор карточек по контракту `CARD_FORMAT.py`. Скупой вывод — коучит создателя.

Проверяет на карточку:
- H1 = имя файла (легаси `# name — summary` помечается как «перенеси сводку на отд. строку»);
- сводка (первая непустая строка после H1) не пуста (пустая строка после заголовка — ок);
- присутствуют ВСЕ секции из H2_SECTIONS (не-канонические/иноязычные заголовки помечаются как
  «мигрировать» через canon());
- `Dependencies Internal` = `(none)` или таблица с колонками DEPS_COLUMNS; каждый `File Path`
  резолвится в существующую карточку (иначе — ошибка);
- `Public API` = `(none)` или ≥1 H3; приватные `_x` в Public API запрещены (кроме `Re-exports`);
- (опц. с --project-root) сироты — карточка без исходника.

Выход 1, если есть проблемы. Использование:
    python validate_cards.py [--cards-dir PATH] [--project-root PATH]
"""

import argparse
import sys
from pathlib import Path

import CARD_FORMAT as cf
from graph_from_cards import build_graph, _cells, _is_sep, _DASH


def _sections(lines):
    """-> [(raw_h2, [body_lines])] по порядку."""
    secs, cur = [], None
    for line in lines:
        if line.strip().startswith("## "):
            cur = [line.strip()[3:].strip(), []]
            secs.append(cur)
        elif cur is not None:
            cur[1].append(line)
    return secs


def _entry_name(h4_line):
    """'#### `\\_setup = x`' -> '_setup' (снимает бэктики, экранирование, звёздочки)."""
    e = h4_line.strip()[5:].strip().strip("`").strip()
    e = e.lstrip("\\").lstrip("*").lstrip("\\").strip()
    return e.split("(")[0].split("=")[0].split(" ")[0].strip()


def validate_card(path, cards_dir, unresolved_raw, project_root):
    issues = []
    pending = []   # File Path -> исходник есть, карточки пока нет (норм при поштучной сборке)
    lines = path.read_text(encoding="utf-8").splitlines()
    fname = path.name[:-3]  # 'db.py'

    # H1 + сводка
    h1, idx = None, None
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("# ") and not s.startswith("## "):
            h1, idx = s[2:].strip(), i
            break
    if h1 is None:
        issues.append("no H1 `# <filename>`")
    else:
        legacy = bool(_DASH.search(h1))
        name = _DASH.split(h1, 1)[0].strip() if legacy else h1
        if name != fname:
            issues.append(f"H1 name '{name}' != file '{fname}'")
        if legacy:
            issues.append("legacy H1: move summary onto its own line below H1")
        summary = _DASH.split(h1, 1)[1].strip() if legacy else ""
        if not summary:
            for line in lines[idx + 1:]:
                t = line.strip()
                if not t:
                    continue
                if t.startswith("#"):
                    break
                summary = t
                break
        if not summary:
            issues.append("empty summary (first non-empty line after H1)")

    # секции
    secs = _sections(lines)
    present = {}
    for raw, body in secs:
        c = cf.canon(raw)
        present.setdefault(c, (raw, body))
        if c in cf.H2_SECTIONS_PACKAGE and raw != c:
            issues.append(f"non-canonical header '{raw}' -> '{c}'")
    for sec in cf.sections_for(fname):
        if sec not in present:
            issues.append(f"missing section: {sec}")

    # Dependencies Internal
    if "Dependencies Internal" in present:
        body = present["Dependencies Internal"][1]
        if not cf.is_empty("\n".join(body)):
            hdr = None
            for line in body:
                if line.strip().startswith("|"):
                    cells = _cells(line)
                    if _is_sep(cells):
                        continue
                    hdr = [cf.canon(c) for c in cells]
                    break
            if hdr is None:
                issues.append("Dependencies Internal: neither (none) nor a table")
            elif hdr != cf.DEPS_COLUMNS:
                issues.append(f"deps columns {hdr} != {cf.DEPS_COLUMNS}")

    for raw in unresolved_raw:
        # Исходник существует, а карточки-цели ещё нет -> «в очереди», НЕ ошибка:
        # при поштучной сборке зависимость на не-скарженный сосед — норма, не повод
        # выкидывать реальную строку deps. Настоящая ошибка — когда и исходника нет.
        if project_root is not None and (project_root / raw).exists():
            pending.append(raw)
        else:
            issues.append(f'File Path resolves to neither a card nor a source file: "{raw}"')

    # Public API — приватные вне Re-exports
    if "Public API" in present:
        body = present["Public API"][1]
        if not cf.is_empty("\n".join(body)):
            cur_h3, has_h3 = None, False
            for line in body:
                s = line.strip()
                if s.startswith("### "):
                    cur_h3, has_h3 = cf.canon(s[4:].strip()), True
                elif s.startswith("#### "):
                    nm = _entry_name(line)
                    if nm.startswith("_") and cur_h3 not in cf.PRIVATE_OK_SUBSECTIONS:
                        issues.append(f"review: private '{nm}' in Public API (keep only if consumed elsewhere)")
            if not has_h3:
                issues.append("Public API: neither (none) nor an H3 subsection")

    # сироты (опц.)
    if project_root is not None:
        node_id = path.relative_to(cards_dir).as_posix()[:-3]
        if not (project_root / node_id).exists():
            issues.append("orphan: source file missing")

    return issues, pending


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Validate cards against CARD_FORMAT.py")
    ap.add_argument("--cards-dir", type=Path, default=None)
    ap.add_argument("--project-root", type=Path, default=None, help="для проверки сирот")
    args = ap.parse_args()

    cards_dir = args.cards_dir.resolve() if args.cards_dir else (Path.cwd() / "__map")
    if not cards_dir.exists():
        print(f"cards dir not found: {cards_dir}", file=sys.stderr)
        sys.exit(1)
    project_root = args.project_root.resolve() if args.project_root else None

    # рёбра/резолв берём из графа один раз
    unresolved_by_card = {}
    for nid, raw in build_graph(cards_dir)["unresolved"]:
        unresolved_by_card.setdefault(nid, []).append(raw)

    cards = sorted(p for p in cards_dir.rglob("*.md") if "." in p.stem)
    total = len(cards)
    bad = 0
    report = []
    pending_all = {}
    for p in cards:
        nid = p.relative_to(cards_dir).as_posix()[:-3]
        issues, pending = validate_card(p, cards_dir, unresolved_by_card.get(nid, []), project_root)
        if issues:
            bad += 1
            report.append((nid, issues))
        if pending:
            pending_all[nid] = pending

    for nid, issues in sorted(report):
        print(f"{nid}:")
        for iss in issues:
            print(f"  - {iss}")

    # «В очереди» — НЕ ошибка: зависимость на существующий исходник, чья карточка ещё не
    # создана. Печатаем как справку (не роняем exit), чтобы агент НЕ выкидывал реальные deps.
    if pending_all:
        n = sum(len(v) for v in pending_all.values())
        print(f"\npending ({n}) — deps на исходники без карточек (норм при сборке; не ошибка):")
        for nid, raws in sorted(pending_all.items()):
            print(f"  {nid}: {', '.join(raws)}")

    print(f"\nchecked {total} cards, {bad} with issues, {total - bad} clean"
          + (f", {len(pending_all)} with pending deps" if pending_all else ""))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
