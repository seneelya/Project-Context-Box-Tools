"""Общие куски для модулей языков: чтение исходника и выбор бэкенда объявлений
(tree-sitter / regex) для brace-языков по `CONFIG__TOOLS.DECL_BACKEND`."""

import importlib
import sys

EMPTY = {"docstring_first": None, "exports": [], "all_defs": {}, "reexports": []}

_WARNED = set()   # warn once per (language) per process


def empty():
    return {k: (v.copy() if hasattr(v, "copy") else v) for k, v in EMPTY.items()}


def read_source(target_abs):
    """Текст исходника или None, если не читается."""
    try:
        return open(target_abs, encoding="utf-8", errors="replace").read()
    except OSError:
        return None


def _decl_backend(project_root):
    """DECL_BACKEND from the TARGET project's CONFIG__TOOLS (REQ-007 — not the one next to this
    script): 'auto' | 'treesitter' | 'regex' (default 'auto')."""
    from graph_from_cards import load_config_at
    mod = load_config_at(project_root)
    return getattr(mod, "DECL_BACKEND", "auto") if mod else "auto"


def _warn_fallback(lang, pkg, forced):
    if lang in _WARNED:
        return
    _WARNED.add(lang)
    how = "DECL_BACKEND=treesitter but its grammar is missing" if forced else \
          "high-fidelity tree-sitter backend not installed"
    sys.stderr.write(
        f"[make_interface_card] WARNING: {how} for {lang} - running in the REGEX FALLBACK "
        f"(lower-fidelity signatures). For a full parse install:  "
        f"pip install tree-sitter {pkg}   (or set CONFIG__TOOLS.DECL_BACKEND='regex' to silence)\n"
    )


def brace_declarations(lang, ts_module, pkg, src, project_root):
    """Declared surface for a brace language via DECL_BACKEND (tree-sitter or regex).

    `ts_module` — модуль tree-sitter-бэкенда (`available()`, `declarations(src)`), `pkg` —
    pip-пакет его грамматики. Emits a one-time stderr WARNING when `auto`/`treesitter`
    wanted tree-sitter but the grammar isn't installed, so an agent knows results are the
    lower-fidelity fallback.
    """
    backend = _decl_backend(project_root)
    if backend in ("treesitter", "auto"):
        try:
            ts = importlib.import_module(ts_module)
            if ts.available():
                return ts.declarations(src)
            _warn_fallback(lang, pkg, forced=(backend == "treesitter"))
        except Exception as e:
            sys.stderr.write(f"[make_interface_card] WARNING: tree-sitter backend for {lang} failed ({e}); using regex.\n")
    from get_codeblock.handlers import get_handler
    return get_handler(lang).declarations(src.splitlines(keepends=True))
