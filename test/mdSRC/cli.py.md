# cli.py
Модуль CLI для подкоманд `hermes memohood status|stats|reindex|seed|consolidate|setup`  

## Public API

### Функции

#### register_cli(subparser) -> None

Создаёт дерево подкоманд argparse для `hermes memohood`. Вызывается `discover_plugin_cli_commands()` из `plugins/memory/__init__.py` как `setup_fn`. Регистрирует подкоманды: `status`, `stats`, `reindex`, `seed`, `consolidate`, `setup`.

#### memohood_command(args) -> None

Диспетчер команд. Ищуется по имени `{provider_name}_command` из `discover_plugin_cli_commands()`. Диспетчирует на основе `args.memohood_subcommand`: `status`/`stats` → `_print_status`, `setup` → `setup_wizard.run_wizard`, `reindex` → `embed_mod.reembed_captures_shadow`, `seed` → `db.catch_up_from_state` (с поддержкой `--dry-run`), `consolidate` → `memohood_consolidate.run_nightly`.

#### register(ctx) -> None

Точка входа плагина для `register_memory_provider`. Не вызывает `ctx.register_cli_command`, так как CLI-подключение для memory-provider плагинов происходит через `register_cli`/`memohood_command` на уровне модуля.

### Функции (внутренние, не описаны)

#### \_print_status(hermes_home: str) -> None

Внутренняя вспомогательная функция (не публичный API).

#### \_setup = register_cli

Псевдоним обратной совместимости (приватное имя, не описывается).

#### \_handle = memohood_command

Псевдоним обратной совместимости (приватное имя, не описывается).

## Dependencies Internal

| Импортирует      | Из файла          | Объекты                                                                        | Зачем                                                            |
| ---------------- | ----------------- | ------------------------------------------------------------------------------ | ---------------------------------------------------------------- |
| `.config`        | config.py         | `get_memohood_config_readonly()`                                               | Получение конфигурации memohood для status, reindex, consolidate |
| `.consolidate`   | consolidate.py    | `run_nightly(conn, cfg)`                                                       | Запуск ночной консолидации по подкоманде `consolidate`           |
| `.db`            | db.py             | `get_connection(hermes_home=...)`, `catch_up_from_state(conn, hermes_home)`    | Подключение к БД для status, reindex, seed, consolidate          |
| `.tools`         | tools.py          | `memohood_stats({}, conn=..., cfg=..., session_id=None)`                       | Получение статистики памяти по подкоманде status/stats           |
| `._engine.embed` | \_engine/embed.py | `embedding_signature(cfg)`, `reembed_captures_shadow(conn, cfg)`, `EmbedError` | Пере-эмбеддинг captures по подкоманде reindex                    |
| `.` (lazy)       | setup_wizard.py  | `run_wizard(hermes_home=...)`                                                  | Запуск мастера настройки ключей по подкоманде setup              |

## How it works

CLI для memory-provider плагинов не подключается через `ctx.register_cli_command`, а обнаруживается напрямую: `discover_plugin_cli_commands()` сканирует модуль `cli.py` активного провайдера на наличие двух имен — `register_cli(subparser)` (для построения дерева подкоманд) и `memohood_command(args)` (диспетчер, именуемый как `{provider_name}_command`). Подкоманды `status` и `stats` являются алиасами, обе вызывают `memohood_stats`. Подкоманда `reindex` пере-эмбеддит все captures в теневую таблицу через `embed_mod.reembed_captures_shadow`; `seed` выполняет catch-up индексации истории диалогов (`messages_fts`) с опциональным `--dry-run` и информирует, что извлечение фактов (captures) из старой истории через LLM не реализовано в текущем релизе; `consolidate` запускает `consolidate.run_nightly()` (decay/dedup/rollup/FTS-rebuild) вручную, так как автоматический cron-запуск не регистрируется плагином.

## Dependencies External

- `hermes_constants` (`get_hermes_home`) — импортируется лениво внутри `memohood_command` для получения пути к домашней директории Hermes.

## ⚠️ Расхождения docstring ↔ код

Нет противоречий. Docstring точно описывает поведение: `register_cli` сканируется загрузчиком CLI, `memohood_command` — диспетчер; `status`/`stats` — алиасы; `reindex` работает через `_engine/embed.py`; `seed` только индексирует историю без извлечения фактов; `consolidate` вызывает `run_nightly`; `setup` лениво импортирует `setup_wizard`.
