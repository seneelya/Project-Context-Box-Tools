# get_codeblock

Returns a self-contained code block containing the specified line in a source file. Designed for LLM agents to get precise code context around any location without reading entire files.

**Target:** provide `--file PATH` and `--line N`.

## Modes

* **Default (no `--query`)** — the nesting LADDER: every enclosing block innermost→outermost
  (`#Block level: N range: X-Y` per line). One cheap call shows all zoom options; no text yet.
* **`--query`** — the actual code, byte-for-byte, framed by anchor comments (header
  `#Block level: N range: X-Y`, footer `#Block end: E`) so concatenated blocks don't merge.
* **`--level K`** — which block from the ladder to `--query`. `0` (default) = innermost;
  `-N` = up to parents; `+N` = from the top (`+1` = outermost). Only affects `--query`.


