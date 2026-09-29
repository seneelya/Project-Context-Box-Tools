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
