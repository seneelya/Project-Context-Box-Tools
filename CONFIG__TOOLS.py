"""Shared configuration for tools in /project/tools directory.

This file is optional — if missing, tools fall back to hardcoded defaults and print a warning.
Each project should have its own copy of this file with appropriate paths and language settings.

Public interface (tools just import these):
    PROJECT_ROOT       -> str  # first existing path from candidates list, or "." as fallback
    LANGUAGE           -> str  # default language for tools that support --language flag
    TEST_DIRS          -> list # test directories excluded from scanning by default
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
# LANGUAGE: default language handler to use
# Change this according to your project's primary language.
# Supported values depend on each tool — codebase_import_search supports:
#   python, typescript (ts), js, csharp (cs)
# ---------------------------------------------------------------------------
LANGUAGE = "python"

# ---------------------------------------------------------------------------
# TEST_DIRS: list of test directories relative to PROJECT_ROOT.
# Files under these paths are excluded from scanning by default.
# Use --tests-only flag to show usages FROM test files only.
# Paths are relative to PROJECT_ROOT, e.g.:
#   "tests"              -> /workspace/SRC/memohood/tests/...
#   "_engine/tests"      -> /workspace/SRC/memohood/_engine/tests/...
# ---------------------------------------------------------------------------
TEST_DIRS = [
    # Add your project's test directories here (relative to PROJECT_ROOT)
]

# ---------------------------------------------------------------------------
# DECL_BACKEND: which engine extracts the DECLARED surface (signatures / block
# boundaries) for the card stamp (card_api.py) on brace-languages (TS/JS).
#   "auto"       -> tree-sitter if installed, else the built-in regex heuristic
#   "treesitter" -> force tree-sitter (falls back to regex + a stderr note if missing)
#   "regex"      -> force the built-in zero-dependency regex fallback
# Python always uses stdlib `ast` (py_api), regardless of this setting.
# tree-sitter is an OPTIONAL dependency: `pip install tree-sitter tree-sitter-typescript`.
# ---------------------------------------------------------------------------
DECL_BACKEND = "auto"
