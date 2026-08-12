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

- Boundary: source-analysis tools (`codebase_import_search`, `get_codeblock`, `py_api`) are **fact-fetchers**; "who-calls-whom" / project map is the **card layer** (`graph_from_cards` over cards). Do NOT grow the fetchers into a graph system — anti-monster, fight for every flag.
- Paths in tool output are always `/` (POSIX), regardless of OS — stable, greppable output.
- All CLI tools force UTF-8 stdout — cards/commits are often Cyrillic; a cp1251 Windows console would crash otherwise.
- `get_codeblock` levels: `level = 1 + enclosing block bodies`, file root = 1; **`0` is never a real depth** — it is reserved for `--level` addressing (the code line itself). Full ideology in `Vision01__get_codeblock.md`.
- Card tools default their cards dir to `./__map` (CWD-relative) — a hand finds the map in whatever project it is run in, independent of where the script lives.

## Card stamp (make_interface_card)

- Declared surface has ONE source per language: Python → stdlib `ast` (py_api); TS/JS → get_codeblock `declarations` — избегаем регекс-эвристики там, где можно разобрать по-настоящему.
- tree-sitter — ОПЦИОНАЛЬНЫЙ бэкенд объявлений, переключается `CONFIG__TOOLS.DECL_BACKEND` (auto|treesitter|regex); regex остаётся zero-dep фолбэком — тул копируется куда угодно и работает без установки.
- Резолюция модулей (`.js`→`.ts`, index-файлы, namespace) — всегда НАША: это build-семантика, парсер её не даёт.
- Public API карточки = что выходит наружу (свои публичные / протёкшие `_`-приватные consumed / чужие ре-экспортнутые); Dependencies = что входит для работы. Барел-индекс (`index.*`/`__init__`/`mod.rs`) = фасад.

## Tests

- Golden oracle = **human hand-count** (independent of the code's author); lock/verify at semantic-change moments. Run `py test/check.py` green through every change; a FAIL names the exact file/line/case.
