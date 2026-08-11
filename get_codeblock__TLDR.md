# get_codeblock

Returns a self-contained structural block containing a line — for code (`.py/.ts/.js/.cs`)
AND Markdown (`.md`: heading sections). Lets an agent get precise context around any
location, or the file's table of contents, without reading the whole file.

**Target:** `--file PATH` + `--line N` (or `--file PATH --outline` for the map, no line).

## Modes

* **`--outline`** (no `--line`) — the file's structural table of contents: named blocks only
  (headings for MD; `def/class`/methods for code — control blocks excluded), `#Block level: N
  range: X-Y — label` per line. `--level K` caps depth. This is how you FIND the line to go to.
* **Default (no `--query`)** — the nesting LADDER for a line: every enclosing block
  innermost→outermost. One cheap call shows all zoom options; no text yet.
* **`--query`** — the actual text, byte-for-byte, framed by anchor comments (header
  `#Block level: N range: X-Y`, footer `#Block end: E`) so concatenated blocks don't merge.
* **`--level K`** — which block from the ladder to `--query`. `0` (default) = innermost;
  `-N` = up to parents; `+N` = from the top. In `--outline` it caps depth instead.

Typical MD/doc flow: `--outline` (see the map) → `--line N --query` (pull that exact section).


