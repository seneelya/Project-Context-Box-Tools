# План (ОТЛОЖЕН): нарезка JSX-return на именованные landmark'и (TSX)

**Дата:** 2026-09-13. **Статус:** отложено — проанализировано, не начато. Собрано из живого
обсуждения после Vision05 (эскалация) + SCSS-фикса той же сессии.

**Промежуточная мера уже сделана (не заменяет этот план):** `get_codeblock/jsx_note.py` —
детектирует большой плоский JSX-блок и печатает `known limitation: …` в `--outline`/`--query`,
без какого-либо реального разбора. Чисто чтобы агент не принял «пусто в карте» за «здесь
пусто». Когда этот план будет реализован, заглушка сама перестанет срабатывать (depth перестанет
быть 1) — конфликта нет, ничего вручную отключать не придётся.

## Проблема

Большой `return (...)` в React-компоненте — один флэт-блок для outline/адресации: JSX-элементы
внутри return'а сейчас НЕ промоутятся в landmark'и (в отличие от `const X = () => {}` — та привязка
уже промоутится). Итог: `--outline` не видит НИ ОДНОГО структурного узла внутри return'а, а
`--query`/`--ancestor-level` на любой строке внутри отдаёт ВЕСЬ return целиком — сотни строк за раз.

**Живой пример** (реальный файл, не синтетика): `App.tsx`, 602 строки, `const App = () =>` [98-600],
внутри — ОДИН `~return_statement` [123-599] (476 строк), контент — ~50 `<Route>` и других JSX-детей,
outline их не видит вообще.

**Откуда пришло:**
- Исходный фидбек: [`__dev/Requests/cursor_feedback__gcb.md`](Requests/cursor_feedback__gcb.md) —
  запись «2026-08-23 — Flat mega-component: no carve of JSX / route islands» (**не закрыта**, единственный
  оставшийся открытый пункт в этом файле).
- Репро-файл: [`__dev/Requests/feedback/files/Warehub.Frontend/src/App.tsx`](Requests/feedback/files/Warehub.Frontend/src/App.tsx)
  (гитигнорится — реальный внешний исходник, не публиковать; см. `.gitignore` в этой же папке `tools/`).
  Второй репро (то же явление, другой файл, из того же фидбека) —
  [`Requests/feedback/files/Warehub.Frontend/src/shared/VideoDropzone/VideoDropzone.tsx`](Requests/feedback/files/Warehub.Frontend/src/shared/VideoDropzone/VideoDropzone.tsx).

## С чего начать (порядок чтения для восстановления контекста)

1. [`get_codeblock/reader/CONTRACT.md`](../get_codeblock/reader/CONTRACT.md) — контракт reader-слоя
   целиком: секция «Адресация (Vision04)» — как рунги строятся из `named_def`/`control`/
   `body_types`; инвариант #6 (карта и адресация ОБЯЗАНЫ давать один ответ — ключевое ограничение
   для этой задачи).
2. [`get_codeblock/reader/address.py`](../get_codeblock/reader/address.py) — функции `_collect`,
   `_has_body`, `_is_standalone_body` (строки ~44-78 на момент записи плана): это движок, который
   реально отдаёт `--query`/`--line`/ladder, и он работает НАПРЯМУЮ по `ls.named_def`/`ls.control`/
   `ls.body_types` — **не** через `TreeSitterSpec.unwrap_def()`.
3. [`get_codeblock/reader/backends/treesitter.py`](../get_codeblock/reader/backends/treesitter.py) —
   `TreeSitterSpec.unwrap_def()`/`_arrow_binding_value()`/`body()`/`filler_kind()`: движок карты
   (`--outline`/`.0`), ЕСТЬ кастомная промоушен-логика (прецедент для JSX-промоушена).
4. [`get_codeblock/handlers/typescript_handler.py`](../get_codeblock/handlers/typescript_handler.py) —
   `_TS_NAMED`/`_TS_BODY`/`_TS_CONTROL`, `_make_ts_spec` (строки ~45-80): ОДИН `LangSpec`, шаримый
   между `TS_SPEC` (`.ts`/`.js`) и `TSX_SPEC` (`.tsx`/`.jsx`) — и с легаси-`declarations()`
   (проверено: `declarations()` — независимая regex-эвристика, `named_def`/`body_types` НЕ трогает,
   так что интерфейс-карты `make_interface_card.py` не затронуты этой задачей).
5. [`get_codeblock/reader/profiles/typescript.py`](../get_codeblock/reader/profiles/typescript.py) +
   [`base.py`](../get_codeblock/reader/profiles/base.py) — `TSProfile`, `binders`/`value_types` —
   существующий пример «профиль передаёт данные, движок остаётся общим», по этому же образцу
   заводить JSX-промоушен.
6. Живая проверка дерева (потребуется снова, дерево tree-sitter-tsx для конкретно этого случая):
   ```python
   from get_codeblock.reader.registry import resolve
   backend, spec = resolve('.tsx')
   root = backend.root(src_bytes)
   # смотреть на root -> ... -> return_statement -> parenthesized_expression -> jsx_element
   # прямые дети jsx_element: jsx_opening_element / jsx_self_closing_element / jsx_expression /
   # jsx_closing_element — КАЖДЫЙ уже несёт имя тега, НЕ обёрнут в отдельный body_types-контейнер.
   ```

## Ключевые находки (уже сделаны, не передумывать заново)

1. **Просто добавить `jsx_element` в `named_def` — недостаточно.** `_has_body()`/
   `_is_standalone_body()` в `address.py` требуют, чтобы у узла БЫЛ child/сам узел был
   `body_types`-типа (фигурноскобочный foldable-регион). У JSX нет своих фигурных скобок — дети
   лежат прямо в узле, не в отдельной "body"-обёртке. Значит нужно ТАКЖЕ зарегистрировать
   JSX-типы в `body_types` — а это уже **общая, шаримая с C/C++/C#/CSS** машина (`_collect`
   используется для ВСЕХ brace-языков, не только TSX).
2. **Нельзя промоутить JSX огулом** — иначе `<div>`/`<span>` на любой глубине тоже станут
   landmark'ами, outline взорвётся шумом хуже прежнего плоского блоба. Естественный фильтр:
   **имя тега с большой буквы = React-компонент, с маленькой = нативный HTML** — но это ТЕКСТОВЫЙ
   предикат, а `named_def`/`body_types` сейчас — простое membership-тестирование по типу узла, без
   текстовой проверки.
3. **Предикат должен быть ОДИН и консультироваться в ОБОИХ движках** — `classify.py`'s
   `unwrap_def()` (карта, уже умеет кастомные проверки — `_arrow_binding_value` прецедент) И
   `address.py::_collect()` (адресация, сейчас работает НАПРЯМУЮ по сырым типам, в обход
   `unwrap_def`). Если сделать фильтр только в одном месте — карта и адресация разъедутся
   (нарушение инварианта #6, тот же класс бага, что чинили в августе — «ladder теряет имена,
   которые есть в outline», см. `cursor_feedback__gcb.md` запись «2026-08-23 — Ladder labels lose
   names»).
4. **Рекурсия — открытый вопрос, рекомендация: НЕ рекурсировать (v1).** У JSX нет отдельной
   "body"-обёртки для собственных детей (в отличие от `statement_block`), поэтому `body()`/
   `_own_end_row` не умеют естественно спускаться в JSX-узел ещё на уровень. Сделать промоутнутые
   JSX-landmark'и ЛИСТЬЯМИ (без дальнейшего спуска в их собственных детей) — закрывает исходную
   жалобу (один гигантский блоб → несколько именованных кусков) БЕЗ необходимости учить
   `body()`/`_own_end_row` новой JSX-специфике и без риска рекурсивного взрыва глубины.

## Рекомендуемый scope (v1, если/когда возьмёмся)

- Только `jsx_element`/`jsx_self_closing_element`, чьё имя тега начинается с ЗАГЛАВНОЙ буквы.
- Только ПРЯМЫЕ дети JSX-корня return'а (листья, без рекурсии вглубь — см. находку 4).
- Новый opt-in предикат в `LangSpec` (по образцу уже существующих `preprocess`/
  `is_synthetic_comment` — Vision05/SCSS-фикс той же сессии), консультируемый ОБОИМИ движками.
- `.ts`/`.js` (не-JSX грамматика) не затрагиваются — там таких node-типов физически нет.

## Что можем сломать / объём регресс-тестов

**Не TSX, а все brace-языки** — потому что трогаем `_collect`/`_has_body`/`_is_standalone_body` в
`address.py`, общие для C/C++/C#/CSS/TS/TSX. Нужен полный прогон `test/golden_check.py` +
`test/check.py` + `test/sweep_invariants.py` **на всех языках**, не только на новых TSX-фикстурах —
тот же протокол, что уже применялся для `.mjs`-маппинга (Vision05-сессия) и SCSS-маска-фикса.
Существующие TSX golden-фикстуры (outline/ladder на файлах с JSX) легитимно изменятся — нужно будет
их пересмотреть и перезаписать, не просто дежурно принять.

## Оценка

Не однострочный патч и не переписывание с нуля — «полдня-день» реальной работы с тестами: 2 новых
регистрации типов + новый кросс-движковый предикат + решение по рекурсии (рекомендация — не
рекурсировать, см. выше) + полный регресс на ВСЕХ brace-языках.
