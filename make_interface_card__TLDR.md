# make_interface_card

The card **STAMP**: ONE command → a ready `.md` card skeleton where the FACT sections are
filled deterministically and the prose is left as `<Agent: …>` directive lines for the LLM to
complete after reading the source. It analyzes nothing new — it ORCHESTRATES three facts.

**Target:** `make_interface_card.py <file> --project-root R [--out PATH] [--force]` — multilingual (py/ts/cs).

## Quick use  (copy, tweak, run)
```
make_interface_card.py <f>.py --project-root . --out __map/<f>.py.md   # stamp → write the card
make_interface_card.py <f>.py --project-root .                         # preview to stdout (no write)
make_interface_card.py <f>.py --project-root . --out <card> --force    # overwrite an UNFILLED stamp
```

## The three facts it fills

* **Declared surface + signatures** — Python → `py_api.collect` (ast, exact param types);
  TS/JS/C# → `get_codeblock` declarations (structural block headers).
* **Consumed surface** — `codebase_import_search` downstream: who REALLY imports each symbol
  (`consumers N: file…`); exposes leaked-private and dead surface.
* **Dependencies** — `codebase_import_search --incoming`, resolved to files.

## Flags & output

* **`--out PATH`** — write the card file (creates folders); refuses to overwrite without
  **`--force`** (exit 2). Without `--out` it prints to stdout (redirect yourself).
* Emits `## Package layout` + `### Re-exports` for package/index files automatically.
* Declared-surface backend = `CONFIG__TOOLS.DECL_BACKEND` (`auto|treesitter|regex`); on a
  missing tree-sitter grammar prints a one-time stderr WARNING and falls back to regex.

Contract of the format it writes = `card_format.py`. Authoring recipe = `__HQ/guides/Guide__MakeCard.md`.
