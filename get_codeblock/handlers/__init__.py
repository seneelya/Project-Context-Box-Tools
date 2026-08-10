"""Language handlers registry for get_codeblock."""


def get_handler(language: str):
    """Get a language handler by name.

    Raises ValueError if the language is not supported.
    """
    handlers = {
        "python": _make_python_handler,
        "py": _make_python_handler,
        # Add more here as they are implemented
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
