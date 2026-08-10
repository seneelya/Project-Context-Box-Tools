# get_codeblock

Returns a self-contained code block containing the specified line in a source file. Designed for LLM agents to get precise code context around any location without reading entire files.

**Target:** provide `--file PATH` and `--line N`.

## Modes

* **Default** — What block contains this line? Returns metadata only: level (nesting depth) and range (start–end lines). Use when you need block boundaries without consuming tokens on text content yet.
* **`--query`** — Give me the actual code. Returns byte-for-byte block text . 
* **`--level -N`** — Go up the hierarchy. Parent (`-1`), grandparent (`-2`) blocks. Use when you need broader context than the immediate block.
* **`--level +N`** — Navigate from top of nesting. `+1` = outermost container, `+2` = progressively deeper levels. You will get wider look.


