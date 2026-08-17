# get_codeblock — TLDR

Returns a self-contained structural block containing a line — for code
(`.py`/`.ts`/`.js`/`.cs`/`.cpp`/`.cc`/`.h`/`.hpp`/`.c`) AND Markdown (`.md`: heading sections).
Lets an agent get precise context around any location, or a file's table of contents, without
reading the whole file.

> **Dependencies:** Python (`.py`) and Markdown (`.md`) are zero-dependency. C/C++, C# and
> TypeScript/JS use tree-sitter grammars — see `get_codeblock/requirements.txt`. If a needed
> package is missing, the tool prints the exact `pip install` command for the interpreter that
> ran it (no traceback) — just run it and retry.

## Route yourself

| Your goal | Command |
| --- | --- |
| "What's in this file? Where do I go?" | `--file PATH` (bare — defaults to `--outline`) |
| "Pull the exact text of the section/function at `--line N` " | `--file PATH --line N --query` |
| "Give me the parent/grandparent block, not the innermost `--line N` " | add `--level -1`, `-2`, ... |
| "Give me block N counting from the file top for given `--line N` " | add `--level +1`, `+2`, ... |
| "Big file — cap outline to top 2 levels" | `--file PATH --outline --level 2` |

## Workflow

```
get_codeblock --file PATH                   # outline: find the line you want
get_codeblock --file PATH --line N --query  # pull that exact block, byte-for-byte
```

## Level addressing — two different numbers, don't confuse them

- The **level printed in output** (`Block level: N`) = real nesting depth (1 = file top,
  deeper = higher number).
- The **`--level` flag** (used with `--line`) picks a block two ways:
  - `+N` = absolute — go to depth N from the top.
  - `0` / `-N` = relative — N steps up from the block at `--line` (`0` = that block itself,
    the default).
  - With `--outline`, `--level` instead caps the max depth shown — it's not an address there.

## Gotchas

- **Bare `--outline` is an adaptive OVERVIEW, not the full tree.** It sizes depth to
  the file: tiny files / a lone top-level object expand to level 2; otherwise it shows
  level 1 only when a deeper map would exceed ~15% of the file or ~40 rows. The header
  line reports total depth + per-level counts (`depth 3, L1=1 L2=5 L3=1, showing 1..2`)
  so you know there's more. Add `--level N` for an EXACT depth cap (high N = everything).
- Transparent frames (a C#/C++ `namespace`, `extern "C"`) render with a `.` marker
  instead of a level number — they're a wrapper, not a nesting level.
- `--outline` works for Python (indentation), Markdown (headings), and C/C++ & C#
  (tree-sitter). TypeScript/JS have no outline yet — it errors out.
- `--outline` range end is "line before the next same-or-shallower header" — a TOC estimate,
  not the exact block boundary. Use `--query` when you need the real end line.
- The green level-legend line and the outline's `#outline` / `Level  Range` header only print
  on a real terminal (`isatty()`). Piped/programmatic callers get bare
  `#Block level: N range: X-Y` lines — nothing extra to parse.
- `--query` prints `#File: PATH` as its very first line, before `#Block level:` — so a block
  self-identifies its source when several extractions get concatenated and the call that
  produced them is no longer in view.
