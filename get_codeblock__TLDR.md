# get_codeblock

Get code block containing a line in a file, with optional query for parent blocks.

**Target:** provide `--file PATH` and `--line N`.

## Modes

* **Default** — Returns `<level> <from_line> <to_line>` for the block containing the line.
* **`--query N`** — Returns text of block at level N (1 = topmost, 0 = current, -1 = parent).
* **`--level N`** — Returns block boundaries at level N (0 = current, 1 = parent, -1 = grandparent).

## Configuration notes

When `tools_config.py` exists, `PROJECT_ROOT`, `LANGUAGE`, and `TEST_DIRS` are used as defaults.

Language priority: CLI `--language` → file extension → config → `python`.

Configure `TEST_DIRS` to define test directories (relative paths). Tests are excluded from default scans; use `--tests-only` to inspect what API tests cover.