#!/usr/bin/env python3
"""Актуальность .py.md карточек (__map/) — вывод под чтение ЛЛМ.

Режимы:
- git: карточка устарела, если исходник тронут без обновления карточки — в
  рабочем дереве (незакоммиченная правка исходника при чистой карточке) или по
  истории (последний коммит исходника новее последнего коммита карточки).
- mtime: фоллбэк — сравнение mtime карточки и исходника.

Вывод намеренно скупой: без рамок и эмодзи (шум/токены + cp1251-краш на Windows),
отставание — числом. Для устаревших в git-режиме добавляются коммиты, тронувшие
исходник после карточки — агент сразу видит, что смотреть.

Использование:
    python check_freshness.py [--cards-dir PATH] [--project-root PATH]
По умолчанию карточки в <project>/__map/, корень — родитель __map/
(скрипт лежит в __HQ/tools/).
"""

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def get_mtime(path):
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


# --------------------------------------------------------------------------- #
# git
# --------------------------------------------------------------------------- #

def _git(root, *args):
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
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
    code, out = _git(root, "status", "--porcelain")
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


def _rel(path, root):
    return path.relative_to(root).as_posix()


def check_git(cards_dir, root):
    fresh, outdated, orphan = [], [], []
    dirty = _dirty_paths(root)
    for card in sorted(cards_dir.rglob("*.py.md")):
        source = root / str(card.relative_to(cards_dir)).replace(".md", "")
        if not source.exists():
            orphan.append(card)
            continue
        src_rel, card_rel = _rel(source, root), _rel(card, root)
        src_dirty, card_dirty = src_rel in dirty, card_rel in dirty
        if src_dirty and not card_dirty:
            lag = (get_mtime(source) - get_mtime(card)).total_seconds()
            outdated.append({"card": card, "lag": lag, "note": "uncommitted src edit"})
            continue
        if src_dirty or card_dirty:
            fresh.append(card)
            continue
        src_ct = _last_commit_ts(root, src_rel)
        card_ct = _last_commit_ts(root, card_rel)
        if src_ct is None:
            fresh.append(card)
            continue
        if card_ct is None or src_ct > card_ct:
            base = card_ct if card_ct is not None else 0
            commits = _commits_since(root, src_rel, base)
            note = "commits: " + " | ".join(commits) if commits else "history newer"
            outdated.append({"card": card, "lag": float(src_ct - base), "note": note})
        else:
            fresh.append(card)
    return {"fresh": fresh, "outdated": outdated, "orphan": orphan}


def check_mtime(cards_dir, root):
    fresh, outdated, orphan = [], [], []
    for card in sorted(cards_dir.rglob("*.py.md")):
        source = root / str(card.relative_to(cards_dir)).replace(".md", "")
        if not source.exists():
            orphan.append(card)
            continue
        card_mt, src_mt = get_mtime(card), get_mtime(source)
        if card_mt >= src_mt:
            fresh.append(card)
        else:
            outdated.append({"card": card, "lag": (src_mt - card_mt).total_seconds(), "note": "mtime"})
    return {"fresh": fresh, "outdated": outdated, "orphan": orphan}


def _lag(seconds):
    hours = seconds / 3600
    return f"{seconds:.0f}s" if hours < 1 else f"{hours:.1f}h"


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # пути/сабджекты коммитов бывают с юникодом
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Freshness of .py.md cards (LLM-lean output)")
    ap.add_argument("--cards-dir", type=Path, default=None, help="карточки (по умолч. <project>/__map/)")
    ap.add_argument("--project-root", type=Path, default=None, help="корень проекта (по умолч. родитель __map/)")
    args = ap.parse_args()

    if args.cards_dir:
        cards_dir = args.cards_dir.resolve()
    else:
        # карточки в <project>/__map/ (запускай из корня проекта)
        cards_dir = Path.cwd() / "__map"
    project_root = args.project_root.resolve() if args.project_root else cards_dir.parent

    mode = "git" if is_git_repo(project_root) else "mtime"
    result = check_git(cards_dir, project_root) if mode == "git" else check_mtime(cards_dir, project_root)
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
