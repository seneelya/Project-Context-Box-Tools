# get_codeblock

Get code block containing a line in a file, with optional query for parent blocks.

**Target:** provide `--file PATH` and `--line N`.

## Modes

* **Default** — Returns `<level> <from_line> <to_line>` for the block containing the line. Use with `--level` to target blocks relative to current position (`0`=current block, `-1`=parent).
* **`--query Q`** — Returns raw text of block at level `Q` (from top: `1`=outermost containing block) or relative to line (`-1`=parent, `-2`=grandparent). Returns entire block contents as-is from the file.

## Configuration notes

When `tools_config.py` exists, `PROJECT_ROOT` is used as default for resolving relative file paths. Language is detected by file extension (`.py`, `.ts`, `.js`, `.cs`).
