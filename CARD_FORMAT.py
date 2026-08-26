"""Контракт формата карточки — ЕДИНЫЙ источник истины.

Правь ФОРМАТ здесь; `validate_cards.py` / `graph_from_cards.py` / `collect_card_bundle.py` / `make_interface_card.py`
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
    <|Agent:07 … |>                строка-ДИРЕКТИВА (ЛЛМ: описание или удалить). Номер
                                   уникален в карточке -> строка адресуема: якорь
                                   `<|Agent:07 ` (с пробелом) не повторяется. См.
                                   number_directives().

Привязка «заголовок ↔ переменная» прямая:  `##` → H2_SECTIONS ,  `###` → H3_API_SUBSECTIONS .

ЕДИНЫЙ маркер обращения к агенту — `<|Agent: … |>` (строй через agent(), детектируй через
is_agent_directive() / has_agent_directive()). Выбран так, чтобы НЕ встречаться в коде (в py/cs/ts
`<|` — не синтаксис) и в markdown (тег не может начинаться с `|`, рендерится как есть). Незаполненная
директива в карточке = статус «ждёт прохода агента» (валидатор сообщает это, но НЕ как ошибку).
Детекторы терпят и легаси-форму `<Agent: …>` — карточки в работе не ломаются.
"""

import re

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
# тоже ДОПУСТИМЫ. Заполняется штемпелем `make_interface_card.py` из consumed surface.
CONSUMED_SUBSECTION = "Consumed internals"

# Подсекции Public API, где приватные `_`-имена легальны (не флагаются валидатором).
PRIVATE_OK_SUBSECTIONS = {REEXPORT_SUBSECTION, CONSUMED_SUBSECTION}

# Таблица "Dependencies Internal" — колонки в фиксированном порядке.
DEPS_COLUMNS = ["Import", "File Path", "Symbols", "Why", "Kind"]
EDGE_COLUMN = "File Path"     # из какой колонки берём рёбра графа (root-relative путь к файлу)
IMPORT_KINDS = ["normal", "lazy", "conditional", "type"]

# Маркер пустой секции/ячейки. Парсер принимает и вариант в бэктиках: `(none)`.
EMPTY = "(none)"

# ЕДИНЫЙ маркер директивы агенту: `<|Agent: … |>`. Строй только через agent(); детектируй
# через is_agent_directive() (поле ЦЕЛИКОМ = директива) / has_agent_directive() (есть где-либо).
AGENT_OPEN = "<|Agent:"
AGENT_CLOSE = "|>"
# новую `<|Agent:…|>` и легаси `<Agent:…>` (для терпимого чтения карточек в работе).
_AGENT_RE = re.compile(r"<\|?Agent:.*?\|?>", re.S)


def agent(msg):
    """Собрать директиву агенту единым маркером: agent('why?') -> '<|Agent: why? |>'."""
    return f"{AGENT_OPEN} {msg.strip()} {AGENT_CLOSE}"


def is_agent_directive(text):
    """True, если (stripped) поле ЦЕЛИКОМ = незаполненная директива-плейсхолдер (new/legacy)."""
    s = text.strip().strip("`").strip()
    return s.startswith(AGENT_OPEN) or s.startswith("<Agent:")


def has_agent_directive(text):
    """True, если ГДЕ-ЛИБО в тексте осталась незаполненная директива агенту (new/legacy)."""
    return bool(_AGENT_RE.search(text))


# Нумерация директив. Текст директивы в одной карточке повторяется десятками
# байт-в-байт одинаковых строк (по одной на каждый элемент Public API), поэтому
# АДРЕСОВАТЬ конкретную было нельзя: правка «замени вот эту» не выражается через
# уникальный old_string. Номер ставится СРАЗУ ПОСЛЕ двоеточия, а не в конец, по
# двум причинам: (1) AGENT_OPEN остаётся префиксом, поэтому is_agent_directive и
# _AGENT_RE продолжают работать без правок и старые карточки читаются как раньше;
# (2) короткий уникальный якорь оказывается в НАЧАЛЕ строки — для адресации
# достаточно `<|Agent:07 `, всю фразу копировать не надо.
#
# Уникальность якоря включает завершающий ПРОБЕЛ: без него `<|Agent:10` был бы
# префиксом `<|Agent:100` в карточке со >99 директивами. С пробелом якорь
# однозначен при любом их числе.
#
# Номер ПОЗИЦИОННЫЙ, не стабильный: добавили функцию — последующие сдвинулись.
# Осознанно: стабильность нужна только сценарию «отштамповали → заполнили часть →
# перештамповали», он редкий; зато нумерация не зависит от имён и языка и не может
# разойтись с фактическим содержимым карточки.
_AGENT_NUM_RE = re.compile(r"(<\|?Agent:)(?:\s*\d+)?\s*")


def number_directives(text, start=1):
    """Перенумеровать все директивы в тексте карточки: `<|Agent:07 … |>`.

    Идемпотентна: уже стоящий номер СНИМАЕТСЯ и ставится заново, поэтому повторный
    штамп (merge протаскивает незаполненные директивы из старой карточки вместе с
    их прежними номерами) не даёт `<|Agent:07 03 why?`. Форма маркера сохраняется:
    legacy `<Agent:` не переписывается в новую — штамп не трогает то, что не его.
    """
    counter = [start - 1]

    def _repl(m):
        counter[0] += 1
        return f"{m.group(1)}{counter[0]:02d} "

    return _AGENT_NUM_RE.sub(_repl, text)


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
    """True, если тело секции/ячейка — маркер пустоты (с бэктиками или без).

    Терпимо к пояснению после маркера на ТОЙ ЖЕ строке: `(none) — почему`
    (естественный инстинкт LLM — аннотировать; формат адаптируется к нему).
    Многострочное тело со структурой ниже (H3/таблица) пустым НЕ считается —
    иначе реальные подсекции молча потерялись бы. Защита от `(nonexistent)` и т.п.:
    сразу за маркером должен идти не буквенно-цифровой символ (пробел, тире, пунктуация).
    """
    s = text.strip().strip("`").strip()
    if s == EMPTY:
        return True
    lines = [ln for ln in s.splitlines() if ln.strip()]
    if len(lines) != 1:
        return False
    first = lines[0].strip().strip("`").strip()
    if first == EMPTY:
        return True
    tail = first[len(EMPTY):]
    return first.startswith(EMPTY) and not tail.lstrip()[:1].isalnum()


def is_package(filename):
    """True для пакетной/узловой карточки (__init__ и языковые аналоги)."""
    return filename.rsplit("/", 1)[-1] in PACKAGE_BASENAMES


def sections_for(filename):
    """Обязательные секции для карточки данного файла (пакет vs модуль)."""
    return H2_SECTIONS_PACKAGE if is_package(filename) else H2_SECTIONS


if __name__ == "__main__":
    # Not a CLI — it's the format contract. Running it (or --help) prints the
    # skeleton (this module's docstring) so you can read the contract directly.
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print(__doc__)
