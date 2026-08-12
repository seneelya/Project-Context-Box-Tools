# test fixtures — golden-test inputs

Real (copied) files for golden tests of `codebase_import_search` and `get_codeblock`.
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

- **csharpSRC/** — `CoreSharp` pair (flat; C# resolves by namespace, not path).
  Link: `GlobalStopWatchInstance.cs` uses the `IGlobalStopWatch` interface.

- **csharpSRC2/Core/** — the `Core/` cluster of **SwarmUI** (7 files, one `namespace
  SwarmUI.Core`; `ExtensionsManager` uses the `Extension` type, etc.). Realistic C#:
  public types with members and modifiers, and same-namespace type usage that has NO
  `using` line — the case that makes C# "who uses this" a type-name question, not an
  import one. Big multi-type file: `Settings.cs` (34 types → nested-member attribution).

- **unitySRC/Services/Analytics/** — a **Unity** DI/adapter cluster (7 files): interface
  `IAnalyticsAdapter` implemented by 3 adapters in a CHILD namespace
  (`Code.Services.Analytics.Adapters`) that see the parent type with no `using`, plus
  `AnalyticsService : IAnalyticsService`. Exercises the third C# visibility case —
  descendant-namespace sees ancestor types (interface→implementations = 4 consumers).

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

## Provenance
Copied from memohood (own), ts-prune (MIT), zod (MIT), CoreSharp, SwarmUI (MIT), a Unity project — for local test fixtures only.
