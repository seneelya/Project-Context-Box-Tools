# codebase_import_search
Returns a table of all usages of the given module/file in the codebase with import categories: top-level (always loaded), lazy (inside function/method), conditional (inside if block), fallback (try/catch optional dep), and dynamic runtime access via string names.

## Parameters CLI flags

| Flag | Required | Description | Example |
|------|----------|-------------|---------|
| `--file PATH` | One of `--file` or `--module` | Target file path relative to project-root | `_engine/auth.py`, `src/analyzer.ts` |
| `--language LANG` | No (default: `python`) | Language handler to use | `python`, `typescript`, `ts`, `js` |
| `--module-names N1,N2,...` | No | Extra names by which this module can be imported | `_secret_module,auth_core` |
| `--project-root PATH` | No (default: current dir) | Root directory to scan for imports | `/workspace/SRC/memohood`, `.` |

## Output format explained

First line summary:
```text
# N files, M unique symbols (+K with dynamic access)
```

Each following line is one consumer file grouped by import kind:
```text
src/runner.ts: [analyze] [lazy: initCache] [fallback: optionalHelper]
config_loader.ts: Possible Dynamic import [import()]
```

Categories meaning for documentation:
- `[symbol]` — top-level static import → public API always available
- `[lazy: x]` — loaded only when function runs → optional dependency path
- `[conditional: y]` — imported under if condition → feature-gated or platform-specific
- `[fallback: z]` — inside try/catch → soft dependency may be absent at runtime
- `Possible Dynamic import [...]` — module name appears as string → symbols unknown but module is reachable dynamically
