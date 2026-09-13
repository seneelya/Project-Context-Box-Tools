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
    consumers N:                   строка ФАКТА (машинная: кто реально импортит символ);
    - a.py                        ПО ОДНОМУ потребителю на строку (Plan02 pt.1) — два
    - b.py                        независимых добавления правят РАЗНЫЕ строки, не одну
                                   и ту же (git-мердж сходится сам, не гарантированный
                                   конфликт).
    <|Agent:07 … |>                строка-ДИРЕКТИВА (ЛЛМ: описание или удалить). Номер
                                   уникален в карточке -> строка адресуема: якорь
                                   `<|Agent:07 ` (с пробелом) не повторяется. См.
                                   number_directives().

    Тот же приём («одно значение — одна строка», Plan02 pt.1+2) — в `Package layout`
    (`known submodules (re-exported from):` + `- modname` построчно) и в `In-Project
    Dependencies` (переименована из `Dependencies Internal`, Plan03 pt.0 — старое
    "Internal" читалось как «внутри файла», не «внутри проекта»; таблица `Import |
    File Path | Symbols | Kind` — ОДНА СТРОКА НА СИМВОЛ, не на файл; факт без прозы).
    Проза `Why` вынесена из таблицы в отдельный bullet-список НИЖЕ неё, по одному
    импорту на строку — `Why` больше не смешана с фактом в одной физической строке,
    LLM правит только свою строку, не переписывая факты (Plan02 pt.3):

        ## In-Project Dependencies

        | Import | File Path | Symbols | Kind |
        |---|---|---|---|
        | `utils` | `utils.py` | `bar` | normal |
        | `utils` | `utils.py` | `baz` | normal |

        ### Why these imports are used (one line per import — free text)
        - `utils` — <прозу пишет LLM>

    ## Runtime seams                ОПЦИОНАЛЬНАЯ секция (Plan03/Vision07, как
                                   `## Salvage` — появляется, только если есть что
                                   описывать; штамп не создаёт её пустой и не трогает
                                   существующую, кроме строки-контракта):

        ## Runtime seams

        Contract: `python __HQ/tools/make_interface_card.py --help-seams` (columns, Kind/Shape vocab, examples).

        | Target | Symbol | Kind | Shape | Why |
        |---|---|---|---|---|
        | `promo_engine.py` | `apply_discount` | by-path | dependent | loaded by feature flag |

    <!-- card-format: X.Y.Z -->    ПОСЛЕДНЯЯ строка файла (см. VERSION ниже) — какой
                                   версией контракта проштампована ЭТА карточка.
                                   Инвизибл в markdown-превью. Последняя строка, а не
                                   сразу после H1, чтобы не путаться с summary/прозой
                                   секций — парсер вычищает её из тела ДО разбора на
                                   секции (см. is_version_comment()), так что её
                                   позиция в файле — вопрос читаемости, не разбора.

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
# "Dependencies Internal/External" переименованы в "In-Project/External Dependencies" (Plan03
# pt.0) — старое "Internal" читалось как "внутри файла", а не "внутри проекта". Старые заголовки
# остаются читаемыми через ALIASES (canon()), карточки со старым именем не ломаются при чтении.
H2_SECTIONS = [
    "Public API",
    "In-Project Dependencies",
    "External Dependencies",
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

# Таблица "Dependencies Internal" — колонки в фиксированном порядке. `Why` больше не
# колонка (Plan02 pt.3) — вынесена в отдельный bullet-список "### Why these imports are
# used" под таблицей, факт и проза больше не в одной физической строке.
DEPS_COLUMNS = ["Import", "File Path", "Symbols", "Kind"]
EDGE_COLUMN = "File Path"     # из какой колонки берём рёбра графа (root-relative путь к файлу)
IMPORT_KINDS = ["normal", "lazy", "conditional", "type"]

# "## Runtime seams" — ОПЦИОНАЛЬНАЯ H2-секция (Plan03/Vision07): связи, которых не видно из
# импортов (динамическая загрузка по пути, отдельный процесс, общий файл, шина событий). НЕ
# входит в H2_SECTIONS/H2_SECTIONS_PACKAGE — как "## Salvage", появляется только если есть что
# описывать, штамп никогда не создаёт её пустой. Таблица `SEAM_COLUMNS` пишется целиком ЛЛМ
# (штамп её не трогает, кроме строки-контракта — см. make_interface_card.py); Kind/Shape — два
# НЕЗАВИСИМЫХ закрытых словаря, любая комбинация валидна.
RUNTIME_SEAMS_SECTION = "Runtime seams"
SEAM_COLUMNS = ["Target", "Symbol", "Kind", "Shape", "Why"]

# Kind (канал): по какому механизму существует связь. file/event неоднозначны по направлению
# без явной пометки — допускают суффикс через ":". by-path/process/http однозначны конвенцией
# "строку пишет инициатор/загрузчик", суффикс для них не предусмотрен.
SEAM_KIND_BASE = ["by-path", "process", "http", "file", "event"]
SEAM_KIND_SUFFIXES = {
    "file": ["reads", "writes", "reads+writes"],
    "event": ["emits", "listens"],
}

# Shape (форма связи): ломается ли что-то, если цель исчезнет — у зависимой стороны (dependent),
# у обеих (equal) или ни у кого (reference, чисто справочная связь).
SEAM_SHAPE = ["dependent", "equal", "reference"]


def is_valid_seam_kind(s):
    """True, если `s` — валидное значение Kind, с учётом суффиксов направления у file/event."""
    s = s.strip()
    if s in SEAM_KIND_BASE:
        return s not in SEAM_KIND_SUFFIXES  # file/event без суффикса недопустимы — направление обязательно
    if ":" in s:
        base, _, suffix = s.partition(":")
        return base in SEAM_KIND_SUFFIXES and suffix in SEAM_KIND_SUFFIXES[base]
    return False


def is_valid_seam_shape(s):
    """True, если `s` — одно из трёх значений Shape."""
    return s.strip() in SEAM_SHAPE


# Строка-контракт над таблицей Runtime seams — ФАКТ, не проза (Vision07): штамп пишет и
# перезаписывает её на КАЖДОМ проходе, как строку версии (см. version_comment() выше), агент её
# не редактирует и не удаляет. Узнаётся по фиксированному префиксу "Contract:" (Plan03 pt.2).
_SEAM_CONTRACT_TEXT = ("Contract: `python __HQ/tools/make_interface_card.py --help-seams` "
                       "(columns, Kind/Shape vocab, examples).")


def seam_contract_line():
    """Render the Runtime seams contract-note line (always current, refreshed every stamp)."""
    return _SEAM_CONTRACT_TEXT


def is_seam_contract_line(line):
    """True, если `line` — строка-контракт Runtime seams (по префиксу, не по точному тексту —
    переживает будущую правку формулировки)."""
    return line.strip().startswith("Contract:")

# Маркер пустой секции/ячейки. Парсер принимает и вариант в бэктиках: `(none)`.
EMPTY = "(none)"

# ЕДИНЫЙ маркер директивы агенту: `<|Agent: … |>`. Строй только через agent(); детектируй
# через is_agent_directive() (поле ЦЕЛИКОМ = директива) / has_agent_directive() (есть где-либо).
# Bump on any change that affects the card's ON-DISK FORMAT (section names, table
# columns, list-vs-single-line facts, directive marker) — cards have real external
# readers (Hermes agents), so this is a public contract, not a private detail. Stamped
# into every card as its LAST line (see version_comment()/is_version_comment() below) so
# an already-written card carries its own provenance — a version number that only lives
# in this file tells you nothing about files stamped by an older copy of the tool.
VERSION = "1.1.0"

_VERSION_RE = re.compile(r"^<!--\s*card-format:\s*(\S+)\s*-->\s*$")


def version_comment(version=None):
    """Render the card-format version marker line (belongs LAST in the file)."""
    return f"<!-- card-format: {version or VERSION} -->"


def is_version_comment(line):
    """True if `line` is a card-format version marker (any version, so old stamps
    from a future/past VERSION are still recognized and stripped correctly)."""
    return bool(_VERSION_RE.match(line.strip()))


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
    "Dependencies Internal": "In-Project Dependencies",
    "Зависимости (внутренние)": "In-Project Dependencies",
    "Internal dependencies": "In-Project Dependencies",
    "Dependencies External": "External Dependencies",
    "Внешние зависимости": "External Dependencies",
    "External dependencies": "External Dependencies",
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
