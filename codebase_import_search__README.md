# codebase_import_search — поиск реального публичного API модуля

## Цель инструмента

Два режима работы:

- **Default mode (downstream consumers)** — агент исследует файл → пишет карточку документации описывающую внешний интерфейс модуля → запускает утилиту `codebase_import_search` → видит что из этого файла реально импортируется и используется в других файлах проекта → корректирует описание публичного API.
  - **Ключевой вопрос:** ЧТО из исследуемого модуля является внешним интерфейсом (реально используется вовне)?

- **`--incoming` mode (upstream dependencies)** — показывает откуда целевой файл берёт свои зависимости: каждый исходный файл внутри project-root перечислен с символами, которые из него импортируются. Внешние пакеты/stdlib сгруппированы внизу как `[external]: <import_line>`.
  - **Ключевой вопрос:** ОТКУДА этот модуль импортирует символы? Где определены его зависимости?

- **`--verbose` mode (per-symbol detail)** — группирует вывод default mode по символам вместо файлов: для каждого символа показывает все файлы и точные номера строк где он используется, тип загрузки (lazy/top-level/conditional/fallback) и глубину блока на этой строке. Символы, которые импортируются, но нигде не используются, выносятся в раздел `# dangling imports`. Включает самодокументирующую легенду формата на первой строке.
  - **Ключевой вопрос:** ГДЕ именно (в каких файлах на каких строках и в каком контексте) используется каждый конкретный символ моего API?

- **`--incoming --verbose` mode** — для каждого импортированного символа: его файл-источник + где символ используется ВНУТРИ таргет-файла (строки + уровни блоков). Это прямой вход для `get_codeblock`: берёшь строку → пристрелка до объемлющего блока. Незадействованные внутри таргета импорты — в раздел `# dangling imports`.
  - **Ключевой вопрос:** Откуда пришёл символ и где я его использую в ЭТОМ (возможно, огромном) файле?

- **`--symbol N1,N2,...` filter** — пост-фильтр вывода по имени символа(ов), работает во всех режимах (фильтрует готовые данные, не логику). Для случая «мне важен фан-ин/фан-аут одного символа».

Инструмент сканирует весь проект и находит все файлы, которые импортируют целевой модуль, а затем определяет какие именно символы (функции, классы, константы) из него используются в каждом файле-потребителе.

---

## Пример работы

Запрос:
```bash
cd /workspace/SRC/memohood
python3 codebase_import_search.py --file "_engine/backends/__init__.py" --module-names "backends"
```

Вывод:
```text
# 10 files, 15 unique symbols

_engine/backends/chat.py: [BackendError, _build_headers, _post_with_retries]
_engine/embed.py: [lazy: _embed_once, embed, resolve_chain]
selftest.py: [BackendError, _RERANK_PROVIDERS, chat, is_local_backend, rerank, resolve_chain]
plugin_loader.py: Possible Dynamic import [__import__, import_module]
...
```

**Что это значит:** модуль `_engine/backends/__init__.py` используется в 10 других файлах. В `selftest.py` из него берутся конкретные символы: `resolve_chain`, `chat` и др. Это — реальный публичный API этого модуля (даже если некоторые символы начинаются с подчёркивания).

**Маркеры:**
- `[symbol]` — top-level импорт (загружается сразу при инициализации модуля)
- `[lazy: symbol]` — ленивый импорт внутри функции/метода (загрузится только при вызове)
- `[conditional: x]` — условный импорт в if блоке (только при определённых условиях)
- `[fallback: y, z]` — опциональный импорт в try/except (fallback паттерн)
- `Possible Dynamic import [...]` — динамический доступ через строковое имя модуля (точные символы неизвестны)

---

## Инструкция по использованию

### Параметры CLI

| Параметр | Описание | Пример |
|----------|----------|--------|
| `--file PATH` | Путь к исследуемому файлу (относительный от project-root или абсолютный) | `_engine/auth.py`, `src/analyzer.ts` |
| `--module NAME` | Имя модуля (альтернатива --file; в v1 не используется активно) | `auth_module` |
| `--module-names N1,N2,...` | Дополнительные имена по которым этот модуль можно импортировать | `_secret_module,auth_core` |
| `--language LNG` | Язык обработчика/резолвера (поддерживает Python, TypeScript/JS, C#). По умолчанию автодетект по расширению файла или python | `python`, `typescript`, `csharp` |
| `--incoming` | Показать upstream зависимости (откуда целевой файл импортирует символы) вместо downstream consumers | (без значения) |
| `--verbose` | Группировать вывод по символам с номерами строк, типами загрузки и уровнями блоков (работает только в default mode); добавляет легенду формата | (без значения) |
| `--project-root PATH` | Root directory to scan for imports (default from CONFIG__TOOLS.py or current dir) | `/workspace/SRC/memohood`, `.` |
| `--tests-only` | Show usages only from configured test directories (reveals API covered by tests) | (no value needed) |
| `--symbol N1,N2,...` | Post-filter output to these symbol name(s). Works in every mode (filters the produced data, not the logic) | `resolve_chain`, `chat,embed` |

### Режимы работы

**Default mode (downstream consumers)** — без флага `--incoming`:
Показывает кто использует символы из целевого файла. Формат вывода:
```text
# N files, M unique symbols (+K with dynamic access)
path/to/file1.py: [symbol1] [lazy: symbol2]
path/to/file2.ts: [SymbolA, SymbolB]
```

**`--incoming` mode (upstream dependencies)** — с флагом `--incoming`:
Показывает откуда целевой файл импортирует символы. Формат вывода:
```text
# N imports in target, M resolved to K unique sources
_engine/__init__.py: [backends, db]
_engine/security.py: [DEFAULT_USER_AGENT]

# external (P not resolved in project):
  import logging
  from typing import Any, Dict, List
```

(Формат `file: [symbols]` совпадает с default mode для консистентности. Пути всегда `/`.
Внешние/нерезолвнутые импорты собраны в раздел `# external (...)`.)

**`--incoming --verbose`** — сгруппировано по файлу-источнику; под каждым — символы и где
они используются внутри таргет-файла (строки + уровни блоков через `get_codeblock`).
Группировка по источнику (а не по символу как в default verbose), потому что incoming
работает над ОДНИМ файлом, куда входит много источников:
```text
# N imports in target, M resolved to K unique sources
# Format: source_file -> symbol: used in target lines=[..] levels=[..]

_engine/backends/_http.py:
  BackendError: lines=[51, 136, 154] levels=[0, 2, 3]
  _post_with_retries: lines=[59] levels=[0]
_engine/backends/resolve.py:
  resolve_chain: lines=[72, 131, 200, 270] levels=[0, 1, 2, 2]

# dangling imports (imported, not used in target):
  IConfigInterface <- src/configurator.ts
```

**`--verbose` mode (per-symbol detail)** — в default mode с флагом `--verbose`:
Группирует вывод по символам вместо файлов, показывая точные номера строк использования, тип загрузки и глубину блока на каждой строке. Формат вывода:
```text
# N files, M unique symbols (+K with dynamic access)
# Format: Symbol -> load_type: file_path: lines=[usage_line_numbers] levels=[block_depths]

BackendError:
  top-level: _engine/backends/chat.py: lines=[52, 81, 83] levels=[1, 2, 2]
_embed_once:
  lazy: _engine/embed.py: lines=[18, 495] levels=[1, 0]
backends:
  fallback: _lab/backends_cfg.py: lines=[1, 6, 11] levels=[0, 1, 1]
```

Типы загрузки:
- `top-level` — символ импортирован на уровне модуля (загружается сразу)
- `lazy` — импорт внутри функции/метода (ленивая загрузка при вызове)
- `conditional` — импорт в if блоке (условная загрузка)
- `fallback` — импорт в try/except (опциональная зависимость)

Уровни блоков (`levels=[]`) показывают глубину вложенности на каждой строке использования:
- level 0 = код на уровне модуля (top-level, обычно публичный API или инициализация)
- level 1+ = внутри функции/класса (чем выше число, тем глубже вложенность)

### Примеры запуска default mode (downstream consumers)

**Базовый случай:** исследуем файл внутри текущего проекта:
```bash
cd /workspace/SRC/memohood
python3 codebase_import_search.py --file "db.py"
```

**С дополнительными именами модуля:** если модуль импортируют под разными именами:
```bash
python3 codebase_import_search.py --file "_core/secret.py" --module-names "_secret_module,auth_core"
```

**Явный project-root:**
```bash
cd /workspace/SRC/memohood
python3 codebase_import_search.py --file "_engine/backends/__init__.py" --project-root "."
```

### Примеры запуска `--incoming` mode (upstream dependencies)

**Python:** показать зависимости файла `_engine/embed.py`:
```bash
cd /workspace/SRC/memohood
python3 codebase_import_search.py --incoming --file "_engine/embed.py"
# Вывод:
# # 12 imports in target, 3 resolved to 2 unique sources
# _engine/__init__.py: [backends, db]
# _engine/security.py: [DEFAULT_USER_AGENT]
# [external]: import logging
```

**TypeScript:** показать зависимости файла `src/analyzer.ts`:
```bash
cd /workspace/SRC/ts-prune
python3 codebase_import_search.py --incoming --file "src/analyzer.ts"
# Вывод:
# # 8 imports in target, 6 resolved to 6 unique sources
# src/configurator.ts: [IConfigInterface]
# src/constants.ts: [ignoreComment]
# [external]: import {(10 symbols) from "ts-morph"};
```

**C#:** показать зависимости файла `GlobalStopWatchInstance.cs`:
```bash
cd /workspace/SRC/CoreSharp
python3 codebase_import_search.py --incoming --file "source/CoreSharp/Utilities/GlobalStopWatchInstance.cs"
# Вывод:
# # 4 imports in target, 1 resolved to 1 unique source
# source/CoreSharp/Interfaces/IGlobalStopWatch.cs: [IGlobalStopWatch]
# [external]: using System;
```

**Автодетект языка:** достаточно указать `--file` — язык определяется по расширению:
```bash
python3 codebase_import_search.py --incoming --file "src/state.ts" --project-root "/workspace/SRC/ts-prune"
```

**C# на больших проектах:** SWARM_SRC и Unity (автодетект по .cs):
```bash
python3 codebase_import_search.py --incoming --file "Backends/BackendHandler.cs" --project-root "/workspace/SRC/test_SWARM_SRC"
python3 codebase_import_search.py --incoming --file "Code/Core/Common/Commands/HttpCmd.cs" --project-root "/workspace/SRC/test_Unity"
```

### Формат вывода default mode (downstream consumers)

**Первая строка — саммари:**
```text
# N files, M unique symbols (+K with dynamic access)
```
- `N` — количество файлов проекта, которые используют целевой модуль через статические импорты
- `M` — общее количество уникальных символов из целевого модуля, используемых во всём проекте
- `(+K with dynamic access)` — опционально: файлы с динамическим доступом через строки (точные символы неизвестны)

Если ничего не найдено:
```text
# No external usages found.
```

**Каждая последующая строка — один файл-потребитель:**
```text
path/to/file.py: [symbol1, symbol2] [lazy: symbol3] [fallback: symbol4]
```
- `path/to/file.py` — путь файла относительно project-root
- Символы сгруппированы по типу импорта (см. маркеры выше), внутри группы отсортированы по алфавиту
- Файлы отсортированы по пути

Файлы с динамическим доступом выводятся отдельно:
```text
plugin_loader.py: Possible Dynamic import [__import__, import_module]
```

### Обработка ошибок

| Ситуация | Поведение |
|----------|-----------|
| Не указан `--file` или `--module` | Показывает help + ошибку → exit(1) |
| Указанный файл не существует | Ошибка с полным путём файла → exit(1) |
| project-root не является директорией | Ошибка с путём → exit(1) |
| Язык не поддерживается (не python в v1) | Ошибка «not supported yet» → exit(1) |

Все ошибки выводятся в stderr. Успешный запуск — exit(0).

---

## Механизм работы (без чтения кода)

### Шаг 1: Определение имён целевого модуля

Инструмент должен понимать под какими именами целевой файл может быть импортирован из других файлов проекта. Он автоматически генерирует список target names из пути файла:

| Исходный файл | Автоматически добавленные имена |
|---------------|----------------------------------|
| `db.py` (в корне пакета) | `db`, `memohood.db` |
| `_engine/auth.py` | `auth`, `_engine.auth`, `memohood._engine.auth` |
| `_engine/backends/__init__.py` | `backends`, `_engine.backends`, `memohood._engine.backends` |

Плюс все имена из `--module-names` добавляются к этому списку.

### Шаг 2: Сканирование файлов проекта

Инструмент рекурсивно обходит project-root и собирает все `.py` файлы, исключая известные директории:
`.git`, `__pycache__`, `.venv`, `node_modules`, `dist`, `build`, `*.egg-info`, `__map`, `__HQ`.

Целевой файл исключается из результатов (мы не ищем импорты самого себя).

### Шаг 3: Анализ каждого файла — два типа импорта

Для каждого файла проекта инструмент ищет импорты через regex-паттерны (не AST) и определяет относятся ли они к целевому модулю.

#### Тип А: `from X import Y, Z as W` → символы фиксируются сразу

Правила:
1. Парсится строка импорта и определяется от какого модуля идёт импорт
2. Если это относительный импорт (`from .foo import bar`), точки резолвятся относительно директории файла-потребителя
3. Проверяется относится ли imported module к target names
4. **Если да:** все имена после `import` фиксируются как используемые символы целевого модуля
   - `from foo import db_connect, _init as init` → фиксируем `[db_connect, _init]` (оригинальные имена)

**Специальный случай — импорт целого пакета:**
```python
from ._engine import backends as _backends
```
Если `backends` это целевой пакет (`_engine.backends` в target names), то `_backends` не фиксируется как символ. Вместо этого он записывается как alias для следующего шага (Тип Б).

#### Тип Б: `import X [as ALIAS]` → поиск attribute access по алиасу

Когда модуль импортирован целиком (`import foo as fa`) или пакет через from-import (см. выше), нужно найти что именно из него используется:

1. Алиас (или имя без `as`) записывается как mapping к целевому модулю
2. По всему файлу ищутся вхождения `ALIAS.` с помощью regex
3. Всё что между алиасом и границей токена — это путь к символу внутри целевого файла:
   - Граница токена: пробел, конец строки/выражения, оператор (`+`, `=`, `,`, `)`, `;`, `[`, `:`)

Примеры:
```python
import _core.auth as fa

fa.db_connect()              # → db_connect
fa.foo.function()            # → foo.function (вложенный доступ)
x = fa.CONSTANT              # → CONSTANT (нет скобок, но есть атрибутный доступ)
y = some_func(fa.handler)    # → handler (передан как аргумент без вызова)
```

### Шаг 4: Фильтрация ложных срабатываний

Regex-based подход не идеален — он видит текст, а не AST. Чтобы уменьшить шум применяются простые фильтры:

- Символы длиной ≤ 3 буквы (только буквы), которые выглядят как расширения файлов (`py`, `md`, `txt`) — игнорируются. Это ловит ложные срабатывания на строках вроде `"module.py"` в docstring или комментариях.

### Шаг 5: Вывод результатов

- Символы из каждого файла объединяются (дедуплицируются)
- Файлы отсортированы по пути относительно project-root
- Символы внутри каждого файла отсортированы по алфавиту
- Первая строка содержит саммари: количество файлов и уникальных символов

---

## Что ловим (v1.2 для Python)

✅ `import foo` → alias = `foo`, ищем `foo.sym`  
✅ `import foo as fa` → alias = `fa`, ищем `fa.sym`  
✅ `from foo import bar` → сразу фиксируем `bar`  
✅ `from foo import bar as b` → фиксируем оригинальное имя `bar`  
✅ `from .foo import ...`, `from ..pkg.foo import ...` — относительные импорты (резолвим относительно файла)  
✅ `import os, sys, foo as f` — множественный импорт в одной строке  
✅ Локальные импорты внутри функций (сканируем весь файл целиком)  
✅ Multiline imports: `from module import (\n    name1,\n    name2\n)`  
✅ Атрибутный доступ без скобок: `fa.CONSTANT`, `some_func(fa.handler)`  
✅ Детекция типа импорта: top-level / lazy / conditional / fallback  
✅ Dynamic/runtime imports: `__import__('target')`, `sys.modules['target']`, `importlib.import_module('target')`

## НЕ ловим (отложено на будущие версии)

❌ Полное извлечение символов из dynamic imports (только флажим что есть)  
❌ Runtime сборка имени строками (`getattr(sys.modules[...], ...)`) без прямого упоминания target name  
❌ Языки кроме Python, TypeScript/JS, C# — но архитектура готова для расширения через LanguageHandler

---

## Архитектурное примечание

Инструмент спроектирован модульно с самого начала:

- `LanguageHandler(ABC)` — абстрактный класс обработчика языка в `codebase_import_search/core.py`
- Реализации по языкам в отдельных файлах:
  - `handlers/python_handler.py` — PythonHandler (static imports, dynamic detection, import kinds)
  - `handlers/ts_handler.py` — TypeScriptHandler (ES modules, CommonJS require, namespace imports)
  - `handlers/csharp_handler.py` — CSharpHandler (using directives, namespace extraction from source files)
- Реестр хендлеров в `handlers/__init__.py`: `get_handler('python')`, `get_handler('typescript')`, ...

Это позволяет добавлять поддержку новых языков без переписывания ядра.

---

## Default values from CONFIG__TOOLS.py

If `./CONFIG__TOOLS.py` exists and defines valid paths/languages, the tool reads defaults automatically:

| Config constant | Used as default for | Cascade priority |
|-----------------|---------------------|------------------|
| `PROJECT_ROOT` | `--project-root PATH` | CLI flag > config value > current dir (`.`) |
| `LANGUAGE` | `--language LNG` | CLI flag > auto-detect from file extension > config value > `python` |
| `TEST_DIRS` | Test directories to exclude/include | Config value > empty list (no exclusions) |

**How it works:**
1. Tool loads `CONFIG__TOOLS.py` at startup (optional — if missing, prints warning and uses hardcoded defaults)
2. `PROJECT_ROOT` is computed by `_resolve_root([...])` which returns the first existing path from a list of candidates (works across Docker/Windows/Linux without environment detection)
3. When config is present, agent only needs to specify `--file PATH` or `--module NAME`; project root and language are taken from config automatically

**Auto-detect language from file extension:**
- When `--file PATH` is provided and `--language` is not explicitly set, tool automatically detects language from file extension:
  - `.ts`, `.js` → TypeScript handler
  - `.cs` → C# handler  
  - `.py` → Python handler
- This uses the same cascade priority mechanism, so explicit CLI flag still takes precedence over auto-detection

**Test directory exclusion:**
- By default, files under directories listed in `TEST_DIRS` (relative to PROJECT_ROOT) are **excluded** from scanning
- Use `--tests-only` flag to show usages **only from test directories** (reveals what public API is covered by tests)
- Example: if production scan shows 10 symbols but `--tests-only` shows 7, then 3 symbols have no test coverage

This simplifies CLI for agents working on a specific project — no need to repeat the same paths/languages in every command.
