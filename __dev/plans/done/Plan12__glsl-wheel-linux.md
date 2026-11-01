# Plan12 — Linux-колесо GLSL (ТЗ для Gpt-Sol)

Исполнитель: Gpt-Sol. Поставлено владельцем 2026-11-01. Claude проверяет в конце и коммитит.
Возражения до начала — в `Plan12__KICKBACK.md`.

Основа: Plan11 закрыт коммитом `9f9c736` (get_codeblock 0.10.0, GLSL). Готово только колесо
Windows x64. Нужно такое же для Linux x86_64 — той же грамматики и той же правкой привязки.
Предыстория и рецепт сборки: `wheels/README.md`, `wheels/capsule1.patch`,
`__dev/review/GLSL_BUILD.md`, `__dev/plans/done/Plan10__glsl-grammar-wheel.md`.

## Решения (не переоткрывать)

- **L1. Та же грамматика и та же правка.** Коммит `3a00d49a88cb53eec519b49d8e234e77d916f8ac`
  (Caellian/tree-sitter-glsl), `capsule1.patch` без изменений; `parser.c`/`grammar.js` — те же
  SHA256, что у Windows-колеса (`build_manifest.json`). Версия `1.0.0+capsule1`.
- **L2. Наше колесо и на Linux**, хотя `OverflowError` там, вероятно, не возникает (`unsigned long`
  64-битный): `env_check` требует capsule на всех платформах, одна правка — одно поведение.
- **L3. Цель — `cp310-abi3-manylinux_2_17_x86_64` (manylinux2014)**: любой Linux x64 с glibc ≥ 2.17
  и CPython ≥ 3.10. Если abi3/manylinux2014 не выходит — записать почему и что получилось.
- **L4. Сборка в Docker** (Docker Desktop запущен), официальный образ `quay.io/pypa/manylinux2014_x86_64`
  (или cibuildwheel поверх него); `auditwheel repair`/`show` — подтвердить тег.
- **L5. Проверка в WSL Ubuntu** (запущена): отдельный venv, CPython ≥ 3.10, `tree-sitter==0.26.0`,
  колесо ставится точным путём. Те же критерии, что приняты для Windows (D1 Plan11 — индексный доступ
  к точкам).
- **L6. В `env_check`** — одна строка в таблицу `artifacts` записи `glsl`
  (`"linux-x86_64": "wheels/<имя колеса>"`). Ключ — то, что реально отдаёт
  `sysconfig.get_platform()` в WSL; проверить, не угадывать.
- **L7. ARM (aarch64) и macOS — не делаем.**

## Ограничения

- **Шейдеры PlanetWeather — личные, репо tools — публичный (MIT, GitHub).** В репо НЕ класть ни
  их копии, ни вырезки, ни JSON/логи с их текстом (baseline, результаты прогонов, `--query`-выводы).
  Всё это — только в `T:/AgentsWork/glsl-wheel-plan10/`. В отчётах — имена файлов, номера строк и
  числа, без цитат кода. В тестах репо — только фикстуры `test/glslSRC/` (там уже разрешённые).

- Эталонный Windows venv, Windows-колесо, Hermes и шейдеры PlanetWeather — не трогать (шейдеры —
  только чтение, из WSL через `/mnt/y/...`).
- Временные данные, кэши, Docker-тома с исходниками — на T: (из WSL — `/mnt/t/...`), не на C:.
  Образ Docker сам по себе живёт в хранилище Docker — это допустимо, записать его размер.
- Production-код get_codeblock — только строка L6 (+ тест к ней). Больше ничего.
- Не коммитить, не деплоить.

## Шаги

1. **Исходники:** как в `wheels/README.md` (fetch коммита L1, `git apply capsule1.patch`). Сверить
   SHA256 `parser.c`/`grammar.js` с `build_manifest.json`.
2. **Сборка в Docker** (L3/L4). Записать точные команды — копипаста для повтора. `auditwheel show`
   в отчёт.
3. **Проверка в WSL** (L5):
   - прямой `Language(module.language())` — capsule, без ctypes;
   - `glsl_wheel_accept.py --index-points` (если скрипт завязан на Windows-пути/`.pyd` — минимально
     обобщить: `.so`, пути; не менять смысл проверок) — 22 файла × 20 процессов + минимальный повтор
     × 20, всё зелёное, совпадение с baseline
     `T:/AgentsWork/glsl-wheel-plan10/review-archive/glsl_probe_results_runtime25_2026-11-01.json` (функции,
     диапазоны, ERROR/MISSING, счётчики). Если байты шейдеров при чтении из WSL разошлись (CRLF и
     т. п.) — сначала сверить SHA256 с baseline и объяснить;
   - сам get_codeblock из WSL по рабочей копии tools (`/mnt/t/...`): `test/test_glsl.py` по
     `test/glslSRC` и по 22 шейдерам (`--shaders … --baseline …`) — PASS; `--outline`/`--name` на `cover-map.fs` выглядят как на
     Windows (сравнить вывод с Windows-прогоном, отличия перечислить и объяснить);
   - контроль дефекта: `.row` на 0.26.0 в Linux — воспроизводится ли (ожидаем «да», правило
     индекса этим не меняется; просто записать факт).
4. **env_check** (L6) + в `test/test_glsl_env.py` случай «linux-x86_64 → команда с Linux-колесом»
   (подмена `sysconfig.get_platform`, как уже сделано для «другой платформы»); прежний случай
   «нет колеса для платформы» перевести на платформу без колеса (например, `macosx-…`/`linux-aarch64`).
   Из WSL — реальный прогон D7: модуля нет → команда указывает на Linux-колесо.
5. **Документация:** `wheels/README.md` (строка колеса, команды сборки, `auditwheel`, SHA256),
   `get_codeblock__TLDR.md` и `get_codeblock__README.md` (готовые колёса: Windows x64, Linux x86_64),
   `__dev/CONTEXT_RESTORE.md` (где колёса), строка в `__dev/TRACKER.md`.
6. **Регресс на Windows** эталонным Python: всё из `__dev/CONTEXT_RESTORE.md` «Regression» —
   числа прежние (+ новый случай env-теста).

## Что сдать

- Колесо `wheels/tree_sitter_glsl_spec-1.0.0+capsule1-cp310-abi3-manylinux_2_17_x86_64…whl`
  (точное имя — как выдаст `auditwheel`).
- Правки шагов 4–5 в рабочей копии tools, без коммита.
- `__dev/review/GLSL_LINUX.md` — отчёт: сборка (команды, образ, размер), `auditwheel show`, таблица
  приёмки, сравнение вывода Windows/Linux, D7 из WSL, регресс. Сырые JSON прогонов — НЕ в репо, а в
  `T:/AgentsWork/glsl-wheel-plan10/` (в репо — только итог, если он маленький, ≤ 100 КБ).

## Готово, когда

- Колесо собрано из L1 с теми же хэшами `parser.c`/`grammar.js`; тег manylinux подтверждён `auditwheel`.
- WSL: приёмка 480/480 (+ минимальный повтор), совпадение с baseline, `test_glsl.py` PASS на
  фикстурах и 22 шейдерах, D7 даёт команду с Linux-колесом.
- Windows-регресс прежний; Windows-колесо и эталонный venv не тронуты; ничего не закоммичено.
