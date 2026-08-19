"""Единый реестр ридера: расширение → (Backend, Spec). ОДИН вход (Vision03).

Заменяет собой размазанную диспетчеризацию (lang_map ×3 в core.py, get_handler,
_spec_for_ext). Пока только tree-sitter-языки; новый язык = одна запись здесь,
новый backend (docx/pdf) = ветка на другой Backend-класс.
"""

from .backends.treesitter import TSBackend, TreeSitterSpec


def _load_python_language():
    import tree_sitter_python
    from tree_sitter import Language
    return Language(tree_sitter_python.language())


def _py_ts_spec():
    from ..handlers._treesitter_blocks import LangSpec
    return LangSpec(
        "Python(ts)", _load_python_language,
        body_types={'block'},
        transparent_parents=set(),
        named_def={'function_definition', 'class_definition'},
        container=set(),
        control={'if_statement', 'for_statement', 'while_statement',
                 'with_statement', 'try_statement', 'match_statement'},
        scope_body='block',
    )


def _python_backend_spec():
    """Python: tree-sitter-python если есть; иначе ГРОМКИЙ фолбек на stdlib ast."""
    try:
        import tree_sitter_python  # noqa: F401
    except ImportError:
        import sys
        print("[!] tree_sitter_python не установлен - .0 для Python идёт через stdlib ast "
              "(НЕПОЛНО: без ~comment-полос, декоратор схлопнут).\n"
              "    Полный режим:  pip install tree_sitter_python",
              file=sys.stderr)
        from .backends.python_ast import PythonAstBackend, PythonAstSpec
        return PythonAstBackend(), PythonAstSpec()
    return TSBackend(_py_ts_spec()), TreeSitterSpec(_py_ts_spec())


def _langspec_for_ext(ext):
    """Существующий LangSpec под расширение (переиспользуем движковые SPEC-и)."""
    ext = ext.lower()
    if ext in ('.cpp', '.cc', '.cxx', '.hpp', '.h', '.hh', '.c'):
        from ..handlers.cpp_handler import CPP_SPEC
        return CPP_SPEC
    if ext in ('.ts', '.js'):
        from ..handlers.typescript_handler import TS_SPEC
        return TS_SPEC
    if ext in ('.tsx', '.jsx'):
        from ..handlers.typescript_handler import TSX_SPEC
        return TSX_SPEC
    if ext == '.cs':
        from ..handlers.csharp_handler import CS_SPEC
        return CS_SPEC
    if ext in ('.scss', '.sass', '.css'):
        from ..handlers.css_handler import CSS_SPEC
        return CSS_SPEC
    return None


def resolve(ext):
    """(Backend, Spec) под расширение, или ValueError. Единый вход: ветка на нужный
    backend по формату (tree-sitter-код / markdown / позже docx/pdf)."""
    ext = ext.lower()
    if ext in ('.md', '.markdown'):                    # core2 — НЕ tree-sitter
        from .backends.markdown import MarkdownBackend, MarkdownSpec
        return MarkdownBackend(), MarkdownSpec()
    if ext == '.py':                                   # tree-sitter-python или ast-фолбек
        return _python_backend_spec()
    ls = _langspec_for_ext(ext)                        # core1 — tree-sitter
    if ls is None:
        raise ValueError(f"reader: формат {ext} пока не поддержан")
    return TSBackend(ls), TreeSitterSpec(ls)
