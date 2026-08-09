# How to Test codebase_import_search

## Quick sanity check (all languages in one run)

```bash
cd /project/tools

# Python handler — memohood project
python codebase_import_search.py --file "_engine/backends/__init__.py" \
  --project-root "/workspace/SRC/memohood" | head -3

# TypeScript handler (explicit flag) — ts-prune project  
python codebase_import_search.py --file "src/state.ts" --language typescript \
  --project-root "/workspace/SRC/ts-prune" | head -3

# C# handler — CoreSharp project
python codebase_import_search.py --file "source/CoreSharp/Interfaces/IGlobalStopWatch.cs" \
  --language csharp --project-root "/workspace/SRC/CoreSharp" | head -3
```

Expected: each command returns `# N files, M unique symbols` with non-zero counts.

## Test auto-detect language by file extension

Auto-detect should work when using `--file` without explicit `--language`:

```bash
cd /project/tools

# .ts → typescript (compare output to explicit --language typescript)
python codebase_import_search.py --file "src/analyzer.ts" \
  --project-root "/workspace/SRC/ts-prune" | head -3

# .cs → csharp
python codebase_import_search.py --file "source/CoreSharp/Interfaces/IGlobalStopWatch.cs" \
  --project-root "/workspace/SRC/CoreSharp" | head -3
```

Expected: same results as when passing `--language` explicitly. Priority order:
`CLI flag > auto-detect from extension > tools_config.LANGUAGE default`.

## Test TEST_DIRS exclusion and --tests-only flag

1. Configure test directories in `/project/tools/tools_config.py`:

```python
TEST_DIRS = [
    "tests",          # root-level tests folder
]
```

2. Run scan on a project with known test files (hermes-agent-src has `tests/` and `tests-js/`):

```bash
cd /project/tools

# Production only (tests excluded by default) — should show fewer files
python codebase_import_search.py --file "/workspace/SRC/hermes-agent-src/agent/__init__.py" \
  --project-root "/workspace/SRC/hermes-agent-src" | head -1

# Tests only — shows what public API is covered by tests
python codebase_import_search.py --file "/workspace/SRC/hermes-agent-src/agent/__init__.py" \
  --project-root "/workspace/SRC/hermes-agent-src" --tests-only | head -5
```

Expected: `--tests-only` output should show ONLY files inside configured TEST_DIRS (paths starting with `tests/`). Default run excludes those paths entirely.

## Test semantic import detection (Python lazy/conditional/fallback)

Run on a module that exercises all import kinds:

```bash
cd /project/tools
python codebase_import_search.py --file "_lab/backends_cfg.py" \
  --project-root "/workspace/SRC/memohood" | head -5
```

Expected output includes tags like `[lazy: ...]`, `[conditional: ...]`, `[fallback: ...]` showing correct import kind detection.

## Test dynamic import detection

```bash
cd /project/tools
python codebase_import_search.py --file "/workspace/SRC/hermes-agent-src/agent/__init__.py" \
  --project-root "/workspace/SRC/hermes-agent-src" | head -1
```

Expected: header shows `( +N with dynamic access )` indicating files that use string-based/dynamic imports referencing the target module.

## Test error handling and validation

```bash
cd /project/tools

# Missing file should exit with error code and message
python codebase_import_search.py --file "nonexistent.py" --project-root "/workspace/SRC/memohood"; echo "exit=$?"

# Invalid language should exit with error
python codebase_import_search.py --file "foo.py" --language invalidlang; echo "exit=$?"
```

Expected: both commands print error to stderr and return non-zero exit code.

## Test tools_config.py optional dependency

Temporarily rename the config file and verify tool falls back gracefully:

```bash
cd /project/tools
mv tools_config.py tools_config.py.bak
python codebase_import_search.py --file "_engine/backends/__init__.py" \
  --project-root "/workspace/SRC/memohood" | head -3
mv tools_config.py.bak tools_config.py
```

Expected: prints `Warning: tools_config.py missing — using defaults.` to stderr but still works with hardcoded defaults (`PROJECT_ROOT="."`, `LANGUAGE="python"`).

## Test TTY-only colored summary line

```bash
cd /project/tools

# Piped output — should be plain text (no ANSI codes)
python codebase_import_search.py --file "_engine/backends/__init__.py" \
  --project-root "/workspace/SRC/memohood" | head -1 | cat -v

# Direct terminal — should show yellow color (visually check)
python codebase_import_search.py --file "_engine/backends/__init__.py" \
  --project-root "/workspace/SRC/memohood" | head -1
```

Expected: piped output contains no `^[[` escape sequences.

## Test --incoming mode (upstream dependencies)

New flag `--incoming` shows where a target file's imports come from within project-root. Output format matches default mode: `file: [symbols]`. External packages/stdlib grouped as `[external]: <import_line>` at end.

### Python incoming test

```bash
cd /project/tools

# Show upstream deps of _engine/embed.py
python codebase_import_search.py --incoming --file "_engine/embed.py" \
  --project-root "/workspace/SRC/memohood"
```

Expected:
- Header: `# N imports in target, M resolved to K unique sources`
- Local imports: `file.py: [symbol1, symbol2]` format
- stdlib/third-party (logging, typing, requests) → `[external]: import logging`

### TypeScript incoming test

```bash
cd /project/tools

# Show upstream deps of src/analyzer.ts
python codebase_import_search.py --incoming --file "src/analyzer.ts" \
  --project-root "/workspace/SRC/ts-prune"
```

Expected:
- Relative imports (`./constants`, `../util/...`) resolve to source files with symbols
- External packages (ts-morph, fs) → `[external]: import ...`
- Multiline named imports handled correctly (compact display for many symbols)

### C# incoming test

```bash
cd /project/tools

# Show upstream deps of GlobalStopWatchInstance.cs
python codebase_import_search.py --incoming --file "source/CoreSharp/Utilities/GlobalStopWatchInstance.cs" \
  --project-root "/workspace/SRC/CoreSharp"
```

Expected:
- `using AndreasReitberger.Core.Interfaces;` → `file.cs: [IGlobalStopWatch]` format
- Framework namespaces (`using System.*`) → `[external]: using System;`

### Incoming mode auto-detect language

Language should be auto-detected from file extension in incoming mode too:

```bash
cd /project/tools

# .py auto-detect
python codebase_import_search.py --incoming --file "_engine/embed.py" \
  --project-root "/workspace/SRC/memohood" | head -1

# .ts auto-detect  
python codebase_import_search.py --incoming --file "src/state.ts" \
  --project-root "/workspace/SRC/ts-prune" | head -1

# .cs auto-detect
python codebase_import_search.py --incoming --file "source/CoreSharp/Utilities/CommonConverters.cs" \
  --project-root "/workspace/SRC/CoreSharp" | head -1
```

Expected: each command works without explicit `--language` flag.

### Incoming mode regression check (ensure default mode still works)

After testing incoming mode, verify default downstream consumers mode unchanged:

```bash
cd /project/tools

# Python — should match known result: "# 10 files, 16 unique symbols"
python codebase_import_search.py --file "_engine/backends/__init__.py" \
  --project-root "/workspace/SRC/memohood" | head -1

# TypeScript — should match known result: "# 5 files, 1 unique symbol"  
python codebase_import_search.py --file "src/state.ts" \
  --project-root "/workspace/SRC/ts-prune" | head -1

# C# — should match known result: "# 1 file, 1 unique symbol"
python codebase_import_search.py --file "source/CoreSharp/Interfaces/IGlobalStopWatch.cs" \
  --project-root "/workspace/SRC/CoreSharp" | head -1
```

## Test data locations (Docker container paths)

All test projects are mounted at `/workspace/SRC/`:

| Project      | Path                                    | Language   | Notes                         |
|--------------|-----------------------------------------|------------|-------------------------------|
| memohood     | `/workspace/SRC/memohood`               | Python     | Primary test project          |
| hermes-agent | `/workspace/SRC/hermes-agent-src`       | Python     | Large project, has tests/     |
| ts-prune     | `/workspace/SRC/ts-prune`               | TypeScript | Small TS project              |
| CoreSharp    | `/workspace/SRC/CoreSharp`              | C#         | .NET library                  |

## Config constant naming convention rule

CLI flags must map to config constants via simple uppercase:
- `--project-root` → `PROJECT_ROOT` ✓
- `--language` → `LANGUAGE` ✓  
- `TEST_DIRS` → used by `--tests-only` logic ✓

If you add a new flag, follow this pattern for the corresponding config variable.
