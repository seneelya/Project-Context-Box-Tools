# capture.py
Модуль двухэтапного захвата фактов (free-signal scoring + LLM extraction) для memohood.  

## Public API

### Классы

Нет.

### Функции

#### compute_signals(text: str, \*, side: str = "user") -> Dict\[str, Any]

Бесплатный (без LLM) скоринг текстового сигнала по RU/EN regex-паттернам. Возвращает `{"score": float, "kind": str, "pinned": bool, "matched": [pattern-pattern[:40], ...]}`. Никогда не поднимает исключение; пустой/незначащий текст возвращает нулевую оценку.

#### extract_and_store(conn, text: str, \*, side: str = "user", session_id: str = "", cfg: Optional\[Dict\[str, Any]] = None) -> Optional\[Dict\[str, Any]]

Полный двухэтапный пайплайн захвата (шаги 1-6) для одной стороны conversation-turn. Возвращает результат `_store_capture` или `None`, если поворот отброшен (пустой, definite-noise, LLM сказал "не запоминается", эхо консолидации, полностью вымаран как секрет). Никогда не поднимает исключение.

#### process_turn(conn, user_content: str, assistant_content: str, \*, session_id: str = "", cfg: Optional\[Dict\[str, Any]] = None) -> Dict\[str, Optional\[Dict\[str, Any]]]

Запускает `extract_and_store` независимо для обеих сторон завершённого поворота. Каждая сторона обрабатывается отдельно, отказ одной не блокирует другую. Возвращает `{"user": result_or_None, "assistant": result_or_None}`.

#### manual_capture(conn, content: str, \*, kind: str = "fact", notability: str = "high", pinned: bool = False, session_id: str = "", cfg: Optional\[Dict\[str, Any]] = None) -> Dict\[str, Any]

Явный захват, решённый вызывающим (инструмент `memohood_capture`, `on_memory_write`'s mirror, `on_delegation`'s observation). Пропускает gate/LLM-классификацию, но выполняет шаги 3-6 (sanitization, supersede, embed+FTS+vec). Поднимает `ValueError` при пустом содержимом или если всё содержимое распознано как секрет.

## Dependencies Internal

| Импортирует         | Из файла              | Объекты                                                                        | Зачем                                                                |
| ------------------- | --------------------- | ------------------------------------------------------------------------------ | -------------------------------------------------------------------- |
| `.db`               | `db.py`               | `ensure_vec_table`, `now`, `vec_table_name`, `DbError`                         | Таблица vec0, текущее время, имя таблицы, ошибки БД                  |
| `.extract_llm`      | `extract_llm.py`      | `extract()`, `judge()`, `resolve_model()`, `_VALID_KINDS`, `_VALID_NOTABILITY` | LLM-экстракция/суждение, разрешение модели, валидные kind/notability |
| `.query_norm`       | `query_norm.py`       | `meaningful_terms()`                                                           | Нормализация терминов для Jaccard-overlap                            |
| `._engine.embed`    | `_engine/embed.py`    | `embed_texts()`, `EmbedError`, `serialize_vector()`, `embedding_signature()`, `effective_embedder_dims()` | Векторизация через пул бэкендов, сериализация вектора     |
| `._engine.retrieve` | `_engine/retrieve.py` | `_build_match_expression()`                                                    | FTS5 query hardening для fallback dup-детекции                       |
| `._engine.security` | `_engine/security.py` | `scan_secrets()`                                                               | Сканирование секретов в тексте перед хранением                       |
| `._engine.stem`     | `_engine/stem.py`     | `stem_ru()`                                                                    | RU-stemming для FTS-индексации                                       |

## How it works

Модуль реализует двухэтапный пайплайн: сначала бесплатный keyword-signal скоринг по regex-паттернам (score >= `capture_threshold` = definite keep без LLM; score <= 0 = definite drop; между ними — вызов `extract_llm.extract()`). Затем для всех кандидатов выполняется sanitization через `_scrub_secrets`, anti-loop проверка на эхо консолидации, трёхуровневая классификация supersede (cosine >= 0.95 → duplicate; < 0.92 → independent; 0.92-0.95 → LLM judge), и финальная запись с FTS(RU-stem) + vec0-индексацией, где отказ embedder'а деградирует до FTS-only без блокировки захвата. Ширина vec-таблицы берётся из `embed.effective_embedder_dims(cfg)` (pool-режим → dims бэкенда `roles.embedder`, иначе `embedder.dims`), так что таблица и вектора не разъезжаются при пути Б.

## Dependencies External

- Эмбеддер через пул бэкендов (`embed.embed_texts` → `backends.embed`, `roles.embedder`) — для векторной части; при недоступности пула модуль деградирует в FTS-only.

- SQLite с расширениями vec0 (KNN) и FTS5 (RU-stem).

- Gemini Flash-lite (через `extract_llm`) — для borderline-band классификации.

## ⚠️ Расхождения docstring ↔ код

1. Docstring `compute_signals` утверждает, что поле `matched` содержит `[pattern-name, ...]`, но фактически в список записывается `pattern.pattern[:40]` (первые 40 символов regex-строки), а не осмысленное имя паттерна.
2. Docstring `compute_signals` говорит "empty/falsy *text* returns a zero score", но код сначала делает `text = text or ""`, затем проверяет `if not text.strip()` — т.е. строка из одних пробелов тоже обнуляется, что шире, чем "falsy".
3. Docstring `_nearest_captures` утверждает "Never raises", и это подтверждено: внутри `except sqlite3.Error` с `return [], new_vec`. (Ledger-учёт убран из этого пути 2026-07-28 — эмбеддинг идёт через пул, фантом-charge cloudflare вырезан.)
