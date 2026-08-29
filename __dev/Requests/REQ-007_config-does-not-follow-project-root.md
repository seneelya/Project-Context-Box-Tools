# REQ-007 · CONFIG__TOOLS резолвится по расположению СКРИПТА, не по `--project-root`

**Тул:** все, кто читает `CONFIG__TOOLS.py` (`import CONFIG__TOOLS`) — затронуто минимум
`make_interface_card.py --all` (TEST_DIRS/LANGUAGE).
**Нашлось:** 2026-08-30, ручной прогон `make_interface_card.py --all --project-root <memohood>`
из чужого чекаута `tools/` (тестирование REQ-002). **Статус:** ОТКРЫТ, после компакта.

## Суть

`import CONFIG__TOOLS` резолвится через `sys.path` — то есть берёт копию, что лежит РЯДОМ СО
СКРИПТОМ (или в cwd), а не ту, что лежит в `<--project-root>/__HQ/tools/CONFIG__TOOLS.py`. Если
тул запускают из ОДНОГО чекаута `tools/` (например, при разработке/тестировании) с
`--project-root`, указывающим на ДРУГОЙ проект — `TEST_DIRS`/`LANGUAGE`/`DECL_BACKEND` берутся из
чужого, а не из целевого конфига.

## Как обнаружено (конкретно)

`make_interface_card.py --all --project-root <memohood>` запускался ИЗ `t:/…/ProjectStarter/__HQ/tools/`
— локальный (нейтральный, `TEST_DIRS=[]`) конфиг был использован ВМЕСТО memohood-ского
(`TEST_DIRS=["tests"]`). Результат: `--all` наштамповал 43 лишних карточки под `__map/tests/` в
memohood, которые должны были быть исключены. Откачено вручную (`git checkout -- __map/` +
`rm -rf __map/tests/` в memohood).

## Решение — предложено пользователем

`TEST_DIRS` и так документированы как пути ОТНОСИТЕЛЬНО `PROJECT_ROOT` — значит правильно не
менять их формат, а менять ТОЧКУ ЗАГРУЗКИ конфига: читать
`<резолвленный --project-root>/__HQ/tools/CONFIG__TOOLS.py` напрямую (а не полагаться на
`sys.path`/cwd), и разрешать `TEST_DIRS`-записи относительно ЭТОГО корня. Если структура целевого
проекта не совпадает с тем, что записано в его же `TEST_DIRS` — это ответственность целевого
конфига, не тула; специальная обработка/валидация не нужна, это нормальное поведение.

## Acceptance criteria

1. `make_interface_card.py --all --project-root R` (запущенный из ЛЮБОГО cwd/чекаута) использует
   `TEST_DIRS`/`LANGUAGE`/`DECL_BACKEND` из `R/__HQ/tools/CONFIG__TOOLS.py`, не из своего.
2. То же для остальных card-тулов, которые читают конфиг (`validate_cards`, `check_cards_freshness`,
   `graph_from_cards`, `collect_card_bundle`) — если у них есть подобная зависимость от `TEST_DIRS`
   и т.п. (проверить по коду, не все могут быть затронуты).
3. Живой кейс: повторить `--all` из этого репозитория `tools/` с `--project-root <memohood>`,
   убедиться что `tests/` пропускается.
4. Не трогать generic-тулы (`get_codeblock`, `find_code_usage`, `show_pyfile_api`) сверх того, что
   уже сделано в Vision01 — у них конфиг читается только по явному `@`, это отдельный вопрос.

— Соня5 (Claude Sonnet 5), 2026-08-30
