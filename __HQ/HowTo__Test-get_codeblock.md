# HowTo: Тестирование get_codeblock

## Тестовые проекты

### Python
| Проект | Путь | Размер |
|--------|------|--------|
| memohood | `/workspace/SRC/memohood/` | маленький |
| hermes-agent-src | `/workspace/SRC/hermes-agent-src/` | большой (большие файлы) |

### TypeScript
| Проект | Путь | Размер |
|--------|------|--------|
| ts-prune | `/workspace/SRC/ts-prune/` | средний |

### C#
| Проект | Путь | Размер |
|--------|------|--------|
| CoreSharp | `/workspace/SRC/CoreSharp/` | маленький |
| test_SWARM_SRC | `/workspace/SRC/test_SWARM_SRC/` | большой |
| test_Unity | `/workspace/SRC/test_Unity/` | большой |

## Инструкции по тестированию

### Базовые тесты (Python — indentation-based)

1. **Строка внутри функции** → `level=0`, блок = функция с заголовком + докстринг сверху если есть без пустых строк
2. **Вложенность 2+ уровня** — строка в `if` внутри `def` → `level=0` вернёт if, `--level -1` вернёт def
3. **Compound blocks (try/except, if/elif)** — блок включает все ветки на одном уровне отступа
4. **Комментарий перед блоком** — приклеен к следующему заголовку блока
5. **Строка между блоками** — fallback: возвращается ближайший блок (вверх или вниз), комментарии игнорируются

### Тесты с большими файлами (hermes-agent-src)
- Проверить производительность на файлах 1000+ строк
- Проверить корректность на файлах без вложенностей (только глобальный код)

### TypeScript / JavaScript (brace-based `{}`)
- Блоки определяются по парам скобок `{...}`
- Игнорируются скобки внутри строк, template literals `"...${}..."`, однострочных комментариев `// ...` и многострочных `/* ... */`
- Проверить функции, классы, if/for/while, arrow functions

### C# (brace-based `{}`)
- Скопировать паттерн TS: блоки по скобкам `{}`
- Игнорируются вербатим строки `@"..."` и однострочные комментарии `// ...`
- Проверить namespace → class → method → if/for/while вложенность

## Формат вывода для тестов

### Без `--query` (metadata only, желтым цветом на TTY)
```
#Block level: N range: X-Y
```
Пример: `#Block level: 3 range: 71-87` — блок уровня вложенности 3 от строки 71 до 87 включительно.

**Префикс комментария зависит от языка:**
- Python → `#`
- TypeScript/C# → `//`

### С `--query` (текст блока byte-for-byte)
```
#Block level: N range: X-Y
        try:
            return something()
```
Первая строка — metadata header как комментарий, далее текст блока без изменений.

## Аргументы и флаги

| Флаг | Смысл |
|------|-------|
| `--file PATH` | Путь к файлу (абсолютный или относительный) |
| `--line N` | Номер строки (1-based), с которой искать блок |
| `--level L` | Адрес блока: 0=current, -N=родители, +N=от верха иерархии |
| `--query` | Флаг без цифр — вернуть текст блока вместо только метаданных |
| `--project-root PATH` | Корень для относительных путей (CLI перебивает конфиг) |

## Критерии успеха

- [x] Python: memohood (маленький) — все уровни корректны, indentation-based
- [ ] Python: hermes-agent-src (большой) — производительность + корректность на 1000+ строках
- [x] TypeScript: ts-prune — блоки по `{}` работают, игнорируются скобки в строках
- [x] C#: CoreSharp — малый проект проходит, namespace/class/method/if уровни верны
- [ ] C#: test_SWARM_SRC / test_Unity — большие проекты работают без ошибок

## Импортное API для других тулов

```python
from get_codeblock.core import get_codeblock

result = get_codeblock("path/to/file.py", line_num=50, level=0, query=True)
# result: {"level": 3, "start": 71, "end": 87, "text": "..."}
```
Смотреть `help(get_codeblock)` или Vision01__get_codeblock.md.
