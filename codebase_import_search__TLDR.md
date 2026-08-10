# codebase_import_search

Find where a target module's symbols are imported or used across the project.

**Target:** provide one of `--file PATH` or `--module NAME`.

## Modes

* **Default** — Which files consume the target's symbols? Groups usages by file with load types (`top-level` / `lazy` / `conditional` / `fallback`) and dynamic access detection.
* **`--verbose`** — Where exactly is each symbol used? Groups by symbol and adds precise usage line numbers and load types.
* **`--incoming`** — What does the target import? Shows upstream dependencies within `project-root`; external dependencies are grouped as `[external]: <line>`.
* **`--tests-only`** — Which API is covered by tests? Shows usages only from configured test directories.

## Configuration notes

Language priority: CLI `--language` → file extension → config → `python`.

Configure `TEST_DIRS` to define test directories (relative paths). Tests are excluded from default scans; use `--tests-only` to inspect what API tests cover.
