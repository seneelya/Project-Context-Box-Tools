# codebase_import_search

Three modes: default (downstream consumers), `--incoming` (upstream dependencies), verbose detail (`--verbose`).

- **Default mode** — shows all usages of target's symbols in the codebase with import categories (top-level/lazy/conditional/fallback) and dynamic runtime access detection.
- **`--incoming` mode** — shows where target file's imports originate from within project-root; externals grouped as `[external]: <line>` at end.
- **`--verbose` mode** (default only) — groups by symbol with exact usage line numbers and load types; includes self-documenting legend.

## Parameters CLI flags

| Flag | Required | Description | Example |
|------|----------|-------------|---------|
| `--file PATH` | One of `--file` or `--module` | Target file path relative to project-root | `_engine/auth.py`, `src/analyzer.ts` |
| `--module NAME` | One of `--file` or `--module` | Module name instead of file path (alternative to --file) | `auth_module`, `pkg.submodule` |
| `--language LNG` | No (default: auto or python) | Language handler/resolver to use | `python`, `typescript`, `ts`, `js`, `csharp`, `cs` |
| `--incoming` | No | Show upstream dependencies (where target's imports come from) instead of downstream consumers | (no value needed) |
| `--verbose` | No (default mode only) | Group output by symbol with line numbers and load types; adds format legend | (no value needed) |
| `--module-names N1,N2,...` | No | Extra names by which this module can be imported | `_secret_module,auth_core` |
| `--project-root PATH` | No (default: current dir) | Root directory to scan for imports | `/workspace/SRC/memohood`, `.` |
| `--tests-only` | No | Show usages only from configured test directories (reveals API covered by tests) | (no value needed) |

## When tools_config.py exists:

You only need: `--file` or `--module` — target to analyze. Config provides PROJECT_ROOT and LANGUAGE defaults.

**Auto-detect language:** When using `--file`, tool detects language from extension. Priority: CLI flag > auto-detect > config > default.

**Test coverage:** Configure `TEST_DIRS` in tools_config.py — by default test files are excluded. Use `--tests-only` to see what API is covered by tests.
