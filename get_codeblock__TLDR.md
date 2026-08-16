# get_codeblock — TLDR

Returns a self-contained structural block containing a line — for code (`.py`/`.ts`/`.js`/`.cs`)
AND Markdown (`.md`: heading sections). Lets an agent get precise context around any location,
or a file's table of contents, without reading the whole file.

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

- `--outline` only works for Python (indentation) and Markdown (headings) — TypeScript/C#
  not implemented yet, errors out.
- `--outline` range end is "line before the next same-or-shallower header" — a TOC estimate,
  not the exact block boundary. Use `--query` when you need the real end line.
- The green level-legend line and the outline's `#outline` / `Level  Range` header only print
  on a real terminal (`isatty()`). Piped/programmatic callers get bare
  `#Block level: N range: X-Y` lines — nothing extra to parse.
- Filename is never printed in `--query` output — the caller already knows which file it asked for.
