"""Shared configuration for tools in /project/tools directory.

This file is optional — if missing, tools fall back to hardcoded defaults and print a warning.
Each project should have its own copy of this file with appropriate paths and language settings.

Public interface (tools just import these):
    PROJECT_ROOT       -> str  # first existing path from candidates list, or "." as fallback
    DEFAULT_LANGUAGE   -> str  # default language for tools that support --language flag
"""


def _resolve_root(candidates):
    """Return the first directory that exists among candidates."""
    import os

    for p in candidates:
        if os.path.isdir(p):
            return p
    return None


# ---------------------------------------------------------------------------
# PROJECT_ROOT: cascading paths tried in order (first existing wins)
# Add/remove/modify these according to your environment.
# If none exist, falls back to current working directory (".").
# ---------------------------------------------------------------------------
PROJECT_ROOT = _resolve_root([
    # Docker container path — memohood project
    "/workspace/SRC/memohood",
    # Windows host path — memohood project
    r"Y:\Hermess\body\sandboxes\docker\default\workspace\SRC\memohood",
]) or "."

# ---------------------------------------------------------------------------
# DEFAULT_LANGUAGE: default language handler to use
# Change this according to your project's primary language.
# Supported values depend on each tool — codebase_import_search supports:
#   python, typescript (ts), js, csharp (cs)
# ---------------------------------------------------------------------------
DEFAULT_LANGUAGE = "python"
