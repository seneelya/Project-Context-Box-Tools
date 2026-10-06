# CONTEXT_RESTORE_TOOLS — get_codeblock / universal reader: strategy and gotchas

Not "what was done" (that is `TRACKER.md`) — the reasoning and traps that don't survive a
compaction. Read together with `get_codeblock/reader/CONTRACT.md` (the contract, next to the code).

## Canonical sources

- Ideology: `vision/Vision02__get_codeblock.md` (`.0` classifier: landmark / filler / frame),
  `vision/Vision03__get_codeblock.md` (universal reader: backend -> RNode -> Spec -> IR -> render;
  section "call grammar" = canonical flag order), `Vision04` (addressing), `Vision05` (query
  escalation / `--force`).
- How to add a layer: `get_codeblock/reader/CONTRACT.md` (recipes A/B/C, invariants 1–9, full wiring
  list for a new language). `reader/protocol.py` = the contracts in code.
- Phases: `Plan__universal-reader.md`. Parked: `Plan__jsx-carve-tsx.md` (flat JSX not split yet).

## Architecture in one breath

`Reader` (facade) -> `registry.resolve(ext)` -> (Backend, Spec) -> RNode tree -> TWO consumers:
the MAP (Classifier -> IR `Block` -> outline / `.0` / focus) and ADDRESSING (ladder / query /
line_level). Addressing has three engines: brace languages (`address._BRACE_EXTS`, rungs from
`LangSpec` sets), `.py` (indentation `python_handler`, grammar-free on purpose), everything else
(generic `classify.ladder_at` over the same IR as the map). `--name` (`name_resolver.py`) is not a
mode: name -> lines -> the existing `--line` render.

## Choosing how a new format plugs in

- Brace-shaped code whose body nodes start on the header row (`{`, `do`) -> Recipe A: profile with a
  `LangSpec` + `_BRACE_EXTS` (C/C++, C#, TS, CSS, shell).
- Real grammar whose nodes don't fit the brace model (wrapper nodes, bodies starting after `{`) ->
  Recipe B variant 3: own Spec over `TSNode`, generic addressing (YAML, PowerShell).
- No grammar needed / none good -> Recipe B: own zero-dep parser (Markdown, plain text, batch).
- Test: `test/sweep_invariants.py <real files> --check-query` must be HIGH 0 before it ships.

## Invariants that are easy to break

- Map and addressing give ONE `[start-end]` per block (#6): end = last content line, start = top of
  the preamble (decorators + glued comments). A body node that starts after `{` breaks this in the
  brace engine (`_level_of_row` is body-strict) — that is why PowerShell is not a brace profile.
- A returned rung always contains the line (#7); a filler band is a legitimate container (#9).
- Shared `LangSpec`s in `handlers/` are not edited (#5) — copies in the profile (`cpp.py`).
- Python keeps two engines (tree-sitter map, indentation addressing) aligned on the end convention;
  forcing `.py` through the brace engine was rejected (python `block` starts at the 1st statement).

## Parking (low priority)

- Frame name token leaks into filler (`~identifier`, `~qualified_name`).
- `#define` end-row bleeds one line.
- Outline from IR vs the old outline: not byte-identical (comment glue) — decide consciously if ever.

## Settled — don't relitigate

- Output: indent = depth, `.` = level/scope (filler + frames), number = named landmark, ASCII only.
- Structural summary with trimmed bodies (OMP-style) — not ported.
- `.0` is a layer over the common tree-sitter root, not a second engine.
- `ast` is the Python fallback with a loud English notice.
- Unknown extension = honest error, never "the closest language".
