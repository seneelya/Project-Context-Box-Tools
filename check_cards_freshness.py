#!/usr/bin/env python3
"""Актуальность карточек (__map/, любой язык — .py.md/.js.md/...) — вывод под чтение ЛЛМ.

Режим — ПОПАРНО, каждый файл у своего git (исходники и карточки могут быть в разных репо):
- git: карточка устарела, если исходник тронут без обновления карточки — в
  рабочем дереве (незакоммиченная правка исходника при чистой карточке) или по
  истории (последний коммит исходника новее последнего коммита карточки; `%ct` —
  часы, так что сравнимо и между двумя репо).
- mtime: сторона вне git (или игнорируемая своим репо) — её mtime.

GIT ЗАПРОСЫ ПАКЕТОМ (REQ: скорость в контейнерах, где каждый subprocess через монт стоит ~0.1 c):
на каждое найденное репо — ровно несколько вызовов, НЕ на файл: `rev-parse --show-toplevel`
(на каждый каталог с .git), один `status --porcelain` (dirty-набор), один
`ls-files --others --ignored --exclude-standard` (игноры) и один обход истории
`log --no-renames --name-only -z` (последний коммит + список коммитов для каждого пути).
Полугодичный прогон 361 карточки: ~1500 git-вызовов -> ~8. Отличие от прежнего per-file
`log -1 -- path`: merge-коммиты в обходе не показывают изменённых путей, поэтому для ЗЛОУМЫШЛЕННОГО
merge (изменение файла прямо в merge-коммите, «evil merge») датой останется последний нормальный
коммит файла, а не merge. Обычные (--no-ff) мерджи дают тот же вердикт, что и раньше.

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

# сколько коммитов на путь храним из обхода истории (для перечня у outdated-карточек)
_HIST_CAP = 30


def get_mtime(path):
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


# --------------------------------------------------------------------------- #
# git
# --------------------------------------------------------------------------- #

def _git(root, *args):
    try:
        proc = subprocess.run(
            ["git", "-c", "core.quotepath=off", "-C", str(root), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
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


def _ignored_paths(root):
    """Один вызов вместо per-file `check-ignore`: набор игнорируемых НЕотслеживаемых путей."""
    code, out = _git(root, "ls-files", "--others", "--ignored", "--exclude-standard")
    if code != 0:
        return set()
    return {line.strip() for line in out.splitlines() if line.strip()}


def _history_maps(root):
    """Один обход истории репо -> (last_ct[path], hist[path]) по всем путям сразу.

    Формат: записи коммитов отделены \x1e, имена файлов NUL- terminated (-z, чтобы пути
    с пробелами/кавычками не ломали разбор). --no-renames: путь меняется именно там, где
    менялся (переименование даёт строку и для старого имени — old-файлы всё равно вымерли).
    """
    code, out = _git(root, "log", "--no-renames", "--name-only", "-z",
                     "--format=%x1e%ct\x1f%h\x1f%s")
    if code != 0:
        return {}, {}
    last_ct, hist = _fold_log(out)
    # merge-коммиты в обычном обходе путей не показывают; combined-diff (-c) от merge-ов даёт
    # ровно «злые» merge-и: файлы, изменённые в merge и отличающиеся от ОБОИХ родителей —
    # те же, которые per-file `log -- path` оставлял в истории раньше (дефолтная сепарация).
    code, out = _git(root, "log", "--no-renames", "--merges", "-c", "--name-only", "-z",
                     "--format=%x1e%ct\x1f%h\x1f%s")
    if code == 0:
        m_last, m_hist = _fold_log(out)
        for path, ct in m_last.items():
            if ct > last_ct.get(path, -1):
                last_ct[path] = ct
        for path, entries in m_hist.items():
            h = hist.setdefault(path, [])
            h.extend(entries)
            h.sort(key=lambda e: e[0], reverse=True)
            del h[_HIST_CAP:]
    return last_ct, hist


def _fold_log(out):
    """Разбор `-z`-потока `log --name-only`: -> (last_ct[path], hist[path])."""
    last_ct, hist = {}, {}
    cur = None
    for chunk in out.split("\0"):
        if chunk.startswith("\x1e"):
            rec = chunk[1:].split("\x1f")
            if len(rec) == 3:
                try:
                    cur = (int(rec[0]), rec[1], rec[2])
                except ValueError:
                    cur = None
            else:
                cur = None
            continue
        if cur is None or not chunk:
            continue
        path = chunk.strip()
        if not path:
            continue
        if path not in last_ct:                      # log идёт от новых к старым
            last_ct[path] = cur[0]
        h = hist.setdefault(path, [])
        if len(h) < _HIST_CAP:
            h.append(cur)
    return last_ct, hist


class _Repos:
    """Каждый файл — у СВОЕГО git (Vision08 §3 п.5): исходники и карточки могут жить в разных
    репо (форк + штаб со своим git, скрытый от форка). Репо файла = ближайший `.git` вверх от его
    папки (fs-обход + ОДИН `rev-parse --show-toplevel` на найденный каталог с .git); файл,
    который этот репо ИГНОРИРУЕТ (напр. карточки в `__HQ`, исключённом из git форка, когда у штаба
    своего git нет), — «без git» -> mtime. dirty-набор, игноры и обход истории — по ОДНОму
    вызову на репо (пакетный режим, см. докстринг)."""

    def __init__(self):
        self._top_by_dir, self._dirty_by_top = {}, {}
        self._ignored_by_top, self._hist_by_top = {}, {}

    def top(self, path):
        d = path.parent
        if d not in self._top_by_dir:
            top, cur = None, d
            while True:
                if (cur / ".git").exists():
                    code, out = _git(cur, "rev-parse", "--show-toplevel")
                    top = Path(out.strip()).resolve() if code == 0 and out.strip() else None
                    break
                parent = cur.parent
                if parent == cur:
                    break
                cur = parent
            self._top_by_dir[d] = top
        top = self._top_by_dir[d]
        if top is None:
            return None
        if _rel(path, top) in self._ignored(top):
            return None
        return top

    def dirty(self, top, path):
        if top not in self._dirty_by_top:
            self._dirty_by_top[top] = _dirty_paths(top)
        return _rel(path, top) in self._dirty_by_top[top]

    def _ignored(self, top):
        if top not in self._ignored_by_top:
            self._ignored_by_top[top] = _ignored_paths(top)
        return self._ignored_by_top[top]

    def _history(self, top):
        if top not in self._hist_by_top:
            self._hist_by_top[top] = _history_maps(top)
        return self._hist_by_top[top]

    def last_commit_ts(self, top, rel_path):
        if top is None:
            return None
        last_ct, _ = self._history(top)
        return last_ct.get(rel_path)

    def commits_since(self, top, rel_path, since_ct, limit=5):
        """Коммиты, тронувшие rel_path и новее since_ct: ['<hash> <subject>', ...]."""
        if top is None:
            return []
        _, hist = self._history(top)
        res = []
        for ct, h, subj in hist.get(rel_path, []):
            if ct > since_ct:
                res.append(f"{h} {subj}")
                if len(res) >= limit:
                    break
        return res


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
        src_ct = repos.last_commit_ts(s_top, _rel(source, s_top)) if s_top else int(source.stat().st_mtime)
        card_ct = repos.last_commit_ts(c_top, _rel(card, c_top)) if c_top else int(card.stat().st_mtime)
        if src_ct is None:
            fresh.append(card)
            continue
        if card_ct is None or src_ct > card_ct:
            base = card_ct if card_ct is not None else 0
            commits = repos.commits_since(s_top, _rel(source, s_top), base) if s_top else []
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
        print("\nORPHAN (source file is gone — DELETE these cards):")
        for card in sorted(orphan):
            print(f"  {card.relative_to(cards_dir).as_posix()}")

    sys.exit(1 if (outdated or orphan) else 0)


if __name__ == "__main__":
    main()
