# test fixtures — golden-test inputs

Real (copied) files for golden tests of `find_code_usage` and `get_codeblock`.
Each language set is a **connected chain**: at least one real cross-file link, so the
scanners have something to resolve. Expected outputs get recorded as golden files and the
counts are hand-verified (oracle = human finger-count, not the code's author).

Run with `--project-root test/<set>`.

## Sets & the known links

- **pythonSRC/backends/** — memohood `_engine/backends/` package.
  Links: `__init__.py` re-exports from `_http.py` / `resolve.py` / `chat.py` /
  `embed_driver.py` / `rerank_driver.py`; the drivers also import from `_http.py`.
  Good for: downstream (who uses `_http`), incoming (what `__init__` pulls), levels/outline.

- **tsSRC/src/** — subset of `ts-prune`.
  Links: `runner.ts` imports `analyze` from `analyzer.ts`; `analyzer.ts` imports from
  `configurator.ts`, `constants.ts`, `util/*.ts`, `utils/common.ts`.

- **tsSRC2/core/** — the `v4/core` package of **zod** (dense internal graph; ESM/NodeNext
  `import … from "./x.js"` specifiers that resolve to `.ts` files; barrel `index.ts` with
  `export * from "./x.js"` re-exports). Realistic TS fixture: `util.ts` consumed by 8
  siblings. Exercises `.js`-specifier resolution and (future) TS outline / facade re-exports.

- **csharpSRC/Core/** — `CoreSharp` pair (two namespaces under `AndreasReitberger.Core.*`;
  C# resolves by namespace, not path). Link: `GlobalStopWatchInstance.cs` uses `IGlobalStopWatch`.

- **csharpSRC2/Core/** — the `Core/` cluster of **SwarmUI** (7 files, one `namespace
  SwarmUI.Core`; `ExtensionsManager` uses the `Extension` type, etc.). Realistic C#:
  public types with members and modifiers, and same-namespace type usage that has NO
  `using` line — the case that makes C# "who uses this" a type-name question, not an
  import one. Big multi-type file: `Settings.cs` (34 types → nested-member attribution).

- **unitySRC/Services/** — **Unity** clusters:
  - `Analytics/` (7 files) — DI/adapter: interface `IAnalyticsAdapter` implemented by 3
    adapters in a CHILD namespace (`…Analytics.Adapters`) that see the parent type with no
    `using`, plus `AnalyticsService : IAnalyticsService`. Third C# visibility case —
    descendant-namespace sees ancestor types (interface→implementations = 4 consumers).
  - `Input/InputContext.cs` (**79KB**, generated Input System) — deeply nested `@`-verbatim
    partial class + nested structs/interfaces. Big-file stress: regex vs tree-sitter diverge
    on member count (regex under-reports on generated nesting) — the concrete case for the
    optional tree-sitter backend. `Map/` (MapService 19KB + `IMapService`).

- **mdSRC/** — memohood cards (`capture.py.md`, `cli.py.md`). No import links (Markdown);
  for `get_codeblock` heading sections / `--outline` (the canonical "pull `## Public API`" case).

## Running the checks

```bash
py test/check.py            # full grouped report (for human review)
py test/check.py --fails    # only mismatches + summary (quick regression run)
```

- **`expected.py` is the ORACLE** — the values a human verified by hand. Grouped by
  fixture/case: `LEVELS` = `(line, expected_level, snippet)` per file; `IMPORTS` =
  `{consumer/source file: [symbols]}` per case. **Edit the numbers there if wrong** — that
  is where a bug in the tools shows up (expected ≠ reality).
- `check.py` runs the live tools over the fixtures and compares to `expected.py`
  (exit 1 on any mismatch). A change in tool behavior → a FAIL naming the exact
  file/line/case, so the cause is easy to find.
- Golden was seeded from current output; **verify the counts by finger** (e.g. "chat.py
  really uses 4 symbols of `_http`", "line 140 really sits 4 levels deep").

## Fuzz sweep — `sweep_invariants.py`

`check.py` verifies hand-picked lines. `sweep_invariants.py` does the opposite: it pokes
**every non-blank line** of **every file** in a tree through `get_blocks` (ladder mode) and
flags any result that breaks a structural invariant. It found four ballooning bugs in the
indentation heuristic that only surfaced on real code (hanging-indent signatures,
comprehension `for`/`if`, soft-keyword `match =`, brackets inside string literals).

```bash
py test/sweep_invariants.py                       # default: sweep test/ fixtures (must be 0 HIGH)
py test/sweep_invariants.py "Y:\path\to\SRC"      # stress a real tree
py test/sweep_invariants.py FILE --show 40        # verbose: list up to 40 actionable violations
py test/sweep_invariants.py DIR --show-info       # also itemize SIBLING/EMPTY (noisy, for debugging the sweep itself)
py test/sweep_invariants.py DIR --step 3          # sample every 3rd line (huge trees)
py test/sweep_invariants.py DIR --max-lines 800   # cap lines checked per file
```

- **What it checks** (per line): `CONTAIN` (HIGH) — a rung must span the line (invariant #7);
  `RANGE` (HIGH) — outer rung must span the inner — a real containment/bounds bug; `CRASH`/`OPEN`
  (HIGH); `LEVEL` (LOW) — ranges nest but levels don't strictly increase (try/catch
  sibling-wrapper quirk, cosmetic); `SIBLING` (INFO) — same level, no nesting, but the two rungs
  meet EXACTLY at the hit line (`} else {`, `} catch (e) {`) — both legitimately touch the line,
  this is invariant #8 (the shared-brace-boundary is inherently ambiguous, not a bug); `EMPTY`
  (INFO).
- **Default output only itemizes HIGH/LOW** (the actionable findings) — `SIBLING`/`EMPTY` are
  expected structural noise on any real codebase full of `if/else`, and would otherwise bury real
  bugs under a wall of text. Pass `--show-info` to see them itemized when debugging the sweep itself.
- **Exit code 1 iff any HIGH** — usable as a regression gate. Blank lines are skipped on
  purpose (a blank between blocks legitimately belongs to no block).
- **Speed**: the `.py` path is ~O(lines) per line (no parser), so giant files are slow even
  though the sweep memoizes parse/scan work — reach for `--step` / `--max-lines` on big trees.
- **When it finds something**: it prints `file → line → the offending rung ranges`. Reproduce
  with `get_codeblock.py --file F --line N`, look at the source, fix the handler, then add a
  minimal case to `pythonSRC/hanging_sig.py` (or the relevant `<lang>SRC` fixture) + `expected.py`
  so the oracle guards it forever.

## Provenance
Copied from memohood (own), ts-prune (MIT), zod (MIT), CoreSharp, SwarmUI (MIT), a Unity project — for local test fixtures only.
