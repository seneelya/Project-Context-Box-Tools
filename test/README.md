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

- **csharpSRC/** — `CoreSharp` pair (flat; C# resolves by namespace, not path).
  Link: `GlobalStopWatchInstance.cs` uses the `IGlobalStopWatch` interface.

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
Copied from memohood (own), ts-prune (MIT), CoreSharp — for local test fixtures only.
