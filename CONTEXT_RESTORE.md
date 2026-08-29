# CONTEXT_RESTORE — как поднять контекст в новой сессии

Читать в этом порядке, не блуждать по репо:

1. **`__dev/DECISIONS.md`** — закрытые решения (одна строка = выбор + почему). Не релитигировать.
2. **Хвост `__dev/TRACKER.md`** (последние строки `✅`) — где мы по времени, что было только что.
3. **`__dev/vision/Vision01__path-and-flag-conventions.md`** — контракт путей/флагов, патч сделан
   (см. чеклист там же, весь `[x]`).
4. **`__dev/Requests/`** — `DONE__*` закрыты, без префикса = открыто. Сейчас открыт **REQ-003**
   (не трогали) и свежие **REQ-006**/**REQ-007** (см. ниже).

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

- **REQ-003** — nested-package identity в `find_code_usage` (нашлось раньше, не трогали).
- **REQ-006** — Python-константы модуля (`KNOWN_SEAMS = (...)`) вообще не попадают в карточку ни
  как факт, ни в Salvage — `_declared()` для Python берёт exports только из functions/classes.
- **REQ-007** — `CONFIG__TOOLS` резолвится по расположению СКРИПТА (`sys.path`), не по
  `--project-root` — `--all --project-root <чужой проект>` из этого чекаута читает ЧУЖОЙ
  `TEST_DIRS`/`LANGUAGE`. Найдено живьём (наштамповало 43 лишних карточки в memohood, откачено).

## Регресс (прогнать после любой правки)

```bash
py test/check.py --fails            # 106/0 — общий оракул пакета
py test/test_cardstamp.py           # 103/0 — merge/salvage/зона/discrepancies
py test/run_restamp_fixtures.py     # 21/0 — ручной полигон merge-идентичности
```

## get_codeblock — отдельный, активно развивающийся подпоток

Свой набор vision-доков `__dev/vision/Vision01-04__get_codeblock.md` + операционные заметки
`__dev/CONTEXT_RESTORE_TOOLS.md` (канонические источники, инварианты, ⚠ два репозитория — та
заметка ещё говорит про старый раскол репо, тоже подправлена, но читать вместе с этим файлом, не
вместо). Регресс отдельный: `test/golden_check.py`, `test/sweep_invariants.py` — см.
`test/HowTo__Test-get_codeblock.md`.
