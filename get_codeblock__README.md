# get_codeblock — Get Code Block for LLM Agents

Returns a meaningful, self-contained code block containing a specified line in a source file. Designed as both a CLI tool and importable library function for LLM agents to get contextual code around any location.

## Quick Start

```bash
# The file's map (bare = --outline): named blocks, adaptive depth
python get_codeblock.py --file path/to/file.py

# Block boundaries containing line 100 (the ladder, innermost -> outermost, with labels)
python get_codeblock.py --file path/to/file.py --line 100

# Return the actual text of the innermost block containing line 100
python get_codeblock.py --file path/to/file.py --line 100 --query

# The parent block instead of the innermost (one level up)
python get_codeblock.py --file path/to/file.py --line 100 --ancestor-level 1

# Text of the grandparent block, with line numbers
python get_codeblock.py --file path/to/file.py --line 100 --ancestor-level 2 --query --numbered
```

## Output Format

### Metadata only (default, without `--query`) — the nesting LADDER (staircase)

Prints EVERY enclosing block as a staircase, innermost → outermost (comment prefix per language).
One call shows all zoom options; then pick a `--level` and `--query` it.

```
#You hit in block lvl 3:
#   3 [139-145] if not chain:
#  2  [137-160] def resolve_chain(cfg, role):
# 1   [89-166]  def chat(cfg, role, messages):
```

The header names the depth you landed in (`lvl 3`). Each rung is right-indented so deeper nesting
steps right — innermost at the top, file-level block at the bottom.

**Fields per rung:**
- `level` — nesting depth of that block (file root = 1)
- `[X-Y]` — start and end line numbers (1-based, inclusive)
- trailing **label** — what the block is (its header, or a short tag like `{…} object`,
  `() => {…}` for an anonymous brace region)

**Level semantics** (`level` = `1 + number of enclosing block BODIES`):
- File root = **1** (the file itself is unnumbered). A block header (`if`/`for`/`def`,
  including a wrapped multi-line signature) sits at its parent's level; the body is one
  deeper. Real depths are `1,2,3,…` — **`0` is never a real depth**; it is reserved for
  `--level` addressing (see below), meaning "the block containing the line, wherever it is".
- Two axes, don't conflate: this DEPTH is what `get_line_levels` reports (and what
  `find_code_usage` prints as `levels=`); the `--level` argument below is NAVIGATION.

### Text mode (with `--query`) — block framed by anchor comments

Header + block text byte-for-byte + a footer anchor. The frame lets several extractions
(possibly from different files) be concatenated without merging, and marks the patch region
unambiguously. `--level` chooses which block from the ladder (default `0` = innermost).

```python
#File: path/to/file.py
#Block level: 3 range: 71-77
        try:
            result = do_something()
            return result
        except ValueError as e:
            logger.error(e)
#Block end: 77
```

The file line comes first so a block self-identifies its source even when several
`--query` extractions get concatenated and the originating command is no longer in view.

### `--outline` — structural table of contents (no `--line` needed)

Numbers the file's **named** blocks — headings for Markdown; functions/classes/methods/rules for
code (control blocks like `if`/`for` are excluded; in JS/TS, name-bound arrows such as
`const Foo = () => {…}` ARE included) — hierarchical, with ranges and a label. At the **file
level** it also lists **filler bands** (imports, module constants, comment/license blocks) as `.`
rows whose label indexes the contents (`imports: os, sys, …`). Works for **every supported
language**. This is how an agent discovers WHICH line to go to, then pulls the section with
`--line N --query`.

```
#outline — depth 2, L1=1 L2=2, showing 1..2
#.   [1-11]  imports: logging, contextlib, anyio, starlette.websockets, …
#.   [13-13] assign: logger
#1   [16-67] async def websocket_server(scope, receive, send)
#  2 [35-51] async def ws_reader()   # Pump inbound frames into the read stream …
```

- **Header line** (`outline — depth D, L1=… L2=…, showing 1..K`) reports the whole file's shape
  (total depth + block count per level) so a shallow view still tells you there's more.
- Each row: `<level> [start-end] <label>`. A **number** = a named block at that depth; a `.` = a
  level marker — either a **transparent frame** (a `namespace`, `extern "C"`, shown but adding no
  depth) or a **file-level filler band** (imports/constants/comments) labeled with its contents.
- **Bare `--outline` is adaptive** — it sizes the shown depth to the file (a lone top-level
  object expands to level 2; a big flat file shows the tops). `--level N` forces an EXACT cap
  (`--level 1` = tops only, `--level 10` = everything).
- Section end is exact for the tree-sitter languages (including Python with its grammar installed);
  Markdown headings are a line-before-the-next-heading estimate, and Python's `ast`-fallback (no
  grammar) is reduced — use `--query` for the precise boundary there.

## Arguments and Flags

| Flag | Type | Description |
|------|------|-------------|
| `--file PATH` | required | Path to source file (absolute or relative) |
| `--line N` | for ladder/query | Target line number (1-based). Not needed for `--outline`. |
| `--ancestor-level N` | optional | Relative block address: N blocks **up** from the line (`0`=innermost, `1`=parent). The usual navigator. |
| `--level N` | optional | Absolute block address: depth N from the file **top** (`1`=outermost). With `--outline`, caps the depth shown. |
| `--query` | flag | Return actual text of the chosen block instead of the metadata ladder. |
| `--numbered` | flag | With `--query`, prefix each code line with its absolute line number. Off by default (raw text stays copy/paste-safe). |
| `--project-root PATH` | optional | Root directory for resolving relative file paths. CLI value overrides `CONFIG__TOOLS.py`. |

### Level addressing — two self-describing flags (don't mix)

Both pick which block in the ladder you want when using `--line`:

| Flag | Direction | Example (line inside try → if → function) |
|------|-----------|-------------------------------------------|
| `--ancestor-level 0` (default) | the block itself | the `try` block |
| `--ancestor-level 1` | one parent up | the `if` block |
| `--ancestor-level 2`, `3`, … | grandparent, … | the function definition |
| `--level 1` | outermost from the top | the function definition |
| `--level 2`, `3`, … | Nth level down from the top | the `if`, then the `try`, … |

`--ancestor-level N` is internally `--level -N`; the raw negative `--level -N` still works. If an
address runs past the root or the deepest block, the outermost / deepest available block is
returned.

### Flag order (a writing convention, not a parser rule)

Flags are position-independent — `argparse`-style, order never changes behavior — but commands
read as one sentence when written in this order:

```
--project-root R  --file F  --line N  (--ancestor-level N | --level N)  (--outline | --query)  --numbered
```

Address narrows FIRST (root → file → line → block), THEN the verb acts (outline/query), THEN
adverbs (numbered). Example: `--file PATH --line 49 --ancestor-level 1 --outline`.

### Fallback Mode (Between Blocks)

When `--line` falls between blocks at file-level scope (no containing block found), the tool returns the nearest neighboring block either above or below. Comments are ignored for this distance calculation so they don't interfere with finding real code blocks.

## Supported Languages

| Language | Extension(s) | Detection Method | Notes |
|----------|--------------|------------------|-------|
| Python | `.py` | Indentation-based (no AST) | Multiline signatures, compound blocks (`try/except`, `if/elif` — sibling branches share one depth), docstrings/comments glued to the block they precede. |
| TypeScript / JS / TSX | `.ts` `.js` `.tsx` `.jsx` | tree-sitter (`tree_sitter_typescript`) | Real syntax tree (`typescript` grammar for `.ts`/`.js`, `tsx` for `.tsx`/`.jsx`). Named blocks + name-bound arrows (`const Foo = () => {…}`, `value: () => {…}`, class fields); multi-line object literals & arrow bodies count as blocks. `declarations()` (for make_interface_card) preserved. |
| C / C++ | `.cpp` `.cc` `.cxx` `.c++` `.h` `.hpp` `.hh` `.hxx` `.c` | tree-sitter (`tree_sitter_cpp`) | Real syntax tree: multi-line signatures, `template<...>`, `Class::method`, macros, raw string literals `R"(...)"`. `namespace`/`extern "C"` are **transparent** (shown in `--outline`, add no depth). |
| C# | `.cs` | tree-sitter (`tree_sitter_c_sharp`) | Real syntax tree: multi-line signatures, `record` types, file-scoped namespaces, nested types. Namespaces are **transparent**. |
| CSS / SCSS / Sass | `.css` `.scss` `.sass` | tree-sitter (`tree_sitter_css`) | A block is a rule set `selector { … }`; nested rules (`&::before`), `@media`/`@supports`/`@keyframes`/`@font-face` nest; label = the selector list. SCSS-only syntax (parameterized `@mixin`/`@include`, unquoted `url(../x)`) parses imperfectly but doesn't derail structure. |
| Markdown | `.md`, `.markdown` | Heading hierarchy | Sections by ATX headings (`#`..`######`); level = heading depth. Fenced code skipped so `#` inside code isn't a heading. |

Language detection happens automatically from the file extension — no need to specify it explicitly.

> **tree-sitter dependency.** C/C++, C#, TypeScript/JS/TSX and CSS/SCSS parse a real syntax tree,
> so they need grammars: `pip install tree-sitter tree-sitter-cpp tree-sitter-c-sharp
> tree-sitter-typescript tree-sitter-css` (see `get_codeblock/requirements.txt`). You don't have
> to pre-install — if a needed package is missing the tool prints the exact `pip install` command
> for the interpreter that ran it (no traceback). Python and Markdown stay zero-dependency.

## Importable API for Other Tools

Import and use directly in Python:

```python
from get_codeblock.core import get_codeblock

# Get metadata only (same as CLI without --query)
result = get_codeblock("path/to/file.py", line_num=50, level=0)
print(result)
# {"level": 3, "start": 71, "end": 87}

# Get text too (same as CLI with --query)
result = get_codeblock("path/to/file.ts", line_num=100, query=True)
print(result["text"])
# Actual block content byte-for-byte...

# Parent block at level -1
parent = get_codeblock("code.cs", line_num=25, level=-1)
```

**Arguments:**
- `file_path` (str): Path to source file (absolute or relative).
- `line_num` (int): Target line number (1-based), default: 1.
- `level` (int): Block address level as described above, default: 0.
- `query` (bool): If True also returns block text in the result dict, default: False.

**Returns:** Dictionary with keys:
- `level`: int — real nesting depth of returned block.
- `start`: int — start line number (1-based).
- `end`: int — end line number (1-based, inclusive).
- `text`: str — block content byte-for-byte from file (only present when `query=True`).

**Raises:**
- `FileNotFoundError` if the file doesn't exist.
- `ValueError` if line_num is out of range or no blocks can be found near that line.

Run `help(get_codeblock)` in Python for full docstring reference.

## Configuration

When `CONFIG__TOOLS.py` exists in the project root:
- `PROJECT_ROOT` — base directory used for resolving relative file paths (overridden by CLI `--project-root`).
- Other settings are tool-specific and not required for basic usage.

## Examples

### Python nested blocks with compound try/except

```python
def fetch_data(url):              # Level 1: function definition
    if url.startswith("http"):    # Level 2: if block
        try:                      # Level 3: try block (includes except branches)
            response = requests.get(url)
            return response.json()
        except requests.RequestException as e:
            logger.error(e)
            raise
```

Query line 5 (`return response.json()`):
- Default → `#Block level: 3 range: 4-8` (the try block including its except branch)
- `--level -1 --query` → returns the if block text
- `--level -2 --query` → returns the function definition text

### TypeScript arrow function with template literal braces

```typescript
export const greet = (name: string): string => {
    return `Hello ${name}, count is ${items.length}.`;
};
```

Query line 2 inside the template literal — correctly ignores `${...}` braces and returns level 1 range covering lines 1-3.

### C# nested control flow

```csharp
namespace MyApp.Services          // Level 1: namespace block
{
    public class UserService      // Level 2: class block
    {
        public User GetById(int id) // Level 3: method block
        {
            if (id <= 0)           // Level 4: if block
                throw new ArgumentException();
            
            foreach (var u in users) // Level 5: foreach block
            {
                if (u.Id == id)    // Level 6: nested if block
                    return u;
            }
        }
    }
}
```

Query line 10 (`return u;`):
- Default → `//Block level: 6 range: 10-11` (the innermost if block)
- `--level -3 --query` → returns the method body text from `GetById(int id)` down through all its branches

## Architecture

`core.py` (CLI + importable API) talks to ONE façade, `reader.Reader`; the `reader/` layer is the
engine (Vision03/04 — "universal reader"). A single registry maps extension → (Backend, Spec); one
parse tree feeds two consumers — the **map** (`.0`-classifier → outline/focus) and **addressing**
(`address.py` → ladder/query/line_level). Both read the same per-language `LangSpec`, so a line
gets ONE answer to "which block am I in", whether asked as a map or as an address.

```
get_codeblock/
├── core.py               # CLI parsing, resolve() logic, file I/O, importable get_codeblock()
├── reader/               # the engine (Vision03/04)
│   ├── reader.py           # Reader — façade/router: outline→classify, get_blocks/line_level→address
│   ├── registry.py         # resolve(ext) → (Backend, Spec)   ← single entry
│   ├── protocol.py         # contracts: RNode, Backend, Spec, Analyzer
│   ├── ir.py               # Block (IR the renderers consume) + Role
│   ├── classify.py         # backend-agnostic .0-classifier (the MAP) + focus + render + CLI
│   ├── address.py          # backend-agnostic ADDRESSING for brace langs (get_blocks/line_level)
│   ├── label.py            # filler-band labeler: band → comma-list of names (an index)
│   ├── backends/           # treesitter.py (core1) · markdown.py (core2) · python_ast.py (fallback)
│   └── profiles/           # one plug-in file per language (LangSpec + promotion rules) + presets
└── handlers/             # per-language engines, reused BEHIND the façade
    ├── _treesitter_blocks.py # shared tree-sitter LangSpec (node-type sets) — feeds reader profiles
    ├── python_handler.py     # indentation parser — reader DELEGATES .py addressing here
    ├── markdown_handler.py   # heading hierarchy — reader delegates .md addressing here
    └── cpp/csharp/typescript/css handlers + declarations() for interface cards
```

Two families feed the reader. **tree-sitter** (C/C++, C#, TS/JS/TSX, CSS/SCSS) — a thin `LangSpec`
(node-type sets + grammar loader) wrapped by a language **profile** (`reader/profiles/<lang>.py`);
`address.py` reproduces the shared block model (brace regions, transparent frames, comment gluing,
one canonical range so `get_blocks` and `line_level` agree) on the RNode protocol. **Heuristic**
(Python indentation, Markdown headings) — zero-dependency; the reader uses their tree-sitter/`.0`
map where it can and delegates their addressing to the hand-rolled handler, which shares the same
block-end convention so map and addressing stay consistent.

`Reader.get_blocks(file_path, line) -> list[dict]` returns blocks sorted outermost-first; each dict
has `level` (nesting depth from file root, 1-based), `start`, `end` (1-based, inclusive), and a
`label`. `Reader.line_level(path, idx)` returns one line's depth.

Adding a tree-sitter language is **data, not code** (Vision03): drop a `reader/profiles/<lang>.py`
(a `LangSpec`) + register its extension — the classifier, `address.py`, and the renderers are
untouched. See `reader/CONTRACT.md` for the recipes (new language / new backend / new analyzer).

## Testing

Golden checker: `py test/check.py` (full report) · `py test/check.py --fails` (regressions only).
It compares live output on the `test/` fixtures against the hand-verified oracle in
`test/expected.py` across sections LEVELS / OUTLINE / LADDER / QUERY (plus find_code_usage).
`test/Edge/` is the per-condition, multi-language corpus (comment gluing, syntax edge cases,
one-truth) — one file per language; `test/cssSRC/`, `test/tsSRC/`, `test/csharpSRC/` etc. hold
larger real-world fixtures. Exit 0 = all match.

## Design Principles

1. **Clean output** — only relevant data returned; no noise or extra metadata beyond what agents need.
2. **Self-contained blocks** — each block is a complete, readable unit of code with its header included.
3. **Flexible navigation** — level addressing via positive/negative offsets lets you jump up/down the hierarchy without knowing exact structure upfront.
4. **Language-agnostic core, languages as data** — one registry, one parse tree, two consumers
   (map + addressing) sharing one per-language `LangSpec`. Adding a tree-sitter language is a
   profile file + a registry entry, not new engine code (Vision03).
5. **LLM-friendly** — output format is designed for direct consumption by agents: comment-prefixed metadata doesn't interfere with code parsing, text is byte-for-byte from source files.
6. **Dual interface** — works both as a CLI tool and as an importable library function (`from get_codeblock.core import get_codeblock`).
