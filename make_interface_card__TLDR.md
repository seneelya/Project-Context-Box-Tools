# make_interface_card

The card **STAMP**: ONE command → a ready `.md` card skeleton where the FACT sections are
filled deterministically and the prose is left as `<Agent: …>` directive lines for the LLM to
complete after reading the source. It analyzes nothing new — it ORCHESTRATES three facts.

**Target:** `make_interface_card.py <file> [--project-root R] [--out PATH] [--force [--discard-prose]]` — multilingual (py/ts/cs). `<file>` also as `--file`, same thing.

**`--project-root`** — card-tool rule (`__map/` has no meaning relative to cwd): not given ->
implicitly `CONFIG__TOOLS.PROJECT_ROOT`, sanity-checked (must be an ancestor of where this script
itself lives — a stale/foreign config REFUSES rather than silently stamping the wrong tree). `@` ->
same, explicitly, unchecked. Literal path -> used as given, unchecked.

## Quick use  (copy, tweak, run)
```
make_interface_card.py <f>.py --project-root . --out __map/<f>.py.md   # stamp → write the card
make_interface_card.py <f>.py --project-root .                         # preview to stdout (no write)
make_interface_card.py <f>.py --project-root . --out <card>            # re-stamp: MERGE — facts refreshed, prose KEPT
make_interface_card.py <f>.py --project-root . --out <card> --force    # on an EMPTY stamp: reset, as before
make_interface_card.py <f>.py --project-root . --out <card> --force --discard-prose  # on a FILLED card: required, see below
make_interface_card.py --all                                          # bulk: whole tree, CONFIG LANGUAGE
make_interface_card.py --all --language py,ts                         # bulk: POLYGLOT tree (or 'all')
```

**`--all` is single-language unless you say otherwise.** Extensions come from
`CONFIG__TOOLS.LANGUAGE` (which may itself be a list), so in a `python` project a bulk pass
used to skip every `.js`/`.ts` file *silently* — a polyglot repo (a python backend and its own
JS front end in one tree) got a half-built map and nothing said so. `--language` overrides per
run: comma/space separated, `all` for every known language, short forms `py/ts/js/tsx/cs`
accepted. The pass now prints the languages and extensions it went by, even on success.
Per-FILE analysis was always polyglot — only the bulk selection was not.

## The three facts it fills

* **Declared surface + signatures** — Python → `show_pyfile_api.collect` (ast, exact param types);
  TS/JS/C# → `get_codeblock` declarations (structural block headers).
* **Consumed surface** — `find_code_usage` downstream: who REALLY imports each symbol
  (`consumers N: file…`); exposes leaked-private and dead surface.
* **Dependencies** — `find_code_usage --incoming`, resolved to files.

## Flags & output

* **`--out PATH`** — write the card file (creates folders). On an EXISTING card it **MERGES**:
  facts are re-derived from source, prose is carried over by NAME (not by position/signature text —
  see below), and a stderr delta lists what was kept/renamed/still-needs-writing. It does NOT
  refuse and it does NOT need `--force`. Without `--out` it prints to stdout (redirect yourself).
* **Identity across a re-stamp** — a symbol's prose survives by its NAME, found by position in the
  signature (before `(`/`=`, else after known language keywords), never by guessing "first word" of
  the signature text (that broke on `function foo(x)`/`async def foo`/`public static void Foo` —
  see `REQ-004+005_merge-identity-design.md`). Same name, different signature (became `async`, new
  param) → prose kept with a `⚠ поменялась сигнатура -` marker prepended (stacks on repeat drift,
  no counter). No exact name, but a similar one → treated as a rename, prose kept with a
  `⚠ похоже на переименование, было …` marker. Neither → the entry goes to `## Salvage` as before.
* **`--force`** — write a FRESH stamp instead of merging: **every line of prose in that card is
  discarded**, replaced by `<|Agent:NN …|>` directives. Use it to deliberately reset a card you
  intend to rewrite, never as "overwrite" — the merge path is the one that overwrites safely.
  On a card that still has EMPTY prose (never filled in), `--force` works exactly as before. On a
  card with FILLED prose, `--force` alone is **REFUSED** (exit 2, nothing written) — pass
  `--discard-prose` too to confirm you really mean to throw it away. Same rule under `--all`
  (counted as `blocked`, listed by file, non-zero exit if any).
* Emits `## Package layout` + `### Re-exports` for package/index files automatically.
* Declared-surface backend = `CONFIG__TOOLS.DECL_BACKEND` (`auto|treesitter|regex`); on a
  missing tree-sitter grammar prints a one-time stderr WARNING and falls back to regex.

Contract of the format it writes = `CARD_FORMAT.py`. Authoring recipe = `__HQ/guides/Guide__MakeCard.md`.
