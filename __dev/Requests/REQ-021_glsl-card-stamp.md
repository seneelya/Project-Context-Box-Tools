# REQ-021 — штамп карточек для GLSL: шейдеры в карте кода и их связи с C++

## Зачем это нужно (контекст извне)

contact_lab (`T:\Agents\contact_lab`, 17 Nov 2026) — первый проект C++ + Vulkan на шаблоне. `make_interface_card --all`
с `LANGUAGE = "cpp"` проштамповал 63 файла `src/` и `include/`. 30 файлов GLSL в `shaders/` (17 `.comp` — точки входа,
13 `.glsl` — включаемые части) остались без карточек: их расширения не берёт ни один модуль `stamp_langs/`, файл
отвергается (exit 2). Парсер при этом уже есть: `get_codeblock` читает GLSL (колесо capsule1,
`get_codeblock/reader/profiles/glsl.py`), а `stamp_langs/glsl.py` нет.

В contact_lab шейдеры — половина тяжёлой работы. Каждую правку меряют временем компиляции драйвером. Правило «у тяжёлой
функции один вызов» требует знать, кто кого зовёт через дерево `#include`: компиляция `batch_step_op` выросла со 104 с
до 8–13 минут из-за 8 мест вызова одной функции, каждое — полная копия после инлайна.

## Что нашла (поведение сейчас)

* `make_interface_card --all --language all` в contact_lab: `.comp`/`.glsl` не выбираются, в карте их нет.
* `make_interface_card shaders/batch_pass.glsl` → отказ (exit 2): расширение не принадлежит ни одному языку.
* Связь «шейдер ↔ C++» в карточках C++ не видна: `src/gpu_context.cpp` включает `safety_screen_spv.h`, которого нет в
  дереве (он генерируется CMake при сборке), — в карточке это внешний include без смысла.

## Чего хочется

### 1. `stamp_langs/glsl.py` (форма 1 и 2 CONTRACT)

* `NAME = "glsl"`, `EXTENSIONS = (".comp", ".glsl", ".vert", ".frag", ".geom", ".tesc", ".tese")`.
* `declared()`: функции (сигнатуры), структуры, глобальные `const`, и интерфейс шейдера отдельными видами:
  * буферные блоки: `binding`, `std430`/`std140`, `readonly`/`writeonly`, имя блока, имя экземпляра, поля;
  * блок `push_constant` и его поля (и размер в байтах, где считается: хост обязан совпасть);
  * константы специализации (`layout(constant_id = N) const ...`);
  * `layout(local_size_x = ...)`;
  * `shared`-переменные.
* `all_defs`: все функции, чтобы карточка говорила, какие из них используют другие файлы.

### 2. Граф `#include` и вызовов GLSL

* `#include "x.glsl"` (GL_GOOGLE_include_directive) в обе стороны: карточка `.glsl` перечисляет, кто её включает
  (`batch.comp` → `batch_coast.glsl`, `batch_pass.glsl`, `batch_step.glsl`, …).
* Потребители функции: какие файлы её зовут, в пределах дерева одной точки входа, с числом мест вызова. Для
  contact_lab это главный факт: функция с двумя местами вызова компилируется дважды.
* Ветки препроцессора помечать, не разрешать, как в C++: `#if BATCH_OP == 0` (один `.comp` собирается трижды с
  `-DBATCH_OP=0/1/3`), `#ifdef`; константы специализации — тоже как условия.

### 3. Связь шейдера с хостом (необязательно, вторым шагом)

Шейдер не включается из C++, его компилирует и встраивает CMake, но факты лежат в файлах — их можно штамповать:

* CMake: `add_custom_command` с `glslc ... shaders/<src>.comp -o <name>.spv` и дефайнами (`-DBATCH_OP=1`), затем шаг
  встраивания, пишущий `<name>_spv.h` с массивом `<name>_spv` (contact_lab: цикл `foreach(shader ...)` в
  `CMakeLists.txt`).
* C++: файл, который включает `<name>_spv.h` и использует `<name>_spv` (contact_lab: `src/gpu_context.cpp`, номера
  конвейеров в `Context::prepare`).
* В карточке `.comp`: «собирается как `<name>` (дефайны), встроен в `<name>_spv.h`, используется в
  `src/gpu_context.cpp`». В карточке C++ — какие шейдеры он грузит. Достаточно настраиваемого правила (регэксп на
  команду CMake и имя встраивания) в `CONFIG__TOOLS`.

### 4. Не от штампа

Связи рантайма, которых нет ни в одном файле (какая CPU-функция — близнец GLSL-функции: `screen_core<float>` в
`src/safety_screen.cpp` и `main` в `shaders/safety_screen.comp`), вписываются в карточки руками по ходу работы. Помог
бы слот для них — `## Twins` (свободный текст), сохраняемый при перештамповке, как проза.

## Как проверить

Фикстуры: `test/secret/contact_lab_shaders/` (приватные, в `.gitignore`: код владельца, не публикуется) — настоящие шейдеры contact_lab без правок: замкнутое дерево `batch.comp`
(10 файлов) и отдельный `safety_screen.comp`; что в них искать — в `README.md` той папки.

* contact_lab: `LANGUAGE = ["cpp", "glsl"]`, `STAMP_DIRS = ["src", "include", "shaders"]`; `make_interface_card --all`
  штампует 30 файлов шейдеров без ошибок и отказов.
* Карточка `shaders/batch_pass.glsl`: `pass_point`, `pass_inside` и включающий её `batch.comp`. Карточка
  `shaders/safety_screen.comp`: шесть буферных блоков с binding, блок push (6 полей + `base`), `local_size_x = 64`.
* Карточка `shaders/batch_coast.glsl` называет вызовы тяжёлых функций (`bisect`, `solve_chi64`) с местами вызова.
* Карточки C++ не меняются (перештамповка сливает, проза сохраняется).

## Мелкое, найдено при первом деплое

* Деплой пишет файлы с LF, а git проекта (`core.autocrlf`) превращает их в CRLF при checkout. Проверить, узнаёт ли
  следующий деплой их как известные версии (UPDATE) или покажет CONFLICT.
* `CONFIG__TOOLS.py`: пример в комментарии `#   LANGUAGE = "python"` делает настоящую строку неуникальной для
  текстовой замены — ловушка для скриптов, правящих конфиг.

## Приоритет

Средний: карта C++ уже работает; без GLSL правка шейдеров идёт через `get_codeblock` и grep, как до шаблона.

## Результат — 2026-11-18, Opus (пункты 1–2; 3 и 4 — следующим шагом)

- `stamp_langs/glsl.py` + движок `find_code_usage/glsl_tree.py` (дерево `#include` = сканер C/C++ на
  расширениях GLSL, кэш `glsl_scan`; разбор файла — tree-sitter профиля get_codeblock), хэндлер и
  резолвер `find_code_usage`. Новый необязательный ключ `GLSL_INCLUDE_DIRS`. Поправок CONTRACT нет —
  хватило имеющихся хуков (`entry_key`, `import_line`, `fact_sections`, `source_edges`).
- **Единица компиляции** = точка входа (stage-файл или часть, которую никто не включает) + всё, что она
  включает. Потребители и места вызова считаются внутри единиц: `batch_coast.glsl` зовёт `pass_inside`,
  хотя не включает `batch_pass.glsl` — их обоих включает `batch.comp`.
- Public API: функции, блоки интерфейса (H3 Interfaces, поля списком), structs, спец-константы, `shared`.
  Глобальные `const` — не записи (в `batch_coast` их 142), а счёт по префиксам в фактах; и не потребители
  (иначе все уходили в «Consumed internals» с директивой — первая раскатка дала карточку в 788 строк).
- `## Shader facts`: стадия и `local_size`, `compiled in`, `included by`, размер push / std430-блока в
  байтах, `#if`-зоны (помечены, не разрешены), места вызова каждой функции по файлам и вызывающим
  функциям с метками `[if BATCH_OP == 1]` и `[spec kTrackPipeline]` / `[spec !kX]` (условие `if`/`&&`/`?:`
  на спец-константе), **копии от `main`** (места × копии вызывающих — каждая копия инлайнится; варианты
  `#if` вместе), вызовы в другие файлы единицы, «достаётся через эти вызовы» (с первым чужим шагом),
  предварительные объявления. Часть в 3+ единицах — одна строка на функцию: `×мест/копий` по единицам.
- Проверка «Как проверить» — все пункты (contact_lab, после деплоя): `--all` 93 файла → 30 новых
  карточек шейдеров, 63 C++ слиты без изменений (git чистый по `__map/src`, `__map/include`), 0 ошибок,
  5,6 с; `validate_cards` 93 clean; `graph_from_cards --file shaders/batch_pass.glsl` видит `batch.comp`.
  `batch_pass`: `pass_point`, `pass_inside`, включает `batch.comp`. `safety_screen`: 6 блоков с binding
  0–5, push `Params` 7 полей с `base`, 28 байт, `local_size_x = 64`. `batch_coast`: `bisect` ×1 в
  `scan_events`; `solve_chi64` ← `kepler64_shared.glsl` через `propagate64`; в карточке
  `kepler64_shared`: `solve_chi64` ×1, 40 копий от `main`.
- Мелкое: деплой узнаёт файлы, которые git проекта перевёл в CRLF, — 138 UPTODATE, новые версии
  UPDATE, не CONFLICT. Ловушка `#   LANGUAGE = "python"` в комментарии конфига — не тронута (решение
  владелицы).
- Тесты: `test/test_glsl_stamp.py` 50/0 (синтетика); приватная проверка REQ —
  `test/secret/contact_lab_shaders/check_req021.py` (в `.gitignore`). check 169/0, test_cardstamp 186/0,
  test_cpp 150/0, restamp 21/0, golden 16/16, name_resolver 55/0, views 57/0, test_glsl/test_glsl_env PASS.
- Не сделано: п.3 (CMake `glslc` → `<name>_spv.h` → C++), п.4 (слот `## Twins`).
