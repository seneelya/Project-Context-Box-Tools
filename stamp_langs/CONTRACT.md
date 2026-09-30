# CONTRACT — модуль языка штемпеля · **FROZEN 2026-09-30**

Сходятся **штемпель** (`make_interface_card.py`: `build_card`, `_cis_setup`, `_strip_decorators`,
`_stamp_all`) и **модули языков** (`stamp_langs/<lang>.py`). Расходятся молча: ключ, которого
модуль не отдал, превращается в пустую секцию карточки, а не в ошибку, — карточка «чистая» и врёт.

## Почему заморожено именно сейчас

Три производителя (python, typescript, csharp) уже дают одну и ту же форму — она устоялась.
Четвёртый (C/C++, Plan08) добавит поля; делаем это поправкой, а не молчаливым расширением.

## Форма 1 — атрибуты модуля

```python
NAME = "csharp"            # канон; ОБЯЗАН совпадать с именем в find_code_usage get_handler/get_resolver
EXTENSIONS = (".cs",)      # в нижнем регистре, с точкой; расширение принадлежит ОДНОМУ языку
ALIASES = ("cs",)          # необяз.; синонимы для --language / CONFIG__TOOLS.LANGUAGE
DECORATORS = ("public", …) # необяз.; служебные слова ПЕРЕД именем в сигнатуре (ключ merge)
```

Довод про `NAME`: штемпель берёт факты потребления/зависимостей у `find_code_usage` по этому
имени. Разойдутся — `ValueError` там, но только когда дойдёт до файла этого языка.

## Форма 2 — `declared(project_root, target_abs) -> dict`

```python
{
  "docstring_first": "Первая строка докстринга" | None,
  "exports":  [{"name": "Foo", "kind": "class", "signature": "public class Foo", "methods": [...]}],
  "all_defs": {"Foo": "public class Foo", "_helper": "def _helper(x)"},   # ВСЁ определённое, вкл. приватное
  "reexports": [{"name": "bar", "source": ".mod", "module": "mod", "level": 1}],  # module/level — необяз.
}
```

- `exports` — объявленная поверхность (Public API карточки); `kind` раскладывается по H3 через
  `_KIND_H3` штемпеля, незнакомый `kind` → «Objects» (не ошибка).
- `all_defs` — нужен для «Consumed internals»: символ, который импортируют снаружи, но его нет
  в `exports`. Пустой `all_defs` молча прячет утечки приватного — поэтому ключ обязателен.
- Файл не читается → вернуть пустую форму (`_common.empty()`), не бросать.
- Проверка: `Lang.declared_surface` бросает `ValueError`, если нет одного из четырёх ключей.

## Форма 3 — необязательные хуки (умолчания — `_Defaults` в `__init__.py`)

| хук | когда нужен | умолчание |
|---|---|---|
| `extra_target_names(handler, target_abs) -> set` | язык импортирует не файл, а имя (C# — namespace) | `set()` |
| `reexport_signature(target_abs, reexport) -> str\|None` | сигнатуру ре-экспорта можно достать из соседа (Python) | `None` → имя |

## Что сознательно НЕ в контракте

- Как модуль добывает объявления (ast / tree-sitter / regex) — его дело; `_common.brace_declarations`
  — удобство, не обязанность.
- Формат карточки — `CARD_FORMAT.py`; факты потребления/зависимостей — `find_code_usage`.
- Порядок языков в реестре не значим (расширения не пересекаются).

## Как менять

Новый язык: модуль + имя в `_MODULES`, штемпель не трогать. Новое поле формы — ПОПРАВКА снизу
с датой и доводом + обновить всех производителей + тест в `test/test_cardstamp.py`
(`test_stamp_langs_registry`). Заморозку не переписывать.

— Опус5.5 (Claude Opus 5.5), 2026-09-30, Plan08 шаг 0, по решению Натальи («модульность, а не if»)

## ПОПРАВКА 1, 2026-09-30 — C/C++: условие у объявления и два хука (Plan08 шаги 2–7)

Четвёртый производитель (`cpp.py`) показал три недоспецифицированных места:

- **`exports[].cond`** — НЕОБЯЗАТЕЛЬНОЕ поле: `#if`-условие, под которым стоит объявление
  (`"GGML_USE_HIP"`, `None` = безусловно). Штемпель пишет его отдельной факт-строкой
  `condition: X` под `####`, НЕ в сигнатуру: сигнатура — ключ merge, а `(` внутри
  `[if defined(X)]` сбил бы поиск имени. Остальные языки поле не отдают — это не ошибка.
- **Хук `entry_key(signature) -> str | None`** (умолчание `None` = общее правило по позиции).
  Довод: общее правило берёт `void` в `typedef void (*cb)(int)` и `#define` в `#define X 4` —
  имя в C/C++ не всегда перед `(`/`=`. Язык знает форму своих сигнатур лучше штемпеля.
- **Хук `fact_sections(project_root, target_abs, declared) -> [(title, [lines])]`** (умолчание
  `[]`). Секции ЧИСТОГО факта, которые штемпель вставляет перед `How it works` и пересобирает на
  каждом проходе (`_parse_old_prose` их не знает — старое не переживает merge). C/C++ отдаёт
  `## Build facts` (`CARD_FORMAT.BUILD_FACTS_SECTION`). Прозу туда не писать.

Тест формы — `test/test_cpp.py` (`test_entry_key`, `test_stamp_cards`, `test_merge_and_validate`).

— Опус5.5 (Claude Opus 5.5), 2026-09-30

## ПОПРАВКА 2, 2026-09-30 — хук `import_line(line) -> bool` (Plan09 шаг 1, найдено замером)

`## External Dependencies` = список внешних импортов (ФАКТ, `raw_line` резолвера, пересобирается)
+ строка агента. Merge отделял факт от прозы по префиксам Python (`import `/`from `), поэтому
`#include <memory>` (C/C++) и `using System;` (C#) считались прозой и копились на каждой
перештамповке (llama `ggml-cpp.h.md` — 4 копии). Хук: язык сам говорит, похожа ли строка на его
импорт. Умолчание — Python-префиксы; `typescript` — `import`/`export`/`require(`; `csharp` —
`using`; `cpp` — `#include`. Тест — `test/test_cpp.py::test_merge_and_validate` (идемпотентность).

— Опус5.5 (Claude Opus 5.5), 2026-09-30

## ПОПРАВКА 3, 2026-09-30 — хук `api_families(project_root, target_abs, declared) -> list | None` (Plan09 шаг 3)

Где исходник САМ интерфейс (C/C++-заголовок), карточка не копирует сигнатуры (Vision10 §3).
Язык решает форму Public API, штемпель рендерит:
- `None` (умолчание) — как раньше, записи `####` из `declared["exports"]`.
- список семейств `[{name, how, decls: [имена], first, last}]` — форма «API: in source»
  (`CARD_FORMAT` 1.3.0): строка-маркер + таблица семейств + проза `### What each family is for`
  по имени семейства; `exports` записями НЕ рендерятся. Имена семейств уникальны в карточке
  (ключ прозы). `cpp` отдаёт семейства для заголовков, `None` — для реализаций.
Тест — `test/test_cpp.py` (`test_families`, `test_stamp_cards`, `test_merge_and_validate`).

— Опус5.5 (Claude Opus 5.5), 2026-09-30
