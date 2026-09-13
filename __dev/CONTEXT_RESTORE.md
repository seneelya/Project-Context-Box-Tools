# CONTEXT_RESTORE — как поднять контекст в новой сессии

Читать в этом порядке, не блуждать по репо:

1. **`__dev/DECISIONS.md`** — закрытые решения (одна строка = выбор + почему). Не релитигировать.
2. **Хвост `__dev/TRACKER.md`** (последние строки `✅`) — где мы по времени, что было только что.
3. **`__dev/vision/Vision01__path-and-flag-conventions.md`** — контракт путей/флагов, патч сделан
   (см. чеклист там же, весь `[x]`).
4. **`__dev/Requests/`** — `DONE__*` закрыты, без префикса = открыто. На 2026-09-14 открытых нет
   (см. «Открыто, ждёт следующей сессии» ниже).

## Что это за репозиторий

Независимый git (`__HQ/tools/.git`), вложенный в ProjectStarter, но `.gitignore`-нутый им — коммитить
СЮДА, не в ProjectStarter. `__dev/` (история/vision/decisions/requests) и `__delme/` (пусто, было
для того же — раскол снят 2026-08-30) исключены из `deploy_hq.py` — в проекты не уезжают.
`TOOLS.md` — router по тулам, `test/HowTo__Test-*.md` — как тестировать каждый.

## Что сделано в последней сессии (2026-09-14, крупно)

**REQ-010/Plan03 закрыты — `## Runtime seams`**: связи, которых не видно из импортов (динамическая
загрузка по пути, отдельный процесс, общий файл, шина событий). `CARD_FORMAT.VERSION` 1.0.0 → 1.1.0:
`Dependencies Internal/External` переименованы в `In-Project/External Dependencies` (старые заголовки
читаются через `ALIASES`), новая опциональная секция-таблица (`Target|Symbol|Kind|Shape|Why`), штамп
хранит её как есть кроме строки-контракта. Новое: `seam_scanner/` (детектор-ПАКЕТ, не тул — нет
`__main__`/TLDR, только импортируется штампом), `--help-seams`/`<file> --info-seams`,
`graph_from_cards.py` рисует швы ОТДЕЛЬНЫМ маркером (`【SEAM⇢】`/`【SEAM⇠】`, прошёл 3 итерации — см.
хвост `plans/done/Plan03__runtime_seams.md`), `components()`/острова считаются СТРОГО по импортам
(швы не сливают острова — это стёрло бы факт «разные приложения»; отдельно — `_seam_bridges()`/
`## runtime seams (N)`/`--view seams-mermaid`), `validate_cards.py` проверяет Kind/Shape/Target.
Ручная миграция 8 живых карточек `hermes-filetools` + раскатка на `memohood` (0 issues на обоих) —
детали и НАЙДЕННЫЕ ПО ХОДУ вещи (переименование ломает хардкод в потребителях, пропущенный обратный
вид шва, 2 ошибки и 1 пропуск в исходной human-прозе) — в хвосте `plans/done/Plan03__runtime_seams.md`
и в `DECISIONS.md` (раздел «Runtime seams»). Всё запушено (ProjectStarter outer+tools, hermes-filetools).

## Открыто, ждёт следующей сессии

Пусто — ни одного файла без `DONE__` в `__dev/Requests/` (не считая `sonet_feedback__gcb.md`, это
живой intake-лог get_codeblock, не формальный реквест, и он пуст), `__dev/plans/` пуст, кроме `done/`.

## Регресс (прогнать после любой правки)

Эталонный интерпретатор — `T:\AgentsWork\venv` (3.12; пакет требует Python >= 3.10). Только в нём
стоят ВСЕ грамматики из `get_codeblock/requirements.txt`. У `py` их нет, и прогон выйдет неполным:
хвост `N skipped (grammar missing)` — это не «ок», а «столько кейсов не проверялось».

```bash
T:/AgentsWork/venv/Scripts/python.exe test/check.py --fails         # 120/0 — общий оракул пакета
T:/AgentsWork/venv/Scripts/python.exe test/test_cardstamp.py        # 142/0 (2026-09-14) — merge/salvage/зона/discrepancies/seams
T:/AgentsWork/venv/Scripts/python.exe test/run_restamp_fixtures.py  # 21/0 — ручной полигон merge-идентичности
T:/AgentsWork/venv/Scripts/python.exe test/golden_check.py          # 13/13 — реальный CLI-вывод (subprocess)
T:/AgentsWork/venv/Scripts/python.exe test/sweep_invariants.py      # HIGH=0 (LOW LEVEL=5 на TS try/catch — известный шум)
```

## get_codeblock — отдельный, активно развивающийся подпоток

Свой набор vision-доков `__dev/vision/Vision01-06__get_codeblock.md` (05 — query-эскалация/`--force`,
06 — семя идеи «разборщик монструозных файлов», брейншторм, не решение) + операционные заметки
`__dev/CONTEXT_RESTORE_TOOLS.md` (канонические источники, инварианты, ⚠ два репозитория — та
заметка ещё говорит про старый раскол репо, тоже подправлена, но читать вместе с этим файлом, не
вместо). Регресс отдельный: `test/golden_check.py`, `test/sweep_invariants.py` — см.
`test/HowTo__Test-get_codeblock.md`.
