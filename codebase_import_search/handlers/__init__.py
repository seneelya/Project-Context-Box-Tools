"""Language handlers registry for codebase_import_search."""

from ..core import LanguageHandler


def get_handler(language: str) -> LanguageHandler:
    """Get a language handler by name.

    Raises ValueError if the language is not supported.
    """
    handlers = {
        "python": _make_python_handler,
        # Add more here as they are implemented:
        # "typescript": _make_ts_handler,
        # "javascript": _make_js_handler,
    }

    factory = handlers.get(language.lower())
    if not factory:
        supported = ", ".join(sorted(handlers.keys()))
        raise ValueError(f"Language '{language}' not supported yet (supported: {supported})")

    return factory()


def _make_python_handler():
    from .python_handler import PythonHandler
    return PythonHandler()
