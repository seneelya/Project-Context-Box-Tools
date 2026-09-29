# check_cards_freshness

Which `__map/` cards are **stale** versus their source, and which are **orphans**. Lean,
LLM-readable output (no frames/emoji); exit 1 if anything is stale or orphaned.

**Target:** `check_cards_freshness.py [--cards-dir P] [--project-root P]` 
`--project-root` not given -> implicitly `CONFIG__TOOLS.PROJECT_ROOT` of this tool's own `__HQ` (must exist; missing config -> refuses, never a silent cwd; a RELATIVE value must still contain this tool). `@` -> same, explicit, unchecked. Literal path -> as given. Cards: `--cards-dir` > `CONFIG__TOOLS.MAP_DIR` (relative to `__HQ`) > `<root>/__map/`; an explicit `--project-root` always means `<root>/__map/` (Vision08). Freshness is per file, each in its OWN git (sources and cards may be two repos: `mode=src:git cards:git(own)`); a side outside git -> its mtime. Missing cards dir now says so distinctly from "no
cards found" (empty dir).

## Quick use
```
check_cards_freshness.py --project-root .    # list stale + orphan cards (git mode)
```

## Modes

* **git** (default) — a card is stale if the source was touched without updating the card:
  in the working tree (uncommitted source edit while the card is clean) OR by history (source's
  last commit newer than the card's). For stale cards it also lists the commits that touched the
  source after the card — the agent sees immediately what to look at.
* **mtime** (fallback) — compares card vs source mtime when git isn't available.

Use it to decide WHICH cards to re-stamp (`make_interface_card --force`) after code changes.
