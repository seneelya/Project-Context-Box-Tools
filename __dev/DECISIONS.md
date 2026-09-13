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

## Runtime seams (Plan03/Vision07) — 2026-09-14

- Seams are a DIFFERENT edge kind from imports, always — own marker (`【SEAM⇢】`/`【SEAM⇠】`), own
  report section (`## runtime seams (N)`), never merged into `→`/`←`. A dashed arrow lives INSIDE
  the marker, never the plain `→`/`←` glyph — a text search for one must never match the other.
- Seams do NOT redefine what "independent part" means — `components()`/island-count is import-only,
  full stop. Seam-crossed islands are reported SEPARATELY (`_seam_bridges`), never silently merged
  into one component — merging erases the exact fact islands exist to surface (these are
  architecturally different apps, glued at one explicit point, not the same app).
- The marker applies to EVERY seam, not only ones crossing an island boundary — an app dynamically
  loading its own sibling is just as real a fact as one talking to a separate app.
- Declared on the dependent/consuming side ONLY (same convention as imports) — the graph computes
  the reverse (`【SEAM⇠】`) itself; never hand-duplicate the reverse edge on the target's own card.
- Kind and Shape are two INDEPENDENT closed-vocabulary axes (not "5 Kinds" collapsing `by-path`/
  `process` into one — they stay separate, just share the "same channel family" framing).
- The section is OPTIONAL and the stamp never invents it empty (same anti-pattern lesson as
  REQ-009) — a detector hit without an existing section produces a one-line HINT only, never a
  placeholder section or directive.
- `seam_scanner` is an internal helper module (a package, `seam_scanner/__init__.py`, no `__main__`,
  no TLDR/README) — imported by `make_interface_card.py`, never a standalone CLI tool in its own
  right, unlike its sibling tools under `__HQ/tools/`.

## Merge identity (make_interface_card) — 2026-08-29/30

- Entry-name matching for merge is by POSITION in the signature (before `(`/`=`, else after known per-language keywords), never by guessing the "first word" of the signature text — that broke on any JS/TS/C#/async-Python file (see `__dev/Requests/DONE__REQ-004+005_merge-identity-design.md`).
- `--force` on a card that already has prose REFUSES without `--discard-prose` (exit 2) — force is a muscle-memory flag, prose is expensive; the two must not collide silently.
- No shared resolver module across the 9 CLI tools (deliberate — see path/flag conventions below); a shared helper WITHIN the closely-coupled card family (`graph_from_cards.resolve_project_root`, reused by `validate_cards`/`check_cards_freshness`) is fine — that coupling already existed.
