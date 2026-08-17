# get_codeblock — GUIDE

A structural navigator for source files. Point it at a **line** and it returns the exact
block(s) that contain it, with real boundaries; or ask for a file's **outline** (its table of
contents). It parses each language for real (tree-sitter / indentation), so it is precise where
grep and brace-counting are not.

**Use it to stop reading whole files.** Grep gives you line numbers; get_codeblock turns a line
into "what is this, and where are its edges" — then you pull just that region.

Languages: Python `.py` · C/C++ `.cpp .cc .cxx .h .hpp .c` · C# `.cs` · TypeScript/JS/TSX
`.ts .js .tsx .jsx` · CSS/SCSS `.css .scss` · Markdown `.md`.

---

## Three modes

### 1. `--outline` — the map (what's in this file, where)

```
python get_codeblock.py --file PATH                # bare = outline (the default)
```
```
//outline — depth 3, L1=1 L2=5 L3=1, showing 1..2
//.   [1-56] namespace Edge.Cases
//1   [3-55] public class Widget
//  2 [8-17]  public Widget( int count, string name)
//  2 [19-28] public int Increment()
//  ...
```
- Header line = **the shape of the whole file**: total `depth`, count of blocks per level
  (`L1=1 L2=5 L3=1`), and how deep it is `showing`. So even a shallow view tells you there's more.
- Each row: `<level> [start-end] <label>`. Indentation mirrors nesting.
- `.` instead of a number = a **transparent frame** (a `namespace`, `extern "C"`) — shown so you
  see the wrapper, but it adds no depth.
- **Bare `--outline` is adaptive**: it sizes the shown depth to the file (a lone top-level object
  expands; a big flat file shows just the tops). Force an exact depth with `--level N`
  (`--level 1` = tops only, `--level 10` = everything). Outline lists **named** blocks only —
  functions/classes/methods/rules — never anonymous noise.

### 2. `--line N` — the ladder (what contains this line)

```
python get_codeblock.py --file PATH --line N
```
```
//Block level: 3 range: 70-73  () => {…}
//Block level: 2 range: 69-74  {…} object
//Block level: 1 range: 17-77  function $constructor<T extends ZodTrait, …>
```
Every block enclosing line N, innermost → outermost, each with its range **and a label of what
it is**. Anonymous brace regions (arrow bodies, object literals) get a short tag. This is the
grep companion: grep → line → ladder → pick the rung you want.

### 3. `--query` — pull the block's text

```
python get_codeblock.py --file PATH --line N --query
```
```
//File: PATH
//Block level: 2 range: 87-97  public async Task<Uri> GetStreamingUrlAsync(File file)
        public async Task<Uri> GetStreamingUrlAsync(File file)
        { … byte-for-byte … }
//Block end: 97
```
Returns one block's exact text, framed by `//File:` … `//Block end:` so several extractions can
be concatenated and each still says where it came from. Add `--numbered` to prefix code lines
with absolute line numbers (off by default — raw text stays copy/paste-safe).

---

## Picking which block (with `--line`)

By default you get the **innermost** block. Two flags move the target — pick one, don't mix:

- **`--ancestor-level N`** — relative, the usual one: walk **N blocks up** from where the line
  lands. `0` = the block itself (default), `1` = its parent, `2` = grandparent.
- **`--level N`** — absolute: jump to depth **N counted from the file top** (`1` = outermost).

`Block level: K` in the output is the block's real nesting depth (1 = file top). Depth is one
truth: `--line`'s ladder and the level a tool reports for a symbol always agree.

---

## What counts as a block

A block is a **multi-line brace region** (or, in Python, an indented suite): functions, classes,
methods, interfaces, enums, control blocks (`if`/`for`/`while`/`try`…), and — in JS/TS —
multi-line object literals and arrow-function bodies (so a method hidden in
`{ value: (x) => {…} }` still resolves). A one-line `if (x) return;` or a single-line `{…}` is
**not** a block — nothing to fold.

Comments directly above a block (doc `///`/`/** */`, `#`, `//`, banners) **glue onto it**: land
on the comment and you get the block it documents; the block's range starts at the comment.

---

## Dependencies

Python and Markdown need nothing. The tree-sitter languages need a grammar package
(`get_codeblock/requirements.txt`). You don't have to pre-install: run the tool, and if a package
is missing it prints the exact `pip install …` command **for the interpreter that ran it** — run
that, retry. Nothing else fails silently.

---

## Typical agent workflow

```
# 1. Orient — one call shows the file's structure
get_codeblock --file src/thing.ts

# 2. Found the area at line N (from the outline, or from grep) — see what encloses it
get_codeblock --file src/thing.ts --line N

# 3. Pull exactly that block (or a parent, via --ancestor-level)
get_codeblock --file src/thing.ts --line N --query
```

That's usually all you need: outline to locate, one `--line`/`--query` to extract — instead of
reading the file.

---

## Good to know

- **Piped output is clean**: block/outline lines are comment-prefixed (`//`/`#`) and parseable;
  human hints (the green legend, "add --level N") print only on a real terminal.
- **`--outline` end lines** for Python/Markdown are a table-of-contents estimate (line before the
  next same-or-shallower header); the tree-sitter languages give the exact end. For a precise
  boundary always trust `--query`.
- **SCSS caveat**: nested rule sets, `&` nesting, `@media`/`@supports` are solid; parameterized
  `@mixin($x)` / `@include(...)` / unquoted `url(../x)` parse imperfectly (css grammar) but don't
  derail the surrounding structure.

See `get_codeblock__TLDR.md` for the one-screen version, `get_codeblock__README.md` for the full
reference (every flag, edge cases, architecture).
