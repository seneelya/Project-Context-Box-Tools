# codebase_import_search — агент-инструкция (TL;DR)

## Когда использовать

Пишешь карточку документации модуля и хочешь знать **что из него реально используется вовне** → запусти этот инструмент вместо того чтобы гадать.

## Как вызвать

```bash
cd /workspace/SRC/memohood
python3 codebase_import_search.py --file "_engine/auth.py" [--language python|typescript]
```

Ключевые флаги:
- `--file PATH` — исследуемый файл (относительно project-root)
- `--module-names N1,N2` — дополнительные имена модуля если импортируют под другим именем
- `--project-root PATH` — корень проекта (по умолчанию текущая директория)

## Что значит вывод

```text
# 7 files, 4 unique symbols (+1 with dynamic access)

src/runner.ts: [analyze]
src/presenter.ts: [ResultSymbol]
tests/mocks.test.ts: [lazy: analyze]
config_loader.ts: Possible Dynamic import [import()]
```

- `# N files` — сколько файлов проекта зависят от этого модуля
- `[symbol]` — top-level импорт (всегда загружается)
- `[lazy: x]` — ленивый импорт в функции/методе (загрузится только при вызове)
- `[fallback: y]` — опциональный импорт в try/catch (не обязательная зависимость)
- `Possible Dynamic import [...]` — модуль упоминается как строка, точные символы неизвестны

## Как интерпретировать для документации

| Сигнал | Что писать в карточку |
|--------|----------------------|
| Символ используется в 3+ файлах top-level | Публичный API (обязательно документировать) |
| Только lazy/conditional/fallback | Опциональный или внутренний API |
| `Possible Dynamic import` | Есть runtime-загрузка, точный API неизвестен |
| Подчёркивание (`_private`) но широко используется | Фактически публичный (хотя и с префиксом) |

## Языки

Python (`python`, по умолчанию), TypeScript/JS (`typescript`, `ts`, `js`).
