# get_codeblock — Get Code Block for LLM Agents

Returns a meaningful, self-contained code block containing a specified line in a source file. Designed as both a CLI tool and importable library function for LLM agents to get contextual code around any location.

## Quick Start

```bash
# Show block boundaries (metadata only, yellow on TTY)
python get_codeblock.py --file path/to/file.py --line 100

# Return actual text of the current block containing line 100
python get_codeblock.py --file path/to/file.py --line 100 --query

# Show parent block boundaries (one level up)
python get_codeblock.py --file path/to/file.py --line 100 --level -1

# Return text of grandparent block (two levels up)
python get_codeblock.py --file path/to/file.py --line 100 --level -2 --query
```

## Output Format

### Metadata only (default, without `--query`)

Prints a single line with language-specific comment prefix:

```
#Block level: 3 range: 71-87      # Python
//Block level: 1 range: 5-12      # TypeScript/C#
```

**Fields:**
- `level` — real nesting depth of the returned block (counted from file root)
- `range: X-Y` — start and end line numbers (1-based, inclusive)

### Text mode (with `--query`)

Prints metadata header as a valid comment for the language, followed by the block text byte-for-byte from the source file:

```python
#Block level: 3 range: 71-87
        try:
            result = do_something()
            return result
        except ValueError as e:
            logger.error(e)
            raise
```

## Arguments and Flags

| Flag | Type | Description |
|------|------|-------------|
| `--file PATH` | required | Path to source file (absolute or relative) |
| `--line N` | required | Target line number (1-based), where we search for the block |
| `--level L` | optional | Block address level. Default: `0`. See details below. |
| `--query` | flag | Return actual text of block instead of metadata only. No digits needed — it's a boolean flag. |
| `--project-root PATH` | optional | Root directory for resolving relative file paths. CLI value overrides the config file setting (`tools_config.py`). |

### Level Addressing

The `--level` argument controls which block in the hierarchy you want:

| Value | Meaning | Example (line inside try → if → function) |
|-------|---------|-------------------------------------------|
| `0` (default) | Current block — the innermost one containing the line | Returns the `try` block |
| `-1` | Parent of current block | Returns the `if` block |
| `-2`, `-3`, ... | Grandparent, etc. Going up N steps from current block | Returns the function definition |
| `+1` | Topmost containing block (outermost in hierarchy) | Returns the file-level/root block or outermost container |
| `+2`, `+3`, ... | Next level down from top of nesting hierarchy | Counts down into nested blocks from the top |

If a negative level goes beyond the root, returns the outermost available block. If a positive level exceeds actual depth, returns the deepest available block.

### Fallback Mode (Between Blocks)

When `--line` falls between blocks at file-level scope (no containing block found), the tool returns the nearest neighboring block either above or below. Comments are ignored for this distance calculation so they don't interfere with finding real code blocks.

## Supported Languages

| Language | Extension(s) | Detection Method | Notes |
|----------|--------------|------------------|-------|
| Python | `.py` | Indentation-based (no AST) | Handles multiline function signatures, compound blocks (`try/except`, `if/elif`), docstrings attached above functions. Comments are semantically assigned to the block they precede. |
| TypeScript / JavaScript | `.ts`, `.js` | Brace matching `{...}` | Ignores braces inside strings, template literals `${...}`, single-line comments `//`, and multi-line comments `/* ... */`. Arrow functions, classes, interfaces all treated uniformly as blocks by their brace pair. |
| C# | `.cs` | Brace matching `{...}` | Handles verbatim strings `@"..."`, single-line comments `//`. Namespace → class → method → control-flow hierarchy tracked via brace depth. |

Language detection happens automatically from the file extension — no need to specify it explicitly.

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

When `tools_config.py` exists in the project root:
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

```
get_codeblock/
├── __init__.py
├── core.py              # CLI parsing, resolve() logic, file I/O, importable get_codeblock() function
└── handlers/
    ├── __init__.py      # Language registry (get_handler(language) factory)
    ├── python_handler.py    # Indentation-based block detection (no AST)
    ├── typescript_handler.py # Brace matching with string/template literal awareness
    └── csharp_handler.py    # Brace matching with verbatim string support
```

Each handler implements `get_blocks(file_path, line_num) -> list[dict]` returning blocks sorted outermost-first. Each block dict has:
- `level`: int — nesting depth from file root (1-based).
- `start`: int — start line number (0-based internally, converted to 1-based for output).
- `end`: int — end line number (inclusive).

## Testing

Test projects located at `/workspace/SRC/` (host paths mapped via Docker bind mounts):
- Python: `memohood/` (small), `hermes-agent-src/` (large)
- TypeScript: `ts-prune/` (medium)
- C#: `CoreSharp/` (small), `test_SWARM_SRC/`, `test_Unity/` (large)

See `__HQ/HowTo__Test-get_codeblock.md` for detailed test scenarios and checklists.

## Design Principles

1. **Clean output** — only relevant data returned; no noise or extra metadata beyond what agents need.
2. **Self-contained blocks** — each block is a complete, readable unit of code with its header included.
3. **Flexible navigation** — level addressing via positive/negative offsets lets you jump up/down the hierarchy without knowing exact structure upfront.
4. **Language-agnostic core** — handlers are interchangeable; new languages can be added by implementing `get_blocks()`.
5. **LLM-friendly** — output format is designed for direct consumption by agents: comment-prefixed metadata doesn't interfere with code parsing, text is byte-for-byte from source files.
6. **Dual interface** — works both as a CLI tool and as an importable library function (`from get_codeblock.core import get_codeblock`).
