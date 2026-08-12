"""Контракт формата карточки — ЕДИНЫЙ источник истины.

Правь ФОРМАТ здесь; `validate_cards.py` / `rebuild_graph.py` / `bundle.py` / `card_api.py`
импортят эти переменные — код тулов не трогаем.

СКЕЛЕТ КАРТОЧКИ (точная форма с вложенностью; ЛЛМ дописывает прозу, прочитав исходник):

    # <name.ext>                    H1: ТОЛЬКО имя файла (== имени исходника)

    <one-line summary>             сводка: ПЕРВАЯ НЕПУСТАЯ строка после H1
                                   (пустая строка после заголовка — ок, так пишет ЛЛМ)

    ## <H2_SECTION>                каждый  ##  = элемент H2_SECTIONS (все, по порядку);
                                   у пакета (__init__) — H2_SECTIONS_PACKAGE.
    <body>                         если секция пуста — строка EMPTY  ((none))

    ### <H3_SUBSECTION>            только в Public API: группировка = H3_API_SUBSECTIONS
    #### `signature | name`        H4: одна запись-символ
    consumers N: a.py, b.py        строка ФАКТА (машинная: кто реально импортит символ)
    <Agent: …>                     строка-ДИРЕКТИВА (ЛЛМ: описание или удалить)

Привязка «заголовок ↔ переменная» прямая:  `##` → H2_SECTIONS ,  `###` → H3_API_SUBSECTIONS .
"""

# H1 = ТОЛЬКО имя файла. Сводка = ПЕРВАЯ НЕПУСТАЯ строка после H1 (пустые строки после
# заголовков допустимы — контракт подогнан под ЛЛМ-паттерн «пустая строка после ## »).

# Обязательные  ## (H2)  для МОДУЛЬНОЙ карточки, в этом порядке. Секция не обнаружена -> тело EMPTY.
H2_SECTIONS = [
    "Public API",
    "Dependencies Internal",
    "Dependencies External",
    "How it works",
    "Doc links",
    "Discrepancies",
]
# ПАКЕТНАЯ/УЗЛОВАЯ карточка (__init__ и языковые индексы пакета) добавляет "Package layout"
# (подмодули со ссылками на их карточки); Public API там = диспетчеры + Re-exports.
H2_SECTIONS_PACKAGE = ["Package layout"] + H2_SECTIONS

# Файлы-«индексы пакета» (фасады): по ним карточка считается ПАКЕТНОЙ (Package layout +
# импорты трактуются как Re-exports). У каждого языка свой: Python __init__.py, TS/JS barrel
# index.*, Rust mod.rs.
PACKAGE_BASENAMES = ["__init__.py", "index.ts", "index.js", "index.tsx", "index.jsx", "mod.rs"]

# Рекомендуемые  ### (H3)  под Public API — НЕ закрытый список: группируй экспорт по виду
# и добавляй уместные для языка (Enums, Interfaces, Macros, ...). Порядок — важное первым.
H3_API_SUBSECTIONS = ["Functions", "Classes", "Constants", "Types", "Objects",
                      "Re-exports", "Consumed internals"]

# Ре-экспорты/алиасы: имена, выставленные наружу, но живущие в другом файле (напр.
# back-compat `_setup = register_cli`). Здесь `_`-имена ДОПУСТИМЫ — это намеренный
# интерфейс, поэтому validator НЕ считает их "private in Public API".
REEXPORT_SUBSECTION = "Re-exports"

# "Consumed internals": `_`-приватные имена, которые ФАКТИЧЕСКИ импортируются другими
# файлами (обратный индекс) — де-факто интерфейс, хотя названы приватно. Здесь `_`-имена
# тоже ДОПУСТИМЫ. Заполняется штемпелем `card_api.py` из consumed surface.
CONSUMED_SUBSECTION = "Consumed internals"

# Подсекции Public API, где приватные `_`-имена легальны (не флагаются валидатором).
PRIVATE_OK_SUBSECTIONS = {REEXPORT_SUBSECTION, CONSUMED_SUBSECTION}

# Таблица "Dependencies Internal" — колонки в фиксированном порядке.
DEPS_COLUMNS = ["Import", "File Path", "Symbols", "Why", "Kind"]
EDGE_COLUMN = "File Path"     # из какой колонки берём рёбра графа (root-relative путь к файлу)
IMPORT_KINDS = ["normal", "lazy", "conditional", "type"]

# Маркер пустой секции/ячейки. Парсер принимает и вариант в бэктиках: `(none)`.
EMPTY = "(none)"

# Синонимы старых/иноязычных токенов -> канон (для миграции и терпимого чтения).
ALIASES = {
    # секции
    "Публичный API": "Public API",
    "Зависимости (внутренние)": "Dependencies Internal",
    "Internal dependencies": "Dependencies Internal",
    "Внешние зависимости": "Dependencies External",
    "External dependencies": "Dependencies External",
    "Принцип работы": "How it works",
    "Расхождения docstring ↔ код": "Discrepancies",
    "Docstring ↔ code discrepancies": "Discrepancies",
    "Раскладка пакета": "Package layout",
    "Публичный API (реэкспорт из пакета)": "Public API",
    # подсекции
    "Функции": "Functions",
    "Классы": "Classes",
    # колонки
    "Импортирует": "Import",
    "Из файла": "File Path",
    "From file": "File Path",
    "Объекты": "Symbols",
    "Objects": "Symbols",
    "Зачем": "Why",
    "Как": "Kind",
}


def canon(token):
    """Канонизирует заголовок/колонку через ALIASES (иначе возвращает как есть)."""
    return ALIASES.get(token.strip(), token.strip())


def is_empty(text):
    """True, если тело секции/ячейка — маркер пустоты (с бэктиками или без)."""
    return text.strip().strip("`").strip() == EMPTY


def is_package(filename):
    """True для пакетной/узловой карточки (__init__ и языковые аналоги)."""
    return filename.rsplit("/", 1)[-1] in PACKAGE_BASENAMES


def sections_for(filename):
    """Обязательные секции для карточки данного файла (пакет vs модуль)."""
    return H2_SECTIONS_PACKAGE if is_package(filename) else H2_SECTIONS
