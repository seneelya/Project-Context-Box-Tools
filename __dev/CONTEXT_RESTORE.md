# CONTEXT_RESTORE — как поднять контекст в новой сессии

Читать в этом порядке, не блуждать по репо:

1. **`__dev/DECISIONS.md`** — закрытые решения (одна строка = выбор + почему). Не релитигировать.
2. **Хвост `__dev/TRACKER.md`** (последние строки `✅`) — где мы по времени, что было только что.
3. **`__dev/vision/Vision01__path-and-flag-conventions.md`** — контракт путей/флагов, патч сделан
   (см. чеклист там же, весь `[x]`).
4. **`__dev/Requests/`** — `DONE__*` закрыты, без префикса = открыто. На 2026-08-30 открытых нет —
   REQ-003/006/007 (см. ниже, были параллельно с этим доком) все закрыты в ту же сессию.

## Что это за репозиторий

Независимый git (`__HQ/tools/.git`), вложенный в ProjectStarter, но `.gitignore`-нутый им — коммитить
СЮДА, не в ProjectStarter. `__dev/` (история/vision/decisions/requests) и `__delme/` (пусто, было
для того же — раскол снят 2026-08-30) исключены из `deploy_hq.py` — в проекты не уезжают.
`TOOLS.md` — router по тулам, `test/HowTo__Test-*.md` — как тестировать каждый.

## Что сделано в последней сессии (2026-08-29/30, крупно)

1. **Merge-identity в `make_interface_card.py`** — re-stamp карточки терял прозу на ЛЮБОМ
   JS/TS/C#/async-Python файле (угадывание имени по «первому слову» сигнатуры ломалось на языковой
   обёртке `function`/`async`/`public static void`). Починено: имя ищется по позиции, переименования
   ловятся по похожести (fuzzy), расхождение сигнатуры помечается стопкой маркеров `⚠`, `--force` на
   заполненной карточке требует `--discard-prose`. Design + acceptance — `DONE__REQ-004+005_merge-identity-design.md`.
   Тесты: `test/test_cardstamp.py` (+7 новых), ручной полигон `test/restamp_fixtures/` +
   `run_restamp_fixtures.py --diff` (файл+карточка на 3 языка, видно все 5 исходов merge одним диффом).
2. **Путевой/флаговый контракт на весь пакет (9 тулов)** — `Vision01__path-and-flag-conventions.md`.
   Суть: **generic-тулы** (`find_code_usage`, `get_codeblock`, `show_pyfile_api`, `replace_in_files`)
   резолвят относительный путь от cwd, конфиг читают ТОЛЬКО по явному `--project-root @`/`--path @`.
   **card-тулы** (`make_interface_card`, `validate_cards`, `check_cards_freshness`,
   `graph_from_cards`, `collect_card_bundle`) — наоборot, без флага неявно берут
   `CONFIG__TOOLS.PROJECT_ROOT`, но со sanity-check (корень обязан содержать сам тул — иначе отказ).
   `--file`/`--path` добавлены как флаги-алиасы к позиционным везде, где их не было. Осознанно БЕЗ
   общего модуля-резолвера (независимость тулов важнее). `deploy_hq.py --init` теперь сам вписывает
   реальный путь деплоя в свежий `CONFIG__TOOLS.PROJECT_ROOT` (не статичный список кандидатов).
3. **Реорганизация `__dev/`** — старый `ProjectStarter/__dev/tools/` (внешний, отдельный репо) слит
   сюда целиком; `__delme/`→`__dev/` для `DECISIONS.md`/`TRACKER.md` (актуализированы),
   `RESTORE__card_stamp.md` удалён (узкий, устаревший, суперсижен).

## Открыто, ждёт следующей сессии

Пусто — REQ-003/006/007 закрыты в этой же сессии (2026-08-30, после первой версии этого файла):

- **REQ-007** — `CONFIG__TOOLS` резолвился по расположению СКРИПТА, не по `--project-root`.
  Фикс: `graph_from_cards.load_config_at(root)` грузит `<root>/__HQ/tools/CONFIG__TOOLS.py` по
  файловому пути; `make_interface_card._decl_backend`/`_config_lang_testdirs` теперь берут
  конфиг ЦЕЛЕВОГО корня. Живой прогон на memohood подтверждён (`tests/` больше не штампуется).
- **REQ-006** — Python-константы модуля не попадали в карточку. Фикс: `show_pyfile_api.collect()`
  возвращает `constants` (публичные top-level присваивания) → `make_interface_card` кладёт их в
  `exports` с `kind="const"`, рендерится в уже существующий `### Constants` H3.
- **REQ-003** — nested-package identity в `find_code_usage`. Фикс: путь-based сверка (по
  реальным директориям через dots, независимо от `__init__.py`-цепочки) добавлена РЯДОМ со старой
  dotted-name проверкой в `python_handler.py`, не заменяя её.

Все три — `DONE__REQ-{003,006,007}_*.md` в `__dev/Requests/`, детали фикса — хвост
`__dev/TRACKER.md`. Регресс на момент закрытия: golden 107/0, test_cardstamp 109/0,
run_restamp_fixtures 21/0.

## Регресс (прогнать после любой правки)

Эталонный интерпретатор — `T:\AgentsWork\venv` (3.12; пакет требует Python >= 3.10). Только в нём
стоят ВСЕ грамматики из `get_codeblock/requirements.txt`. У `py` их нет, и прогон выйдет неполным:
хвост `N skipped (grammar missing)` — это не «ок», а «столько кейсов не проверялось».

```bash
T:/AgentsWork/venv/Scripts/python.exe test/check.py --fails         # 120/0 — общий оракул пакета
T:/AgentsWork/venv/Scripts/python.exe test/test_cardstamp.py        # 109/0 — merge/salvage/зона/discrepancies
T:/AgentsWork/venv/Scripts/python.exe test/run_restamp_fixtures.py  # 21/0 — ручной полигон merge-идентичности
T:/AgentsWork/venv/Scripts/python.exe test/golden_check.py          # 12/12 — реальный CLI-вывод (subprocess)
T:/AgentsWork/venv/Scripts/python.exe test/sweep_invariants.py      # HIGH=0 (LOW LEVEL=5 на TS try/catch — известный шум)
```

## get_codeblock — отдельный, активно развивающийся подпоток

Свой набор vision-доков `__dev/vision/Vision01-04__get_codeblock.md` + операционные заметки
`__dev/CONTEXT_RESTORE_TOOLS.md` (канонические источники, инварианты, ⚠ два репозитория — та
заметка ещё говорит про старый раскол репо, тоже подправлена, но читать вместе с этим файлом, не
вместо). Регресс отдельный: `test/golden_check.py`, `test/sweep_invariants.py` — см.
`test/HowTo__Test-get_codeblock.md`.
