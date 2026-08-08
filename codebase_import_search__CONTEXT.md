# codebase_import_search — Context & Specification

## Цель инструмента

Агент исследует файл → пишет карточку документации описывающую внешний интерфейс модуля → запускает утилиту `codebase_import_search` → видит что из этого файла реально импортируется и используется в других файлах проекта → корректирует описание публичного API.

**Ключевой вопрос:** ЧТО из исследуемого модуля является внешним интерфейсом (реально используется вовне)?

---

## Формат вывода — plain text, сжатый

```text
src/api/auth.py: [_secret_key]
src/tests/test_foo.py: [_internal_helper, _config]
src/logic/processor.py: [_internal_calc, _debug_log]
src/utils/helper.py: [_sync_internal_state]
```

Одна строка = один файл. Список уникальных символов целевого модуля, используемых в этом файле. Без JSON, без лишних заголовков, без дубликатов внутри файла.

---

## Ввод (CLI аргументы)

Агент передаёт:

- `--file PATH` или `--module NAME` — что ищем (путь к исследуемому файлу или имя модуля)
- `--aliases ALIAS1,ALIAS2,...` — список имён по которым этот модуль можно импортировать (имя файла без `.py`, имена публичных подмодулей). Агент сам извлекает их из карточки/файла.
- `--language LNG` — язык (по умолчанию Python)
- `--project-root PATH` — корень проекта для поиска (опционально, дефолт = текущая директория)

Пример запуска:
```bash
codebase_import_search --file "_core/secret.py" --aliases "secret,_secret_module" --language python
```

---

## Алгоритм обработки файла (Python)

Для каждого файла проекта (.py):

### Случай 1: `from <target> import X, Y as Z`
- Сразу фиксируем символы `X`, `Y` как внешние интерфейсы
- Дальнейший поиск этих имён в файле НЕ требуется
- Пример: `from secret import db_connect, _init as init` → фиксируем `[db_connect, _init]`

### Случай 2: `import <target> [as ALIAS]`
- Ищем все вхождения `ALIAS.something(...)` (или `target.something(...)`)
- Фиксируем ВСЁ что между алиасом и первой открывающей скобкой `(` — это путь к символу в файле
- Пример: `fa.foo.function()` → фиксируем `foo.function`
- Пример: `fa.db_connect()` → фиксируем `db_connect`
- Дубликаты внутри одного файла игнорируются

### Покрытие Python v1 — что ловим:
- `import foo` → alias = `foo`, ищем `foo.sym`
- `import foo as fa` → alias = `fa`, ищем `fa.sym`
- `from foo import bar` → сразу фиксируем `bar`
- `from foo import bar as b` → фиксируем оригинальное имя `bar`
- `from .foo import ...`, `from ..pkg.foo import ...` — относительные импорты (резолвим относительно файла)
- `import os, sys, foo as f` — множественный импорт, разбиваем и обрабатываем каждый
- Локальные импорты внутри функций — ловим (сканируем весь файл целиком)

### НЕ ловим в v1 (отложено на итерацию 2):
- Динамические импорты через `__import__('foo')`
- Runtime сборка имени строками (`getattr(sys.modules[...], ...)`)
- Импорт через `importlib.import_module()` без статического анализа

### Исключаемые папки/файлы (дефолт):
`.git`, `__pycache__`, `.venv`, `node_modules`, `dist`, `build`, `*.egg-info`, `__map`, `__HQ`

Для Python: сканируем только файлы `*.py`.

---

## Архитектура — модульная с начала

Файл движка: `codebase_import_search.py` в `__HQ/tools/`

```python
class LanguageHandler(ABC):
    """Абстрактный класс обработчика языка."""
    
    def extract_aliases(self, line) -> List[Tuple[alias, original_symbol]]:
        """Извлечь алиасы импорта из строки. Return list of (used_alias, original_name_or_None)."""
        
    def matches_target(self, import_line, target_names) -> bool:
        """Проверить, относится ли импорт к целевому модулю."""
        
    def find_usages_in_file(self, aliases, file_lines) -> Set[str]:
        """Найти все использования алиасов в файле. Return set of symbols used."""
```

PythonHandler встроен в файл как референс-реализация:
```python
class PythonHandler(LanguageHandler):
    ...
```

Другие языки подключаются позже через отдельные файлы или классы, импортируемые по имени языка:
```python
# Пример будущего TypeScript handler
from ts_handler import TSImportsHandler

handlers = {
    "python": PythonHandler(),
    "typescript": TSImportsHandler(),
}
```

---

## Ключевые решения и рассуждения

1. **Почему не JSON?** Потребитель — АИ агент, ему нужен читаемый plain text. Скобки JSON только шумят.

2. **Почему сжатый формат (`file: [symbols]`)?** Агенту важно знать ЧТО используется вовне, а не КАЖДУЮ строку использования. Дубликаты внутри файла не нужны — важен факт использования символа.

3. **Почему двухфазный поиск?** Просто grep по имени модуля даёт много шума и не показывает какие именно символы используются. Нужно: сначала определить как модуль импортирован (под каким алиасом), потом найти использование этого алиаса с точкой.

4. **`from foo import Y as Z` → фиксируем `Y`:** Важно вернуть оригинальное имя из целевого модуля, а не локальный алиас. Агент должен понять что именно экспортируется из исследуемого файла.

5. **Относительные импорты:** Нужно резолвить `from .db import X` относительно пути файла где стоит импорт, чтобы сопоставить с целевым модулем.

---

## Примеры работы

### Запрос: `codebase_import_search --file "foo.py" --aliases "foo"`

Файл 1 (`src/logic/processor.py`):
```python
import foo as fa
result = fa._internal_calc(data)
fa._debug_log('Processing started')
```
→ Вывод: `src/logic/processor.py: [_internal_calc, _debug_log]`  
(Всё между `fa.` и скобкой)

Файл 4 (`src/main.py`) — вложенные объекты:
```python
import foo as fa
fa.handlers.auth.process()
fa.config.get_value()
```
→ Вывод: `src/main.py: [handlers.auth.process, config.get_value]`  
(Сохраняем весь путь до скобки)

Файл 2 (`src/api/auth.py`):
```python
from foo import _secret_key as s
token = s.generate_token()
```
→ Вывод: `src/api/auth.py: [_secret_key]` (сразу из импорта, поиск не нужен)

Файл 3 (`src/utils/helper.py`):
```python
def sync_data():
    import foo as f
    f._sync_internal_state()
```
→ Вывод: `src/utils/helper.py: [_sync_internal_state]`

Итоговый вывод инструмента:
```text
src/api/auth.py: [_secret_key]
src/logic/processor.py: [_internal_calc, _debug_log]
src/main.py: [handlers.auth.process, config.get_value]
src/utils/helper.py: [_sync_internal_state]
```

---

## Границы ответственности инструмента

- ✅ Найти файлы, импортирующие целевой модуль
- ✅ Определить какие символы из целевого модуля используются в каждом файле
- ✅ Вернуть сжатый список `file: [symbols]` для каждого файла-потребителя
- ❌ НЕ анализировать AST на 100% — использовать regex/heuristics (достаточно для АИ)
- ❌ НЕ ловить runtime динамические импорты (v2+)
- ❌ НЕ показывать каждую строку использования — только уникальные символы

---

## Связь с остальной системой

Этот инструмент работает в связке с системой карточек документации (`validate_cards.py`, `card_format.py`). Агент использует результат для уточнения секции `Public API` в карточке исследуемого файла.

---

## Важное уточнение: алиас НЕ возвращается, возвращается путь до первой скобки

Алиас — это локальный артефакт файла-потребителя. Нам не интересен `fa`, нам интересны **символы внутри исследуемого файла**.

Правило простое: **всё между алиасом и первой открывающей скобкой `(` — это путь к символу в файле.** Мы импортировали ФАЙЛ, а не абстрактный модуль — поэтому сохраняем всю цепочку вызова до вызова функции.

### Пример 1: Импорт файла с простыми функциями

Исследуемый файл: `_core/auth.py`

```python
# src/app.py
import _core.auth as fa
fa.db_connect()        # → db_connect
fa._internal_calc()    # → _internal_calc
```

Вывод: `src/app.py: [db_connect, _internal_calc]`

### Пример 2: Импорт файла с вложенными объектами

Исследуемый файл: `src/auth.py` (внутри него есть объекты/классы `foo` и `boo`)

```python
# src/main.py
import src.auth as fa
fa.foo.function()      # → foo.function   (всё между fa. и скобкой)
fa.boo.function()      # → boo.function
```

Вывод: `src/main.py: [foo.function, boo.function]`

**Почему это правильно:**
- Различение: агент видит что `function` из `foo` и `function` из `boo` — разные вещи
- Точность: сохраняется вся цепочка вызова внутри файла
- Понятность: агент получает `foo.function`, заходит в `src/auth.py`, находит объект `foo` и метод `function`

### Пример 3: from-import (без алиаса)

```python
# src/api/auth.py
from _core.auth import db_connect, _init as init
token = init()
```

Вывод: `src/api/auth.py: [db_connect, _init]`  
Сразу из строки импорта. Оригинальные имена символов из целевого файла. Алиас `as init` не важен — мы знаем что `_init` используется.

### Почему это важно

Могут быть одинаковые символы в разных файлах одного импортирующего файла:
```python
import auth as fa
import db as da
fa.db_connect()    # db_connect из auth
da.db_connect()    # db_connect из db — другой файл!
```

Мы:
1. Знаем что `fa = auth` (целевой файл) → всё после `fa.` до `(` → символ из `auth`
2. `da = db` (не наш файл) → игнорируем

**Итоговое правило:** алиас импорта целевого файла — это «ключ». Снимаем его, возвращаем ВСЁ что между ним и первой скобкой `()` (путь к символу внутри исследуемого файла).
