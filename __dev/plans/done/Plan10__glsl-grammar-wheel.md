# Plan10 — колесо GLSL-грамматики под tree-sitter 0.26 (ТЗ для Gpt-Sol)

**Статус: закрыт решением Plan11 D1.** Индексная приёмка установленного capsule1: 480/480.

Исполнитель: Gpt-Sol (автор `__dev/review/GLSL_PROBE.md`). Поставлено владельцем 2026-11-01.
Замечания исполнителя `Plan10__KICKBACK.md` (K1–K4) приняты и внесены сюда — исполнять по этому файлу.
Это ТОЛЬКО шаг «собрать и проверить грамматику». Подключение GLSL в get_codeblock (профиль,
адаптер дерева, ошибки препроцессора) — отдельный план, после разбора результата этого.

## Зачем

Хотим, чтобы get_codeblock читал шейдеры (`.fs`/`.vs`/`.glsl`…, первый набор —
`Y:/AgentsWork/PlanetWeather/viewer_layered/export/shaders`, 22 файла). Основа —
`tree-sitter-glsl-spec` (меньше ошибок, см. `GLSL_PROBE.md`). Мешает загрузка на нашем
рабочем tree-sitter 0.26.0:

1. Опубликованное колесо `tree-sitter-glsl-spec 1.0.0` отдаёт язык старым способом —
   `PyLong_FromVoidPtr(tree_sitter_glsl())` (см. `site-packages/tree_sitter_glsl_spec/binding.c`).
   0.26 на Windows x64 читает это через `PyLong_AsUnsignedLong` → `OverflowError`.
2. Обход через `ctypes.pythonapi.PyCapsule_New(ptr, b"tree_sitter.Language", None)` загружает
   язык, но процесс НЕДЕТЕРМИНИРОВАННО падает (access violation, 0xC0000005) на больших файлах.

## Что уже известно (не перепроверять заново, опираться)

- Падение воспроизводится стабильно: `__dev/review/glsl_probe.py --worker tree-sitter-glsl-spec
  cloud-layer.fs <out.json>` на 0.26 — падает каждый раз. Место падения ПЛАВАЕТ (разные строки
  Python от прогона к прогону) — похоже на порчу памяти, а не на один «плохой» вызов.
- Минимальный повтор (тот же мост через ctypes) — падает на шаге, где после полного обхода дерева
  идут `n.is_named` / `n.type` / `n.is_missing` по всем ~28.7k узлам `cloud-layer.fs`:

  ```python
  import ctypes, tree_sitter as ts, tree_sitter_glsl_spec as g
  from collections import Counter
  f = ctypes.pythonapi.PyCapsule_New
  f.restype, f.argtypes = ctypes.py_object, [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p]
  lang = ts.Language(f(g.language(), b"tree_sitter.Language", None))
  src = open("Y:/AgentsWork/PlanetWeather/viewer_layered/export/shaders/cloud-layer.fs", "rb").read()
  tree = ts.Parser(lang).parse(src); root = tree.root_node
  def walk(r):
      st = [r]
      while st:
          n = st.pop(); yield n; st.extend(reversed(n.children))
  nodes = list(walk(root))
  Counter(n.type for n in nodes if n.is_named)
  [(n.type, n.start_point.row) for n in nodes if n.type == "ERROR" or n.is_missing]  # <- падает здесь или рядом
  ```
- Тот же код на изолированном tree-sitter 0.25.2 (прямой `Language(g.language())`) — стабилен.
- Падает и старая `tree-sitter-glsl 0.2.0` (ABI 14), не только `glsl-spec` (ABI 15). Значит, дело
  не только в ABI 15.
- ВАЖНО: мост через ctypes делает по сути то же, что сделает исправленная привязка
  (`PyCapsule_New(tree_sitter_glsl(), "tree_sitter.Language", NULL)`). Поэтому НЕ гарантировано,
  что пересборка сама уберёт падения. Пересборка гарантированно убирает только `OverflowError`.
  Проверка этого — главная цель плана, а не формальность.
- Источник: `Project-URL: Homepage, https://github.com/Caellian/tree-sitter-glsl` (из METADATA
  колеса 1.0.0). C-символ языка — `tree_sitter_glsl` (тот же, что у tree-sitter-grammars/glsl).
- Окружение: эталонный Python `T:/AgentsWork/venv/Scripts/python.exe` (3.12.10, Windows x64),
  tree-sitter 0.26.0. Компилятор есть: Visual Studio Community 2022, MSVC 14.39 (`cl`).

## Ограничения (жёсткие)

- Рабочий tree-sitter 0.26.0 в эталонном venv НЕ понижать и не заменять.
- Production-код get_codeblock (`get_codeblock/**`, `get_codeblock.py`) НЕ трогать. Профиль GLSL
  не подключать.
- Python Hermes, `Y:/Hermess/**`, hermes-filetools — не трогать.
- Исходники шейдеров PlanetWeather — только чтение.
- Сборка — во временной папке ВНЕ репо (TEMP). В репо попадают только итоги (ниже).
- В эталонный venv колесо ставить ТОЛЬКО после того, как оно прошло проверку из изолированной
  папки (`pip install --target <TEMP>/glsl-test ...` + `PYTHONPATH`). Старое 1.0.0 при этом
  заменяется — это нормально, на 0.26 оно и так не работает.
- Не коммитить. Владелица и Claude разберут результат и закоммитят сами.
- Скачивать — только исходники грамматики (git clone / архив тега) и, если понадобится,
  `setuptools`/`wheel`/`build` и tree-sitter CLI. Ничего крупного (CUDA, SDK) не нужно.

## Шаги

### 1. Исходники (одна переменная — привязка) · KICKBACK K2
- Клонировать `https://github.com/Caellian/tree-sitter-glsl` на коммите публикации PyPI 1.0.0 —
  `3a00d49a88cb53eec519b49d8e234e77d916f8ac` (provenance Windows x64 колеса на PyPI). Проверить
  recipe публикации в этом коммите (CI/`pyproject`/`setup.py`).
- «Ближайший коммит» НЕ брать. Колесо 1.0.0 не содержит `parser.c`/`grammar.js`, сверить их
  напрямую нельзя — поэтому опора только на этот коммит. Если соответствие установить не удалось —
  это блокер воспроизводимости (остановиться и отчитаться), а не тихая замена грамматики.
- Записать: URL, коммит, SHA256 `src/parser.c` и `grammar.js`, версию CLI из шапки `parser.c`,
  `LANGUAGE_VERSION` (ABI).
- Записать SHA256 всех 22 шейдеров. Если байты разошлись с тем, на чём снят
  `glsl_probe_results_runtime25.json`, — снять новый baseline на 0.25.2 для текущих байтов в
  ОТДЕЛЬНЫЙ файл (`glsl_probe_results_runtime25_<дата>.json`); исторический не перезаписывать.

### 2. Привязка
- Если `bindings/python` в репо уже современная (возвращает `PyCapsule`) — собрать как есть.
- Если старая (`PyLong_FromVoidPtr`) — заменить `language()` на
  `PyCapsule_New(tree_sitter_glsl(), "tree_sitter.Language", NULL)` по образцу привязки
  `tree-sitter-cpp`, установленной в venv (`site-packages/tree_sitter_cpp/binding.c`). Diff записать.
- `parser.c` по умолчанию НЕ перегенерировать (грамматика должна остаться той же, что в пробе).

### 3. Сборка колеса
- Цель: `abi3`, Python ≥ 3.10, `win_amd64` (одно колесо годится и для venv 3.12, и для Python
  Hermes, если он ≥ 3.10). Если abi3 не собирается — `cp312`, и записать почему.
- Сборка из Developer Command Prompt / с `vcvars64`, в TEMP.
- Записать точные команды — повтор должен быть копипастой.
- Дать колесу отличимую локальную версию `1.0.0+capsule1` (K3), записать SHA256. Ставить только
  точным путём: `pip install --force-reinstall --no-deps <путь к .whl>` и после установки
  проверить версию и SHA256 установленного `_binding.pyd`.

### 4. Проверка на 0.26 (главное)
`glsl_probe.py` — диагностика, НЕ приёмка (K1): ловит неудачную прямую загрузку и уходит в ctypes,
падение worker не меняет код выхода, гоняет обе грамматики, нет таймаута/повторов/сравнения, а на
0.26 пишет в `..._runtime26_diagnostic.json`. Его не менять.

**Написать приёмочный runner** `__dev/review/glsl_wheel_accept.py` (входит в объём работ):
- одна выбранная грамматика; загрузка строго `Language(module.language())`, БЕЗ ctypes —
  неудача загрузки = FAIL;
- явный путь вывода (по умолчанию `glsl_probe_results_runtime26.json`);
- каждый из 22 файлов — **20 отдельных процессов**, плюс минимальный повтор выше — 20 процессов;
  у каждого процесса таймаут;
- результат КАЖДОГО повтора сохраняется (не только последнего);
- сравнение с baseline 0.25.2: функции, их диапазоны, ERROR/MISSING (тип + позиция), счётчики
  узлов. Известные ERROR/MISSING — часть baseline, сами по себе НЕ FAIL;
- FAIL и ненулевой exit code при: падении, таймауте, пропущенном файле, ошибке загрузки,
  расхождении с baseline, провале проверки окружения (ниже).

**Проверка окружения в КАЖДОМ worker, до обхода дерева** (K3) — записать в результат и
проверить:
- `sys.executable`, версия Python, архитектура;
- версия и путь `tree_sitter` и его бинарного модуля — должен быть эталонный 0.26.0;
- путь GLSL-пакета и его `_binding.pyd`, версия (`1.0.0+capsule1`), SHA256 бинарника — должен
  грузиться из проверяемой папки (`--target`), а не старое колесо из venv;
- `module.language()` возвращает capsule, не int;
- `GLSL_PROBE_RUNTIME` и прочие диагностические подмены не заданы (worker запускать с
  очищенным от них окружением).

Прогон: из изолированной папки (`--target` + `PYTHONPATH`), эталонным Python, затем — после
установки в venv — повторить тот же runner уже без `PYTHONPATH`.

Контроль рантайма: тот же паттерн обхода (полный walk + `is_named`/`type`/`is_missing` по всем
узлам) на большом C++ файле через `tree-sitter-cpp` на 0.26. Трактовка (K4): это проверка,
общий ли сбой для контрольного обхода, а НЕ доказательство отсутствия бага 0.26 — он может
зависеть от формы дерева, ERROR/MISSING, числа узлов. 20 чистых повторов — критерий этого
эксперимента, не доказательство отсутствия любых нативных ошибок.

### 5. Если падения остались
Не подключать, локализовать и отчитаться:
- Повтор с `-X faulthandler`, минимальный файл (урезать `cloud-layer.fs`, пока падает).
- Отдельный ВАРИАНТ эксперимента (не замена основного, K2): перегенерировать `parser.c` текущим
  tree-sitter CLI (ABI 15, затем `--abi 14`), пересобрать с другой локальной версией
  (`+regen15`/`+regen14`), прогнать runner. Новые SHA256 `parser.c` записать; расхождения с
  baseline здесь объяснимы грамматикой и перечисляются отдельно.
- Контроль: так же пересобрать `tree-sitter-grammars/tree-sitter-glsl` (старая, ABI 14) — падает
  ли она после пересборки.
- Итог: минимальный повтор + гипотеза с доказательством (что меняли → что изменилось). Если
  доказательства нет — допустимый итог «причина не локализована, колесо не принято» (K4).

## Что сдать

1. Колесо — `wheels/tree_sitter_glsl_spec-<ver>-<tag>.whl` в корне tools (папку создать).
2. `wheels/README.md` — по строке на колесо: источник (URL + коммит), SHA256 `parser.c`/`grammar.js`,
   ABI, теги Python/платформы, SHA256 колеса, команда установки (`--force-reinstall --no-deps`),
   точные команды сборки, diff привязки.
3. `__dev/review/glsl_wheel_accept.py` — приёмочный runner (шаг 4).
4. `__dev/review/GLSL_BUILD.md` — отчёт: что собрали, SHA256 шейдеров, результаты шага 4 таблицей
   (файл × повторы × падения/таймауты), окружение worker'ов, сравнение с 0.25.2, при падениях — шаг 5.
5. `__dev/review/glsl_probe_results_runtime26.json` — все повторы runner'а на новом колесе
   (диагностический `..._runtime26_diagnostic.json` и исторический `..._runtime25.json` не
   перезаписывать).
6. Строку в конец `__dev/TRACKER.md` (формат как у записи 2026-11-01 про GLSL).

## Готово, когда

- Колесо собрано из коммита `3a00d49`, изменена только привязка/упаковка (хэши `parser.c`/`grammar.js`
  записаны).
- Runner завершился с кодом 0: загрузка прямым `Language(module.language())`, 22 файла × 20
  процессов + минимальный повтор × 20 — ноль падений и таймаутов, окружение каждого worker'а
  подтверждено (0.26.0, новое колесо, capsule, без подмен).
- Функции/диапазоны/ERROR/MISSING/счётчики совпадают с baseline 0.25.2.
- После установки в venv runner повторён без `PYTHONPATH` — тоже код 0, SHA256 установленного
  бинарника = проверенного.
- Рабочий tree-sitter по-прежнему 0.26.0; production-код и Hermes не тронуты; ничего не закоммичено.

Если любой пункт «Готово» не достигнут — это тоже результат: сдать отчёт по шагу 5, колесо не
ставить в эталонный venv.

## Не входит

- GLSL-профиль get_codeblock, нормализация `statement_list`/`declarator_list`, извлечение имён.
- Поведение на ошибках препроцессора (`#ifdef` внутри if/else).
- Выбор расширений (`.fs` — ещё и F#), раскатка в Hermes и проекты.
