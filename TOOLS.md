# TOOLS — Agent Router Directive

**THIS IS NOT DOCUMENTATION. THIS IS YOUR ROUTER.**

When you are working in this project and need to inspect code, understand dependencies, or edit files at scale — **consult this file first**. Treat these rules the same way you treat your built-in tool instructions (read_file, write_file, terminal). They constrain how you work.

---

## ROUTE YOURSELF — Pick Tool by Task

Match your current goal to exactly one path below. Do not guess which tool fits; follow the mapping.

| Your task | Primary tool(s) | Secondary / verification |
|-----------|-----------------|--------------------------|
| "What does this project look like? What depends on what?" | `graph_from_cards` (`--view depth`) | then `--file PATH` for focus slice |
| "I need to work on FILE — give me its context" | `collect_card_bundle FILE --depth 1..2` | then read the bundle, not raw sources |
| "Who uses this file / symbol? What breaks if I change it?" | `find_code_usage --file PATH [--symbol NAME]` | add `--verbose` for line numbers → use with `get_codeblock` |
| "Show me just this function/class/block around line N" | `get_codeblock --file PATH --outline` (map) → `--line N --query` (text) | use `--level K` to zoom in/out the nesting ladder |
| "Quick glance: what public API does this Python file expose?" | `show_pyfile_api FILE.py` | treat as hint only; verify with raw code when precision matters |
| "Create or refresh a card for FILE" | `make_interface_card FILE --force > __map/FILE.md` | then fill `<|Agent: …|>` placeholders → run `validate_cards` |
| "Are my cards valid / up-to-date?" | `validate_cards` (format) + `check_cards_freshness` (stale vs source) | fix issues before trusting cards for reasoning |
| "Mass find-and-replace across many files" | `replace_in_files FOLDER MASK -r FIND WITH --dry-run` | add `-m 'EXPR'` guard if context-sensitive; confirm dry-run then run without it |

**RULE:** If your task is not in this table, fall back to:
1. Source analysis tools (`find_code_usage`, `get_codeblock`) for facts about code.
2. Card-map tools (`graph_from_cards`, `collect_card_bundle`) for topology and context.
3. Only read raw source files when no tool gives you what you need precisely.

---

## PRE-FLIGHT: Before Using Any Tool

These steps are **mandatory**, not optional:

1. **Open the tool's TLDR before running it:** `__HQ/tools/<name>__TLDR.md`
   - This is your quick-reference for flags, idiomatic usage, and gotchas.
   - Do NOT rely solely on `--help`; TLDR contains patterns specific to this project workflow.
2. **Run from project root.** Card tools (`make_interface_card`, `validate_cards`,
   `check_cards_freshness`, `graph_from_cards`, `collect_card_bundle`) resolve `--project-root` and
   `__map/` from `CONFIG__TOOLS.PROJECT_ROOT` automatically when the flag is omitted (sanity-checked
   against a stale/foreign config). Generic tools (`find_code_usage`, `get_codeblock`,
   `show_pyfile_api`) resolve relative paths from **cwd** instead, and only read
   `CONFIG__TOOLS.PROJECT_ROOT` if you write `--project-root @` explicitly. See
   `__dev/vision/Vision01__path-and-flag-conventions.md` for the full contract.

This sequence is: TOOLS.md → `<tool>__TLDR.md` → execute tool. Do not skip step 1.

---

## WORKFLOW PATTERNS — Common Scenarios

### Pattern A: Understanding an unfamiliar file
```
graph_from_cards --file TARGET.py --verbose 1      # see its position + deps + consumers
collect_card_bundle TARGET.py --depth 1            # get card + dependency APIs in one block
find_code_usage --file TARGET.py                   # verify real consumed surface
get_codeblock --file TARGET.py --outline           # structural map before reading code
```

### Pattern B: Assessing blast radius of a change
```
find_code_usage --file CHANGED.py --verbose        # who imports what, at which lines?
graph_from_cards --file CHANGED.py --edges in      # upstream dependents (who breaks?)
# Then for each affected file: get_codeblock --line N --query to see exact usage context
```

### Pattern C: Creating/updating a card
```
make_interface_card FILE.py --force > __map/FILE.py.md   # generate skeleton with facts
# You (the agent) now fill all <|Agent: …|> placeholders by reading the actual code.
validate_cards                                           # verify format compliance
check_cards_freshness                                    # confirm freshness status
```

### Pattern D: Mass refactoring / migration
```
replace_in_files . "*.py" -r "OLD_TEXT" "NEW_TEXT" --dry-run    # preview impact first!
# Inspect output; if guard needed:
replace_in_files . "*.py" -m 'line.startswith("def ")' "OLD" "NEW" --dry-run
# Once confirmed, rerun WITHOUT --dry-run to apply.
```

---

## PROHIBITIONS — What NOT to Do

- **DO NOT** read entire source files when a tool can give you exactly what you need (card bundle, codeblock, API hint). Use tools first; raw reads are fallback only.
- **DO NOT** run a tool without reading its TLDR file first. You will miss idiomatic flags and project-specific conventions.
- **DO NOT** trust `show_pyfile_api` output as specification — it is an AST hint with possible inaccuracies. Verify against actual code when correctness matters.
- **DO NOT** ignore card freshness. If `check_cards_freshness` marks a card outdated, refresh it before using it for reasoning. Stale cards lead to wrong conclusions.
- **DO NOT** run `replace_in_files` without `--dry-run` first. Always preview the blast radius on text changes across files.

---

## TOOL REFERENCE INDEX

All CLI tools run from project root: `python __HQ/tools/<name>.py [args]`

### Source analysis (facts about raw code)

| Tool | One-liner |
|------|-----------|
| `find_code_usage.py --file PATH` | Reverse import index: who really imports this file/symbol and which symbols they consume |
| `get_codeblock.py --file PATH [--line N]` | Structural block around a line: `--outline` for TOC, `--query` for exact framed text |
| `show_pyfile_api.py FILE.py` | Python AST hint: public functions/classes with signatures + imports (quick glance only) |

### Card map ("second compilation" over `__map/`)

| Tool | One-liner |
|------|-----------|
| `make_interface_card.py FILE [--force]` | Stamp a card skeleton from source (facts auto-filled, prose as `<\|Agent:\…\|>`) |
| `validate_cards.py` | Gate cards against CARD_FORMAT contract; reports issues and awaiting-agent markers |
| `check_cards_freshness.py` | Which cards are stale vs source (git/mtime) + orphans |
| `graph_from_cards.py [--view tree\|depth]` | Project topology from cards: modules, edges, hotspots, cycles, focus slices |
| `collect_card_bundle.py FILE [--depth N]` | Target card + its deps' Public API in one block (for passing context to another agent) |

### Maintenance

| Tool | One-liner |
|------|-----------|
| `replace_in_files.py FOLDER MASK -r FIND WITH [-m EXPR] [-n]` | Batch find-and-replace by mask with optional Python guard; `-n` = dry-run first |

### Non-CLI files (read/edit only, do not run)

| File | One-liner |
|------|-----------|
| `CARD_FORMAT.py` | Card format contract: section names, deps columns, aliases — the schema cards must follow |
| `CONFIG__TOOLS.py` | Per-project defaults: PROJECT_ROOT, LANGUAGE, TEST_DIRS, DECL_BACKEND |

Each CLI tool has a one-screen TLDR: `__HQ/tools/<name>__TLDR.md` (glance-and-apply examples).

---

## ENVIRONMENT & DEPENDENCIES

- **Run from project root:** `python __HQ/tools/<name>.py …`. See "Getting started" above for how
  `--project-root` resolves per tool category (card tools vs generic tools) — it isn't the same
  everywhere on purpose.
- **Language auto-detected from extension.** Python (indentation, stdlib `ast`); `.ts`/`.js`, `.cs`,
  `.cpp`/`.h`/…, `.yaml`/`.yml` (tree-sitter); Markdown (`.md`) and plain text (`.txt`,
  experimental) for `get_codeblock`.
- **Dependencies are minimal and OPTIONAL per language.** Python, Markdown and plain text work
  with **zero** third-party packages. The tree-sitter languages (incl. YAML) need grammar
  packages — see `get_codeblock/requirements.txt`.
  - `get_codeblock` **preflights**: if a language you use needs a package that isn't installed, it
    prints the exact `pip install` command for the current interpreter (no traceback) — run it and retry.
  - `make_interface_card` on TS/JS & C#: backend `CONFIG__TOOLS.DECL_BACKEND` = `auto` (tree-sitter if
    present, else regex) · `treesitter` (force) · `regex` (force zero-dep fallback). A missing grammar
    prints a one-time stderr WARNING naming the pip package, then falls back to regex.
  - Install grammars: `<python> -m pip install -r get_codeblock/requirements.txt` (no numpy/torch
    cascade; needs Python >= 3.10). All CLI tools force UTF-8 stdout (cards/commits are often Cyrillic).
- **The folder is self-contained** and travels with a project by copying — except `__delme/` and
  `__dev/` (dev-only notes/history/vision, safe to delete when deployed — `deploy_hq.py` already
  excludes both). `CONFIG__TOOLS.py` holds per-project defaults
  (`PROJECT_ROOT`, `LANGUAGE`, `TEST_DIRS`, `DECL_BACKEND`); `CARD_FORMAT.py` is the card-shape contract.

---

**END OF DIRECTIVE.** When in doubt about how to use these tools, re-read this file. It is your router; follow it.
