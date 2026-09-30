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

**C/C++/CUDA** (`.h .hpp .cuh .c .cpp .cu …`): an `#include` brings the whole header, so a consumer
is any file that includes the target directly OR through a chain of in-tree includes (reverse
include graph of the whole root), and its symbols = which of the target's declared names it uses.
Kinds: `include`, `include [if X]` (under `#if`), `via <header>` (through a chain). `--incoming`
lists the target's includes; unresolved ones carry a tag (`[not in tree; if GGML_USE_METAL]`).
Include lookup: own folder -> `CONFIG__TOOLS.CPP_INCLUDE_DIRS` -> unique path-suffix in the tree.

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

**`--project-root`** — not given -> `CONFIG__TOOLS.PROJECT_ROOT` if set and existing, else cwd (the
agent often starts OUTSIDE the project). Relative `--file`: first under the root, then cwd; found in
BOTH (different files) -> the root wins + a one-line warning. `@` -> explicitly the config value.
Literal path -> used as given. Vision08 §5 (ProjectStarter `__dev/vision/`).

Language priority: CLI `--language` → file extension (the handler that claims it) → config → `python`.
Paths in output are always `/`-normalized (cross-platform, joinable with card File Path).
Configure `TEST_DIRS` (relative paths) to define test directories; excluded from default
scans, shown alone with `--tests-only`.
