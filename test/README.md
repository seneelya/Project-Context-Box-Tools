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

## Provenance
Copied from memohood (own), ts-prune (MIT), CoreSharp — for local test fixtures only.
