# check_cards_freshness

Which `__map/` cards are **stale** versus their source, and which are **orphans**. Lean,
LLM-readable output (no frames/emoji); exit 1 if anything is stale or orphaned.

**Target:** `check_cards_freshness.py [--cards-dir P] [--project-root P]` 
`--project-root` not given -> implicitly `CONFIG__TOOLS.PROJECT_ROOT` of this tool's own `__HQ` (must exist; missing config -> refuses, never a silent cwd; a RELATIVE value must still contain this tool). `@` -> same, explicit, unchecked. Literal path -> as given. Cards: `--cards-dir` > `CONFIG__TOOLS.MAP_DIR` (relative to `__HQ`) > `<root>/__map/`; an explicit `--project-root` always means `<root>/__map/` (Vision08). Freshness is per file, each in its OWN git (sources and cards may be two repos: `mode=src:git cards:git(own)`); a side outside git -> its mtime. Missing cards dir now says so distinctly from "no
cards found" (empty dir).

## Quick use
```
check_cards_freshness.py                        # stale + orphan cards (root + MAP_DIR from config)
check_cards_freshness.py --project-root <R>     # a foreign project -> <R>/__map
```

## Modes

* **git** (default) — a card is stale if the source was touched without updating the card:
  in the working tree (uncommitted source edit while the card is clean) OR by history (source's
  last commit newer than the card's). For stale cards it also lists the commits that touched the
  source after the card — the agent sees immediately what to look at.
  **Git calls are BATCHED per repo, never per file** (one full history walk `-z --name-only`,
  one `log -c --merges` pass for evil merges — files changed inside a merge vs both parents,
  exactly what per-file history simplification kept before, one `status --porcelain`, one
  `ls-files --others --ignored`, one `rev-parse` per .git dir found). ~9 subprocesses per side
  regardless of card count — seconds even where each subprocess over a container mount costs ~0.1 s
  (measured: 361 cards, 3m03 -> 6s, verdicts byte-identical to the old per-file version).
* **mtime** (fallback) — compares card vs source mtime when git isn't available. Watch the
  `mode=` line: a worktree created by another OS (its `.git` file points to an absolute path
  the local git cannot resolve, e.g. a container Linux path read from Windows) silently lands
  HERE and the verdict is mostly noise — run the tool in the environment that owns the worktree.

Use it to decide WHICH cards to re-stamp (`make_interface_card --force`) after code changes.
