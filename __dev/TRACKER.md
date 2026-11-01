# TRACKER — tail log

Execution progress. **Read only the TAIL** (last lines). How to fill/read → `guides/Guide__Tracker.md`.

---
<!-- progress log — append below, newest last -->
✅ consolidate step1 (pull 7 ProjectStarter tools + fix self-locate to CWD/__map, golden green) → next: base pull (adapted scaffold: START/roles/tracker, no cards, no long plans)
✅ consolidate step2 (base pulled + adapted: AGENTS/START/CONTEXT_RESTORE + __HQ WORKFLOW/TRACKER/DECISIONS + Role__Exec/Plan/EnvSetup/Doc + guides Tracker/SplitLargeFiles/Doc; cards+long-plan ritual dropped; unified TOOLS.md by 3 layers; golden 49/0) → next: wire LLM playbook into roles/guides (plan step 5), then optional show_pyfile_api⟷--outline dedup (step 3)
✅ card stamp engine: show_pyfile_api.collect() structured AST + make_interface_card.py (one cmd → fact-filled card skeleton: declared API+signatures × consumed surface × deps); contract tweaks: blank-line-after-heading wording, new `Consumed internals` H3 (private OK). golden 49/0 → next: rewrite MakeCard skill stamp-first (old mechanism = fallback)
✅ card stamp format pass: fact label `consumers N`/`consumers 0`; external imports one-per-line + drop `__future__`; richer <Agent: …> directive; re-export source on H4 heading (`← .mod`), consumers line pure. CARD_FORMAT: renamed H2_SECTIONS/H2_SECTIONS_PACKAGE/H3_API_SUBSECTIONS + docstring = nested card skeleton with var mapping (updated validate_cards refs). → next: rewrite MakeCard skill stamp-first; decide multi-language stamp
✅ TS reverse-index fix: handle ESM/NodeNext `.js` specifiers (import "./util.js" → util.ts) in ts_resolver._resolve_module + ts_handler.matches_target; +tsSRC2 fixture (zod v4/core, 19 files). util.ts now 8 consumers (was 0). golden 49/0 → next: TS/C# outline + index.* as package + make_interface_card declared-source via outline (multilingual card)
✅ multilingual card (TS): CARD_FORMAT PACKAGE_BASENAMES += index.*/mod.rs (barrel=facade); get_codeblock TS declarations() (top-level decls: name/kind/exported/reexport/signature); make_interface_card rewritten to a single declared-source (Python→show_pyfile_api ast, TS→declarations) + kind→H3 grouping. Verified on zod (index.ts facade, parse.ts leaf) + python db.py no regression. golden 49/0. known nit: TS sig truncates at inline `{` (object-type literal). → next: C# declarations; golden coverage for tsSRC2 (incoming .js→.ts lock) + declarations
✅ TS bug fixes (const sig cut at type annotation; import type resolved as dep) + tree-sitter foray: optional high-fidelity declared-surface backend (get_codeblock/handlers/ts_treesitter.py) selectable via CONFIG__TOOLS.DECL_BACKEND (auto|treesitter|regex); make_interface_card._ts_declarations dispatches, regex stays zero-dep fallback. Verified regex==treesitter on parse.ts (37 decls, clean sigs). golden 49/0 → next: C# declared surface; golden coverage for tsSRC2 + declarations
✅ C# consumed surface (#2): analyze_file now treats same-namespace as implicit import (types visible without `using`) → reverse index finds type-name usages (Extension consumed by ExtensionsManager/Program/WebServer). Fixed _extract_public_types phantoms ("that" from prose, "class" from `record class`) via line-anchored regex. golden 49/0 → next: C# declarations (#1)
✅ C# declarations (#1): get_codeblock csharp_handler.declarations() (public types + public members via line-anchored regex; string-literal-aware method vs field; record class handled); make_interface_card C# branch (classes bucket + methods), struct/record→Classes. Verified on SwarmUI Core (Extension: class+fields+methods+3 consumers; ExtensionsManager: generics/async). golden 49/0. C# multilingual card COMPLETE (regex; tree-sitter-c-sharp optional later). → next: golden coverage for tsSRC2/csharpSRC2; MakeCard skill stamp-first
✅ C# fixtures enriched + 3rd visibility case: +unitySRC (Unity Analytics DI/adapter cluster), +Settings.cs big-file exercise. Fixed: descendant namespace sees ancestor types w/o using (target ns via target_file_path, cached) → IAnalyticsAdapter now 4 consumers (3 adapters + service); nested-member attribution + initializer-cut on big files. golden 49/0 → next: golden coverage lock (tsSRC2/csharpSRC2/unitySRC); MakeCard skill stamp-first
✅ C# tree-sitter backend (cs_treesitter.py) via same DECL_BACKEND switch; generalized make_interface_card._declarations(lang,src) dispatch for TS+C#. Missing-grammar informing: one-time stderr WARNING in auto/treesitter mode (names pip pkg + "regex fallback"), silent in forced regex. Verified regex==treesitter on Extension/Settings (1/20, 34/208). golden 49/0 → next: golden-lock new cases; MakeCard skill stamp-first
✅ big Unity fixtures added (Services/Input InputContext.cs 79KB generated, Services/Map 19KB). Surfaced regex fallback limit: missed `@`-verbatim `@InputContext` (fixed: name regex `@?\w+`) and under-counts members on deep generated nesting (regex 39 vs tree-sitter 50 types-match/members-diverge) → concrete case for tree-sitter. golden 49/0
→ CONTEXT ANCHOR written: __HQ/RESTORE__card_stamp.md (minimal read-set to resume the card-stamp stream). Near context limit; resume there.
✅ Guide__MakeCard rewritten STAMP-FIRST (for a local model: exact steps + launch keys make_interface_card/validate_cards; card path convention; tree-sitter WARNING handling). Part 2 = manual FALLBACK, triggered only if make_interface_card fails, with Step 0 "REPORT TO CALLER first" then hand-authoring per CARD_FORMAT contract. → STOP (context anchor: RESTORE__card_stamp.md)
✅ make_interface_card --out/--force (writes card file; refuses to clobber existing card unless --force → protects filled prose). Guide__MakeCard: Step 1 uses --out, Step 1b handles "card exists" (unfilled stamp → --force; filled → stdout + hand-merge facts). +make_interface_card row in TOOLS.md. golden 49/0. → STOP
✅ golden extended 49→56: locked the new multilingual cases — cs same-namespace consumers (IMPORTS Extension), TS ESM .js->.ts (CONSUMERS zod util + INCOMING_SOURCES zod schemas=12), C# descendant-namespace (CONSUMERS IAnalyticsAdapter=4), DECLARATIONS via regex backend (deterministic; cs class/interface + ts const). test/check.py + expected.py new sections CONSUMERS/INCOMING_SOURCES/DECLARATIONS. 56/0.
✅ [bridge, 2026-08-30] Large gap not logged line-by-line here — get_codeblock grew a full universal-reader layer (Vision01-04, reader/ package, .0-classifier, tree-sitter backends) and the card layer matured (discrepancies digest, agent-directive marker, awaiting-agent status, colorized graph_from_cards output). This session specifically: merge-identity rewrite for make_interface_card (entry-name matching by position not text-guessing, exact→fuzzy rename detection, ⚠-marker stacking, --force/--discard-prose guard — `__dev/Requests/DONE__REQ-004+005_merge-identity-design.md`); path/flag conventions across all 9 CLI tools (generic tools resolve relative addressing from cwd, card tools implicitly from CONFIG__TOOLS.PROJECT_ROOT with a sanity-check, `@` alias everywhere, `--file`/`--path` flag-aliases added to positionals — `__dev/vision/Vision01__path-and-flag-conventions.md`); moved this repo's own dev-history out of ProjectStarter's `__dev/tools/` into here (`__dev/`), which is now excluded from `deploy_hq.py` like `__delme/`. golden 106/0, test_cardstamp.py 103/0, run_restamp_fixtures.py 21/0. Two fresh findings filed for later: REQ-006 (Python module-level constants never become declared exports at all) and REQ-007 (CONFIG__TOOLS resolves via the running script's own location, not the target `--project-root` — a bulk `--all` against another project can silently use the wrong TEST_DIRS/LANGUAGE). → next: whichever of REQ-003/006/007 gets picked up first.
✅ REQ-007 fixed: added `graph_from_cards.load_config_at(root)` (loads `<root>/__HQ/tools/CONFIG__TOOLS.py` by file path, not via sys.path import); `make_interface_card._decl_backend`/`_config_lang_testdirs` now take `project_root` and read the TARGET's config, threaded through `_declarations`/`_declared`. Verified live against memohood (`--all --project-root <memohood>` from this checkout → 84 files, no `__map/tests/` noise this time; demo diff reverted). golden 106/0, test_cardstamp 103/0, run_restamp_fixtures 21/0. → next: REQ-006 (Python module constants not declared) or REQ-003 (nested-package identity in find_code_usage).
✅ REQ-006 fixed: `show_pyfile_api.collect()` now returns `constants` (public top-level `Assign`/`AnnAssign` names, signature = source segment collapsed to one line/120 chars for a valid H4 heading) alongside the existing all-inclusive `module_globals` (now `{name,signature}` dicts, used as before for the all_defs leaked-private fallback); `make_interface_card._declared()` python branch feeds `constants` into `exports` with `kind="const"` → renders under the existing `### Constants` H3 (already mapped for TS/JS/C#). New fixture `test/pythonSRC/consts.py` + 2 tests (declared+private-excluded, merge-preserves-prose) in test_cardstamp.py. golden 106/0, test_cardstamp 109/0, run_restamp_fixtures 21/0. → next: REQ-003 (nested-package identity in find_code_usage) is the only one left open.
✅ REQ-003 fixed (last of the three deferred items — all closed this session): find_code_usage's Python relative-import resolver matched `from . import X` by DOTTED NAME, walking up collecting `__init__.py`-bearing ancestor names and stopping at the first undeclared one — silently truncated for a target nested under an undeclared intermediate dir or a hyphenated dir name, both real in `hermes-filetools/self_delegate`. Added a PATH-based check alongside it (not a replacement): `_relative_import_root_dir` walks up by dot-count alone (no `__init__.py` dependency), then compares resolved absolute file candidates directly against the target's own path — immune to undeclared packages, hyphens, and same-basename collisions across packages. New fixture `test/pythonSRC2/` (the reported shape + an unrelated same-named sibling to prove no cross-package conflation) + a new golden CONSUMERS entry. golden 107/0, test_cardstamp 109/0, run_restamp_fixtures 21/0. → next: nothing queued — REQ-003/006/007 all closed; pick up whatever surfaces next session.
✅ Triaged and closed 4 of 5 findings in `__dev/Requests/cursor_feedback__gcb.md` (get_codeblock, real Cursor-agent usage on Warehub). #1 ladder lost bound names for `const foo = () => {...}` — `address.py::_bound_ancestor_label` walks up the binder chain reusing `spec.name()`, same as outline; new golden `LADDER_LABEL` (LADDER never checked label text before). #4 C# primary-ctor labels ran hundreds of chars — `TreeSitterSpec.name()` caps at 350 chars, display-only. #3 (default `--query` too small) already fixed by an unrelated 2026-08-24 commit that added an inline `--ancestor-level` legend — verified it still fires, no new change. #5 SCSS `~ERROR` bands on top-level `$var: value;` (whole-file parse cascade, `root.type` itself became `'ERROR'`) — added `LangSpec.preprocess` (generic opt-in hook, `None`/no-op for every other language — kept the "languages self-contained" rule the owner flagged explicitly) + `css_handler._mask_scss_top_level_vars` (rewrites top-level `$var:` into same-length real CSS comments before parsing). New fixtures: `test/cssSRC/vars.scss`. Residual, separately-noted finding (not fixed): `$var` used AS A VALUE inside a rule (`property: $var;`) can also cascade — bigger/riskier, left for later. #2 (JSX/route-island carving) deliberately deferred per owner ("да все кроме отложить" — #2 was the one meant to stay parked, no acceptance criteria). golden 110/0, test_cardstamp 109/0, run_restamp_fixtures 21/0. Log itself annotated with `**Fixed:**`/`**Already fixed:**` notes per entry, nothing renamed (not a `Requests/REQ-*` file).
✅ Регресс перестал умирать от отсутствующей опциональной грамматики. `yaml_backend.root()` импортировал `tree_sitter_yaml` голым `import` мимо `env_check` (единственное такое место — остальные языки прикрыты `LangSpec.parser()`), поэтому `check.py` падал трейсбеком и уносил ВЕСЬ прогон, включая 115 проверок, к YAML не относящихся. Фикс: `ensure_language("yaml")` в `YamlBackend.root` (то же сообщение с готовой командой pip, что печатает CLI) + декоратор `_optional_grammar` на ридер-раннерах `check.py` → SKIP кейса вместо падения, счётчик `N skipped (grammar missing)` в итоге (без молчаливого сокрытия). CLI, к слову, был исправен всегда — гард `ensure_language` живёт в `core.py`, а ридер-шов (`Reader`→`classify.outline_rows`→`backend.root`) его не звал. Питон — единственный язык с МОЛЧАЛИВЫМ фолбеком (`ast`), поэтому его OUTLINE-эталоны без грамматики давали ложный FAIL, а не исключение: `outline_for` теперь сам проверяет `tree_sitter_python` и отдаёт SKIP. Заодно закрыт корень: `tree-sitter-python>=0.23` дописан в `requirements.txt` (как ОПЦИОНАЛЬНЫЙ апгрейд — `LANGUAGE_MODULES["python"]` намеренно остаётся пустым, чтобы фолбек не стал жёсткой ошибкой) и поставлен в эталонный венв `T:\AgentsWork\venv`. Там же зафиксирован минимум Python >= 3.10 (его требуют и tree-sitter 0.26/css/yaml/python, и наш `str | None` в сигнатурах без `from __future__ import annotations`). Регресс в эталонном венве: check 120/0, cardstamp 109/0, restamp 21/0, golden 12/12, sweep HIGH=0 (LOW LEVEL=5 на TS try/catch — старый шум). На голом `py` тот же прогон: 115 passed, 0 failed, 5 skipped. Эталонный интерпретатор прописан в `__dev/CONTEXT_RESTORE.md` и `test/HowTo__Test-get_codeblock.md`. В `TOOLS.md` — НЕТ и не должно быть: это диливерабл-файл, а `test/` вообще не деплоится (`__dev/deploy_hq.py:45`), так что прежняя строка про тесты вела в несуществующий путь. По той же причине `CONTEXT_RESTORE.md` (чистый дневник сессий) переехал из корня пакета в `__dev/`.
✅ [2026-09-13] Closed the last open item in `cursor_feedback__gcb.md` (#2, JSX/route-island carving,
parked since 2026-08-30) with a root-caused writeup instead of a fix — `__dev/Plan__jsx-carve-tsx.md`:
`address.py`'s `_collect` needs `body_types`, not just `named_def`, to make a JSX node addressable at
all (JSX has no brace body), and a capitalized-tag promotion filter needs a predicate consulted by
BOTH `classify.py` (map) and `address.py` (query) or they diverge (invariant #6) — touches shared
brace machinery used by every language, deliberately deferred, not a quick patch. Shipped an interim
stopgap instead: `get_codeblock/jsx_note.py` flags a large flat TSX/JSX block (`known limitation: …`)
in both `--outline`/`--query`, self-obsoleting once the real carve ships. Same session, unrelated to
the JSX item: (1) **Vision05** — `--query` on an undersized/uninformative result now auto-escalates
by rewriting `--line`/`--level` into a horizontal sibling-gather (asymmetric cost fn vs FLOOR/TARGET/
CEILING in `CONFIG__TOOLS.py`), reusing the existing batch-resolve path (`escalate.py`, new); `--force`
(reserved since Vision03's grammar-of-the-command, never wired up) now does something — skips the
escalation, exact requested range. Resolve-once reordering (`_resolve_query_runs`/`_render_query_runs`
split) means the common non-escalating call pays zero extra cost. (2) `.mjs` aliased onto the existing
JS/TS profile (same grammar, Node's ESM marker isn't a syntax difference) — 4 touch points. (3) SCSS
residual from the 2026-08-30 entry above, actually fixed this time: a `preprocess`-masked `$var:` was
gluing onto the NEXT rule as its preamble in THREE independent raw-node-type comment checks
(`filler_kind`, `classify._owning_block`, `address._comment_rows`) — new opt-in
`LangSpec.is_synthetic_comment` excludes it from all three. (4) outline header axes labeled (`max
depth N`, `showing levels A..B`) — was bare numbers, ambiguous. Docs pass across TLDR/README/GUIDE for
all of the above, plus a stale drift found live in `core.py` itself (`--help`/TTY legend still said
`'Block level: K'`, a format no live output has printed in a long time — reworded to the ladder's own
level number). `__dev/Requests/feedback/` raw intake `.md` dupes deleted (fully merged into
`__dev/Requests/*.md` already); `feedback/files/` (real external repro sources) gitignored. golden_check
13/13, check.py 120/0, sweep clean (LOW LEVEL=5 pre-existing noise). → next: nothing queued from this
session — `Plan__jsx-carve-tsx.md` is the one deliberately parked item, pick up whenever.
✅ [2026-09-14] REQ-010/Plan03 closed: `## Runtime seams` — connections the import graph can't see
(dynamic load by path, separate process, shared file, event bus). `CARD_FORMAT.VERSION` 1.0.0 ->
1.1.0: `Dependencies Internal/External` renamed to `In-Project/External Dependencies` (old headers
still read via `ALIASES`/`canon()`), new `RUNTIME_SEAMS_SECTION`/`SEAM_COLUMNS`/`SEAM_KIND_BASE`/
`SEAM_SHAPE` + `seam_contract_line()`. `make_interface_card.py`: preserves an existing seams table
byte-for-byte except the contract-note line (refreshed like the version marker); `--help-seams`
(full contract, no file) + `<file> --info-seams` (grep hint only, never decides Kind/Shape/Why);
new `seam_scanner/` package (detector, NOT a CLI tool — moved out of a flat top-level file per
owner review) with hint-on-`--all`. `graph_from_cards.py`: seams parsed/resolved separately from
import deps; rendered with a dedicated marker (`【SEAM⇢】`/`【SEAM⇠】` — went through 3 iterations,
see Plan03's own retrospective section for why); `components()` stays import-only after a
mid-implementation correction (seams used to merge islands, which erased the fact they're
different apps) — `_seam_bridges()`/`_all_seams()` + a `## runtime seams (N)` section report seams
separately instead; new `--view seams-mermaid`. `validate_cards.py`: closed-vocab Kind/Shape check,
pending/unresolved for path-like `Target` (URL-scheme targets excluded from that heuristic).
142 new/updated tests, `check.py`/`sweep_invariants.py` clean. Manual regression + real migration
on `hermes-filetools` (its own 8 free-text `RUNTIME SEAM` markers rewritten into the new table,
caught 2 markers that didn't hold up against source — `core.js`/`prompt-mirror.js` weren't actually
seam participants — and 1 real by-path load the old prose had missed entirely,
`file_ops/_tool_text.py`); rolled out + re-stamped on `memohood` too (0 issues, 0 discrepancies on
both). Docs pass: `graph_from_cards__TLDR.md`/`validate_cards__TLDR.md`/
`make_interface_card__README.md`/`Guide__AuditCards.md`/`Guide__MakeCard.md`. All pushed
(ProjectStarter outer+tools, hermes-filetools origin). → next: nothing queued from this session —
open items are the ones Plan03 itself already lists (full detector pattern list grows by findings).
✅ [2026-09-14] `make_interface_card.py` gets opt-in call-logging, same mechanism get_codeblock
already had (`CONFIG__TOOLS.LOG_ENABLED_TOOLS`/`LOG_DIR`, thin `main()`/`_main_impl()` split, JSONL
per invocation — argv/status/exit_code/duration/error, never a card's content). Record adds
`mode` (preview/stamp/all/info-seams/help-seams), `status` (new/merged/forced/blocked) for single
stamps, and `all_files`/`all_counts`/`all_seam_hints` for `--all` — same summary already printed to
stderr, just structured for later analysis. Both tools now ON by default in `CONFIG__TOOLS.py`
(was opt-in/commented-out). Surfaced a real bug while enabling it here: this repo's own NEUTRAL
CONFIG__TOOLS.py has `PROJECT_ROOT = "."`, and `LOG_DIR = "__HQ/tools/_logs"` double-nested
(`__HQ/tools/__HQ/tools/_logs`) because every test/doc here already runs with cwd = `__HQ/tools/`
itself — fixed by setting THIS copy's `LOG_DIR = "_logs"` (real deployed projects, whose
PROJECT_ROOT is a genuine absolute path, keep `"__HQ/tools/_logs"` — unaffected, verified live on
both memohood and hermes-filetools). `_logs/` gitignored. Regression: test_cardstamp 142/0,
check.py 120/0, golden_check 13/13, sweep clean, run_restamp_fixtures 21/0. Deployed + committed on
ProjectStarter/memohood/hermes-filetools. → next: nothing queued.

## split_monster — Markdown, replace API, шапка для агента (2026-09-23)

### Функциональность
- `.md`: `replace()` + `STUB_XX` + `monster.replace()` в generate; код по-прежнему `cut` + `monster.cut`.
- `--split` принимает список строк через запятую (`12,34,45`) на один target.
- Адресация md-секций через get_codeblock (`level=0` в `cut`/`replace`).

### Документация и UX агента
- Единая шапка API во всех сгенерированных `move.py` (cut/replace, `\n`, только `Replace[]` в `monster.replace`).
- `--help` epilog: форматы, ESM auto-import, smoke-фикстуры.

### Тесты и выкладка
- `test/test_split_monster.py` — 27 кейсов (md replace, stub, comma-split, palette header).
- Коммит `5ec9d2d`, push `origin/main` (Project-Context-Box-Tools).

## make_interface_card — короткая DIRECTIVE_DESC (2026-09-23)

### Штамп
- `DIRECTIVE_DESC` для `####` записей Public API: `write short does+role, or remove` вместо длинного one-liner placeholder (меньше повторяющихся токенов в новых карточках).
- `DIRECTIVE_SUMMARY` / `DIRECTIVE_HOWITWORKS` без изменений.

### Тесты и миграция
- `test/test_cardstamp.py` — регресс на короткую форму в свежем штампе.
- `hermes-filetools`: массовая замена в `__map/*.md` через `replace_in_files` (346 директив); утилита скопирована в `__HQ/tools/`.

### Выкладка
- Коммит `b82a6a6` + TRACKER; push `origin/main` (Project-Context-Box-Tools).

## 2026-09-30 — Plan08: C/C++ в штемпеле (старт)

- Vision09 перенесён сюда (`__dev/vision/`), план — `__dev/plans/Plan08__cpp-stamp.md`.
- Решение владельца: языки подключаются ЗАПИСЬЮ в реестр, не веткой `if` → шаг 0 = `stamp_langs/` + `CONTRACT.md`, без C++.
- ✅ Шаг 0 (`5973592`): реестр `stamp_langs/` (python/typescript/csharp + `_common`), `CONTRACT.md` (форма `declared` + хуки, громкая проверка ключей). В `make_interface_card.py` ноль `lang ==`; незнакомое расширение → отказ exit 2 (раньше молча python — `.h` ушёл бы в Python-разбор). Регресс = база: check 121, cardstamp 144→154 (+10 на реестр), restamp 21, split ok, replace 15/21 старое.
- ✅ Шаг 1: фикстура `test/cppSRC/` — 14 файлов llama.cpp `7fee17846` целиком (+LICENSE, свой CONFIG, README со связями). Находка: `ggml-vulkan.cpp` достаёт `ggml-vulkan.h` только транзитивно (common→push-constants→types) → цепочка добавлена в фикстуру; `ggml-vulkan-shaders.hpp` генерируется сборкой, в дереве его нет.
- ✅ Шаги 2–8 (`eede1f6` + доводка): C/C++ в штемпеле/связях/графе — `#include` с `#if`-условием (Kind `conditional(X)`), объявления tree-sitter + второй разбор для сломанных мест, `## Build facts` (пара, зоны `#if`, кто включает во всём дереве, швы vtable/registry/dlopen, opaque), граф `--flags`, зона `--all --path`. CARD_FORMAT 1.2.0. Тесты: test_cpp 82/0, check 121, cardstamp 155, restamp 21. Приёмка: llama.cpp_mix — 37 карточек, validate 0 issues (штаб `dc32fba`). Шаг 9 (compile_commands) отложен — нет Ninja-сборки микса; `--flags` покрывает граф одной сборки.
- → next: проза карточек (Grok) по `Guide__MakeCard`; расширять зону по задачам микса (server, загрузка модели).
- ✅ Свёртка потребителей в штампе: >8 файлов у символа -> одна строка `consumers N (by folder): …` (глубина папок — самая глубокая, где топ-6 покрывают >=50%) + подсказка `find_code_usage --symbol`. llama `ggml.h.md` 8486 -> 2637 строк; граф не затронут (он читает deps-таблицу, `used-by` считает переворотом). → обсуждается Vision10: карточка / граф / запросы (clangd), граф с рёбрами из исходников для файлов без карточек.
- → Vision10 + Plan09 (`__dev/vision/Vision10__cards-links-and-meaning.md`, `__dev/plans/Plan09__cards-links-and-meaning.md`): карточка = связи и смысл; у C/C++-заголовка «API: in source» + таблица семейств + «What each family is for»; семейства механически (секции автора → префикс → вид); кэш сканов в `tools/_cache/<root>-<hash>/` с проверкой по git-отпечаткам; граф с рёбрами из исходников для файлов без карточек; запросы — clangd позже. → next: Plan09 шаг 0 (баг флагов) по «поехали».
- ✅ Plan09 шаг 1 — кэш сканов (`find_code_usage/scan_cache.py`, `tools/_cache/<root>-<hash>/cpp_scan.json`, отпечатки git blob / mtime+size, версия = хеш исходника производителя). llama: дерево 5,2 → 0,35 с, зона 36 карточек 31 → 8 с (основной выигрыш — однопроходный regex потребителей с предфильтром по идентификаторам; кэш имён отложен). Баг: `#include`/`using` в External Dependencies дублировались при merge → хук `import_line` (ПОПРАВКА 2); карточки llama вычищены (-705 строк). test_cpp 99/0, check 121, cardstamp 155, restamp 21. → next: Plan09 шаг 2 (семейства).
- ✅ Plan09 шаг 2 — семейства API (`stamp_langs/cpp.py::families`): секции автора → префикс имён (рекурсивно для групп >30) → вид. ggml-backend.h 11, llama.h 31, ggml.h 36 семейств. test_cpp 106/0. → next: шаг 3 (форма «API: in source», CARD_FORMAT 1.3.0).
- ✅ Plan09 шаг 3 — карточка заголовка «API: in source» (CARD_FORMAT 1.3.0, хук `api_families` ПОПРАВКА 3, валидатор, Guide__MakeCard § C/C++). Проза семейств по имени, исчезнувшее → Salvage. test_cpp 111/0, check 121, cardstamp 155, restamp 21. → next: шаг 4 (граф: рёбра из исходников для файлов без карточек).
- ✅ Plan09 шаг 4 — граф `--file`: файлы без карточек узлами `(no card)` с рёбрами из include-дерева (хук `source_edges`, ПОПРАВКА 4), свёртка по папкам, `--cards-only`; обзорные виды и --discrepancies по-прежнему по карточкам. test_cpp 117/0.
- ✅ Plan09 шаг 5 — приёмка llama: зона 7,7 с (было 31), ggml.h.md 2637 → 169 строк, validate 0, граф видит всё дерево. **Plan09 закрыт.** → next: проза карточек (Grok) по новой форме — когда владелец решит; clangd (Plan08 шаг 9) — при Ninja-сборке микса.

## 2026-09-30 — get_codeblock: C-заголовки, --name, макросы

- ✅ Адресация в C-заголовке: строки внутри `#ifdef __cplusplus` (рамка без тела) давали `<file>` — цепочка теперь спускается в рамку как карта; typedef без тела — свой блок (`classify.leaf_landmark_at`); прототип — полоса `decl:`. `--query` за концом файла — ошибка, не traceback. (`f42d9f9`)
- ✅ `--name` — `get_codeblock/name_resolver.py`: имя → строки → существующий `--line` (точно 1 → `--query`; иначе `--outline` по кандидатам; шапка одной строкой; exit 2 = ничего). Точно / маска / близко (регистр, подстрока, слова, опечатка). C/C++/Python/C#/TS/md. test_name_resolver 32/0. (`110694a`)
- ✅ Макросы C/C++ вырезаются ДО разбора в get_codeblock (`get_codeblock/cpp_source.py`, хук `preprocess` на копии `CPP_SPEC`): конфиг `CPP_*` + автоопределение по `#define` самого файла; строки/колонки сохраняются. Одна реализация для ридера, штемпеля, find_code_usage (`cpp_includes` реэкспортирует). Было: `ggml.h` L934–2050 и `llama.h` L514–1685 — один мусорный узел. (`888f52c`, `e8b7424`)
- Известное, не наше: `sweep_invariants` CRASH=71 на cp1252-фикстуре replace_in_files; `golden_check` 4/13 — устаревшие эталоны шапки.
- ✅ `make_interface_card --all --stale` — только карточки с устаревшим СВОИМ исходником (вердикт check_cards_freshness), новые не создаёт; ограничение: новые потребители из-за чужих правок — только полный `--all`.
- ✅ Свёртка Why: ≥5 импортов без прозы из одной папки -> `папка/*` (N: имена) — ключ группы; написанная проза всегда своей строкой. llama `ggml-cuda.cu.md` 259 -> 183 строки.
- ✅ Карточки без номеров строк (git-шум): зоны `#if` — `in f · wraps g · top level`; швы — группы по контейнеру (`vtable ×10 in <таблица>`), мелкие — с кодом; семейства — колонка `From` (первое объявление) вместо `Lines`; opaque — `in f (~N lines)`. Якоря — имена `name_resolver` (`container_at`, `outermost_in`), читаются `get_codeblock --name`. Тест: сдвиг строк исходника -> карточка байт в байт та же.
- ✅ Баг карты get_codeblock: `#ifdef`, обёртывающий ровно одну функцию, терял функцию (`Spec.body` рамки разворачивал определение) — исправлено, тест.
- test_cpp 140/0, name_resolver 32/0, check 121, cardstamp 155, restamp 21; llama validate 0.
- VERSION get_codeblock (формат вывода: шапка `--name`) — бампнуть в конце сессии.
- → next: nothing queued (Grok-проза по новой форме — решение владельца).
- ✅ Фуззер инвариантов get_codeblock на зоне микса llama (ggml/include, ggml-cuda, ggml-vulkan, include): 314 файлов, 22008 проб (--step 3 --check-query) — HIGH 0 (CONTAIN/RANGE/CRASH/QUERY), LOW 3 (однострочные struct{ operator() } в ggml-cpp.h — уровень по строкам, не баг). Фуззер теперь берёт расширения из реестра ридера (раньше пропускал .cu/.cuh).
- ✅ llama STAMP_DIRS = зона задачи микса (экспертный параллелизм MoE: backend/meta/scheduler, ggml.c mul_mat_id, gguf, CUDA mmid/mmq/mmvq/mmf/topk-moe/moe-weighted-reduction, Vulkan, llama model/loader/graph/context/quant/arch, qwen3moe/qwen3next/qwen35moe, common/arg, imatrix, quantize) — 74 карточки, `--all` 13 с, validate 0. Баг штампа: реализация C++ повторяла `Class::method` из класса заголовка — исправлено (llama-graph.cpp.md 356 -> 68 строк).
- ✅ Plan01/Plan02 card-prose review (llama, executor Composer 2.5) exposed stamp/reader bugs, all fixed with tests: C/C++ entry key = full qualified name; prose paragraphs kept on merge; get_codeblock recovers after an unparsable function body (`cpp_source._recover`, ggml-vulkan.cpp); rename similarity by bare name within the same qualifier; private class members count as declared in the header; English rename/signature markers; `golden_check` separator-agnostic (13/13); `sweep_invariants` extensions from the reader registry. Guide__MakeCard: don't trim facts, never replace `####` entries, no line numbers in prose, read the re-stamp report. get_codeblock VERSION 0.6.0 -> 0.7.0. test_cpp 150/0.
- ✅ REQ-013 (DONE__): get_codeblock shows YAML frontmatter in `.md` as its own landmark `meta: <keys>` (outline + `--line`/`--query`); a YAML `# comment` is no longer a heading. check.py 123/0.
- ✅ REQ-012 (DONE__): get_codeblock reads shell scripts — `.sh` (bash profile), `.ps1` (own Spec over tree-sitter-powershell), `.bat` (labels, zero-dep); one ext->language map (`language_for_ext`, 4 copies removed); `--name` takes hyphenated names and skips shell command calls. check 131/0, name_resolver 36/0. Language rule -> template `Guide__Language.md`.
- get_codeblock VERSION 0.7.0 -> 0.8.0 (frontmatter, scripts, `--name` hyphen names). `__dev/CONTEXT_RESTORE*.md` rewritten for the tools only (English); Plan09 -> plans/done.
- ✅ get_codeblock .py addressing: a line inside a multi-line string / open bracket / after `\` continues its statement (`python_handler._is_continuation`) — it no longer ends a block (dedented JSON in `"""`), nor starts one (`\` + `else (...)`). Sweep: rlm 434 HIGH -> 0, TRELLIS.2 3 -> 0, beellama scripts 36 -> 0, tools tree 3 -> 0. check 135/0.
- ✅ get_codeblock `views.py` (Plan30 of hermes-filetools): every CLI mode as DATA + its renderer (`outline_view`/`ladder_view`/`outline_batch_view`/`query_view` + `render_*`, `as_text` == CLI stdout), CLI = parse_args -> view -> renderer -> print; `block_range(src, line, count)` — both ends of [line, line+count-1] snapped to blocks (tol = count//2, cut = innermost block when the end can't snap). core.py 1080 -> 717 lines. Output unchanged: check 129/0 (6 skipped, no grammars in this python), replay of 1482 logged calls old vs new — 0 differ. test/test_views.py 27/0. Found, not fixed: `--name` with 2 exact hits in a .cu file crashes in `classify.outline_rows` (`parent_scope` None) — old version too.
- 📝 REQ-014 (md section body blocks: paragraphs/list items/fences/tables inside `~content`) and REQ-015 (`--name` 2 exact in .cu crashes in classify.outline_rows) filed. Also: views `Source.display`, block_range `tol = count // 2` (`15984b4`, `330f600`); hermes-filetools vendors this repo @ 330f600.
- ✅ REQ-015 (DONE__): `--name` with 2 exact hits, one inside a bodyless `#else`, no longer crashes the focus outline — `classify._scope_inside` is one scope rule for the ladder and `outline_rows`. Golden `name_ambiguous_else_branch` 14/14, check 129/0, test_views 31/0.

## 2026-10-09 — split_monster: безопасность + Python/Markdown (Vision06 «Заход 1»)

- ✅ Байт-в-байт: LF-файл на Windows превращался в CRLF (text mode) — теперь бинарный IO, EOL/BOM источника сохраняются и наследуются новыми целями.
- ✅ `monster.verify()` после закрывающего cut/replace: ни строки не потеряно/не выдумано, всё парсится (где парсилось до) — иначе откат всех файлов, exit 1. cut без write теперь отвергается (раньше молча терял блок).
- ✅ Устаревший план: `expect_source` только ПРЕДУПРЕЖДАЕТ о смене хэша файла; каждый `cut(..., expect=<отпечаток текста блока>)` сверяет свой блок — тот же текст = работаем, другой = стоп, `--force` = предупреждение и режем.
- ✅ Языки: Python (`ast`: имена, импорты, `def`-превью) и Markdown (якоря-слаги, ссылки `#anchor`) — по-настоящему; прочие — честная пометка в скрипте. `monster.consumers` не падает на `.md`/`.mjs`.
- ✅ Идентификаторы вместо слов (`_identifiers`: ast / tree-sitter) — комментарии и строки больше не рождают ложные `add_import`.
- ✅ `--rebase move.py [--write] [--accept-changed]` — лёгкая перегенерация: переставляет номера строк в существующем скрипте по отпечаткам блоков, ручные правки не трогает; изменённый текст — только с `--accept-changed`.
- ✅ Лог использования `split_monster.log.jsonl` (тот же opt-in механизм, `LOG_ENABLED_TOOLS` + `LOG_DIR`): записи `generate` / `rebase` / `run` (исход прогона `move.py`: dry-run / applied_verified / verify_failed / refused_block_mismatch, force, stale_warning). Тесты не пишут в реальный лог (`SPLIT_MONSTER_NO_LOG`).
- ✅ Заход 2 (граф по набору разреза, Py/JS/TS): кросс-импорты между целями и из цели в остаток источника, `SOURCE_IMPORTS` (обратный импорт в источник через `monster.cut(..., imports=)`), предупреждения `export` (только предупреждение — текст блока не правим) и `cycle`.
- ✅ `split_langs/` — реестр языков split_monster (python / javascript / markdown + `other`-фолбек), контракт `split_langs/CONTRACT.md` с громкой проверкой при загрузке; из ядра убраны все `if kind == …` (1539 → 1175 строк). Поведение не менялось. Следующие шаги — «каннибализм» доноров: универсальные имена/идентификаторы/шапка через get_codeblock, импорты/пути через find_code_usage resolvers, export через stamp_langs.
- ✅ Шаг 2 «каннибализма»: `split_langs/treesitter.py` — универсальный модуль для C#/C/C++ целиком на get_codeblock (`Spec.role/unwrap_def/body`, поле `name`/дрилл `declarator`, обход frame — namespace/extern "C"/#ifdef; идентификаторы без комментариев/строк/членов; `import_insert_index` по ряду `imports:` outline, для C/C++ — `#include`). Подсказки и `--rebase` теперь работают на .cs/.c/.cpp/.h; автоимпорты — следующий шаг. Контракт: `declared_names/top_level_names/decl_line/import_insert_index` получают `ext`.
- ✅ Шаг 3: импорты C#/C/C++ — `source_imports(lines, ext)`: C# `using` (колонка 0) и безусловные `#include` (донор `find_code_usage.cpp_includes.scan_text`) переносятся в КАЖДУЮ цель (kind `always`: карты имя→импорт без компиляции нет, лишнее безвредно); новый опциональный хук `notes(lines, ext)` → в скрипт: сколько импортов перенесено, `WARNING` про условные `#include` (не переносятся) и про `namespace`, из которого блоки выходят. Граф для C#/C++ осознанно не включён (межфайловые ссылки там — namespace/заголовки, не import). TS-алиасы не нужны: новые импорты между файлами сплита всегда относительные.
- ✅ Шаг 4 (проверка видимости): хуки языка `exported_names(text)` (+`ENFORCES_PRIVACY`, `dangling_exports`, `reexport_line`) вместо `export_problem`. JS/TS: публичное = `export <decl>` / `export default X` / записи `export { a, b as c }`; Python: `__all__` или имена без `_`. Предупреждения в скрипте: `WARNING export` (приватное имя пересекло границу — только JS/TS), `NOTE public API` (публичное имя уехало — импортёры источника сломаются; предложена строка реэкспорта), `WARNING dangling export` (список экспорта/`__all__` источника ссылается на уехавшее имя). `stamp_langs.declared()` НЕ использован: проверено — он не видит `export { x }` списков (для `export { helper }` вернул helper приватным).
- ✅ `--investigate` (бывшая заглушка): таблица блоков (строки, размер, объявляет, использует/используют в этом файле), хабы, семьи (>=2 блоков по связям без хабов и оркестраторов), одиночки, оркестраторы с «на какие семьи опираются», стартовая команда `--split` (отщепить семьи, ядро остаётся). Проверено на make_interface_card.py (1288 строк): 7 осмысленных семей (логи, разбор прозы, similarity, …). Dry-run `move.py` печатает таблицу плана. Лог: kind `investigate`.
- ✅ Боевая обкатка на копии tools (2026-10-10): `make_interface_card.py` (1288 строк) → 6 модулей по предложению `--investigate` (логи, scan, why, facts, prose, identity), источник 923 строки; `verify` прошёл, затем ВСЕ наборы на разрезанном коде: test_cardstamp 155/0, check 135/0, restamp 21/0, test_cpp 150/0. Первый прогон нашёл реальную дыру: имена, нужные другим файлам проекта (тесты берут `mic.DIRECTIVE_WHY`, `mic._MARK_SIG_CHANGED`), не возвращались в источник. Исправлено: Python-реэкспорт — публичные имена + имена с внешними потребителями (`consumers_of`) возвращаются в источник через `SOURCE_IMPORTS` автоматически (хук `AUTO_REEXPORT`). Заодно: швы после вырезки не копят пустые строки (`_tidy_seam`), блок свежих импортов отделяется пустой строкой.
- ✅ Решение владельца по `export`: ДОПИСЫВАТЬ, не править. Приватное JS/TS-имя, пересёкшее границу файла, получает в конец файла-владельца (цель или источник) строку `export { name };` — текст блока не трогается (`append=` в `monster.write/cut/replace`, хук языка `export_line`); проверка сохранности принимает её как разрешённую добавку.
- ✅ «Доправлять, а не прятать» (установка владельца: разрезать файл так, чтобы тесты не упали, — высший пилотаж; цель — помочь агенту ДОвести разрез, а не сделать автоматом за один ход): `--check CMD` (команда проекта, cwd = project-root; ОТЧЁТ без отката; подсказки «имя X из ошибки переехало: откуда → куда» по карте переездов; код 3 = разрез применён, проверка упала), `move.py --undo` (оригиналы всех тронутых файлов в `move.py.undo/`, созданные файлы удаляются), статическая проверка неопределённых имён Python (`symtable`) сразу после verify. Проверено на обкатке make_interface_card: с намеренно сломанными SOURCE_IMPORTS check упал и подсказал, куда переехали `_lang`/`DIRECTIVE_SUMMARY`; `--undo` вернул файл.
- ✅ ЖИВОЙ разрез в hermes-filetools (по просьбе владельца, не критичный файл): `desktop/src/config-pane.js` 724 → 465 строк + `config-widgets.js` (8 блоков) + `config-tools-table.js` (12 блоков, включая 2 комментария-«сироты», взятых из кандидатов). `--check` = node-тесты проекта (354/354) + esbuild-сборка в сторонний outfile + `node --check`: зелёно с первого применения; в пробной копии сначала прогнал то же. Сам `esbuild` ловит несуществующие экспорты — полезная часть check для JS. Дописаны `export { … };` (11 имён) в цели. Карточки: config-pane перештемпелёвана (merge, проза сохранена), 2 новых отштампованы (проза «awaiting agent», как у 59 прочих). НЕ закоммичено в hermes-filetools, `compiled/` не пересобирался, pytest проекта не гонялся (JS-срез). Откат: `T:\AgentsWork\_split_trial_hf\move_real.py --undo`. Находка: RAM-диск проекта (`\Device\ImDisk0\…`) ломает esbuild (не находит entry) — пробную копию делал в обычной папке.
- ✅ Session end 2026-10-10: split_monster `--help` and TLDR brought up to date (were: "v0", "Python import — no"), `test_help_is_current` guards against drift; `CONTEXT_RESTORE.md` got a split_monster section. Trial copy and undo folder deleted (git restores everything).
- Тесты: test_split_monster 59/0 (+32), check 135/0. → next: Заход 2 (граф по набору разреза: кросс-импорты, обратный импорт, export, циклы), см. Vision06.
- ✅ 2026-10-18 get_codeblock code review (`__dev/review/`, status `__dev/review/STATUS.md`): fixed R01 (multi-line decorators), R04 (long md fences), R05 (qualified glob), R06 (multi-declarators), R07 (--name on headings / ast fallback), R10 (empty argv); R09 decided by the owner: unresolved --line = `Missing: line N — …`, exit 0, exit 1 only if nothing resolved. Checked old vs new on Hermes, Strata C++ and llama.cpp sources; all suites green; vendored into hermes-filetools (pytest 1175/2). → next: R08+R03 (one physical line splitter), then R02 + re-parse debt, CONTRACT.md cleanup.
- ✅ 2026-10-18 R03+R08 (`064540b`): one physical line splitter `get_codeblock/physical_lines.py` (line ends at `\n`, ending kept) replaces readlines/splitlines in core, 4 handlers, address and 4 backends. API text byte-exact (was inexact on 656/1843 real files), picture stays `\n`; 1178 CRLF twins render as their LF originals. Vendored into hermes-filetools. → next: R02 + re-parse debt, CONTRACT.md cleanup.
- ✅ 2026-10-18 review closed: R02 not fixing (owner), `reader/CONTRACT.md` cleaned (Missing rule, `■BLOCK` instead of `[i/n]`/`Block level`, views names, no hard-coded version), DECISIONS fact-fetcher root line brought up to date. get_codeblock VERSION 0.8.0 -> 0.9.0 (Missing instead of ERROR, md fences, multi-declarators, CRLF-exact API).

## 2026-11-01 — GLSL: проверка грамматик для get_codeblock

- Скачаны в рабочий venv tree-sitter-glsl-spec 1.0.0 и tree-sitter-glsl 0.2.0. Рабочий tree-sitter остаётся 0.26.0; диагностический 0.25.2 установлен отдельно в TEMP/projectstarter-glsl-runtime25.
- На всех 22 шейдерах PlanetWeather: glsl-spec 18 чистых файлов, 10 ERROR/MISSING; glsl 16 чистых, 51 ERROR/MISSING. На 0.25.2 обе нашли 348 функций, все диапазоны совпали с независимой проверкой сигнатур и фигурных скобок.
- Ограничения glsl-spec: условный препроцессор разрывает if/else в cover-map/color-map/cloud-layer/cloud-near; statement_list и declarator_list требуют адаптации. На 0.26 прямой Language(int) даёт OverflowError; диагностический PyCapsule-мост сопровождался повреждёнными координатами и нативными падениями (причина пока не локализована).
- Существующий Classifier проверен с временной нормализацией statement_list: карта строится. Production-профиль НЕ подключён; --name/--query и полный sweep инвариантов не проверены.
- Отчёт и воспроизведение: __dev/review/GLSL_PROBE.md; скрипты glsl_probe.py, glsl_adapter_probe.py; JSON и пример карты рядом. Нет production-правок, коммита или выкладки.
- → next: glsl-spec предпочтителен как основа; перед интеграцией решить совместимость runtime и корректную адресацию на ошибках препроцессора.

## 2026-11-01 — Plan10: GLSL wheel собран; дефект Point в runtime 0.26 локализован

- По указанию владельца вся сборка и временные данные в T:/AgentsWork/glsl-wheel-plan10 (TEMP/TMP/pip/npm-кэш на T:, C: только чтение установленных инструментов). Точный publishing commit 3a00d49 получен явным fetch, сборка через предоставленный vcvars64.bat / MSVC 14.39.
- Собраны cp310-abi3-win_amd64: glsl-spec 1.0.0+capsule1, +regen15, +regen14 и старая glsl 0.2.0+capsule1. Основной parser.c/grammar.js не изменён; CLI 0.27.1 / ABI 15 воспроизводит тот же parser.c побайтно. Колёса, hashes/diff/команды — wheels/.
- Строгий runner: исходная приёмка main 380/480 (exit 1); регенерации 360/460 каждая; old 380/460. Без таймаутов. Повтор с индексами Point[0/1]: 480/480 (exit 0), все данные совпали с baseline 0.25.2; C++ контроль 20/20 в обоих режимах.
- Причина native-сбоев прежних проб локализована до Point.row/column в Python-привязке runtime 0.26.0: getters возвращают borrowed ref, теряется ссылка; воспроизводится без GLSL/парсера. На 0.25.2 и при индексах refcount корректен. Production-get_codeblock уже использует индексы. Исправление GLSL-обёртки устранило только первоначальный OverflowError.
- Исходные критерии Plan10 НЕ пройдены из-за .row-повтора. Новое колесо в эталонный venv НЕ установлено (там tree-sitter 0.26.0 / GLSL 1.0.0); production/Hermes/шейдеры не тронуты, ничего не закоммичено. Индексный PASS не подменяет исходную приёмку.
- Сдача: __dev/review/GLSL_BUILD.md, glsl_wheel_accept.py, glsl_point_probe.py, все JSON повторов; исторические probes/JSON сохранены. План оставлен для разбора владелицей и Claude.
- → next: решение Plan о критерии индексного доступа / отдельной правке runtime. GLSL-профиль get_codeblock остаётся отдельным шагом.

## 2026-11-01 — Plan11: ревью перед интеграцией GLSL

- Plan11 найден в tools/__dev/plans/ (указанный путь memohood/__dev/plans отсутствует). Memohood не менялся.
- Решения D1–D8 поддержаны; вопросы записаны в __dev/plans/Plan11__KICKBACK.md: K1 — сырые диапазоны baseline против публичной преамбулы/эскалации --name; K2 — локальный Windows wheel, корректные install hints, чистый отказ при старом upstream и переносимость общего requirements.
- Исполнение Plan11 НЕ начиналось, stage 0 не выполнен. В KICKBACK сохранён контекст продолжения после компактизации, включая запрет временных данных на C:, путь сборки на T: и SHA256 capsule1.
- → next: согласовать K1/K2; после компактизации исполнять обновлённый Plan11 целиком. Ничего не коммитить/не деплоить, Hermes не трогать.
- ✅ Повторное ревью обновлённого Plan11: K1/K2 закрыты (D9, D7/D8 и тесты шага 4); существенных возражений нет. → next после компактизации: исполнять актуальный Plan11 с шага 0. Исполнение ещё не начиналось.

## 2026-11-01 — checkpoint перед следующей сессией Sol

- По прямому запросу владелицы подготовлен __dev/CONTEXT_RESTORE_SOL.md: порядок чтения, решения Plan11 D1–D9, состояние venv, точные команды установки/приёмки capsule1, hashes, тесты, ограничения и инвентарь сборки на T:. Ссылка добавлена в общий __dev/CONTEXT_RESTORE.md.
- Сохраняется checkpoint-коммит исследования/колёс/планов. Это отдельное разрешение владелицы; запрет коммитов и деплоя при исполнении Plan11 остаётся в силе до нового указания.
- Проверены SHA256 всех колёс, синтаксис диагностических скриптов, читаемость JSON, результат индексного прогона 480/480 и пути сборки. Production не менялся; полный регресс для этого checkpoint не запускался.
- → next: в следующей сессии прочитать CONTEXT_RESTORE_SOL.md и выполнять актуальный Plan11 с шага 0. Wheel ещё не установлен в эталонный venv; Plan11 не начинался. Не использовать C: для временных данных.


## 2026-11-01 — Plan11 выполнен: GLSL в get_codeblock 0.10.0 (Sol)

- ✅ capsule1 установлен в эталонный venv, tree-sitter остаётся 0.26.0; SHA256 совпал, повтор индексной приёмки без PYTHONPATH 480/480. Три варианта убраны из wheels (копии на T:), оба Plan10-файла в done, README актуализирован по D1.
- ✅ GLSL-профиль и все девять расширений; единый optional TSProfile.node_rules для нормализации дерева карты/адресации/имён; #define, structs/interfaces, multi-declarators, комментарии. Без GLSL-веток в classify/render/address и без изменения общих LangSpec.
- ✅ Point guard + доказанная временная вставка; D7 чистый отказ для отсутствующего модуля, настоящего upstream 1.0.0/int и другой платформы. Сообщения прежних языков не изменились.
- ✅ 22 реальных шейдера: все 4464 строки, 348 сырых функций и 348 пар реальных CLI --name/--line PASS; map/address и исходный текст проверены. GLSL sweep HIGH=0, LOW=2 (косметические однострочные ties); локальные фикстуры HIGH/LOW=0.
- ✅ Регресс: check 150/0, cardstamp 160/0, restamp 21/0, golden 16/16, cpp 150/0, names 55/0, views 57/0. Общий sweep сохранил известный CRASH=71 cp1252 / LOW=5, других HIGH нет. Old/new: 222 файла (104 — вся настроенная C/C++/CUDA зона llama.cpp_mix), 666 сравнений, 0 отличий.
- ✅ TLDR/README/TOOLS/CONTRACT/DECISIONS/context/wheels docs обновлены; VERSION 0.10.0. Отчёт __dev/review/GLSL_INTEGRATION.md, JSON рядом. Sol journal обновлён до итогового состояния.
- ✅ Hermes только прочитан и vendor --check (exit 1 / 12 tracked differences). Уточнено: --check сравнивает tracked working paths, новый untracked glsl.py не включает; нормальный sync требует чистый commit. Help needs GLSL extensions; wheels не копируются sync, доставка/установка отдельно при решении владельца.
- Ничего не закоммичено, не скопировано в vendor, не задеплоено; Hermes Python/gateway/службы/оригинальные шейдеры не тронуты. Все новые временные данные на T:.
- → next: Claude ревью/коммит Plan11; после этого разрешённая синхронизация и решение владельца о поставке колеса в Hermes. Plan11 оставлен активным до ревью.


## 2026-11-01 — Plan12 выполнен (Sol), далее Plan13

- Linux capsule1 cp310-abi3 manylinux2014/manylinux_2_17_x86_64 собран в официальном Docker; parser.c/grammar.js идентичны Windows, patch не менялся. auditwheel: GLIBC_2.2.5, внешних shared libraries нет. Image1,704,774,662 bytes; всё рабочее/venv/cache на T:.
- WSL Python3.12.3/tree-sitter0.26.0: capsule ABI15, 480/480 strict acceptance, синтетика5/178/21, личные22/4464/348 PASS; все сырьевые результаты вне репо. Windows/Linux outline/name совпали после OS-path/CRLF normalization. Point.row defect воспроизведён, index корректен.
- Production только Linux artifacts entry; env-тест6PASS на Windows/WSL. Windows wheel и installed binding hashes прежние. Регресс150/160/21/16/150/55/57, GLSL fixturesPASS; sweep152файла/52083probes сохранил cp1252 CRASH71/LOW5, других HIGH нет.
- Отчёт __dev/review/GLSL_LINUX.md; wheels README/manifest/build-linux.sh и platform docs обновлены. Без коммита/деплоя/Hermes. → next: Plan13, до/после Vulkan + PlanetWeather, только синтетические фикстуры в репо.


## 2026-11-01 — Plan13: Vulkan-маски готовы, V3 ожидает решения по K1 (Sol)

- До:185 shaders,118 файлов с ERROR/MISSING,1164 узла; после атрибутов16/481; после известных coopmat/tensor типов13/124. Все676 атрибутов и148 type-списков обработаны; ошибки на этих конструкциях ушли. Прямых функций368, всех634 — до/после без потерь.
- LangSpec.preprocess, byte-preserving glsl_source.py; имена/arity типов — данные GLSL-профиля. Защита комментариев/строк/CRLF/UTF8/сравнений/неполных конструкций,19 adversarial кейсов; никакой пересборки/веток в движке.
- Проверены ровно185 файлов/25036 физических строк, sweep20968 непустых probes: HIGH0/LOW0 до/после, каждый query byte-exact. Дополнительный #6 контроль нашёл5 предсуществующих blank-preamble mismatch; полный before/after список идентичен. Общее исправление не применялось самовольно. KICKBACK __dev/plans/Plan13__KICKBACK.md, вопрос владельцу отправлен асинхронно.
- PlanetWeather22/4464/348 PASS,88 полных CLI-выводов до/после байт-в-байт, сама маска тождественна исходнику на22/22. В repo только новая синтетическая Vulkan-фикстура; ни личного, ни llama.cpp кода/сырья не добавлялось.
- Регресс: check153/0,cardstamp160/0,restamp21/0,golden16/16,cpp150/0,names55/0,views57/0; GLSL6/204/22 на Windows и WSL; env6PASS. Общий sweep154/52171 сохранил прежние cp1252 CRASH71/LOW5, других HIGH нет.
- Отчёт __dev/review/GLSL_VULKAN.md, CONTRACT/TLDR/DECISIONS/context обновлены. Сырьё и воспроизводящие scripts — T:/AgentsWork/glsl-wheel-plan10/plan13/. Без коммита/деплоя/Hermes, VERSION0.10.0.
- → next: решение по K1 (отдельный дефект и приёмка без новых #6 либо расширение scope общей blank-preamble правкой), затем Claude review/commit Plan12+Plan13. Строгий V3 пока не назван выполненным.


## 2026-11-01 — Plan13 принят по уточнённому V3; K1 CLOSED

- Владелица выбрала вариант 1: отсутствие НОВЫХ #6 при полном сравнении списков до/после. Проверено: пять исходных случаев полностью идентичны, новых нет; все пять перечислены в GLSL_VULKAN.md как известные.
- Общий механизм преамбул не менялся и по прямому указанию не входит в Plan13. Исправление — отдельный REQ-017 (__dev/Requests/REQ-017_blank-line-in-comment-preamble-addresses-file.md), после Plan13.
- KICKBACK CLOSED; критерий в Plan13, отчёт, DECISIONS и оба контекста обновлены. Код/проверенные результаты не менялись; повтор регресса для документирования решения не требуется.
- ✅ Plan12 и Plan13 выполнены, готовы к ревью/коммиту Claude. Ничего не закоммичено/не задеплоено; Hermes не тронут. → next: Claude review/commit, REQ-017 отдельно.

## 2026-11-01 — REQ-017 выполнен, get_codeblock 0.10.1 (Sol)

- ✅ Пустые строки внутри mapped-преамбулы получают её именованного владельца в brace-адресации и focus; сохраняются вложенные предки/leaf-блоки. Python исправлен тем же правилом, включая декораторы и защиту multiline strings. Непустые маршруты не менялись; языковых веток в общем движке нет.
- ✅ Пять синтетических языков,30 основных случаев плюс вложенность/границы/literals;15 ручных ladder-эталонов. Sweep PREAMBLE HIGH доказан на старом движке. Сам фаззер переведён на общий physical_lines, чтобы не считать lone CR/Unicode separator новыми строками.
- ✅ Все пять прежних Vulkan #6 расхождений устранены:185 файлов/25036 строк,20973 sweep probes,HIGH0/LOW0; точный query и map containment PASS.
- ✅ Old/new:253 кандидата,250 декодируемых файлов/185720 физических строк. Все500 outline/dot и185259 неизменившихся line-выводов совпали. Только461 пустая строка изменилась:459 mapped-преамбул и2 исключения ложного владельца перед настоящим комментарием. Три invalid-UTF8 отказа одинаковы; байты исходников не менялись.
- ✅ check169/0,cardstamp160/0,restamp21/0,golden16/16,cpp150/0,names55/0,views57/0,GLSL6/204/22+19 masks,env6PASS. Полный sweep160/52603:CONTAIN0/RANGE0/OPEN0/PREAMBLE0,CRASH71/QUERY23/LOW5,SIBLING431,exit1. Все QUERY23 — старый cp1252 README.md, архив446411f воспроизводит те же23; новых HIGH нет.
- Отчёт __dev/review/REQ017_PREAMBLE.md; CONTRACT,DECISIONS,request и оба контекста актуальны. Сырьё/логи исключительно T:/AgentsWork/glsl-wheel-plan10/req017/; в repo только собственная синтетика. Колёса/venv/Hermes/оригинальные shaders не тронуты.
- → next: Claude review/commit REQ-017. HEAD446411f, без самостоятельного коммита/push/деплоя. Request остаётся без DONE до ревью.

## 2026-11-01 — ревью REQ-017 и раскатка 0.10.1 (Claude)

- ✅ REQ-017 принят (`dd16993`): независимое old/new на 556 файлах sim (C++/шейдеры) и 184 Python memohood — карты и все непустые строки побайтно те же; скорость на пустых строках +~9%. Request → `DONE__`.
- ✅ Раскатано 0.10.1: Hermes (vendor + распакованная грамматика GLSL, задеплоено, шлюз — владелица), hermes-filetools `__HQ/tools`, `Y:\AgentsWork\dVOrbitals\sim` (новый клиент, ветка gfx), `Y:\SRC\llama.cpp_mix` (весь HQ). sim и llama.cpp_mix — записано, НЕ закоммичено (коммит — их сессии/владелица).
- Колесо GLSL в проектах ставится по команде из отказа get_codeblock (владелица предупредила Opus в sim). В Hermes — распаковано в vendor, без установки.
- → open: `dvOrbital__GDD` больше нет — это, видимо, `dvOrbital__DESIGN` (чекауты на T: от 31.10 и на Y: от 17.10, оба get_codeblock 0.8.0) и второй чекаут `T:\AgentsWork\dVOrbitals\sim` (main, 0.9.0): обновлять ли и какие — спросить владелицу, затем поправить таблицу копий в CONTEXT_RESTORE.
