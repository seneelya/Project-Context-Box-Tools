"""Language handlers registry for find_code_usage."""

from ..core import LanguageHandler


def get_handler(language: str) -> LanguageHandler:
    """Get a language handler by name.

    Raises ValueError if the language is not supported.
    """
    handlers = {
        "python": _make_python_handler,
        "typescript": _make_ts_handler,
        "ts": _make_ts_handler,
        "js": _make_ts_handler,
        "csharp": _make_csharp_handler,
        "cs": _make_csharp_handler,
        "cpp": _make_cpp_handler,
        "c": _make_cpp_handler,
        "c++": _make_cpp_handler,
        # Add more here as they are implemented
    }

    factory = handlers.get(language.lower())
    if not factory:
        supported = ", ".join(sorted(handlers.keys()))
        raise ValueError(f"Language '{language}' not supported yet (supported: {supported})")

    return factory()


_CANONICAL = ("python", "typescript", "csharp", "cpp")


def language_for_file(path: str):
    """Canonical language whose handler claims the file's extension (None = nobody). The
    handlers' own get_extensions() is the single source — no second extension table."""
    import os
    ext = os.path.splitext(path)[1].lower()
    for name in _CANONICAL:
        try:
            if ext in get_handler(name).get_extensions():
                return name
        except Exception:
            continue
    return None


def _make_python_handler():
    from .python_handler import PythonHandler
    return PythonHandler()


def _make_ts_handler():
    from .ts_handler import TypeScriptHandler
    return TypeScriptHandler()


def _make_csharp_handler():
    from .csharp_handler import CSharpHandler
    return CSharpHandler()


def _make_cpp_handler():
    from .cpp_handler import CppHandler
    return CppHandler()
