# DECISIONS — settled calls, do not relitigate

Locked design/architecture decisions — **one line each: the choice + a one-line WHY**. Read this
BEFORE (re)designing, so you don't reopen a closed question. Reversing a locked call is a conscious
move (fresh rationale) — update the line, don't casually edit.

Format: `- <decision> — <one-line why>`

## Scheme (this repo)

- `tools/` = the single dev home of the hands (plan A); ProjectStarter consumes finished tools — one place to write/fix/test.
- This repo runs a **lightweight** ProjectStarter: no `__map/` cards, no long-plan ritual — a small tool workshop maps itself by its own docs + tools.
- `__`-prefix marks meta (`__HQ`); the card layer's meta dir is `__map` (in target projects, not here).

## Tools contract

- Boundary: source-analysis tools (`find_code_usage`, `get_codeblock`, `show_pyfile_api`) are **fact-fetchers**; "who-calls-whom" / project map is the **card layer** (`graph_from_cards` over cards). Do NOT grow the fetchers into a graph system — anti-monster, fight for every flag.
- Paths in tool output are always `/` (POSIX), regardless of OS — stable, greppable output.
- All CLI tools force UTF-8 stdout — cards/commits are often Cyrillic; a cp1251 Windows console would crash otherwise.
- `get_codeblock` levels: `level = 1 + enclosing block bodies`, file root = 1; **`0` is never a real depth** — it is reserved for `--level` addressing (the code line itself). Full ideology in `Vision01__get_codeblock.md`.
- Card tools' `--project-root` (and so their `__map` dir) resolves per `Vision01__path-and-flag-conventions.md`: not given → implicitly `CONFIG__TOOLS.PROJECT_ROOT`, sanity-checked against a stale/foreign config; `@`/literal → explicit, unchecked. NOT plain cwd (superseded 2026-08-30 — cwd has no meaning for `__map/`, that was the original bug). Generic fact-fetchers (`find_code_usage`/`get_codeblock`/`show_pyfile_api`) DO default to cwd — the two categories resolve differently on purpose.

## Card stamp (make_interface_card)

- Declared surface has ONE source per language: Python → stdlib `ast` (show_pyfile_api); TS/JS → get_codeblock `declarations` — избегаем регекс-эвристики там, где можно разобрать по-настоящему.
- tree-sitter — ОПЦИОНАЛЬНЫЙ бэкенд объявлений, переключается `CONFIG__TOOLS.DECL_BACKEND` (auto|treesitter|regex); regex остаётся zero-dep фолбэком — тул копируется куда угодно и работает без установки.
- Резолюция модулей (`.js`→`.ts`, index-файлы, namespace) — всегда НАША: это build-семантика, парсер её не даёт.
- Public API карточки = что выходит наружу (свои публичные / протёкшие `_`-приватные consumed / чужие ре-экспортнутые); Dependencies = что входит для работы. Барел-индекс (`index.*`/`__init__`/`mod.rs`) = фасад.

## Tests

- Golden oracle = **human hand-count** (independent of the code's author); lock/verify at semantic-change moments. Run `py test/check.py` green through every change; a FAIL names the exact file/line/case.

## Merge identity (make_interface_card) — 2026-08-29/30

- Entry-name matching for merge is by POSITION in the signature (before `(`/`=`, else after known per-language keywords), never by guessing the "first word" of the signature text — that broke on any JS/TS/C#/async-Python file (see `__dev/Requests/DONE__REQ-004+005_merge-identity-design.md`).
- `--force` on a card that already has prose REFUSES without `--discard-prose` (exit 2) — force is a muscle-memory flag, prose is expensive; the two must not collide silently.
- No shared resolver module across the 9 CLI tools (deliberate — see path/flag conventions below); a shared helper WITHIN the closely-coupled card family (`graph_from_cards.resolve_project_root`, reused by `validate_cards`/`check_cards_freshness`) is fine — that coupling already existed.
