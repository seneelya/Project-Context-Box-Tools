"""Language handlers registry for get_codeblock."""


def get_handler(language: str):
    """Get a language handler by name.

    Raises ValueError if the language is not supported.
    """
    handlers = {
        "python": _make_python_handler,
        "py": _make_python_handler,
        "typescript": _make_ts_handler,
        "ts": _make_ts_handler,
        "js": _make_ts_handler,
        "csharp": _make_csharp_handler,
        "cs": _make_csharp_handler,
        "markdown": _make_markdown_handler,
        "md": _make_markdown_handler,
    }

    factory = handlers.get(language.lower())
    if not factory:
        supported = ", ".join(sorted(handlers.keys()))
        raise ValueError(
            f"Language '{language}' not supported yet (supported: {supported})"
        )

    return factory()


def _make_python_handler():
    from .python_handler import PythonHandler
    return PythonHandler()


def _make_ts_handler():
    from .typescript_handler import TypeScriptHandler
    return TypeScriptHandler()


def _make_csharp_handler():
    from .csharp_handler import CSharpHandler
    return CSharpHandler()


def _make_markdown_handler():
    from .markdown_handler import MarkdownHandler
    return MarkdownHandler()
