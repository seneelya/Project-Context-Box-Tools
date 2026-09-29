# Plan08 — C/C++ в штемпеле и графе (исполнение Vision09)

Замысел — `../vision/Vision09__cpp-stamp.md` (читать целиком). Первый C/C++-проект —
`y:\SRC\llama.cpp_mix` (upstream `7fee17846`). Согласовано с владельцем 2026-09-30.

## Главное правило плана: модульность, а не `if`

Язык подключается ЗАПИСЬЮ в реестр, а не новой веткой `if lang == ...` в штемпеле. C++ — четвёртая
запись, не четвёртая ветка. Поэтому шаг 0 — рефакторинг без C++.

## Шаг 0 — языковой реестр штемпеля + контракт

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

## Шаг 1 — фикстура `test/cppSRC/`

Файлы llama.cpp на `7fee17846` ЦЕЛИКОМ (не обрезаем), с настоящими папками, + `LICENSE` (MIT):
`ggml/include/{ggml,ggml-backend,ggml-cuda,ggml-vulkan}.h`, `ggml/src/ggml-backend-impl.h`,
`ggml/src/ggml-backend-reg.cpp`, `ggml/src/ggml-backend-dl.{h,cpp}`,
`ggml/src/ggml-cuda/ggml-cuda.cu`, `ggml/src/ggml-vulkan/ggml-vulkan.cpp`. Свой `CONFIG__TOOLS`-
фрагмент с `CPP_INCLUDE_DIRS` / `CPP_STRIP_MACROS` / `CPP_PAIRS`. `test/` не деплоится — размер ок.

## Шаги 2–8

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

## Чего НЕ делать

- Не добавлять C++ веткой `if` — только записью в реестр.
- Не писать прозу карточек (это Grok) и не резолвить `#ifdef` угадыванием.
- Не трогать исходники `llama.cpp_mix` и `y:\SRC\llama.cpp`.

— Опус5.5 (Claude Opus 5.5), 2026-09-30, по обсуждению с Натальей
