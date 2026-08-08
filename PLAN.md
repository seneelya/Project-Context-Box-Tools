# План реализации codebase_import_search — v1 (Python)

## Фаза 0: Скелет CLI + аргументы
- [x] git init, CONTEXT.md
- [ ] `codebase_import_search.py` как executable script (`#!/usr/bin/env python3`, `if __name__ == "__main__"`)
- [ ] argparse: `--file`, `--module`, `--module-names`, `--language`, `--project-root`
- [ ] Базовая валидация аргументов (файл/модуль должен быть указан)

## Фаза 1: Авто-резолв имён модуля из пути файла
- [ ] Из `--file "_core/auth.py"` автоматически генерировать target-names:
  - basename без `.py`: `auth`
  - dotted path от project-root (если file под project-root): `_core.auth`
- [ ] Объединить с `--module-names` в единый set target_names

## Фаза 2: Сканирование файлов проекта
- [ ] Рекурсивный обход project-root, сбор всех `.py` файлов
- [ ] Исключаемые директории: `.git`, `__pycache__`, `.venv`, `node_modules`, `dist`, `build`, `*.egg-info`, `__map`, `__HQ`
- [ ] Исключить сам целевой файл из результатов

## Фаза 3: PythonHandler — разбор импортов (regex-based)
### from-import (`from X import Y`)
- [ ] `re` для `from <module> import <symbols>` включая алиасы `as`
- [ ] Относительные импорты: резолв точек относительно пути файла-потребителя
- [ ] Проверка: относится ли imported module к target_names → если да, фиксируем символы
- [ ] `from foo import bar as b` → фиксируем оригинальное имя `bar`

### module-import (`import X [as ALIAS]`)
- [ ] Извлечение алиаса (или имени модуля без as)
- [ ] Проверка: относится ли imported module к target_names
- [ ] Поиск всех вхождений `ALIAS.` или `MODULE.` во всём файле
- [ ] Извлечение пути до границы токена: `[a-zA-Z_][a-zA-Z0-9_.]*` после алиаса
- [ ] Дедупликация символов внутри одного файла

## Фаза 4: Вывод
- [ ] Формат: `relative_path.py: [symbol1, symbol2]`
- [ ] Сортировка по пути файла (для детерминированного вывода)
- [ ] Символы в скобках отсортированы алфавитно

## Фаза 5: Тесты на реальных проектах
- [ ] Протестировать на `/workspace/SRC/memohood`:
  - `--file "db.py"` — посмотреть что импортируется из db
  - `--file "config.py"` — config обычно широко используется
- [ ] Протестировать на `/workspace/SRC/hermes-agent-src`:
  - какой-нибудь центральный модуль (например `agent/agent_runtime_helpers.py`)
- [ ] Проверить edge cases:
  - relative imports внутри пакетов (`from .db import X`)
  - локальные импорты в функциях
  - множественные импорты в одной строке
  - доступ к атрибутам без скобок

## Фаза 6: Абстрактный класс LanguageHandler + структура для расширения
- [ ] Вынести PythonHandler как отдельный класс с интерфейсом из CONTEXT.md
- [ ] Registry handlers dict: `{"python": PythonHandler()}`
- [ ] Подготовить структуру под импортируемые future handlers (ts_handler.py и т.д.)

## Примечания
- Regex-based, не AST — быстро и достаточно для агента
- Plain text output — читаемо для LLM
- Один файл на v1, потом можно разбить если растёт
