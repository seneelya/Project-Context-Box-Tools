"""Import resolvers registry for codebase_import_search (--incoming mode)."""

from ..core import ImportResolver


def get_resolver(language: str) -> ImportResolver:
    """Get an import resolver by language name.

    Raises ValueError if the language is not supported yet.
    """
    factories = {
        "python": _make_python_resolver,
        "typescript": _make_ts_resolver,
        "ts": _make_ts_resolver,
        "js": _make_ts_resolver,
        "csharp": _make_csharp_resolver,
        "cs": _make_csharp_resolver,
    }

    factory = factories.get(language.lower())
    if not factory:
        supported = ", ".join(sorted(factories.keys()))
        raise ValueError(
            f"Import resolution for language '{language}' not implemented yet "
            f"(supported: {supported})"
        )

    return factory()


def _make_python_resolver():
    from .python_resolver import PythonResolver
    return PythonResolver()


def _make_ts_resolver():
    from .ts_resolver import TypeScriptResolver
    return TypeScriptResolver()


def _make_csharp_resolver():
    from .csharp_resolver import CSharpResolver
    return CSharpResolver()
