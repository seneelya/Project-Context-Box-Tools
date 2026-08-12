# Tools

Dev "hands" for the ProjectStarter scheme — small, universal CLIs that compose over pipes (Unix
philosophy), not one monster. **This file is the ROUTER**: pick a tool by task, read the one-line
description + main flags; open the tool's `<name>__TLDR.md` only when you need copy-paste examples.

**Conventions.** Every tool has a one-screen `<name>__TLDR.md` (glance-and-apply examples) and a full
`--help`. Run tools from the **project root**: `python __HQ/tools/<name>.py …` (`--project-root .`
and the `__map/` cards dir resolve from there). The folder is self-contained and travels with a
project by copying — except `__delme/` (dev-only notes, safe to delete when deployed) and
`CONFIG__TOOLS.py` (per-project config).

## Pick by task
- **Make / refresh a card** for a file → `make_interface_card` → check with `validate_cards` / `check_freshness`  (Python AST peek: `py_api`)
- **Read the card map** (topology, gather context) → `rebuild_graph`, `bundle`
- **Answer a fact about source** (who imports it · a code block · a file's API) → `codebase_import_search`, `get_codeblock`, `py_api`
- **Mass-edit across files** (migrate / rename) → `replace_in_files`
- **Change the card format itself** → `card_format` (the contract)

---

## 1. Source analysis — fact-fetchers over raw code

Factual questions about source directly (heuristics for `.py` `.ts`/`.js` `.cs`, plus Markdown for
`get_codeblock`). They fetch facts; they do NOT build the project graph.

- **`codebase_import_search.py --file PATH`** — reverse import index: who *really* imports the target
  and which symbols they consume (the "consumed surface" = real external interface). Flags: `--incoming`
  (upstream deps), `--verbose` (per source file), `--tests-only`, `--symbol NAME`, `--language`.
- **`get_codeblock.py --file PATH [--line N]`** — the self-contained structural block around a line.
  No `--line` + `--outline` = the file's table of contents; `--query` = the exact framed text;
  `--level N` picks which block (`0` = the line, `-N` = enclosing parents, `+N` = from the top).
- **`py_api.py <file.py>`** — Python-only AST hint: public functions/classes/methods with signatures +
  imports (internal/external) + first docstring line. Reads only, never a gate.

## 2. Card map — the "second compilation" over `__map/` cards

Build and consume the per-file `.py.md` card layer (this is where project topology lives — kept OUT of
layer 1 on purpose). Default cards dir `./__map`; override with `--cards-dir` / `--project-root`.

- **`card_format.py`** — (not a CLI) the format contract: section/subsection names, deps columns, the
  `File Path` graph edge, aliases, helpers. Edit the card shape HERE; the tools import it. Running it
  prints the skeleton.
- **`make_interface_card.py <file> --project-root R [--out PATH] [--force]`** — the card STAMP: one
  command → a fact-filled card skeleton (declared API + signatures × consumed surface `consumers N` ×
  deps); prose left as `<Agent: …>`. Multilingual (py/ts/cs). `--out` writes (won't clobber without
  `--force`). Backend `CONFIG__TOOLS.DECL_BACKEND`.
- **`validate_cards.py [--cards-dir P] [--project-root P]`** — gate cards against the contract (H1,
  sections, deps resolve, orphans). Coaches the author; exit 1 on problems.
- **`check_freshness.py [--cards-dir P] [--project-root P]`** — which cards are stale vs source
  (git mode / mtime fallback) and which are orphans. Exit 1 if any.
- **`rebuild_graph.py [--cards-dir P] [--json]`** — flat topology from cards: modules + summaries +
  `depends_on`, entry points, leaves, unresolved refs. `--json` = draft feed for a visualizer.
- **`bundle.py <file> [--cards-dir P] [--depth N]`** — call-saver: target card + only its deps'
  Public API in one block. `--depth` expands transitively (default 1).

## 3. Maintenance / migration

- **`replace_in_files.py <folder> <mask> [-r FIND WITH | -m EXPR FIND WITH] [-R] [-n]`** — batch
  find-and-replace by mask. `-r` = substring; `-m EXPR` = only on lines where the Python `EXPR`
  (`line`, `re`) is true (guard against prose); `-R` = recurse; **`-n`/`--dry-run` = count + list hit
  line numbers, write nothing.** Escapes `\n \t \r \\` decoded in `FIND`/`WITH`.

---

## Configuration notes

- `CONFIG__TOOLS.py` (per-project) supplies defaults `PROJECT_ROOT`, `LANGUAGE`, `TEST_DIRS`,
  `DECL_BACKEND` (CLI flags override).
- Source language auto-detected from extension: `.py`, `.ts`/`.js`, `.cs`. Python indentation-based;
  TS/JS + C# brace matching with string/verbatim awareness.
- All CLI tools force UTF-8 stdout (cards/commits are often Cyrillic).
- Tests: `py test/check.py` (full golden report) · `py test/check.py --fails` (regressions only).
- **Declared-surface backend** (`make_interface_card` on TS/JS and C#): `CONFIG__TOOLS.DECL_BACKEND` =
  `auto` (tree-sitter if installed, else regex) · `treesitter` (force) · `regex` (force zero-dep
  fallback). Python always uses stdlib `ast`. Tree-sitter is OPTIONAL (no numpy/torch cascade):
  `pip install tree-sitter tree-sitter-typescript tree-sitter-c-sharp`. In `auto`/`treesitter`, a
  missing grammar prints a one-time stderr WARNING (names the pip package + "regex fallback").
