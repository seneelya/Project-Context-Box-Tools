"""Контракт формата карточки — ЕДИНЫЙ источник истины.

Правь ФОРМАТ здесь; `validate_cards.py` / `rebuild_graph.py` / `bundle.py`
импортят эти переменные, код тулов не трогаем.

Скелет карточки:
    # <name><ext>            <- H1: ТОЛЬКО имя файла (== имени исходника)
    <one-line summary>       <- 2-я непустая строка: короткая сводка (не пустая!)

    ## <section>             <- все секции из массива MODULE_SECTIONS, по порядку, присутствие
    ...                         обязательно; если пусто — пиши строку из переменной EMPTY.
"""

# H1 НЕ содержит ничего кроме имени файла : строка 1 = имя, строка 2 = сводка.

# Обязательные секции H2 (в этом порядке). Секция при анализе не обноружена? -> Пусто -> значение из переменной EMPTY.
# Две ФОРМЫ карточки:
#  - МОДУЛЬНАЯ (лист/обычный файл);
#  - ПАКЕТНАЯ/УЗЛОВАЯ (__init__ и языковые индексы пакета) — добавляет "Package layout"
#    (подмодули со ссылками на их карточки), а Public API там = re-exports + диспетчеры.
MODULE_SECTIONS = [
    "Public API",
    "Dependencies Internal",
    "Dependencies External",
    "How it works",
    "Doc links",
    "Discrepancies",
]
PACKAGE_SECTIONS = ["Package layout"] + MODULE_SECTIONS
SECTIONS = MODULE_SECTIONS   # дефолт/совместимость

# Файлы-«пакеты» (индекс пакета). Другие языки добавляют свои: mod.rs, index.ts, mod.ts, ...
PACKAGE_BASENAMES = ["__init__.py"]

# Подсекции Public API (H3) — РЕКОМЕНДУЕМЫЕ примеры, НЕ закрытый список: локальная
# модель группирует экспорт по виду и добавляет уместные для языка (Enums, Interfaces,
# Macros, ...). Включаются только те, что реально есть. Порядок — важное первым.
API_SUBSECTIONS = ["Functions", "Classes", "Constants", "Types", "Objects", "Re-exports"]

# Ре-экспорты/алиасы: имена, выставленные наружу, но живущие в другом файле (напр.
# back-compat `_setup = register_cli`). Здесь `_`-имена ДОПУСТИМЫ — это намеренный
# интерфейс, поэтому validator НЕ считает их "private in Public API".
REEXPORT_SUBSECTION = "Re-exports"

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
    return PACKAGE_SECTIONS if is_package(filename) else MODULE_SECTIONS
