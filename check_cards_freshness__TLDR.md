# check_cards_freshness

Which `__map/` cards are **stale** versus their source, and which are **orphans**. Lean,
LLM-readable output (no frames/emoji); exit 1 if anything is stale or orphaned.

**Target:** `check_cards_freshness.py [--cards-dir P] [--project-root P]` — defaults: cards = `<project>/__map/`.

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
