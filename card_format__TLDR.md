# card_format

**Not a CLI — the contract.** The single source of truth for the card format. Its module
docstring IS the card skeleton. Edit the format HERE; the tools import these names, so their
code is never touched.

**Imported by:** `validate_cards.py`, `rebuild_graph.py`, `bundle.py`, `card_api.py`.

## What it defines

* **Section contracts** — `H2_SECTIONS` / `H2_SECTIONS_PACKAGE` (required H2 by card type),
  `H3_API_SUBSECTIONS`, `PRIVATE_OK_SUBSECTIONS` (`Re-exports`, `Consumed internals`).
* **Table shape** — `DEPS_COLUMNS`, `EDGE_COLUMN` (= `File Path`, the column graph edges come
  from), `EMPTY` (= `(none)`), `ALIASES` (RU/legacy heading → canonical).
* **Helpers** — `canon(token)`, `is_empty(text)`, `is_package(filename)` (via
  `PACKAGE_BASENAMES`: `__init__.py`, `index.ts`, `mod.rs`, …), `sections_for(filename)`.

If a card check or the stamp output looks wrong, the fix is almost always here, once.
