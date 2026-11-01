# GLSL_INTEGRATION — Plan11, Sol, 2026-11-01

> JSON прогонов (эталон `glsl_probe_results_runtime25_2026-11-01.json`, `glsl_integration_results.json` и прочие) — вне репо, в `T:/AgentsWork/glsl-wheel-plan10/review-archive/`: в них текст личных шейдеров владелицы. Фикстура `cloud-layer-main.fs` заменена синтетической `preproc-split.fs`.

Plan11 выполнен в рабочей копии tools; **без коммита, push и деплоя**.
get_codeblock VERSION **0.10.0**. Следующий шаг — ревью и коммит Claude, затем
разрешённая синхронизация vendor. Исходный checkpoint: f88fb17.

## Шаг 0 — принятое колесо и Plan10

В T:/AgentsWork/venv установлено tree-sitter-glsl-spec **1.0.0+capsule1**,
рабочий tree-sitter остался **0.26.0**, Python **3.12.10 Windows x64**.
SHA256 установленного _binding.pyd:
`53282c3421928a144513a02671534713d8c5b8558ed2c578e85ad72caf763e8b`.
Wheel SHA256: `6c18b83d121fa32da65c45e86c670d53e9ad4bf8793cbc59235d924c8193ba2a`.
Источник и parser.c не менялись относительно capsule1 Plan10.

Повтор glsl_wheel_accept.py --index-points **без PYTHONPATH**, с --grammar-root
T:/AgentsWork/venv/Lib/site-packages: **480/480, exit 0**. Worker-папка:
T:/AgentsWork/glsl-wheel-plan10/accept-installed-plan11. Результат сохранён отдельно:
glsl_probe_results_runtime26_installed_plan11.json; исторические результаты не перезаписаны.

В wheels оставлено одно основное колесо + README, patch, manifest, build command.
Три диагностических колеса удалены только из tools, копии остались в build-root/dist.
Оба Plan10-файла перенесены в __dev/plans/done; основной план помечен закрытым по D1.
README обновлён; прежний отрицательный вердикт GLSL_BUILD явно помечен историческим.

## Шаг 1 — Point guard

CONTRACT, инвариант 11: координаты tree-sitter только через индекс. Решения D2–D4
записаны в DECISIONS. test/point_guard.py вызывается из check.py и сканирует Python-код
tools, исключая __dev (намеренные исторические пробы), Git, venv и pycache.
Временный test/_point_guard_injection.py с двумя небезопасными обращениями дал
оба ожидаемых нарушения (строки 1/2); файл удалён в finally, повтор сканирования чист.

## Шаги 2–3 — профиль, обвязка, нормализация

Добавлен reader/profiles/glsl.py; все девять расширений D4 зарегистрированы в
profiles, _LANG_MAP и _BRACE_EXTS. Обвязка: stub handler, // metadata comments,
данные env_check, комментарий в requirements (платформенного бинарника там нет).
Общие LangSpec handlers не менялись. В classify/рендерах и адресном движке нет
веток if lang == glsl.

Имеющихся LangSpec-наборов недостаточно: frame сохраняет отдельную строку и не
раскрывает statement_list как детей brace-тела; body_types ошибочно сделали бы
statement_list телом, начинающимся после `{`. Добавлен **один общий необязательный
шов TSProfile.node_rules → TSBackend/TSNode**, по умолчанию пустой. Все потребители
получают одно нормализованное RNode-дерево. Правила описаны в CONTRACT:

- statement_list, declarator_list, field_declarator_list и оболочки type раскрываются;
  безымянный declarator вокруг struct раскрывается только при отсутствии поля name;
- декларация с field_declaration_list получает semantic type interface_block;
- field fallback предоставляет declarator для общих механизмов имён;
- списки полей struct/interface получают строки начала/конца родителя, включая скобки:
  сырая грамматика держит в списке только поля. Иначе карта показывала struct до `}`,
  а адресация обрывалась на последнем поле;
- preproc_def/preproc_function_def с исключающим концом на следующей строке обрезаются
  по последней содержательной строке; #define не захватывает начало следующей функции;
- хвостовой комментарий после кода не образует самостоятельного структурного ребёнка:
  он целиком остаётся в физической строке владельца, query/API. Это предотвращает
  приклейку комментария предыдущей функции к следующей и отдельный filler на строке
  открытия функции. Отдельные строки комментариев сохраняются как преамбулы;
- declarator-типы используются для подписей всех имён в общей полосе; общий resolver
  перечисляет каждое имя в мульти-декларации как отдельный Decl с общим диапазоном.

Пустые node_rules используют прежний путь children/filler_label. Подтверждена
неизменность вывода остальных языков (ниже). Профиль сохраняет все ветки препроцессора,
ERROR/MISSING не удаляются. Макросы, #version и layout не препроцессируются/не маскируются.

## Шаг 4 — фикстуры и весь PlanetWeather

test/glslSRC (после ревью Claude, 2026-11-01): ВСЕ фикстуры синтетические — шейдеры
PlanetWeather личные, а репо публичный. Копии Sol (cover-map.fs, sim-step.fs, cover-map.vs,
вырезка cloud-layer-main.fs) заменены на noise-field.fs, particles.fs, quad.vs,
preproc-split.fs с теми же конструкциями (однострочные функции, преамбула, #ifdef в if/else
с MISSING #endif, ERROR в цикле, layout/struct, вершинный шейдер). Числа ниже про локальные
фикстуры относятся к исходному набору Sol; текущий — 5 файлов / 178 строк / 21 функция.
Небольшая declarations.glsl независимо проверяет uniform, const multi-declarator,
struct/interface, #define и преамбулу функции. README фиксирует происхождение.

expected.py: OUTLINE/LADDER и FOCUS_OUTLINE с ручными диапазонами. В частности,
первая функция фикстуры: expression_statement 8–9, return_statement 10 — statement_list раскрыт.
Golden: glsl_outline/glsl_ladder записаны и просмотрены. test_name_resolver: функция,
uniform, структура, интерфейс, оба имени multi-declarator и пять реальных CLI --name.

Все 22 файла сверены с SHA256 baseline; **348 сырых функций**: start/end и сохранённые
220 символов сигнатуры/текста полностью совпали с runtime25 baseline. Baseline именно
ограничивает text 220 символами; полный исходник не подменялся обрезанным текстом.
Для **каждой из 4464 физических строк**, включая пустые: непустая лестница, каждый
rung содержит строку (#7), query соответствует точным исходным строкам. Каждый
покрывающий строку landmark карты присутствует в лестнице с тем же публичным
диапазоном (#6). Для каждой функции реальный subprocess CLI сравнил текст и диапазон
--name NAME --force и --line SIGNATURE --query --force; все **348/348** равны.
Публичный диапазон найден в карте (landmark или легитимный filler на той же строке).
Не вводилось особого разрешения перегрузок: в этом наборе точные имена однозначны.

D9: функция с комментарием-преамбулой начинается в публичном блоке с комментария 41 (сырая функция 42–47).
Однострочная функция без --force сохраняет авто-эскалацию и её видимую пометку;
с --force остаётся узкий блок. На однострочной функции возможен filler той же
физической строки, если комментарий-преамбула делает landmark шире: это прежние
правила публичной адресации, не сравнение с сырым AST по ошибке.

| Файл | Физ. строк | Сырых функций | ERROR/MISSING | Все проверки |
|---|---:|---:|---:|---|
| cloud-copy.fs | 15 | 4 | 0 | PASS |
| cloud-copy.vs | 5 | 1 | 0 | PASS |
| cloud-layer.fs | 1532 | 101 | 4 | PASS |
| cloud-layer.vs | 6 | 1 | 0 | PASS |
| cloud-near.fs | 1097 | 61 | 4 | PASS |
| cloud-near.vs | 7 | 1 | 0 | PASS |
| color-map.fs | 257 | 25 | 1 | PASS |
| color-map.vs | 6 | 1 | 0 | PASS |
| cover-map.fs | 256 | 25 | 1 | PASS |
| cover-map.vs | 5 | 1 | 0 | PASS |
| lut-transmittance.fs | 68 | 7 | 0 | PASS |
| lut-transmittance.vs | 8 | 1 | 0 | PASS |
| noise-bake.fs | 100 | 16 | 0 | PASS |
| noise-bake.vs | 5 | 1 | 0 | PASS |
| planet-air.fs | 432 | 34 | 0 | PASS |
| planet-air.vs | 8 | 1 | 0 | PASS |
| planet-bake.fs | 48 | 8 | 0 | PASS |
| planet-bake.vs | 8 | 1 | 0 | PASS |
| planet-ground.fs | 437 | 34 | 0 | PASS |
| planet-ground.vs | 8 | 1 | 0 | PASS |
| sim-step.fs | 151 | 22 | 0 | PASS |
| sim-step.vs | 5 | 1 | 0 | PASS |

Машиночитаемый результат: glsl_integration_results.json, включая SHA256 и результат
query каждой физической строки ERROR-зон. Локальные фикстуры: **5 файлов / 855 строк /
50 функций PASS** (README не считается шейдером). Их sweep с query: HIGH=0, LOW=0.

### Честное восстановление в ERROR/MISSING

- cover-map.fs: MISSING #endif в конце main; строка 256 → main **182–256**.
- color-map.fs: аналогичная строка 257 → main **183–257**.
- cloud-layer.fs: ERROR-зона **1479–1532** (вложенный ERROR на 1504 и MISSING на EOF).
  54 реальные строки проверены; 33 возвращают широкий содержащий фрагмент **1475–1532**,
  остальные — реальные более узкие блоки **1479–1482, 1485–1488, 1491–1494, 1497–1500,
  1516–1520**. Широкий фрагмент — содержащий for_statement,
  чьё тело грамматика при ERROR-recovery протянула до конца main,
  обе исходные ветки сохранены. Все его границы проверены на реальном тексте.
- cloud-near.fs: соответствующая ERROR-зона **1044–1097**, 54 строки; 33 получают
  **1040–1097**, прочие **1044–1047, 1050–1053, 1056–1059, 1062–1065, 1081–1085**.

Во всех случаях диапазон содержит запрос и сохранённый исходник, соседняя функция
не подставляется. MISSING на EOF не создаёт дополнительной физической строки.
Уточнённая вложенность в этих зонах не обещается; ERROR/MISSING остаются видны при
анализе грамматики, ветвь не выбирается и код не удаляется.

Отдельный sweep всех шейдеров --check-query: **22 файла / 4258 непустых line-probes**,
HIGH CONTAIN=0 RANGE=0 CRASH=0 OPEN=0 QUERY=0; INFO SIBLING=6.
LOW LEVEL=2: cloud-layer.fs:160 и cloud-near.fs:161 — однострочная функция и её
однострочный if на том же физическом уровне. Диапазоны/текст честны; общий механизм
уровней ради GLSL не менялся. Это косметическое ограничение, не скрытый HIGH.

### D7 — чистый отказ

Проверено test_glsl_env.py, отдельные процессы -S, временный каталог на T: с отдельной
копией runtime; эталонный venv не менялся. Для старого binding действительно установлен
upstream 1.0.0 через pip --target T:/AgentsWork/glsl-wheel-plan10/upstream-plan11.

1. Нет grammar module, cwd вне tools: exit 1, без traceback, абсолютный путь поставляемого
   колеса и текущий Python, --force-reinstall --no-deps.
2. Настоящий upstream 1.0.0 возвращает int: чистое incompatible installed build,
   та же корректная команда; до Language(int) выполнение не доходит, ctypes нет.
3. sysconfig platform подменён на linux-x86_64 только внутри теста: честное отсутствие
   готового колеса, путь к wheels/README.md, заведомо неверной pip-команды нет.

Сообщения всех прежних языков сравнены с модулем до изменений при одинаковом
requirements path и полностью совпали. Обычный тест без --upstream использует
изолированную минимальную legacy-binding фикстуру и также проходит.

## Шаг 5 — регресс и old/new

Эталонный Python, без пропущенных грамматик:

| Проверка | Результат |
|---|---|
| check.py --fails | **150 passed, 0 failed** |
| test_cardstamp.py | **160 passed, 0 failed** |
| run_restamp_fixtures.py | **21 passed, 0 failed** |
| golden_check.py | **16/16** |
| test_cpp.py | **150 passed, 0 failed** |
| test_name_resolver.py | **55 passed, 0 failed** |
| test_views.py | **57 passed, 0 failed** |
| sweep_invariants.py --quiet | **151 файлов / 52709 probes**, CONTAIN=RANGE=OPEN=QUERY=0; известный CRASH=71, LOW LEVEL=5 |

Общий sweep честно возвращает exit 1 из-за документированного старого cp1252-кейса;
это НЕ названо зелёным exit 0. Остаток тот же, что описан в CONTEXT_RESTORE, новых
GLSL HIGH нет. Логи: T:/AgentsWork/glsl-wheel-plan10/regression-plan11.
При первом чтении старого cp1252-лога C++ драйвер упал на декодировании UTF-8;
сам C++ тест был 150/0. Чтение логов исправлено, C++/оставшийся хвост повторены,
коды возврата записаны отдельно. Ничьи тестовые фикстуры ради зелени не исправлялись.

До правок сохранён git archive f88fb17 в T:/AgentsWork/glsl-wheel-plan10/tools-before-plan11.
Сравнение stdout/stderr/exit байт-в-байт: **222 файла / 666 сравнений / 0 отличий**.
118 прежних файлов-фикстур test/ + **104 C/C++/CUDA файла всей настроенной зоны
STAMP_DIRS Y:/SRC/llama.cpp_mix**, не случайная выборка. На каждом: --outline, --dot,
--line 1,MIDDLE,LAST --query --force. Полный JSON: glsl_other_languages_comparison.json;
исходный manifest и сохранённый snapshot — T:/AgentsWork/glsl-wheel-plan10/compare-plan11.

## Шаг 6 — Hermes без деплоя

vendor/sync_get_codeblock.py прочитан; запущен только **--check --src <tools>**.
Exit 1, перечисляет 12 отличающихся tracked файлов. Уточнение фактической реализации sync: `git ls-files` берёт перечень tracked
путей, но filecmp сравнивает их содержимое в рабочей копии. Обычный sync запрещает
грязный source и привязывает результат к HEAD; --check это ограничение обходит и
ничего не пишет. Нового untracked glsl.py в перечне пока нет, поэтому --check не
является полной проверкой будущей GLSL-поставки. Ничего не копировалось. Рабочий sync отложен
до ревью/коммита Claude и разрешённого распространения.

file_ops/read_file__get_codeblock_help.txt прочитан: список поддержанных расширений
пока не содержит GLSL. После доставки профиля и установки колеса в выбранный владельцем
Python туда нужна строка .glsl .vert .frag .geom .comp .tesc .tese .vs .fs и ссылка на
отдельную установку колеса. Внешний репозиторий и его Python не менялись.
Сам vendor sync копирует get_codeblock + LICENSE/NOTICE и **не доставляет wheels/**.
Перед будущим распространением в Hermes отдельно нужен внешний wheel и корректное
расположение wheels относительно пакета (env_check считает корнем родителя
get_codeblock), либо установка выбранным владельцем Python по пути из tools.
Это не выполнялось: текущий план запрещает доставку/установку в Hermes.
Y:/Hermess, gateway и службы не тронуты.

## Шаг 7 — документация и передача

Обновлены TLDR, README Supported Languages, TOOLS, CONTRACT, DECISIONS,
CONTEXT_RESTORE (State + wheel distribution), Sol journal, wheels README и tracker.
VERSION изменён один раз в конце на 0.10.0. Финальный git diff --check чист;
Python syntax проверен без генерации pycache. Все новые временные данные и caches
на T:, C: не использовался как временный диск.

Plan11 оставлен активным до финального ревью; Plan10 закрыт. Не входят и не делались:
GLSL в штемпеле/find_code_usage/split_monster, другие shader-языки, Linux/macOS wheels,
установка/рестарт/деплой Hermes. Коммита реализации нет.

## Воспроизведение

Из tools, после установки capsule1 по wheels/README.md:

```powershell
$env:TEMP = 'T:/AgentsWork/glsl-wheel-plan10/tmp'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = 'T:/AgentsWork/glsl-wheel-plan10/pip-cache'
$env:PYTHONDONTWRITEBYTECODE = '1'
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
$py = 'T:/AgentsWork/venv/Scripts/python.exe'
& $py -B test/check.py --fails
& $py -B test/test_glsl.py
& $py -B test/test_glsl_env.py --upstream T:/AgentsWork/glsl-wheel-plan10/upstream-plan11 --before T:/AgentsWork/glsl-wheel-plan10/tools-before-plan11
& $py -B test/test_glsl.py --shaders Y:/AgentsWork/PlanetWeather/viewer_layered/export/shaders --out __dev/review/glsl_integration_results.json
& $py -B test/sweep_invariants.py Y:/AgentsWork/PlanetWeather/viewer_layered/export/shaders --quiet --check-query
```

Полная установка/приёмка wheel и baseline — в CONTEXT_RESTORE_SOL.md и GLSL_BUILD.md;
исторические JSON не перезаписывать.
