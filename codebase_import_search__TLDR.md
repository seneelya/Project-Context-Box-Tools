# codebase_import_search

Two modes (default: downstream consumers; `--incoming`: upstream dependencies):

- **Default mode** — returns a table of all usages of the given module/file in the codebase with import categories: top-level (always loaded), lazy (inside function/method), conditional (inside if block), fallback (try/catch optional dep), and dynamic runtime access via string names.
- **`--incoming` mode** — shows where the target file's imports come from within project-root: each import mapped to its source file path, plus symbols imported. External packages/stdlib shown as `[not found inside project root]`.

## Parameters CLI flags

| Flag | Required | Description | Example |
|------|----------|-------------|---------|
| `--file PATH` | One of `--file` or `--module` | Target file path relative to project-root | `_engine/auth.py`, `src/analyzer.ts` |
| `--module NAME` | One of `--file` or `--module` | Module name instead of file path (alternative to --file) | `auth_module`, `pkg.submodule` |
| `--language LNG` | No (default: `python`) | Language handler/resolver to use | `python`, `typescript`, `ts`, `js`, `csharp`, `cs` |
| `--incoming` | No | Show upstream dependencies (where target's imports come from) instead of downstream consumers | (no value needed) |
| `--module-names N1,N2,...` | No | Extra names by which this module can be imported | `_secret_module,auth_core` |
| `--project-root PATH` | No (default: current dir) | Root directory to scan for imports | `/workspace/SRC/memohood`, `.` |
| `--tests-only` | No | Show usages only from configured test directories (reveals API covered by tests) | (no value needed) |

## When tools_config.py exists:

You only need: `--file` or `--module` — target to analyze. Config provides PROJECT_ROOT and LANGUAGE defaults.

**Auto-detect language:** When using `--file`, tool detects language from extension (.py → python, .ts/.js → typescript, .cs → csharp). Priority: CLI flag > auto-detect > config > default.

**Test coverage:** Configure `TEST_DIRS` in tools_config.py — by default test files are excluded. Use `--tests-only` to see what API is covered by tests.
