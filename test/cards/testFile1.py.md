# gate.py — модуль принятия решения о необходимости поиска по памяти ДО этапа retrieval  

## Публичный API

### Классы

Нет.

### Функции

#### should_recall(query: str, \*, cfg: Optional\[Dict\[str, Any]] = None) -> Tuple\[bool, float, str]

Решает, заслуживает ли *query* обращения к памяти. Никогда не поднимает исключение. Возвращает `(recall_ok, score, reason)`: `recall_ok=True` — извлекать контекст, `False` — пропустить. `score` — индикативная величина (для бэкенда `pass` и путей деградации всегда `1.0`). `reason` — краткая строка для логирования/отладки. Параметр *cfg* принимает либо полную секцию `memory.memohood`, либо под-словарь `gate`.

#### \_cosine(a: Sequence\[float], b: Sequence\[float]) -> float

Косинусное сходство двух векторов одинаковой длины. Возвращает `0.0` при пустых или несовпадающих по длине векторах.

#### \_decide(pos_sim: float, neg_sim: float, \*, margin: float, threshold: float) -> Tuple\[bool, float, str]

Правило принятия решения с bias toward pass: проходит (recall), если `pos_sim >= neg_sim - margin`; если это не так, но `neg_sim < threshold` — всё равно проходит (низкая уверенность в отрицании). Иначе пропускает (confident no-recall).

#### \_safe_float(value: Any, default: float) -> float

Безопасная конвертация значения в `float` с fallback на *default* при `None`, `TypeError` или `ValueError`.

#### \_safe_int(value: Any, default: int) -> int

Безопасная конвертация значения в `int` с fallback на *default* при `None`, `TypeError` или `ValueError`.

#### \_gate_section(cfg: Optional\[Dict\[str, Any]]) -> Dict\[str, Any]

Принимает полную секцию `memory.memohood` или под-словарь `gate`; возвращает словарь настроек gate. Если *cfg* не словарь — возвращает пустой словарь.

## Зависимости (внутренние)

| Импортирует  | Из файла        | Объекты              | Зачем                                                                                                                                     |
| ------------ | --------------- | -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `query_norm` | `query_norm.py` | `meaningful_terms()` | Быстрый эвристика: если в запросе достаточно содержательных терминов (>= meaningful_terms_floor), recall проходит без вызова embedder'а |

## Принцип работы

Публичная функция `should_recall` читает `cfg["backend"]` и маршрутизирует либо на бэкенд `pass` (всегда `True, 1.0, ...`), либо на `model2vec`. Бэкенд `model2vec` сначала проверяет количество содержательных терминов через `query_norm.meaningful_terms()` (если >= floor=3 — сразу recall); иначе лениво загружает `StaticModel.from_pretrained()`, эмбедит query и два встроенных семени (POSITIVE_SEEDS / NEGATIVE_SEEDS), вычисляет максимальное косинусное сходство с каждым набором и применяет правило `_decide` с bias toward pass. При любой ошибке (отсутствие пакета, неудачная загрузка модели) модуль логирует один раз WARNING и деградирует к поведению бэкенда `pass`.

## Внешние зависимости

- `model2vec` — опциональный пакет (lazy import внутри `_load_embedder`); не устанавливается этим модулем, добавляется через `plugin.yaml`. Используется только при `backend: model2vec`.

## ⚠️ Расхождения docstring ↔ код

Расхождений не обнаружено. Docstring корректно описывает сигнатуру, семантику возвращаемого кортежа, допустимые формы *cfg* и контракт деградации.
