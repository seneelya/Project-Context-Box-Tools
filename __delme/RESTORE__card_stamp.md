# RESTORE — card stamp work stream (context anchor)

> Точка восстановления для текущего потока: **штемпель карточки `make_interface_card.py`** —
> мультиязычный, факто-заполненный скелет карточки. Читай ТОЛЬКО перечисленное ниже, по
> порядку; не перечитывай исходные деревья фикстур и не блуждай по репо.

## Что читать, чтобы вспомнить (по порядку, минимум)

1. **`__HQ/DECISIONS.md`** — закрытые решения (card stamp, tree-sitter опционален, границы). Не релитигировать.
2. **Хвост `__HQ/TRACKER.md`** — лог прогресса (строки `✅`), последние = где мы.
3. **`make_interface_card.py`** — сам штемпель; докстринг вверху объясняет замысел и три факта.
4. **`CARD_FORMAT.py`** — контракт формата; докстринг = точный скелет карточки (H1→summary→`## H2_SECTIONS`→`### H3_API_SUBSECTIONS`→`#### запись: строка-факт + строка-директива`).
5. **`test/README.md`** — фикстуры и оракул (кратко).

Глубже — только если правишь конкретный слой:
- declared surface (declarations): regex — `get_codeblock/handlers/{typescript,csharp}_handler.py::declarations`; опц. tree-sitter — `get_codeblock/handlers/{ts,cs}_treesitter.py`; переключатель — `CONFIG__TOOLS.DECL_BACKEND` (auto|treesitter|regex).
- reverse index / consumed surface: `find_code_usage/handlers/*`, `resolvers/*`.

## Суть (одной сутью)

`py make_interface_card.py <file> --project-root R` → готовый `.md`-скелет карточки: ФАКТЫ заполнены
детерминированно (объявленный API+сигнатуры × кто реально потребляет × зависимости),
проза — строки-директивы `<Agent: …>`, которые ЛЛМ дописывает по исходнику.

Три факта, три источника: **declared** (Python→`py_api` ast; TS/C#→`get_codeblock declarations`,
опц. tree-sitter), **consumed surface** (`find_code_usage` downstream), **deps**
(`--incoming`). Формат — из `CARD_FORMAT.py`. Public API = что выходит наружу
(свои публичные / протёкшие `_`-приватные-consumed / чужие ре-экспорты); Dependencies = что входит.

## Ключевые контракты (детали — в DECISIONS)

- Уровни `get_codeblock`: `1 + объемлющие тела`, корень=1, `0` — только адресация.
- Пути в выводе всегда `/`; UTF-8 stdout; строка факта = `consumers N: файлы` / `consumers 0`.
- **tree-sitter** улучшает ТОЛЬКО declarations; резолюцию (`.js`→`.ts`) и обратный индекс НЕ трогает — они наши.
- Нет либы в auto/treesitter → один раз stderr-WARNING (pip-пакет + «regex fallback»); forced `regex` молчит.
- **Три C#-связи потребления** (все покрыты в `csharp_handler.analyze_file`): same-namespace,
  explicit `using` (cross-namespace), descendant→ancestor (дочерний namespace видит родителя без `using`).

## Проверка / оракул

- `py test/check.py --fails` — регрессия (сейчас **49/0**). Оракул — глаза человека; golden можно править/дополнять после ручной сверки.
- Фикстуры: memohood(py) · zod v4/core(ts) · SwarmUI Core + Unity Services(cs, вкл. 79KB генерённый). Образцы карточек — `test/__map/**` (не закоммичены, для просмотра).
- **Не гонять golden после каждой правки** (он покрывает get_codeblock+import_search, НЕ make_interface_card/format/py_api).

## Открытые задачи (остаток)

1. **golden-lock** новых кейсов: tsSRC2 incoming `.js`→`.ts`; csharpSRC2 same-namespace consumers + declarations; unitySRC descendant-visibility (сверено глазами — фиксировать в `expected.py`).
2. **Скилл `MakeCard`** переписать штемпель-первым (старый механизм = фолбэк) — ждёт стабилизации формата.
3. Косметика: `Kind=type` для type-only TS-импортов; regex-TS тоже срезать `export `-префикс (единообразие с tree-sitter).

## НЕ делать при восстановлении

Не перечитывать исходные деревья фикстур целиком; не релитигировать DECISIONS; не менять
`DECL_BACKEND`-контракт без явной причины; штемпель править пачкой, golden — один раз в конце.
