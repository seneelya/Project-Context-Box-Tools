# codebase_import_search
Returns a table of all usages of the given module/file in the codebase with import categories: top-level (always loaded), lazy (inside function/method), conditional (inside if block), fallback (try/catch optional dep), and dynamic runtime access via string names.

## Parameters CLI flags

| Flag | Required | Description | Example |
|------|----------|-------------|---------|
| `--file PATH` | One of `--file` or `--module` | Target file path relative to project-root | `_engine/auth.py`, `src/analyzer.ts` |
| `--module NAME` | One of `--file` or `--module` | Module name instead of file path (alternative to --file) | `auth_module`, `pkg.submodule` |
| `--language LANG` | No (default: `python`) | Language handler to use | `python`, `typescript`, `ts`, `js` |
| `--module-names N1,N2,...` | No | Extra names by which this module can be imported | `_secret_module,auth_core` |
| `--project-root PATH` | No (default: current dir) | Root directory to scan for imports | `/workspace/SRC/memohood`, `.` |
