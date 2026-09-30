"""stamp_langs — реестр языков штемпеля (`make_interface_card`), Plan08 шаг 0.

Один модуль на язык; штемпель говорит ТОЛЬКО с этим реестром, никаких `if lang == ...`.
Что обязан отдавать модуль языка — `CONTRACT.md` рядом (форма заморожена).
Новый язык = новый модуль + его имя в `_MODULES`. Больше нигде ничего не трогать.
"""

import importlib
import os

_MODULES = ("python", "typescript", "csharp", "cpp")

_DECLARED_KEYS = ("docstring_first", "exports", "all_defs", "reexports")


class _Defaults:
    """Необязательные части контракта — значения по умолчанию (язык без особенностей)."""
    ALIASES = ()
    DECORATORS = ()

    @staticmethod
    def extra_target_names(handler, target_abs):
        return set()

    @staticmethod
    def reexport_signature(target_abs, reexport):
        return None

    @staticmethod
    def entry_key(signature):
        return None          # None -> the stamp's generic position rule

    @staticmethod
    def fact_sections(project_root, target_abs, declared):
        return []

    @staticmethod
    def source_edges(project_root):
        """{rel file: [(rel target, #if cond or None)]} for EVERY file of this language under the
        root, straight from the source scan — lets the graph show files WITHOUT cards (Plan09
        step 4). None = the language has no cheap whole-tree scan (the graph uses cards only)."""
        return None

    @staticmethod
    def api_families(project_root, target_abs, declared):
        """None -> Public API as H4 entries (default). A list of families -> the source IS the
        interface: card form "API: in source" (CARD_FORMAT 1.3.0) with this family table."""
        return None

    @staticmethod
    def import_line(line):
        """Is this line an external-import FACT line (the resolver's raw_line), not prose?"""
        return line.startswith(("import ", "from "))


class Lang:
    """Зарегистрированный язык: атрибуты модуля + умолчания для необязательных хуков."""

    def __init__(self, mod):
        self._mod = mod

    def __getattr__(self, name):
        if hasattr(self._mod, name):
            return getattr(self._mod, name)
        return getattr(_Defaults, name)

    def declared_surface(self, project_root, target_abs):
        """`declared()` модуля + проверка формы: пропущенный ключ — громкая ошибка, а не
        молча пустая секция карточки (ради этого контракт и существует)."""
        d = self._mod.declared(project_root, target_abs)
        missing = [k for k in _DECLARED_KEYS if k not in d]
        if missing:
            raise ValueError(f"stamp_langs.{self.NAME}.declared() broke CONTRACT.md: missing {missing}")
        return d

    def __repr__(self):
        return f"<stamp lang {self.NAME}>"


_REG = None


def _registry():
    global _REG
    if _REG is None:
        reg = {}
        for m in _MODULES:
            lang = Lang(importlib.import_module(f"{__name__}.{m}"))
            reg[lang.NAME] = lang
        _REG = reg
    return _REG


def known():
    """Канонные имена всех языков."""
    return sorted(_registry())


def get(name):
    """Язык по канонному имени или синониму (`ts`, `cs`, `py` …); None — нет такого."""
    if not name:
        return None
    low = str(name).strip().lower()
    for lang in _registry().values():
        if low == lang.NAME or low in lang.ALIASES:
            return lang
    return None


def for_file(path):
    """Язык по расширению файла; None — расширение не знает ни один язык (НЕ python)."""
    ext = os.path.splitext(str(path))[1].lower()
    for lang in _registry().values():
        if ext in lang.EXTENSIONS:
            return lang
    return None


def all_extensions():
    return {e for lang in _registry().values() for e in lang.EXTENSIONS}


def normalize(value):
    """LANGUAGE (скаляр ИЛИ список) / --language -> список канонных имён.

    Полиглотный репозиторий — норма, а не край: у нас питон-плагин и его же
    JS-фронтенд лежат в ОДНОМ дереве. Разбор карточки и так пофайловый
    (`for_file` смотрит на расширение), одноязычным был только выбор того,
    ЧТО попадёт в массовый проход. Скаляр продолжает работать как раньше.
    `"all"` = все известные языки.
    """
    if isinstance(value, str):
        items = [p.strip() for p in value.replace(",", " ").split()]
    elif isinstance(value, (list, tuple, set)):
        items = [str(p).strip() for p in value]
    else:
        items = []
    out, seen = [], set()
    for it in items:
        if not it:
            continue
        if it.lower() == "all":
            return known()
        lang = get(it)
        if lang and lang.NAME not in seen:
            seen.add(lang.NAME)
            out.append(lang.NAME)
    return out


def extensions(value):
    """Расширения одного языка ИЛИ списка языков. Неизвестное/пустое -> все известные."""
    names = normalize(value)
    exts = {e for n in names for e in get(n).EXTENSIONS}
    return exts or all_extensions()
