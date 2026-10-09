# CONTEXT_RESTORE — resuming work on the TOOLS (`__HQ/tools`, its own git)

This file is about the tools and the template only. A downstream project's state (its plans,
tracker, task) lives in that project's `__HQ/` — restore it from there, never from here.

## Read, in order (don't wander the repo)

1. Tail of `__dev/TRACKER.md` — where we are, what just landed.
2. `__dev/DECISIONS.md` — settled choices (one line = choice + why). Don't relitigate.
3. `__dev/Requests/` — `DONE__*` closed, no prefix = open. `__dev/plans/` — open plans (`done/` closed).
4. Touching get_codeblock → `__dev/CONTEXT_RESTORE_TOOLS.md` + `get_codeblock/reader/CONTRACT.md`.
   Touching the card stamp → `make_interface_card__TLDR.md`, `stamp_langs/CONTRACT.md`, `CARD_FORMAT.py`.

Read code with `get_codeblock` (`--outline` -> `--line N --query` / `--name X`), never whole files.

## The repo

Independent git (`__HQ/tools/.git`, remote `Project-Context-Box-Tools`), nested in ProjectStarter and
gitignored by it — commit HERE. `__dev/` (history, visions, plans, requests) and `test/` are not
deployed to projects. `TOOLS.md` routes to every tool; `test/HowTo__Test-*.md` — how to test each.
Deploy to a project: from ProjectStarter `py __dev/deploy_hq.py --target <project> --apply` —
commit this repo FIRST (an unknown blob is reported as CONFLICT).

## State (2026-10-07)

- **get_codeblock 0.8.0** — languages: Python, TS/JS/TSX, C#, C/C++/CUDA, CSS/SCSS, Markdown (+ YAML
  frontmatter = `meta:` block), YAML, plain text, shell `.sh`, PowerShell `.ps1`, batch `.bat`.
  `--name` (name -> lines -> the existing `--line` render). C/C++ macros cut before parsing,
  recovery after unparsable function bodies. One ext -> language map: `reader.reader.language_for_ext`.
  `get_codeblock/views.py` — every CLI mode as DATA + its renderer (`*_view` / `render_*`,
  `as_text` == CLI stdout) and `block_range` (both ends of a line range snapped to blocks); the CLI
  is parse_args -> view -> render. For callers that want data, not text — never one mega-render.
  Usage stats and a replay of logged calls (guard for refactors): `__dev/usage/`.
- **Card stamp** (`make_interface_card`) — CARD_FORMAT 1.3.0; C/C++ via `stamp_langs/cpp.py`
  (API families, "API: in source" header cards, name anchors instead of line numbers, Why folded by
  folder); `--all --stale`; scan cache `_cache/`. `graph_from_cards --file` shows files without cards.
- **Open:** Plan08 step 9 (clangd, needs a Ninja build of the C/C++ test bed); Plan06 (short
  directive markers — directives are already short, plan not formally closed). Open request:
  REQ-014 (markdown section body as one block — paragraphs/lists/fences inside it).
- **Test beds:** `y:\SRC\llama.cpp_mix` (C/C++; zone = its config `STAMP_DIRS`), `hermes-filetools`,
  `memohood` (Python/JS); sweep-only Python trees: `Y:\SRC\rlm`, `Y:\SRC\TRELLIS.2`.

## split_monster (2026-10-10)

Splits monster files: blocks move byte-for-byte past the model; imports / re-exports / appended
`export` lines are generated around them. `split_monster.py` + package `split_langs/` (one module
per language, `CONTRACT.md`), tests `test/test_split_monster.py` (59/0). Read `split_monster__TLDR.md`,
`--help`, and the chronicle at the bottom of `__dev/vision/Vision06__monster-file-split.md` (decisions
and two field trials: `make_interface_card.py` on a copy, and a live JS split of hermes-filetools
`config-pane.js`). Flow: `--investigate` -> `--split ... --out-script move.py` -> `move.py [--apply]
[--check CMD] [--undo]`, `--rebase` when the source changed. Open: `require()`/CommonJS, a compact
`--investigate` for 300+ blocks, a trial on a TS/TSX monster.

## Where copies of the tools live (update after a release)

| Project | What | How |
|---|---|---|
| `y:\SRC\llama.cpp_mix` | whole HQ (tools, guides, roles) | `deploy_hq.py --apply` (commit its HQ first) |
| `t:\AgentsWork\hermes-filetools` | all tools, NOT the deploy | copy git-tracked tool files; keep its `CONFIG__TOOLS.py`, `hermes_python.py`, `hermes-py.cmd` |
| `t:\AgentsWork\hermes-filetools\vendor\get_codeblock` | get_codeblock package, shipped inside that plugin | its own `vendor/sync_get_codeblock.py` mirrors a COMMIT of this repo (commit here first) |
| `t:\AgentsWork\dVOrbitals\dvOrbital__GDD` | get_codeblock only | copy `get_codeblock/`, `get_codeblock.py`, `get_codeblock__*.md`; keep its config |

Copy = `git ls-files` of this repo minus `__dev/`, `test/`, `CONFIG__TOOLS.py`, `CLONE_TOOLS_HERE.md`;
never delete files in the target. Smoke after a copy: `validate_cards.py`, `get_codeblock --file <x>`.

## Regression (before a commit, not after every edit)

Reference interpreter `T:/AgentsWork/venv/Scripts/python.exe` (3.12, ALL grammars). Another Python
gives `N skipped (grammar missing)` — that is "not checked", not "ok".

```bash
T:/AgentsWork/venv/Scripts/python.exe test/check.py --fails          # 135/0
T:/AgentsWork/venv/Scripts/python.exe test/test_cardstamp.py         # 155/0
T:/AgentsWork/venv/Scripts/python.exe test/run_restamp_fixtures.py   # 21/0
T:/AgentsWork/venv/Scripts/python.exe test/golden_check.py           # 13/13
T:/AgentsWork/venv/Scripts/python.exe test/test_cpp.py               # 150/0
T:/AgentsWork/venv/Scripts/python.exe test/test_name_resolver.py     # 36/0
T:/AgentsWork/venv/Scripts/python.exe test/sweep_invariants.py --quiet  # HIGH 0 except CRASH=71 (old cp1252 fixture); LOW LEVEL=5 known
```

`test__replace_in_files.py` is old (15/21) and DELETES fixtures when failing:
`git checkout -- test/test__replace_in_files/fixtures`.

## Gotchas

- Bash heredocs eat backslashes (`\n`, `\b`) — edits with backslashes: Edit/Write or a .py script.
- Bump `get_codeblock/core.py::VERSION` once per session (at the end), not per commit.
- A language plugs in as registry data (`reader/profiles/`, `stamp_langs/`, find_code_usage
  registries), never an `if lang ==` branch. Full wiring list — `reader/CONTRACT.md`, Recipe A.
- Plans / visions that change only tools live here in `__dev/`, not in ProjectStarter.
