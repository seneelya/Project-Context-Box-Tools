# get_codeblock — GUIDE

Navigate source files by structure — don't read them whole. Point the tool at a **line** to get
the exact block(s) that contain it, with real boundaries; ask for a file's **outline** to get its
table of contents. It parses each language for real (tree-sitter / indentation), so trust its
boundaries where grep and brace-counting fail.

**Default to this instead of reading files.** Grep gives you a line number; turn that line into
"what is this, and where are its edges", then pull just that region.

Languages: Python `.py` · C/C++ `.cpp .cc .cxx .h .hpp .c` · C# `.cs` · TypeScript/JS/TSX
`.ts .js .tsx .jsx` · CSS/SCSS `.css .scss` · Markdown `.md`.

---

## Three modes

### 1. `--outline` — get the map (what's in this file, where)

Run this first on any unfamiliar file:

```
python get_codeblock.py --file PATH                # bare = outline (the default)
```
```
#outline — depth 2, L1=1 L2=2, showing 1..2
#.   [1-11]  imports: logging, contextlib, anyio, starlette.websockets, …
#.   [13-13] assign: logger
#1   [16-67] async def websocket_server(scope, receive, send)
#  2 [35-51] async def ws_reader()   # Pump inbound frames into the read stream …
#  2 [53-62] async def ws_writer()   # Drain the write stream out to the WebSocket …
```

Read the header line as **the shape of the whole file**: total `depth`, blocks per level
(`L1=1 L2=2`), and how deep it's `showing`. A shallow view still tells you there's more.

Read each row as `<level> [start-end] <label>`; indentation mirrors nesting. Decode the marker:
- **a number** (`1`/`2`/…) = a **named block** at that depth (function/class/method/rule).
- **a `.`** = a **level marker**, not a name — either a **transparent frame** (a `namespace`,
  `extern "C"`: shown so you see the wrapper, but it adds no depth) OR, at the **file level**, a
  **filler band** whose label indexes its contents (`imports: …`, `assign: logger`, a license
  block). Treat file-level `.` rows as the file's data-at-a-glance.

Don't expect the full tree from bare `--outline` — it's **adaptive**, sizing shown depth to the
file (a lone top-level object expands; a big flat file shows just the tops). Force an exact depth
with `--level N` (`--level 1` = tops only, `--level 10` = everything).

### 2. `--line N` — get the ladder (what contains this line)

Landed on a line (from grep or the outline)? Ask what encloses it:

```
python get_codeblock.py --file PATH --line N
```
```
//You hit in block lvl 4:
//   4 [49-52] for (int i = 0; i < 3; i++)
//  3  [47-53] public void Deep()
// 2   [44-54] public class Inner
//1    [3-55] public class Widget
```

Read it as a **staircase**: the header names the level you hit; each rung is
`<level> [start-end] <label>`, innermost at the top → outermost at the bottom, indented so deeper
nesting steps right. Anonymous brace regions (arrow bodies, object literals) carry a short tag
(`{…} object`, `() => {…}`). Pick the rung you want, then `--query` it.

### 3. `--query` — pull the block's text

Extract one block byte-for-byte:

```
python get_codeblock.py --file PATH --line N --query
```
```
//File: PATH
//Block level: 4 range: 49-52  for (int i = 0; i < 3; i++)
                for (int i = 0; i < 3; i++)
                { … byte-for-byte … }
//Block end: 52
```

Rely on the `//File:` … `//Block end:` frame to keep several extractions distinct when you
concatenate them — each still says where it came from. Add `--numbered` to prefix code lines with
absolute line numbers (off by default — raw text stays copy/paste-safe).

---

## Pick which block (with `--line`)

You get the **innermost** block by default. To target another rung, add ONE flag — don't mix them:

- **`--ancestor-level N`** — relative, the usual one: walk **N blocks up** from where the line
  lands. `0` = the block itself (default), `1` = its parent, `2` = grandparent.
- **`--level N`** — absolute: jump to depth **N counted from the file top** (`1` = outermost).

Read `Block level: K` (under `--query`) / `lvl K` (in the ladder) as the block's real nesting
depth (1 = file top). Trust that this depth is **one truth**: the ladder, the outline, and the
level any tool reports for a symbol all agree — same block boundaries for the same line.

---

## Know what counts as a block

Count as a block: a **multi-line brace region** (or, in Python, an indented suite) — functions,
classes, methods, interfaces, enums, control blocks (`if`/`for`/`while`/`try`…), and, in JS/TS,
multi-line object literals and arrow-function bodies (so a method hidden in
`{ value: (x) => {…} }` still resolves). Don't expect a one-line `if (x) return;` or a single-line
`{…}` to be a block — there's nothing to fold.

Expect a block to **end at its last content line** (like `}`). Trailing blank and comment lines
after it belong to the enclosing scope or, by the next rule, to the block below.

Expect comments directly above a block (doc `///`/`/** */`, `#`, `//`, banners) to **glue onto
it** — land on the comment and you get the block it documents; the block's range starts at the
comment.

---

## Install grammars on demand

Run Python and Markdown with nothing extra. For the tree-sitter languages, don't pre-install: run
the tool, and if a grammar package is missing it prints the exact `pip install …` command **for
the interpreter that ran it** (no traceback) — run that, retry. Nothing fails silently.

---

## Follow the typical workflow

```
# 1. Orient — one call shows the file's structure
get_codeblock --file src/thing.ts

# 2. Land on line N (from the outline, or from grep) — see what encloses it
get_codeblock --file src/thing.ts --line N

# 3. Pull exactly that block (or a parent, via --ancestor-level)
get_codeblock --file src/thing.ts --line N --query
```

Stop there — outline to locate, one `--line`/`--query` to extract — instead of reading the file.

---

## Good to know

- **Parse piped output directly**: block/outline lines are comment-prefixed (`//`/`#`) and
  machine-readable; human hints (the green legend, "add --level N") print only on a real terminal.
- **Trust ranges from the tree-sitter languages** (incl. Python with its grammar installed) as
  exact. Markdown headings give a TOC estimate (line before the next same-or-shallower heading);
  Python's `ast`-fallback (no grammar) is reduced. For a precise boundary in those, `--query`.
- **SCSS caveat**: nested rule sets, `&` nesting, `@media`/`@supports` are solid; parameterized
  `@mixin($x)` / `@include(...)` / unquoted `url(../x)` parse imperfectly (css grammar) but don't
  derail the surrounding structure.

See `get_codeblock__TLDR.md` for the one-screen version, `get_codeblock__README.md` for the full
reference (every flag, edge cases, architecture).
