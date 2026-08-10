# get_codeblock

Search or query exact code block from given line at given depth.

**Target:** provide `--file PATH` and `--line N`.

## Modes

* **Default** — Returns `<level> <from_line> <to_line>` for the block containing the line. Level is counted from file root (0=file-level code, 1=function/class, etc.). Use `--level N` to target blocks relative to current position (`-1`=parent block bounds).
* **`--query Q`** — Returns raw text of the containing block. Positive: level from top (`1`=outermost containing block, clamped if deeper than real level). Negative or zero: relative to line (`0`=current block at line, `-1`=parent, `-2`=grandparent). Output is exact file contents between block boundaries.

## Configuration notes

When `tools_config.py` exists, `PROJECT_ROOT` is used as default for resolving relative file paths. Language is detected by file extension (`.py`, `.ts`, `.js`, `.cs`).
