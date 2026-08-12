# Tools

Dev "hands" for the ProjectStarter scheme — small, universal CLIs that compose over pipes (Unix
philosophy), not one monster. Each tool has a `<name>__TLDR.md` (one-screen) and a
`<name>__README.md` / `--help` (full contract). Grouped by the three layers.

> **Where this lives & how to run.** These tools ship inside `__HQ/tools/`. Invoke them from the
> **project root** as `python __HQ/tools/<name>.py …` (paths like `--project-root .` and the
> `__map/` cards dir are resolved relative to that root). The folder is self-contained and travels
> with a project by copying — **except `__delme/`**, which holds dev-only notes (tracker/decisions/
> restore for building the tools) and is safe to delete in a deployed copy.

## 1. Source analysis — fact-fetchers over raw code

Answer factual questions about source directly (language-agnostic heuristics: `.py` `.ts`/`.js` `.cs`,
plus Markdown for `get_codeblock`). They fetch facts; they do NOT build the project graph.

- **`codebase_import_search.py`** — reverse import index: who *really* imports a target file and which
  symbols they consume (the factual "consumed surface" = the real external interface). Modes: default
  (downstream consumers), `--verbose`, `--incoming` (upstream deps), `--incoming --verbose` (grouped by
  source file), `--tests-only`, `--symbol NAME` filter.
- **`get_codeblock.py`** — the self-contained structural block around a file+line. Metadata probe =
  the nesting **ladder**; `--query TEXT` = framed block (header + body + end marker); `--outline` =
  a file's structural table of contents; `--level N` addresses the block (0 = the line itself,
  `-N` = enclosing parents, `+N` = from the top). Code + Markdown.
- **`py_api.py <file.py>`** — Python-only AST hint for a card writer: public functions/classes/methods
  with signatures + imports (internal/external heuristic) + first docstring line. Reads only, never a gate.

## 2. Card map — the "second compilation" over `__map/` cards

Build and consume the project's card layer (per-file `.py.md` cards). This is where "who-calls-whom" /
project topology lives — kept OUT of the source-analysis tools on purpose. Default cards dir is
`./__map` (run from the target project root); override with `--cards-dir` / `--project-root`.

- **`card_format.py`** — (not a CLI) single source of truth for the card format: section contracts,
  `File Path` edge column, aliases, `canon()`/`is_package()` helpers. Imported by the tools below.
- **`card_api.py <file> --project-root R [--out PATH] [--force]`** — the card STAMP: one command emits
  a fact-filled card skeleton (declared API + real signatures × consumed surface `consumers N` ×
  dependencies), prose left as `<Agent: …>` directives for the LLM. Orchestrates py_api/get_codeblock/
  import_search under the `card_format` contract; multilingual (py/ts/cs). `--out` writes the file
  (won't overwrite without `--force`). Declared-surface backend via `DECL_BACKEND`. Authoring recipe:
  `__HQ/guides/Guide__MakeCard.md`.
- **`validate_cards.py [--cards-dir P] [--project-root P]`** — validate cards against the format
  contract (H1 = filename, required sections, deps resolve, orphans). Coaches the author; exit 1 on problems.
- **`check_freshness.py [--cards-dir P] [--project-root P]`** — which cards are stale vs their source
  (git mode: source committed/edited after the card; mtime fallback) and which are orphans. Exit 1 if any.
- **`rebuild_graph.py [--cards-dir P] [--json]`** — flat project topology from cards: modules + summaries
  + `depends_on`, entry points, leaves, unresolved refs. `--json` is a draft feed for an external
  structure visualizer; for an LLM use the text output.
- **`bundle.py <file> [--cards-dir P] [--depth N]`** — call-saver: a target's full card + only its
  deps' Public API in one block. `--depth` expands transitively (default 1).

## 3. Maintenance / migration

- **`mask_replace.py <folder> <mask> [-r FIND WITH | -m EXPR FIND WITH] [-R]`** — batch find-and-replace
  over files by mask. `-r` = plain substring; `-m EXPR FIND WITH` = replace only on lines where the
  Python `EXPR` (with `line`, `re`) is true (a guard against prose); `-R` = recurse. Escapes `\n \t \r \\`
  are decoded in `FIND`/`WITH`.

---

## Configuration notes

- When `CONFIG__TOOLS.py` exists, `PROJECT_ROOT`, `LANGUAGE`, `TEST_DIRS` are used as defaults for the
  source-analysis tools (overridden by CLI `--project-root`, …).
- Source language is auto-detected from extension: `.py`, `.ts`/`.js`, `.cs`. Python is
  indentation-based; TS/JS brace matching with string/template-literal awareness; C# brace matching
  with verbatim strings.
- All CLI tools force UTF-8 stdout (cards/commits are often Cyrillic).
- Tests: `py test/check.py` (full golden report) · `py test/check.py --fails` (regressions only).
- **Declared-surface backend** (`card_api` on TS/JS and C#): `CONFIG__TOOLS.DECL_BACKEND` —
  `auto` (tree-sitter if installed, else regex), `treesitter` (force), or `regex` (force the
  zero-dependency fallback). Python always uses stdlib `ast`. Tree-sitter is an OPTIONAL,
  self-contained dependency (no numpy/torch cascade):
  `pip install tree-sitter tree-sitter-typescript tree-sitter-c-sharp`.
  A real parse removes the regex signature/brace edge-cases; module resolution and the
  reverse index stay ours. In `auto`/`treesitter` mode, if a grammar is missing the tool
  prints a one-time **stderr WARNING** naming the pip package and that it is running in the
  regex fallback — so an agent knows the results are lower-fidelity (silence with `regex`).
