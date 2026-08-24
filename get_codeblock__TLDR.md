# get_codeblock — TLDR

Returns a self-contained structural block containing a line — for code
(`.py` · `.ts .js .tsx .jsx` · `.cs` · `.cpp .cc .cxx .h .hpp .c` · `.css .scss`) AND Markdown
(`.md`: heading sections). Lets an agent get precise context around any location, or a file's
table of contents, without reading the whole file.

> **Dependencies:** Python (`.py`) and Markdown (`.md`) are zero-dependency. C/C++, C#,
> TypeScript/JS/TSX and CSS/SCSS use tree-sitter grammars — see `get_codeblock/requirements.txt`.
> If a needed package is missing, the tool prints the exact `pip install` command for the
> interpreter that ran it (no traceback) — just run it and retry.

## Route yourself

| Your goal | Command |
| --- | --- |
| "What's in this file? Where do I go?" | `--file PATH` (bare — defaults to `--outline`) |
| "Pull the exact text of the section/function at `--line N` " | `--file PATH --line N --query` |
| "Give me the parent/grandparent block, not the innermost `--line N` " | add `--ancestor-level 1`, `2`, ... |
| "Give me block N counting from the file top for given `--line N` " | add `--level 1`, `2`, ... |
| "Big file — cap outline to top 2 levels" | `--file PATH --level 2 --outline` |
| "Grep gave me N hits — where do they all live, one call" | `--file PATH --line a,b,c` (batch, one merged map) |
| "Pull N blocks by line, one call" | `--file PATH --line a,b,c --query` (merges touching/nested ranges) |

## Workflow

```
get_codeblock --file PATH                   # outline: find the line you want
get_codeblock --file PATH --line N --query  # pull that exact block, byte-for-byte
```

## Batch — `--line` takes an array

`--line 1827,606,867` — one file parse, not N calls. `--level`/`--ancestor-level` take an array
too, broadcast against `--line` (one value → replicated; shorter → last value repeats; longer →
excess ignored). Same three modes as single-line, just merged:
- bare → survey: one merged map of the whole batch (shared ancestors print once, not per hit).
- `--outline` → one merged tree (same merge, sourced from the outline itself).
- `--query` → one `■BLOCK` per resolved range; ranges that touch or nest COLLAPSE into one —
  returning the same file text twice, or with a fake seam where the source has none, isn't a
  format quirk, it's wrong output.

## Level addressing — two flags, one for each direction

- The **level printed in the ladder/outline** (the bare number in front of each row) = real nesting
  depth (1 = file top, deeper = higher number). `--query`'s own `■BLOCK : A-B` never states a level
  at all — it's the exact printed range, true by construction; if a query merged >1 resolved block
  it adds a same-line ` = ranges : Level L  A-B, Level L  A-B, …` tail listing each real constituent
  instead of one (possibly wrong) number for the whole span.
- Picking a block at `--line N` — two self-describing flags (don't mix):
  - **`--ancestor-level N`** = relative — walk N blocks **up** from where the line lands
    (`0` = the innermost block itself, the default; `1` = parent; `2` = grandparent). This is
    the usual one. (Internally = `--level -N`; the raw negative form still works.)
  - **`--level N`** = absolute — jump to depth N counted from the file **top** (`1` = top).
  - With `--outline`, `--level N` instead caps the max depth shown — it's not an address there.

## Gotchas

- **Bare `--outline` is an adaptive OVERVIEW, not the full tree.** It sizes depth to
  the file: tiny files / a lone top-level object expand to level 2; otherwise it shows
  level 1 only when a deeper map would exceed ~15% of the file or ~40 rows. The header
  line reports total depth + per-level counts (`depth 3, L1=1 L2=5 L3=1, showing 1..2`)
  so you know there's more. Add `--level N` for an EXACT depth cap (high N = everything).
- Transparent frames (a C#/C++ `namespace`, `extern "C"`) render with a `.` marker
  instead of a level number — they're a wrapper, not a nesting level.
- `--outline` works for Python (indentation), Markdown (headings), and the tree-sitter
  languages C/C++, C#, TypeScript/JS/TSX (`.ts .js .tsx .jsx`), and CSS/SCSS
  (`.css .scss`). SCSS note: `@mixin`/`@include`/`@function` WITH parameters parse
  imperfectly (css grammar), but nested rule sets, `&` nesting and `@media`/`@supports` are solid.
- Outline **numbers named blocks** (functions/classes/methods/rules). In JS/TS that includes
  name-bound arrows/functions (`const Foo = () => {…}`, `value: () => {…}`, class fields) — React
  components show up; expression-bodied arrows and anonymous inline callbacks stay out by design.
  At the **file level** it ALSO shows filler bands — imports, module constants, comment/license
  blocks — as `.` rows with an **index label** (`imports: os, sys, …`, `assign: logger`): the
  file's data-at-a-glance, not noise. Inside blocks, only named ones show.
- **Depth is one truth (one engine)**: `--line`'s ladder, `--outline`, and `line_level` (the depth
  a tool reports for a symbol) all agree — same block boundaries for the same line, by construction.
  A multi-line `{…}` (incl. JS object literals / arrow bodies) is a block; a one-line
  `if (x) return;` / single-line `{…}` is not.
- **A block ends at its last content line** (like `}`); trailing blank/comment lines belong to the
  next block's preamble. `--outline` ranges are exact for the tree-sitter languages — including
  Python with its grammar installed. Markdown headings are a TOC estimate (line before the next
  same-or-shallower heading); Python's `ast`-fallback (no grammar) is reduced — use `--query` for
  the precise boundary in those.
- **Piped/programmatic output is clean**: every metadata line is comment-prefixed and parseable;
  only the green human hints (legend, "add --level N") are suppressed off a real terminal
  (`isatty()`).
- `--query` prints `#File: PATH (N lines)` once, at the very top, before any `■BLOCK` — so the
  whole call self-identifies its source even with several blocks in one output.
- **`■` = "this line is ours, not the file's"** — `■BLOCK`/`■END` never occur at the start of a
  real source line, so a human pasting a chunk of terminal output straight into code can't
  mistake one for a real comment. Everything else printed (metadata, TTY hints) is still just the
  language's own comment syntax, no marker.

## Not Enough info? whats next? - read `get_codeblock__GUIDE.md`