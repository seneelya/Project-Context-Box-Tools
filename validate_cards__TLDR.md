# validate_cards

Validates cards against the `CARD_FORMAT.py` contract. Lean output that **coaches the author**;
exit 1 on any problem (so it gates in a loop). Independent of `make_interface_card.py`.

**Target:** `validate_cards.py [--cards-dir P] [--project-root P]` — defaults: cards = `<project>/__map/`.
`--project-root` not given -> implicitly `CONFIG__TOOLS.PROJECT_ROOT`, sanity-checked (must contain
this tool's own folder). `@` -> same, explicit, unchecked. Literal path -> as given, unchecked.

## Quick use
```
validate_cards.py --project-root .                         # validate ./__map
validate_cards.py --cards-dir path/__map --project-root .  # custom cards dir
```

## Checks (per card)

* **H1 == file name** (legacy `# name — summary` flagged: move the summary to its own line);
* **summary** (first non-empty line after H1) not empty (a blank line after the heading is fine);
* **all H2 sections** from `H2_SECTIONS` present (non-canonical / other-language headings flagged
  to migrate via `canon()`);
* **`Dependencies Internal`** = `(none)` or a table with `DEPS_COLUMNS`; every `File Path`
  resolves to an existing card (else error);
* **`Public API`** = `(none)` or ≥1 H3; private `_x` in Public API forbidden (except `Re-exports`);
* **orphans** (with `--project-root`) — a card whose source no longer exists.

Green = done. Used both by the card author (self-check) and by an auditor (see `Guide__AuditCards`).
