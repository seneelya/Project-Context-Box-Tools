# План реализации `--incoming` (upstream dependencies) для codebase_import_search

## Контракт нового режима

**Цель:** показать откуда целевой файл импортирует символы — резолвить имена модулей в файлы внутри project-root.

### Формат вызова

```bash
python codebase_import_search.py --incoming --file "_engine/embed.py" --project-root "/workspace/SRC/memohood"
```

Один флаг `--incoming` переключает режим. Все остальные флаги те же:
- `--file / --module`, `--project-root`, `--language` — общие с текущим режимом ✓
- `--tests-only`, `--module-names` — игнорируются в incoming режиме

### Формат вывода (plain text)

```
# N imports resolved to M files inside project root
import foo as fa          -> _engine/foo.py             [alias: fa]
from bar import baz       -> utils/bar.py               [symbol: baz]
from .relative import x   -> ./relative.py              [symbol: x]
import sys                -> [stdlib — ignored]
import numpy as np        -> [third-party — ignored]
```

Правила:
- Показываем ТОЛЬКО импорты которые резолвились в файлы внутри project-root
- Stdlib и third-party (за пределами project-root) помечаем как `[ignored]` или не показываем вообще — обсуждаю ниже
- Пути относительны к project-root

### Архитектура кода

```
codebase_import_search.py          # роутер: --incoming? → resolver / else handler
├── codebase_import_search/
│   ├── core.py                    # +ImportResolver(ABC) рядом с LanguageHandler(ABC)
│   ├── handlers/                  # существующие (downstream consumers)
│   │   ├── python_handler.py
│   │   ├── ts_handler.py
│   │   └── csharp_handler.py
│   └── resolvers/                 # НОВЫЙ пакет (upstream dependencies)
│       ├── __init__.py            # get_resolver(language) — аналог handlers/__init__.py
│       ├── python_resolver.py     # resolve_imports(target_file, project_root) → list[ImportInfo]
│       ├── ts_resolver.py         # то же для TS/JS
│       └── csharp_resolver.py     # то же для C#
```

### Data structure: ImportInfo

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ImportInfo:
    raw_line: str          # исходная строка импорта (trimmed)
    module_name: str       # имя модуля/namespace из импорта
    symbol_names: list[str] | None   # конкретные символы (для from X import Y,Z)
    resolved_path: str | None        # абсолютный путь к файлу-источнику внутри project-root
```

---

## Этап 0: Подготовка и анализ (DONE)

- [x] Прочитать текущий код: `codebase_import_search.py`, `core.py`, хендлеры — понять точки расширения
- [x] Сформулировать точный контракт нового режима (вход → выход, формат)
- **Коммит:** не нужен

---

## Этап 1: Python resolver (MVP на одном языке)

**Задача:** реализовать резолвинг Python-импортов в файлы.

### Алгоритм python_resolver.resolve_imports(target_file, project_root):

1. Парсить импорты из target_file (те же regex что в python_handler или переиспользовать его логику)
2. Для каждого импорта:
   - Извлечь module_name и dots (для relative imports)
   - Попытаться резолвить в файл через `_resolve_module_to_path(module_name, project_root)`
3. Отфильтровать: показать только те где resolved_path внутри project-root

### Функция _resolve_module_to_path (Python):

Вход: `module_name` (dotted string, e.g. "_engine.foo"), `project_root`, `importing_file_dir` (для relative imports)  
Выход: absolute path to .py file or None

Стратегия:
1. Если module_name содержит `/` или начинается с `.` → это уже путь, нормализовать относительно importing_file_dir
2. Иначе dotted name: попробовать как путь `_engine/foo.py` → `_engine/foo/__init__.py`
3. Убедиться что результат внутри project-root (для безопасности)

**Тестовые файлы:**
- Новый функционал: `_engine/embed.py` из memohood (импорты: `_engine.backends`, etc.)
- Regression: старый тест `_engine/backends/__init__.py` без --incoming → тот же результат

### Чеклист:
- [ ] Создать структуру `resolvers/` рядом с `handlers/`
- [ ] Добавить `ImportResolver(ABC)` в `core.py`
- [ ] Реализовать `python_resolver.py`
- [ ] Зарегистрировать resolver в `resolvers/__init__.py`
- [ ] Добавить флаг `--incoming` в CLI, подключить resolver для Python
- [ ] Тестирование + regression check
- **Коммит:** `feat: add --incoming mode with Python resolver`

---

## Этап 2: TypeScript resolver

**Задача:** резолвить ES modules + CommonJS require в файлы.

### Алгоритм ts_resolver.resolve_imports(target_file, project_root):

1. Парсить import/require строки из target_file
2. Для каждого specifier:
   - Если начинается с `.` или `/` → relative path resolution (добавить .ts/.tsx/.js/.jsx + index.)
   - Иначе если содержит `/` и не начинается с `http://` → bare path внутри проекта
   - Иначе → node_modules / external package → игнорировать
3. Проверить что resolved_path внутри project-root

**Тестовые файлы:**
- Новый функционал: `src/analyzer.ts` из ts-prune
- Regression: старый тест `src/state.ts` без --incoming → тот же результат

### Чеклист:
- [ ] Реализовать `ts_resolver.py`
- [ ] Тестирование + regression check
- **Коммит:** `feat(ts): add TypeScript resolver for --incoming mode`

---

## Этап 3: C# resolver

**Задача:** резолвить using directives в файлы.

### Алгоритм csharp_resolver.resolve_imports(target_file, project_root):

1. Парсить `using X.Y.Z;` директивы из target_file
2. Для каждого namespace:
   - Искать .cs файлы внутри project-root где `namespace X.Y.Z { ... }` или file-scoped `namespace X.Y.Z;`
   - Вернуть список файлов (может быть много — namespace может размазан по файлам)
3. Если namespace не найден → [not found in project root]

**Тестовые файлы:**
- Новый функционал: файл из CoreSharp с using directives
- Regression: старый тест `IGlobalStopWatch.cs` без --incoming → тот же результат

### Чеклист:
- [ ] Реализовать `csharp_resolver.py`
- [ ] Тестирование + regression check
- **Коммит:** `feat(csharp): add C# resolver for --incoming mode`

---

## Этап 4: Финальная проверка и документация

### Чеклист:
- [ ] Запустить полный набор regression tests на всех языках (оба режима: default + incoming)
- [ ] Обновить `codebase_import_search__TLDR.md` — добавить описание `--incoming`
- [ ] Обновить `codebase_import_search__README.md` — примеры использования нового режима
- [ ] Обновить `HowTo__Test-codebase_import_search.md` — добавить тестовые команды для incoming mode
- **Коммит:** `docs: document --incoming mode across all docs`

---

## Что НЕ делаем в этом плане (out of scope)

- Транзитивные зависимости (только прямые импорты из целевого файла)
- Transpiled/generated files detection
- Сложный tsconfig path alias resolution (начинаем с relative imports + базового поиска)
- Circular dependency detection
- JSON output (пока только plain text)
