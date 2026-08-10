# get_codeblock

Returns a self-contained code block containing the specified line in a source file. Works as both CLI tool and importable library function for LLM agents.

**Usage:** provide `--file PATH` and `--line N`.

## Modes

- **Default (metadata only)** — Prints one line with language-specific comment prefix:
  ```
  #Block level: 3 range: 71-87      # Python
  //Block level: 1 range: 5-12      # TypeScript/C#
  ```
  Level = nesting depth from file root; range = start-end lines (1-based, inclusive).

- **`--query` flag** — Returns actual text of the block (byte-for-byte from file) with metadata header as first line. No digits needed — it's a boolean flag.

## Level Addressing (`--level L`)

| Value | Meaning |
|-------|---------|
| `0` (default) | Current block containing the line |
| `-1`, `-2`, ... | Parent, grandparent blocks going up N steps |
| `+1`, `+2`, ... | Topmost containing block and next levels down from hierarchy root |

## Fallback Mode

If `--line` falls between blocks at file level (no containing block), returns the nearest neighboring code block above or below. Comments ignored for distance calculation.

## Supported Languages

| Language | Extensions | Detection Method |
|----------|------------|------------------|
| Python | `.py` | Indentation-based (multiline headers, compound try/except/if-elif supported) |
| TypeScript / JavaScript | `.ts`, `.js` | Brace matching `{...}` (ignores strings, template literals, comments) |
| C# | `.cs` | Brace matching `{...}` (handles verbatim strings and single-line comments) |

Language auto-detected from file extension.

## Importable API for Other Tools

```python
from get_codeblock.core import get_codeblock

result = get_codeblock("path/to/file.py", line_num=50, level=0, query=True)
# Returns: {"level": 3, "start": 71, "end": 87, "text": "..."}
```

Run `help(get_codeblock)` for full reference.
