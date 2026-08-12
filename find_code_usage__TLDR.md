# find_code_usage

Find where a target module's symbols are imported or used across the project — the
FACT of the real interface, not a guess.

**Target:** provide one of `--file PATH` or `--module NAME`.

## Modes

* **Default** — Who consumes the target's symbols? Groups usages by file with load
  types (`top-level` / `lazy` / `conditional` / `fallback`) and dynamic-access detection.
* **`--verbose`** — Where exactly is each symbol used? Groups by symbol with precise
  usage line numbers, load types, and code block levels (depth). Symbols that are
  imported but never used land in a `# dangling imports` section.
* **`--incoming`** — What does the target import? Upstream sources within `project-root`;
  everything else is grouped under `# external (...)`.
* **`--incoming --verbose`** — Grouped by source file; under each, its symbols and where
  they are used INSIDE the target file (lines + block levels). Grouped by source (not by
  symbol as in default verbose) because incoming works over ONE file. This is the feed for
  `get_codeblock`: take a line, ranging-shot it to the enclosing block. Ideal for huge files.
* **`--tests-only`** — Which API is covered by tests? Usages only from configured test dirs.

## Filtering

* **`--symbol NAME[,NAME]`** — Post-filter the output to one or a few symbols. Works in
  every mode (it filters the produced data, not the logic). Use when you care about a
  single symbol's fan-in/fan-out.

## Configuration notes

Language priority: CLI `--language` → file extension → config → `python`.
Paths in output are always `/`-normalized (cross-platform, joinable with card File Path).
Configure `TEST_DIRS` (relative paths) to define test directories; excluded from default
scans, shown alone with `--tests-only`.
