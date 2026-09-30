# Plan08 — C/C++ в штемпеле и графе (исполнение Vision09)

Замысел — `../vision/Vision09__cpp-stamp.md` (читать целиком). Первый C/C++-проект —
`y:\SRC\llama.cpp_mix` (upstream `7fee17846`). Согласовано с владельцем 2026-09-30.

## Главное правило плана: модульность, а не `if`

Язык подключается ЗАПИСЬЮ в реестр, а не новой веткой `if lang == ...` в штемпеле. C++ — четвёртая
запись, не четвёртая ветка. Поэтому шаг 0 — рефакторинг без C++.

## Шаг 0 — языковой реестр штемпеля + контракт · ✅ `5973592`

**Что сейчас зашито в `make_interface_card.py`** (инвентарь 2026-09-30):

| место | что языкового |
|---|---|
| `_LANG`, `_lang()` | ext → язык; **незнакомое расширение молча = python** (баг: `.h` пошёл бы как Python) |
| `_normalize_langs` | синонимы `ts/js/cs/py` → канон |
| `_TS_BACKEND`, `_declarations` | жёсткий список модулей tree-sitter + pip-пакетов |
| `_declared()` | цепочка `if python / typescript / csharp`, каждая ветка сама собирает один и тот же dict |
| `_cis_setup` | частный случай C#: namespace → доп. target_names |
| `build_card` | частный случай Python: `_resolve_sibling_signature` для ре-экспорта пакета |
| `_DECORATORS` | служебные слова перед именем, по языку |

**Сделать:** пакет `stamp_langs/` — `__init__.py` (реестр: `for_file(path)`, `get(name)`,
`known()`, `extensions(langs)`, синонимы) + по модулю на язык (`python.py`, `typescript.py`,
`csharp.py`). Модуль языка отдаёт: `NAME`, `EXTENSIONS`, `ALIASES`, `DECORATORS`, `declared(...)`,
хуки `extra_target_names(...)` и `reexport_signature(...)` (по умолчанию — ничего). Штемпель
вызывает только реестр. Неизвестное расширение → явный отказ / пропуск, не python.

**Контракт** `stamp_langs/CONTRACT.md` (по `__HQ/guides/Guide__Contracts_candidate.md`): форма
dict'а `declared` (`docstring_first`, `exports[{name,kind,signature,methods}]`, `all_defs`,
`reexports`) и набор хуков. Довод: три производителя, форма устоялась, расхождение молчаливо
(пропущенный ключ → пустая секция карточки, не ошибка). C++ добавит поля (условие) поправкой.

**Готово, когда:** регресс = база (`check.py` 116, `test_cardstamp.py` 144, `run_restamp_fixtures.py`
21, `test_split_monster` ok, `test__replace_in_files` 15/21 старое + восстановить фикстуры), в
`make_interface_card.py` нет `lang ==`.

## Шаг 1 — фикстура `test/cppSRC/` · ✅ (+ цепочка `ggml-vulkan-{common,push-constants,types}.h`)

Файлы llama.cpp на `7fee17846` ЦЕЛИКОМ (не обрезаем), с настоящими папками, + `LICENSE` (MIT):
`ggml/include/{ggml,ggml-backend,ggml-cuda,ggml-vulkan}.h`, `ggml/src/ggml-backend-impl.h`,
`ggml/src/ggml-backend-reg.cpp`, `ggml/src/ggml-backend-dl.{h,cpp}`,
`ggml/src/ggml-cuda/ggml-cuda.cu`, `ggml/src/ggml-vulkan/ggml-vulkan.cpp`. Свой `CONFIG__TOOLS`-
фрагмент с `CPP_INCLUDE_DIRS` / `CPP_STRIP_MACROS` / `CPP_PAIRS`. `test/` не деплоится — размер ок.

## Шаги 2–8 · ✅ 2–8 (`eede1f6` + доводка), 9 — отложен (см. «Итог» ниже)

2. **include-рёбра:** `find_code_usage` handler + resolver для C++ (`#include "..."` = импорт;
   резолв: папка файла → `CPP_INCLUDE_DIRS`; `<...>` = внешнее); у ребра — условие из
   preproc-узлов tree-sitter.
3. **Public API заголовков:** `declarations()` для C++ в get_codeblock (tree-sitter), экспортные
   макросы вырезаются до разбора; запись `stamp_langs/cpp.py`.
4. **Пара `.h` ↔ `.c/.cpp/.cu`** — `implements`; тонкая карточка реализации.
5. **Условные зоны файла + подсказки швов** — `seam_scanner.PATTERNS["cpp"]` (таблицы функций,
   `dlopen`/`LoadLibrary`/`GetProcAddress`, регистрация); «непрозрачная зона» для макро-кода.
6. **Формат:** условие у ребра, новые `Kind` (`build-flag`, `vtable`, `registry`, `dlopen`), бамп
   `CARD_FORMAT.VERSION`; граф — фильтр `--flags`.
7. **Зона:** `--all --path` / `STAMP_DIRS`; рёбра наружу резолвятся по всему корню; обратный скан
   всего дерева → «кем включается / кто регистрирует, вне зоны».
8. **Приёмка на живом `llama.cpp_mix`** (выборочно, карточки в `__HQ/__map`, исходники не трогаем).
9. *(опц.)* `compile_commands.json` → `live` / `dead` / `unknown`.

## Итог исполнения (2026-09-30)

| шаг | где | статус |
|---|---|---|
| 2 include-рёбра + условие | `find_code_usage/cpp_includes.py`, `handlers/cpp_handler.py`, `resolvers/cpp_resolver.py`; `ImportInfo.kind` → колонка Kind | ✅ |
| 3 Public API заголовков | `get_codeblock/handlers/cpp_treesitter.py` + `stamp_langs/cpp.py` | ✅ |
| 4 пара `.h`↔`.cpp/.cu` | `stamp_langs/cpp.py::_pair` (+ `CPP_PAIRS`), «defines what these headers declare» | ✅ |
| 5 зоны `#if` + швы | `## Build facts`, `seam_scanner.PATTERNS["cpp"]`, `opaque` | ✅ |
| 6 формат + граф | `CARD_FORMAT` 1.2.0 (`BUILD_FACTS_SECTION`, Kind `conditional(X)`, `\|` в ячейке, seam Kind `vtable`/`registry`); `graph_from_cards --flags`, `pair <->` | ✅ |
| 7 зона | `--all --path` / `STAMP_DIRS`; связи — по всему корню | ✅ |
| 8 приёмка на `llama.cpp_mix` | 37 карточек (ggml/include, слой бэкендов, vulkan, ядро cuda), validate 0 issues, штаб `dc32fba` | ✅ |
| 9 `compile_commands.json` | — | ⏸ отложен |

**Отклонения от плана/вижена (сознательные):**
- `#if`/`#include` — построчный скан директив, НЕ tree-sitter: директивы строковые по определению,
  так точнее, без грамматики и быстро (1445 файлов llama.cpp — 4 с). Tree-sitter — только для объявлений.
- Второй разбор объявлений: tree-sitter теряет весь файл, когда `#if/#else` рвёт скобки или
  X-макросы без `;` сидят в теле функции (`ggml-vulkan.cpp` с L1678). Решение: для сломанных
  диапазонов — повторный разбор текста «одна ветка на `#if` + пустые тела функций». Остаток — `opaque`.
- Новые ключи: `CPP_WRAPPER_MACROS` (`DEPRECATED(decl, "hint")`), `STAMP_DIRS`; `CPP_STRIP_MACROS`
  режет и вызов за именем (`X_ATTRIBUTE_FORMAT(1,2)`); CUDA-квалификаторы режутся всегда.
- Kind `build-flag` и `dlopen` НЕ введены: условное ребро уже выражено `conditional(X)` в deps,
  `dlopen` — это существующий `by-path`.
- Попутно исправлено: `find_code_usage` CLI держал свою таблицу расширений (без C++) → теперь
  спрашивает реестр обработчиков; `report` печатал только питоновские виды импорта.

**Шаг 9 отложен — почему:** граф ОДНОЙ сборки уже даёт `--flags` без всякой сборки; а
`compile_commands.json` требует CMake-генератор Ninja, сборки `mix` ещё нет (стабильная — VS, и её
не трогаем). Вернуться, когда появится сборка микса: `-D` каждого TU → `live/dead` у рёбер и зон.

## Чего НЕ делать

- Не добавлять C++ веткой `if` — только записью в реестр.
- Не писать прозу карточек (это Grok) и не резолвить `#ifdef` угадыванием.
- Не трогать исходники `llama.cpp_mix` и `y:\SRC\llama.cpp`.

— Опус5.5 (Claude Opus 5.5), 2026-09-30, по обсуждению с Натальей
