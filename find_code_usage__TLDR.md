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

## Compose — locate coarse, then pull the exact block (not only for cards)

The fast way to get **level-aware facts** about a file: what symbols it exposes, who uses them,
and — with `--verbose` — the exact usage `lines` plus their block **`levels`** (how deep each
call sits). `grep` gives you a line; the depth lets you decide how big a block to pull with
`get_codeblock`, instead of dumping the whole file. Symbol-search is deliberately NOT baked in
(that would just re-be `grep`) — compose instead:
```
grep -rn "BackendError" .                                     # coarse: where it lives
find_code_usage --file backends/_http.py --symbol BackendError --verbose
   #  backends/chat.py: lines=[81,…] levels=[3,…]             # precise: where + how deep
get_codeblock --file backends/chat.py --line 81 --level 0     # surgical: just that block
```
Note: `--verbose` `levels` are informational **depth** (how nested the call is) — use them to
*decide* the zoom, then address it with `get_codeblock --level` (relative: `0` innermost,
`-N` up to enclosing parents). The number is not passed through verbatim.

## Configuration notes

**`--project-root`** — not given -> cwd (relative `--file` resolves from where you actually stand,
never silently from config). `@` -> explicitly `CONFIG__TOOLS.PROJECT_ROOT`. Literal path -> used
as given. Config is never read without writing `@` — see `__dev/vision/Vision01__path-and-flag-conventions.md`.

Language priority: CLI `--language` → file extension → config → `python`.
Paths in output are always `/`-normalized (cross-platform, joinable with card File Path).
Configure `TEST_DIRS` (relative paths) to define test directories; excluded from default
scans, shown alone with `--tests-only`.
