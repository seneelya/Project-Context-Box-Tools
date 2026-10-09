"""split_langs — language registry of `split_monster` (Vision06). One module per language; the
tool core talks ONLY to this registry, no `if language == ...` in it. What a module must give —
`CONTRACT.md` next to this file. Same shape as `stamp_langs/`, kept separate on purpose (a
different job: names/imports of BLOCKS, not a card's public surface).

New language = a new module here + its name in `_MODULES`. Nothing else changes. A file whose
extension no module claims gets the `other` module: cut/replace still work (get_codeblock
addresses the blocks), name hints / import propagation are simply off — and the script says so.
"""

import importlib
import os

from ._common import treesitter_syntax_ok

_MODULES = ("python", "javascript", "markdown")

_REQUIRED = ("NAME", "EXTENSIONS", "declared_names", "top_level_names", "identifiers",
             "decl_line", "name_from_decl", "source_imports", "render_import")


class _Defaults:
    """Optional parts of the contract — what a language gets if its module says nothing."""
    HAS_NAMES = True      # False -> no hints, no imports, no graph (the `other` module)
    CUT_LEVEL = 1         # get_codeblock level `--split LINE` resolves at (md: 0 = innermost section)
    STUBS = False         # True -> generated script leaves a STUB_XX (replace) instead of cutting
    CONSUMERS = False     # True -> `monster.consumers` (make_interface_card) understands this language
    GRAPH = False         # True -> needs `file_spec` and `import_insert_index` too

    @staticmethod
    def ref_pattern(name):
        """Regex of how another line MENTIONS `name`."""
        import re
        return rf"\b{re.escape(name)}\b"

    @staticmethod
    def file_spec(from_file, to_file):
        """Import specifier `from_file` uses to reach `to_file`. None = unknown (no graph)."""
        return None

    @staticmethod
    def import_insert_index(segs):
        """0-based index into the source's lines where new import lines go (after the header)."""
        return 0

    @staticmethod
    def export_problem(name, block_text):
        """A message when `name` — declared in `block_text` — is not visible from other files, else None."""
        return None

    @staticmethod
    def syntax_ok(data, ext):
        return treesitter_syntax_ok(data, ext)


class Lang:
    """A registered language: the module's attributes plus defaults for the optional hooks."""

    def __init__(self, mod):
        missing = [k for k in _REQUIRED if not hasattr(mod, k)]
        if missing:
            raise ValueError(f"split_langs.{getattr(mod, '__name__', '?')} broke CONTRACT.md: missing {missing}")
        if getattr(mod, "GRAPH", False):
            missing = [k for k in ("file_spec", "import_insert_index") if not hasattr(mod, k)]
            if missing:
                raise ValueError(f"split_langs.{mod.NAME}: GRAPH=True needs {missing}")
        self._mod = mod

    def __getattr__(self, name):
        if hasattr(self._mod, name):
            return getattr(self._mod, name)
        return getattr(_Defaults, name)

    def __repr__(self):
        return f"<split lang {self.NAME}>"


_REG = None
_OTHER = None


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
    """Canonical names of the registered languages."""
    return sorted(_registry())


def for_ext(ext):
    """The language of an extension (with the dot), or the `other` fallback — never None."""
    global _OTHER
    ext = (ext or "").lower()
    for lang in _registry().values():
        if ext in lang.EXTENSIONS:
            return lang
    if _OTHER is None:
        _OTHER = Lang(importlib.import_module(f"{__name__}.other"))
    return _OTHER


def for_file(path):
    return for_ext(os.path.splitext(str(path))[1])
