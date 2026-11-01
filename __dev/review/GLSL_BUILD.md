# GLSL_BUILD — Plan10, 2026-11-01

> JSON прогонов (эталон `glsl_probe_results_runtime25_2026-11-01.json`, `glsl_integration_results.json` и прочие) — вне репо, в `T:/AgentsWork/glsl-wheel-plan10/review-archive/`: в них текст личных шейдеров владелицы. Фикстура `cloud-layer-main.fs` заменена синтетической `preproc-split.fs`.

> **Позднейшее решение Plan11 D1:** capsule1 принят с индексным доступом Point.
> Колесо установлено в эталонный venv; повтор без PYTHONPATH — 480/480.
> Интеграция и актуальный статус: [GLSL_INTEGRATION.md](GLSL_INTEGRATION.md).
> Ниже сохранён исторический вердикт исходной `.row`-приёмки Plan10.

**Вердикт: колесо собрано, но исходная строгая приёмка Plan10 НЕ пройдена.
В эталонный venv НЕ установлено.** Выявлен дефект Python API самого tree-sitter 0.26.0:
свойства Point.row/Point.column неверно передают владение ссылкой на Python-число.
При индексном доступе к координатам основное колесо прошло отдельный диагностический
прогон 480/480, полностью совпав с baseline. Это НЕ подмена проваленной исходной приёмки.

## Что собрано и где

- Исходники/сборки/кэши/worker-файлы: `T:/AgentsWork/glsl-wheel-plan10`.
- TEMP/TMP/PIP_CACHE_DIR, npm-cache, изолированные grammar/runtime/build-deps — на T:.
  C: использован только для чтения установленного MSVC/SDK/Node; новые сборочные
  временные данные на C: не размещались. npm registry вернул EACCES; npm остановлен,
  официальный CLI скачан с GitHub непосредственно на T:.
- Основной источник: https://github.com/Caellian/tree-sitter-glsl,
  commit `3a00d49a88cb53eec519b49d8e234e77d916f8ac`, 2026-04-07T15:43:13+02:00.
  Коммит не входит в обычную ветку клона, получен явным `git fetch origin <sha>`.
- `.github/workflows/publish-pypi.yml` подтверждает установку версии из workflow input
  и сборку cibuildwheel. Исходный pyproject содержит 0.0.0-dev — локальная версия
  1.0.0+capsule1 задаётся аналогично recipe публикации.
- Компилятор: MSVC 14.39.33519, x64, VS 2022 Community; окружение через указанный
  владельцем `vcvars64.bat` в том же cmd-процессе. Python 3.12.10, Windows AMD64.
- Wheel: `cp310-abi3-win_amd64`, Py_LIMITED_API=0x030A0000, Requires-Python >=3.10.
  Проверена Python 3.12.10; совместимость иных Python по тегу не выдаётся за live-тест.
- `parser.c`/`grammar.js` основной сборки не изменены; diff — только binding/упаковка.
  Основной ABI 15. В шапке parser.c версия генератора не указана; package-lock фиксирует
  CLI 0.26.8. Регенерация CLI 0.27.1 / ABI 15 дала ИДЕНТИЧНЫЙ parser.c.
- Результирующие wheels, полный diff, команды и SHA256: `../../wheels/README.md`,
  `../../wheels/build_manifest.json`, `../../wheels/capsule1.patch`.

## Причина сбоев: минимизировано до Point, без GLSL и без парсера

`glsl_point_probe.py` создаёт Point(100000, 200000), сохраняет его элемент через
индекс, измеряет sys.getrefcount до/во время/после чтения свойства и удаления
временной переменной. Большие числа выбраны вне кеша малых целых CPython.

| Runtime | Доступ | Изменение счётчика при чтении / после del |
|---|---|---|
| 0.25.2 | .row | +1 / 0 — корректно |
| 0.26.0 | .row | 0 / -1 — некорректно |
| 0.26.0 | .column | 0 / -1 — некорректно |
| 0.26.0 | [0] | +1 / 0 — корректно |

В [исходнике py-tree-sitter v0.26.0 point.c](https://github.com/tree-sitter/py-tree-sitter/blob/v0.26.0/tree_sitter/binding/point.c)
getters point_get_row/point_get_column возвращают PyTuple_GetItem (borrowed reference),
хотя Python getter должен возвращать новую ссылку. Это объясняет преждевременное
освобождение объектов чисел, повреждённые координаты и плавающие access violations
при последующем обходе/JSON-сериализации. Наблюдаемая первичная ошибка сведена до
нескольких строк без файла шейдера — дальнейшее уменьшение cloud-layer не требуется
для доказательства этого дефекта. Минимальный тест фиксирует потерю ссылки, а не
полагается на обязательный немедленный segfault.

**Уточнение предыдущего исследования GLSL_PROBE:** его вспомогательный код читает
`.start_point.row`/`.column`, поэтому нативные падения с ctypes-мостом не доказывали
поломку самой грамматики. Прямой индексный обход исправленного wheel на 0.26 стабилен
в пределах выполненного набора. Production-get_codeblock уже читает start/end_point[0]
(reader/backends/treesitter.py и brace handlers); прямых start/end_point.row/column
в get_codeblock поиском не найдено. Это обнадёживает, но интеграция GLSL не выполнялась.

Первоначальный OverflowError — ДРУГАЯ ошибка: PyLong_FromVoidPtr у GLSL wheel и
PyLong_AsUnsignedLong в runtime на Windows x64. PyCapsule исправляет именно её.
Исправленная C-привязка здесь работает без ctypes; размер исходного ABI не причина
дефекта Point, что подтверждено контрольными ABI 14/15 и независимым Point-тестом.

## Приёмочный runner и подтверждение окружения

`glsl_wheel_accept.py` запускает каждый повтор отдельным процессом с faulthandler,
таймаутом 45 с. Проверяет Python executable/version/architecture, runtime version/path,
пути обоих binary modules, SHA256 grammar binary и его локальную версию, PyCapsule.
Проверяет TEMP/TMP под сборочным T:-корнем, убирает диагностические runtime overrides.
Перед разбором пишет env-json, который остаётся даже при нативном падении; все env-данные
включены в итоговый отчёт. Ошибка/падение/таймаут/разница baseline → exit 1 родителя.
Выводы сохраняются по явным путям, существующие отчёты runner не перезаписывает.

Основной binary в target и внутри wheel:
`53282c3421928a144513a02671534713d8c5b8558ed2c578e85ad72caf763e8b`.
Рабочий runtime binary:
`308ae28f960129b14bcd18f4b33c57fd994ea21b18c1724904b63ee2bc7e059c`.
Все workers основного прогона загрузили новый GLSL из `T:/AgentsWork/glsl-wheel-plan10/glsl-test`
и runtime 0.26.0 из эталонного venv. Диагностический `--index-points` явно помечен
в configuration JSON, изменяет только доступ к координатам; основной результат не затёрт.

## Сравнение с baseline

Исторический baseline не содержит hashes шейдеров. Поэтому снят свежий baseline
0.25.2 на текущих байтах, с исходным опубликованным wheel 1.0.0, в отдельный
`glsl_probe_results_runtime25_2026-11-01.json` (22/22). Дополнительно сопоставлены
с историческим baseline имена файлов, счётчики, диапазоны функций, типы и строки
ERROR/MISSING: различий нет. Старый файл не изменён.

Отдельный индексный прогон wheel 1.0.0+capsule1 на 0.26 совпал со свежим baseline
по каждому из 22×20 результатов: SHA256 файла, counts, 348 функций и их диапазоны/
фрагменты, ERROR/MISSING с координатами/byte ranges, total_nodes и has_error.
Все старые 10 ERROR/MISSING в 4 файлах сохранены; это ожидаемая часть baseline,
а не признак провала этой проверки. Новый профиль и обработка этих ошибок вне Plan10.

## Основной прогон: файл × повторы × результат

Нативный сбой = exit 0xC0000005. «Python» — exit 1 worker; «Разница» — worker exit 0,
но данные расходятся с baseline. Таким образом, exit 0 worker не принимается за PASS.

| Файл | Повторов | PASS (.row) | Нативных сбоев | Таймаутов | Python | Разница | Индексный PASS |
|---|---:|---:|---:|---:|---:|---:|---:|
| cloud-copy.fs | 20 | 20 | 0 | 0 | 0 | 0 | 20/20 |
| cloud-copy.vs | 20 | 20 | 0 | 0 | 0 | 0 | 20/20 |
| cloud-layer.fs | 20 | 0 | 15 | 0 | 0 | 5 | 20/20 |
| cloud-layer.vs | 20 | 20 | 0 | 0 | 0 | 0 | 20/20 |
| cloud-near.fs | 20 | 0 | 11 | 0 | 0 | 9 | 20/20 |
| cloud-near.vs | 20 | 20 | 0 | 0 | 0 | 0 | 20/20 |
| color-map.fs | 20 | 20 | 0 | 0 | 0 | 0 | 20/20 |
| color-map.vs | 20 | 20 | 0 | 0 | 0 | 0 | 20/20 |
| cover-map.fs | 20 | 20 | 0 | 0 | 0 | 0 | 20/20 |
| cover-map.vs | 20 | 20 | 0 | 0 | 0 | 0 | 20/20 |
| lut-transmittance.fs | 20 | 20 | 0 | 0 | 0 | 0 | 20/20 |
| lut-transmittance.vs | 20 | 20 | 0 | 0 | 0 | 0 | 20/20 |
| noise-bake.fs | 20 | 20 | 0 | 0 | 0 | 0 | 20/20 |
| noise-bake.vs | 20 | 20 | 0 | 0 | 0 | 0 | 20/20 |
| planet-air.fs | 20 | 0 | 20 | 0 | 0 | 0 | 20/20 |
| planet-air.vs | 20 | 20 | 0 | 0 | 0 | 0 | 20/20 |
| planet-bake.fs | 20 | 20 | 0 | 0 | 0 | 0 | 20/20 |
| planet-bake.vs | 20 | 20 | 0 | 0 | 0 | 0 | 20/20 |
| planet-ground.fs | 20 | 0 | 20 | 0 | 0 | 0 | 20/20 |
| planet-ground.vs | 20 | 20 | 0 | 0 | 0 | 0 | 20/20 |
| sim-step.fs | 20 | 20 | 0 | 0 | 0 | 0 | 20/20 |
| sim-step.vs | 20 | 20 | 0 | 0 | 0 | 0 | 20/20 |

Минимальный исходный повтор cloud-layer: 20 процессов, PASS 0/20 (14 native crash,
6 Python errors), таймаутов 0. Индексный вариант того же повтора: PASS 20/20.
C++ контроль ggml-vulkan.cpp (881158 байт), 20 процессов: PASS 20/20 в обоих режимах.
C++-успех не исключал runtime-баг; минимальный Point-тест его локализовал напрямую.

## Варианты шага 5

| Вариант | Процессов | PASS | Native crash | Таймаутов | Python | Разница |
|---|---:|---:|---:|---:|---:|---:|
| capsule1 / .row | 480 | 380 | 80 | 0 | 6 | 14 |
| capsule1 / индексы | 480 | 480 | 0 | 0 | 0 | 0 |
| regen15 / .row | 460 | 360 | 65 | 0 | 7 | 28 |
| regen14 / .row | 460 | 360 | 75 | 0 | 5 | 20 |
| old capsule1 / .row | 460 | 380 | 49 | 0 | 0 | 31 |

Главный прогон и индексный включают по 20 C++-контролей; остальные три — по 460
(22×20 + минимальный×20), без повторного C++-контроля. Все проваленные исходные
прогоны runner завершили exit 1. Индексный — exit 0. Дополнительно 22/22 baseline
старой грамматики на 0.25.2 (`glsl_probe_results_old_runtime25_2026-11-01.json`).

Регенерация ABI 15 дала тот же parser.c; ABI 14 изменился, но runtime-сбой остался.
Старая грамматика собрана из v0.2.0 / e47b8b6 с тем же исправлением PyCapsule.
Её прогоны .row тоже ломаются. Данные повреждённых процессов не использовать
для заключений об изменении грамматики. Причина потери ссылок от ABI не зависит.

| Вариант | SHA256 parser.c | SHA256 grammar.js |
|---|---|---|
| capsule1 | `d8759daf83d69862a25417a98807b09b7ac32f15625706b839057e2df3d898e6` | `fd517076cfac59fc52bb07ae45f1495cba2a1d831ad8660ff67c90a43128fbe5` |
| regen15 | `d8759daf83d69862a25417a98807b09b7ac32f15625706b839057e2df3d898e6` | `fd517076cfac59fc52bb07ae45f1495cba2a1d831ad8660ff67c90a43128fbe5` |
| regen14 | `4e357d2a9978c951f7cb408d78199cd448944ee8e43ea7e9e6470155c1bd3b38` | `fd517076cfac59fc52bb07ae45f1495cba2a1d831ad8660ff67c90a43128fbe5` |
| old-capsule1 | `a175dc73eab717b1b745a6d1826ac1ddef1a46c72dc174f07ec721ac1f32e9ad` | `8e4348daa59e73aab734a074b66bb84808629bdd38dbb2bb8ed27faf32ff75a6` |

## Воспроизведение после сборки (из корня tools)

Все команды запускаются с TEMP/TMP на T:, PYTHONDONTWRITEBYTECODE=1;
полная подготовка и сборка — в wheels/README.md.

```powershell
$env:TEMP = 'T:\AgentsWork\glsl-wheel-plan10\tmp'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = 'T:\AgentsWork\glsl-wheel-plan10\pip-cache'
$env:PYTHONDONTWRITEBYTECODE = '1'
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
Remove-Item Env:GLSL_PROBE_RUNTIME -ErrorAction SilentlyContinue
$py = 'T:/AgentsWork/venv/Scripts/python.exe'
& $py -B __dev/review/glsl_point_probe.py row
& $py -B __dev/review/glsl_point_probe.py column
& $py -B __dev/review/glsl_point_probe.py index
# Новые пути результатов и work-dir: runner отказывается перезаписывать существующие.
& $py -B __dev/review/glsl_wheel_accept.py --baseline __dev/review/glsl_probe_results_runtime25_2026-11-01.json --work-dir T:/AgentsWork/glsl-wheel-plan10/accept-repeat --out T:/AgentsWork/glsl-wheel-plan10/repeat.json --cpp test/cppSRC/ggml/src/ggml-vulkan/ggml-vulkan.cpp
# Отдельный диагностический режим, не исходная приёмка:
& $py -B __dev/review/glsl_wheel_accept.py --index-points --baseline __dev/review/glsl_probe_results_runtime25_2026-11-01.json --work-dir T:/AgentsWork/glsl-wheel-plan10/index-repeat --out T:/AgentsWork/glsl-wheel-plan10/index-repeat.json --cpp test/cppSRC/ggml/src/ggml-vulkan/ggml-vulkan.cpp
```

Для regen15/regen14 добавить `--grammar-root T:/AgentsWork/glsl-wheel-plan10/test-regen15`
(или test-regen14), `--grammar-version 1.0.0+regen15` (или +regen14), отдельные work-dir/out.
Контроль старой: root test-old, `--grammar-module tree_sitter_glsl --grammar-package tree-sitter-glsl
--grammar-version 0.2.0+capsule1`, baseline старой грамматики. Подробные результаты каждого
повтора находятся в соответствующих glsl_probe_results_runtime26*.json.

## SHA256 целевого набора

| Файл | SHA256 |
|---|---|
| cloud-copy.fs | `f3a37996c3d887b6c944638374279621c9475c6747039c625d21dc1b3730d8f6` |
| cloud-copy.vs | `ece661b3da02f3b9672ad8d5671ec683ef11d26e9c3da7985cda455d5aca7d53` |
| cloud-layer.fs | `7f3bcf98a45e9606e9eee8717f49e72a13889751d81b8ca29230a15ce3577012` |
| cloud-layer.vs | `83963ee151a21569996252369e57ac7a0d5d9deee36e736b5f428b72ce9989e9` |
| cloud-near.fs | `ab293680ed40936bebbff91e18804fa01a6e2c213b93f5329e96352019ebf07d` |
| cloud-near.vs | `b2108a29b6ff2c4e3fa363ae93cb8773197bc4d1c7c9ced99a407c6b6018a4a0` |
| color-map.fs | `556a13dba0259879598f349a2b612e4ddfe25a94f57a1d64981b8afcbb7016b2` |
| color-map.vs | `395e528f3d3b2b28ed16dd6b94abe6bf77ce1560dd570a6febfbc6926d251a46` |
| cover-map.fs | `6a89c80bef1f1396f0f1ec88032b417f0a03d5b715637a0bdf2c19b32a4e0182` |
| cover-map.vs | `947eb098ec2283e1f11c7ff0e89b041b9d67e7a32dc4051864ba7f099e53b582` |
| lut-transmittance.fs | `eda91d19dbb66f31ac13784563c3b5629c802ece8dac8d83b13026b25e123768` |
| lut-transmittance.vs | `7356e4a6c798bfc1029411639c86dc7a8b04332992fa7d630a7edb8d18f58ed1` |
| noise-bake.fs | `1edbf98cd0e7480d98c182b3fed710dfbed34b4c55a939acc22aa20d02165b20` |
| noise-bake.vs | `6c33011ba1589176c0515e9219b982fcf5afb1050615e58381aba1478f87cb9b` |
| planet-air.fs | `3cb37432e2d8068efc6f111cf65654c78f8052c4260ab6b89213c2c14d291a62` |
| planet-air.vs | `0acd5a1b337214439d5bd9af540990e0cac55243275e8058352628bab3090887` |
| planet-bake.fs | `08f6f19db339f28ff674451ec3ceece074d53207a3aeba2d6cd01941d53bb812` |
| planet-bake.vs | `0a368a38cbb6cc7f1b39ced56759ca713b6f0e04ee3992f14264c55b8bd1f890` |
| planet-ground.fs | `77335668438168600779b7d2a9ce22cbc21b5b334d566857982cbf7e4ad7d61c` |
| planet-ground.vs | `d82c2d3f520142ecb13e6741c5c3cbead17d19eacb5ad756ac5d33ae43d5f936` |
| sim-step.fs | `e23053b58e65130fab9823e1aa1416e87744a823299a3912a3027d2606c045e6` |
| sim-step.vs | `80235be49d20ea06871e9f181f125298b91158e719fe9d10990cb4153b86bb76` |

## Границы результата и следующий шаг

- Эталонный tree-sitter остаётся 0.26.0, GLSL-пакет в нём остаётся опубликованным 1.0.0.
- Новое колесо не установлено: обязательный .row-повтор исходного Plan10 не прошёл.
  Послеустановочный прогон поэтому не выполнялся — это не пропущенный успешный этап.
- Production-код, requirements, GLSL-профиль, Hermes и файлы шейдеров не изменены.
  Ничего не закоммичено и не развёрнуто в проекты. План оставлен на месте для разбора владельцем.
- Возможный следующий выбор владельца/Plan: принять индексный доступ как корректный путь
  для get_codeblock и обновить критерий приёмки либо отдельно исправлять/обновлять runtime.
  Собственная сборка tree-sitter/runtime в этот шаг НЕ вводилась.
- Скрипты проверены на синтаксис, приёмка демонстрирует ненулевой exit при нативных
  сбоях и расхождении baseline. Полный регресс production-tools не запускался: production
  не менялся и новый wheel в эталонный venv не установлен.
