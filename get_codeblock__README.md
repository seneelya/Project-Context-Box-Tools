# get_codeblock — Get Code Block

Returns a meaningful, self-contained code block containing a specified line in a file. Designed for LLM agents to get context around a code location.

## Quick Start

```bash
# Show block boundaries (level + from-to lines)
python get_codeblock.py --file path/to/file.py --line 100

# Show text of parent block (one level up)
python get_codeblock.py --file path/to/file.py --line 100 --query -1

# Show text of topmost containing block
python get_codeblock.py --file path/to/file.py --line 100 --query 1

# Show text of grandparent block
python get_codeblock.py --file path/to/file.py --line 100 --query -2
```

## Modes

### Default (no flags)
Returns `<level> <from_line> <to_line>` — the level number and boundaries of the block containing the specified line.

- Level 0 = file root
- Level 1 = first-level definition (function/class/method)
- Level 2+ = nested blocks (if/for/while inside functions, etc.)

### `--query N`
Returns the actual text content of a block at the specified level.

**Positive N (counting from top):**
- `--query 1` → topmost containing block (e.g., the function)
- `--query 2` → next level down (e.g., an if-statement inside that function)
- If N exceeds the actual nesting depth, returns the deepest available block

**Zero:**
- `--query 0` → current block (the one containing the line)

**Negative N (counting from current upward):**
- `--query -1` → parent block (one level up)
- `--query -2` → grandparent block (two levels up)
- If N goes beyond file root, returns the outermost block

### `--level N`
Returns `<level> <from_line> <to_line>` for a specific level.

- `--level 0` → current block boundaries
- `--level 1` → parent block boundaries
- `--level -1` → grandparent block boundaries

## Supported Languages

| Language | Extension | Handler |
|----------|-----------|---------|
| Python   | `.py`     | AST-based indentation tracking |
| TypeScript/JS | `.ts`, `.js` | Brace matching with import/export filtering |
| C#       | `.cs`     | Brace matching + `#region` support |

## Configuration

When `tools_config.py` exists in the project root, it provides:
- `PROJECT_ROOT` — base directory for relative paths
- `LANGUAGE` — default language (auto-detected from extension if not specified)
- `TEST_DIRS` — directories excluded from analysis (use `--tests-only` to include them)

## Examples

### Python nested blocks
```python
def process_data():              # Level 1 (function)
    if data:                     # Level 2 (control_flow)
        for item in data:        # Level 3 (control_flow)
            print(item)          # Line we query
```

Query line 4:
- Default → `3 4 4`
- `--query 1` → entire `def process_data():` function
- `--query -1` → the `if data:` block
- `--query -2` → the function definition

### C# with regions
```csharp
public class MyClass {          # Level 0 (class)
    #region Properties          # Level 1 (region)
    public int Value { get; }   # Line we query
    #endregion
}
```

Query line 3:
- Default → `2 3 3`
- `--query 1` → entire class
- `--query -1` → the region block

## Architecture

```
get_codeblock/
├── __init__.py
├── core.py              # CLI parsing, resolve() logic, file I/O
└── handlers/
    ├── __init__.py      # Language registry
    ├── python_handler.py    # AST-based block detection
    ├── typescript_handler.py # Brace matching
    └── csharp_handler.py    # Brace + #region matching
```

Each handler implements `get_blocks(file_path, line_num) -> list[dict]` returning blocks sorted outermost-first with level, start, end, and type fields.

## Testing

Test projects located at `/workspace/SRC/`:
- Python: `memohood/` (small), `hermes-agent-src/` (large)
- TypeScript: `ts-prune/`
- C#: `CoreSharp/`, `test_SWARM_SRC/`, `test_Unity/`

## Design Principles

1. **Clean output** — only relevant data, no noise
2. **Self-contained blocks** — each returned block is a complete, readable unit
3. **Flexible navigation** — positive/negative queries for different use cases
4. **Language-agnostic core** — handlers are interchangeable
5. **LLM-friendly** — output is ready to be fed into an LLM context window
