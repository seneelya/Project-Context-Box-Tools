#!/usr/bin/env python3
"""Актуальность карточек (__map/, любой язык — .py.md/.js.md/...) — вывод под чтение ЛЛМ.

Режим — ПОПАРНО, каждый файл у своего git (исходники и карточки могут быть в разных репо):
- git: карточка устарела, если исходник тронут без обновления карточки — в
  рабочем дереве (незакоммиченная правка исходника при чистой карточке) или по
  истории (последний коммит исходника новее последнего коммита карточки; `%ct` —
  часы, так что сравнимо и между двумя репо).
- mtime: сторона вне git (или игнорируемая своим репо) — её mtime.

Вывод намеренно скупой: без рамок и эмодзи (шум/токены + cp1251-краш на Windows),
отставание — числом. Для устаревших в git-режиме добавляются коммиты, тронувшие
исходник после карточки — агент сразу видит, что смотреть.

Использование:
    python check_cards_freshness.py [--cards-dir PATH] [--project-root PATH]
Карточки: --cards-dir > CONFIG__TOOLS.MAP_DIR (от __HQ) > <project-root>/__map/.
"""

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from graph_from_cards import resolve_cards_dir, resolve_project_root


def get_mtime(path):
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


# --------------------------------------------------------------------------- #
# git
# --------------------------------------------------------------------------- #

def _git(root, *args):
    try:
        proc = subprocess.run(
            ["git", "-c", "core.quotepath=off", "-C", str(root), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
        )
        return proc.returncode, proc.stdout
    except (OSError, subprocess.SubprocessError):
        return 1, ""


def is_git_repo(root):
    if not (root / ".git").exists():
        return False
    code, out = _git(root, "rev-parse", "--is-inside-work-tree")
    return code == 0 and out.strip() == "true"


def _dirty_paths(root):
    code, out = _git(root, "status", "--porcelain", "--untracked-files=all")  # не схлопывать новую папку в "?? dir/"
    if code != 0:
        return set()
    dirty = set()
    for line in out.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        dirty.add(path.strip('"'))
    return dirty


def _last_commit_ts(root, rel_path):
    code, out = _git(root, "log", "-1", "--format=%ct", "--", rel_path)
    out = out.strip()
    if code != 0 or not out:
        return None
    try:
        return int(out)
    except ValueError:
        return None


def _commits_since(root, rel_path, since_ct, limit=5):
    """Коммиты, тронувшие rel_path и новее since_ct: ['<hash> <subject>', ...]."""
    code, out = _git(root, "log", f"-n{limit * 4}", "--format=%h\x1f%ct\x1f%s", "--", rel_path)
    if code != 0:
        return []
    res = []
    for line in out.splitlines():
        parts = line.split("\x1f")
        if len(parts) != 3:
            continue
        h, ct, subj = parts
        try:
            if int(ct) > since_ct:
                res.append(f"{h} {subj}")
        except ValueError:
            continue
        if len(res) >= limit:
            break
    return res


class _Repos:
    """Каждый файл — у СВОЕГО git (Vision08 §3 п.5): исходники и карточки могут жить в разных
    репо (форк + штаб со своим git, скрытый от форка). Репо файла = ближайший `.git` вверх от его
    папки (`git -C <dir> rev-parse --show-toplevel`); файл, который этот репо ИГНОРИРУЕТ (напр.
    карточки в `__HQ`, исключённом из git форка, когда у штаба своего git нет), — «без git» ->
    mtime. dirty-набор считается один раз на репо."""

    def __init__(self):
        self._top_by_dir, self._dirty_by_top = {}, {}

    def top(self, path):
        d = path.parent
        if d not in self._top_by_dir:
            code, out = _git(d, "rev-parse", "--show-toplevel")
            self._top_by_dir[d] = Path(out.strip()).resolve() if code == 0 and out.strip() else None
        top = self._top_by_dir[d]
        if top is None:
            return None
        code, _ = _git(top, "check-ignore", "-q", "--", _rel(path, top))
        return None if code == 0 else top

    def dirty(self, top, path):
        if top not in self._dirty_by_top:
            self._dirty_by_top[top] = _dirty_paths(top)
        return _rel(path, top) in self._dirty_by_top[top]


def _rel(path, root):
    return path.relative_to(root).as_posix()


def _source_of(card, cards_dir, root):
    return root / card.relative_to(cards_dir).as_posix()[:-3]   # срезаем ровно хвостовой '.md'


def check(cards_dir, root):
    """Свежесть попарно: для исходника и карточки — время по их СОБСТВЕННОМУ git (коммит; `%ct` —
    часы, поэтому сравнимо и между репо) или mtime, если стороны нет в git. Возвращает также
    раскладку `layouts` — какие пары режимов встретились (для строки mode=)."""
    fresh, outdated, orphan, layouts = [], [], [], set()
    repos = _Repos()
    for card in sorted(cards_dir.rglob("*.md")):
        source = _source_of(card, cards_dir, root)
        if not source.exists():
            orphan.append(card)
            continue
        s_top, c_top = repos.top(source), repos.top(card)
        layouts.add(("git" if s_top else "mtime",
                     ("git" if c_top == s_top else "git(own)") if c_top else "mtime"))
        if not s_top and not c_top:
            card_mt, src_mt = get_mtime(card), get_mtime(source)
            if card_mt >= src_mt:
                fresh.append(card)
            else:
                outdated.append({"card": card, "lag": (src_mt - card_mt).total_seconds(), "note": "mtime"})
            continue
        # «правка в работе»: у git-стороны — незакоммичена; у стороны без git — mtime новее другой
        src_dirty = repos.dirty(s_top, source) if s_top else get_mtime(source) > get_mtime(card)
        card_dirty = repos.dirty(c_top, card) if c_top else get_mtime(card) >= get_mtime(source)
        if src_dirty and not card_dirty:
            lag = (get_mtime(source) - get_mtime(card)).total_seconds()
            outdated.append({"card": card, "lag": lag, "note": "uncommitted src edit" if s_top else "mtime"})
            continue
        if src_dirty or card_dirty:
            fresh.append(card)
            continue
        src_ct = _last_commit_ts(s_top, _rel(source, s_top)) if s_top else int(source.stat().st_mtime)
        card_ct = _last_commit_ts(c_top, _rel(card, c_top)) if c_top else int(card.stat().st_mtime)
        if src_ct is None:
            fresh.append(card)
            continue
        if card_ct is None or src_ct > card_ct:
            base = card_ct if card_ct is not None else 0
            commits = _commits_since(s_top, _rel(source, s_top), base) if s_top else []
            note = "commits: " + " | ".join(commits) if commits else "history newer"
            outdated.append({"card": card, "lag": float(src_ct - base), "note": note})
        else:
            fresh.append(card)
    return {"fresh": fresh, "outdated": outdated, "orphan": orphan, "layouts": layouts}


def _lag(seconds):
    hours = seconds / 3600
    return f"{seconds:.0f}s" if hours < 1 else f"{hours:.1f}h"


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # пути/сабджекты коммитов бывают с юникодом
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Freshness of __map/ cards, any language (LLM-lean output)", add_help=False)
    ap.add_argument("-h", "--help", action="help", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    ap.add_argument("--cards-dir", type=Path, default=None,
                    help="карточки. По умолч.: корень из конфига -> CONFIG__TOOLS.MAP_DIR (от __HQ), "
                         "нет ключа -> <root>/__map; явный --project-root -> <root>/__map")
    ap.add_argument("--project-root", type=str, default=None,
                     help="корень проекта. Не задан -> неявно CONFIG__TOOLS.PROJECT_ROOT своего __HQ "
                          "(должен существовать). '@' -> то же явно, без проверки. Литерал -> буквально.")
    args = ap.parse_args()

    # REQ-002-B: корень НЕ угадывается из cards_dir.parent; каталог карточек — общий резолвер
    # card-тулов (Vision08: --cards-dir > MAP_DIR от __HQ > <root>/__map).
    project_root = resolve_project_root(args.project_root)
    cards_dir = resolve_cards_dir(args.cards_dir, args.project_root, project_root)
    if not cards_dir.exists():
        # различаем «папки карточек по этому пути нет» от «карточек нет» (см. total==0 ниже) —
        # раньше эти два случая были неотличимы, оба читались как «карточек нет вообще».
        print(f"cards dir not found: {cards_dir}", file=sys.stderr)
        sys.exit(1)

    result = check(cards_dir, project_root)
    mode = ",".join(f"src:{s} cards:{c}" for s, c in sorted(result["layouts"])) or "-"
    fresh, outdated, orphan = result["fresh"], result["outdated"], result["orphan"]
    total = len(fresh) + len(outdated) + len(orphan)

    try:
        cd = cards_dir.relative_to(project_root).as_posix()
    except ValueError:
        cd = str(cards_dir)
    print(f"cards={cd} project={project_root} mode={mode}")
    print(f"total={total} fresh={len(fresh)} outdated={len(outdated)} orphan={len(orphan)}")

    if not total:
        print("no cards found")
        sys.exit(0)

    if outdated:
        print("\nOUTDATED (remake card):")
        for e in sorted(outdated, key=lambda x: str(x["card"])):
            print(f"  {e['card'].relative_to(cards_dir).as_posix()}  lag={_lag(e['lag'])}  {e['note']}")
    if orphan:
        print("\nORPHAN (no source):")
        for card in sorted(orphan):
            print(f"  {card.relative_to(cards_dir).as_posix()}")

    sys.exit(1 if (outdated or orphan) else 0)


if __name__ == "__main__":
    main()
