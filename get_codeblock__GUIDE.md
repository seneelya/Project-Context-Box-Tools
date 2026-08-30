# get_codeblock — GUIDE

Navigate source files by structure — don't read them whole. Point the tool at a **line** to get
the exact block(s) that contain it, with real boundaries; ask for a file's **outline** to get its
table of contents. It parses each language for real (tree-sitter / indentation), so trust its
boundaries where grep and brace-counting fail.

**Default to this instead of reading files.** Grep gives you a line number; turn that line into
"what is this, and where are its edges", then pull just that region.

Languages: Python `.py` · C/C++ `.cpp .cc .cxx .h .hpp .c` · C# `.cs` · TypeScript/JS/TSX
`.ts .js .tsx .jsx` · CSS/SCSS `.css .scss` · Markdown `.md` · YAML `.yaml .yml` · plain text
`.txt` (experimental).

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
#File: PATH (67 lines) · 1 hit
# 1      | 16-67| async def websocket_server(scope, receive, send)
#  2     | 35-51|   async def ws_reader()
#   3    | 39-49|     try:
#    4   | 40-49|       async with read_stream_writer:
#     5  | 41-49|         async for msg in websocket.iter_text():
#      6 | 44-46|           except ValidationError as exc:
#       →|  → 45|             await read_stream_writer.send(exc)
```

Read it as a **staircase**: outermost first, deeper rungs sit closer to `|`; each row is
`<level>| <start-end>| <label>`. The LAST row is your own line — a `→` marker, never a level
number (it's a hit, not a depth), with just the line number behind it (no index — which `--line`
position it came from stops mattering once it's resolved). Pick a rung's level, then `--query` it.

### 3. `--query` — pull the block's text

Extract one block byte-for-byte:

```
python get_codeblock.py --file PATH --line N --query
```
```
#File: PATH (67 lines)
#■BLOCK : 44-46
                    except ValidationError as exc:
                        await read_stream_writer.send(exc)
                        continue
#■END : 46
```

`■BLOCK : A-B` / `■END : B` are the framing numbers — always true, exactly the slice printed
below, never a depth claim. `■` marks a line as tool-written, never file content (never occurs at
the start of a real source line, so a pasted chunk can't be mistaken for a real comment). Rely on
`#File:` … `■END` to keep several extractions distinct when you concatenate them. Add `--numbered`
to prefix code lines with absolute line numbers (off by default — raw text stays copy/paste-safe).

---

## `--line` takes an array — same three modes, one call

Grep gives you many hits, not one. `--line 45,54,38` resolves all of them in ONE file parse —
`--level`/`--ancestor-level` take an array too, broadcast against `--line` (one value replicates
to all; a shorter array repeats its last value; a longer one has the excess ignored). Same three
modes as above, each merged instead of repeated:

- **Bare** (survey) — one merged map of the WHOLE batch, sorted by file position: shared ancestors
  (the same class, the same containing function) print exactly once, not once per hit that landed
  in them. Each hit's own exact source line still gets its own `→` row, nested where it belongs.
- **`--outline`** — one merged tree, same idea, sourced from the outline itself.
- **`--query`** — one `■BLOCK` per RESOLVED range, but ranges that touch (zero gap) or nest COLLAPSE
  into one. This isn't a formatting choice: printing the same file text twice, or inserting a fake
  seam where the source has none, is wrong output, not just noisy output. A collapsed block that
  absorbed more than one real range lists every one of them (`= ranges : Level L  A-B, …`) instead
  of guessing a single level for the whole span.

```
python get_codeblock.py --file PATH --line 45,54,38 --query
```
```
#File: PATH (67 lines)
#■BLOCK : 35-51  = ranges :  Level 2  35-51,  Level 6  44-46
    async def ws_reader():
        ... (line 38 AND line 45 both landed inside this one function — printed once)
#■END : 51
#■BLOCK : 53-62
    async def ws_writer():
        ...
#■END : 62
```

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

Run Python, Markdown and plain text with nothing extra. For the tree-sitter languages
(including YAML), don't pre-install: run the tool, and if a grammar package is missing it prints
the exact `pip install …` command **for the interpreter that ran it** (no traceback) — run that,
retry. Nothing fails silently.

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
  derail the surrounding structure. A top-level `$var: value;` used to blow up the whole file's
  parse — now masked into a comment before parsing, so the rest of the file recovers.
- **Plain text (`.txt`) is experimental**: no real language understanding, just blank-line
  paragraphs/sections and list-marker splitting — the cheapest structural guess that's still more
  useful than reading the file linearly, not a claim of real prose parsing.

See `get_codeblock__TLDR.md` for the one-screen version, `get_codeblock__README.md` for the full
reference (every flag, edge cases, architecture).
