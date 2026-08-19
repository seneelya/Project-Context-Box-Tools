# reader/ — контракт и как добавлять слои

Этот слой превращает get_codeblock в **универсальный ридер**: `open(file) → карта`, движки под
капотом сменные. Здесь — контракт общения и рецепты расширения. Идеология и правила — в
`Vision03__get_codeblock.md` (архитектура) и `Vision02__get_codeblock.md` (`.0`-классификатор); оба
в ProjectStarter `__dev/tools/` (`../../../../__dev/tools/`).

## Схема потока

```mermaid
flowchart LR
  F["file (.py .ts .md …)"] --> R["Reader · registry.resolve(ext)"]
  R --> P["PROFILE (плагин языка)<br/>profiles/&lt;lang&gt;.py"]
  P -->|backend| TS["tree-sitter backend<br/>(core1)"]
  R -->|.md| MD["markdown backend<br/>(core2)"]
  R -->|.py без грамматики| AST["python ast backend<br/>(фолбек)"]
  TS --> N["RNode<br/>(адаптер узла)"]
  MD --> N
  AST --> N
  P -->|"role/name/label"| SP["Spec-движок"]
  N --> C["Classifier (backend-agnostic)"]
  SP -. "промоушен + label(band)" .-> C
  C --> IR["IR: дерево Block"]
  IR --> OUT["render · outline · query · .0"]
  IR -. "опц., пост-IR" .-> AN["Analyzer<br/>→ block.description"]
  AN -. "смысл" .-> OUT
```

Профиль (backend + Spec-правила) — единственное языко/формато-зависимое место. Общее (`label(band)`
в `label.py`, классификатор, рендеры) правее — backend-agnostic.

## Карта файлов

```
ir.py         — Block (IR: то, что потребляют рендеры) + Role + description(для Analyzer)
protocol.py   — контракты: RNode, Backend, Spec, Analyzer
registry.py   — resolve(ext) → (Backend, Spec)   ← ЕДИНЫЙ вход
profiles/     — плагины языков (Vision03), по файлу на язык:
  base.py       — TSProfile (данные плагина: langspec + extra_frames + binders)
  typescript.py, cpp.py, csharp.py, css.py, python.py — сами профили
  presets.py    — общие наборы (HUMAN_KIND/IMPORT_KINDS/…), чтобы C-подобные не копипастить
  __init__.py   — ts_profile_for_ext(ext) → профиль
backends/
  treesitter.py — core1: TSNode-адаптер + TSBackend + TreeSitterSpec (движок над профилем)
  markdown.py   — core2: свой разбор заголовков, БЕЗ tree-sitter (образец не-TS кора)
label.py      — backend-agnostic лейблер filler-полосы: band → список имён (оглавление)
classify.py   — backend-agnostic .0-классификатор + render + CLI
```

## Контракт (4 роли + IR)

- **RNode** — нормализованный узел: `type`, `start_row`, `end_row` (0-based), `children()`, `text()`,
  `field(name)`. Минимум, который нужен классификатору. (`protocol.py`)
- **Backend** — парсер: `root(source: bytes) → RNode`. (`protocol.py`)
- **Spec** — декоратор формата/языка, ВЕСЬ языкозависимый нюанс: `role/name/body/unwrap_frame/
  unwrap_def/filler_kind` (+ опц. `filler_label(nodes)` — заголовок-оглавление полосы). (`protocol.py`)
- **Profile** *(tree-sitter)* — плагин языка (`profiles/<lang>.py`): данными задаёт backend (LangSpec) +
  надстройки (`extra_frames`, binder/value-типы промоушена). `TreeSitterSpec` — тонкий движок над ним.
- **Analyzer** *(опционально)* — семантический пост-проход: `describe(block, source) → str|None`,
  кладёт смысл в `block.description`. (`protocol.py`)
- **IR = Block** — `role {landmark|filler|frame}`, `kind`, `name`, `start/end` (1-based, end incl.),
  `level`, `count`, `children`, `description`. Рендеры читают ТОЛЬКО это. (`ir.py`)

Поток: `resolve(ext) → (Backend, Spec)` → `Backend.root(bytes)` → `Classifier(Spec).classify(root)` →
`Block`-дерево → `render`.

## Конвенция вывода `.0` (зафиксировано — не переоткрывать)

Метка = обозначение УРОВНЯ, а не типа:
- **число** (`1`/`2`/…) — именованное определение (landmark) на этой глубине;
- **точка** (`.`) — «сам уровень/скоуп»: filler-строки (imports/comments/данные) И прозрачные рамки;
- **отступ** = глубина уровня; точки и числа в одной колонке; диапазоны выровнены; вывод только ASCII.

Точка — маркер уровня, НЕ признак рамки как таковой (рамка тоже точка, но точка ≠ только рамка).
Реализация — `classify.render()`.

## ⚠️ Инварианты (нарушать нельзя)

1. **Рендеры и classify — backend-agnostic.** Новый формат НЕ трогает `classify.py`/рендер.
2. **Всё через `registry.resolve`.** Никаких частных путей в обход единого входа.
3. **Backend отдаёт СТРУКТУРУ, Analyzer — СМЫСЛ.** Backend не ставит `description`; Analyzer не меняет
   `role/range/children`.
4. **Analyzer опционален и чист.** Его отсутствие/падение не ломает пайплайн.
5. **Общие `LangSpec` (в `handlers/`) не менять** — на них завязан рабочий outline/query (оракул
   88/88). Языковые «добавки» ридера держать в профиле (`profiles/<lang>.py`: `extra_frames`, binders).

## Рецепт A — новый язык на tree-sitter

Новый файл-профиль `profiles/<lang>.py` + одна строка в `profiles/__init__.py`. Профиль несёт
`LangSpec` (наборы node-типов: `named_def`→landmark, `transparent_parents`/`extra_frames`→frame,
`body_types`→тело) и, при нужде, binder/value-типы промоушена. Движок, classify, рендер, `label.py`
— НЕ трогаем. Общие label-наборы (если правило делит несколько языков) — в `profiles/presets.py`.

```python
# profiles/rust.py
from ..handlers._treesitter_blocks import LangSpec
from .base import TSProfile

def _load_rust():
    import tree_sitter_rust
    from tree_sitter import Language
    return Language(tree_sitter_rust.language())

RUST = TSProfile(LangSpec("Rust", _load_rust, body_types={'block','declaration_list'},
    transparent_parents={'mod_item'}, named_def={'function_item','struct_item','enum_item',
    'impl_item','trait_item'}, container={'mod_item'},
    control={'if_expression','for_expression','while_expression','match_expression'},
    scope_body='block'))

# profiles/__init__.py:  if ext == '.rs': from .rust import RUST; return RUST
```

## Рецепт B — новый backend (не tree-sitter: plain-text, docx, pdf…)

Реализовать три вещи и подключить в `resolve`. Образец — `backends/markdown.py`.

```python
class MyNode:            # RNode: type,start_row,end_row,children(),text(),field()
    ...
class MyBackend:         # root(source: bytes) -> MyNode  (сам строит дерево)
    def root(self, source): ...
class MySpec:            # role/name/body/unwrap_frame/unwrap_def/filler_kind над MyNode
    ...
# registry.resolve:
if ext in ('.txt',):
    from .backends.mytext import MyBackend, MySpec
    return MyBackend(), MySpec()
```

Backend строит `RNode`-дерево так, чтобы `Spec` мог назвать роли: заголовок/раздел → landmark,
абзац/шум → filler, прозрачная обёртка → frame. Дальше classify/render — общие.

## Рецепт C — новый analyzer (пласт 2, семантика)

Чистая функция над готовым блоком; вешается пост-проходом (обходит `Block`-дерево, ставит
`description`). Ничего в структуре не меняет.

```python
class LicenseAnalyzer:   # protocol.Analyzer
    def describe(self, block, source):
        if block.role is Role.FILLER and block.kind in ('comment','content'):
            head = "\n".join(source.splitlines()[block.start-1:block.end])
            if re.search(r'Copyright|SPDX-License', head):
                return "license-блок"
        return None
```

Прогонять опционально: нет анализатора → блоки рендерятся структурным лейблом (инвариант 4).

## Ссылки на главные правила

- `../../../../__dev/tools/Vision03__get_codeblock.md` — архитектура универсального ридера, швы.
- `../../../../__dev/tools/Vision02__get_codeblock.md` — `.0`-классификатор, роли landmark/filler/frame.
- `../../../../__dev/tools/Plan__universal-reader.md` — фазы реализации.
- `protocol.py` — сами контракты (истина в коде).
