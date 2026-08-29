"""Shared configuration for the tools in this directory (`__HQ/tools/`).

This file is optional — if missing, tools fall back to hardcoded defaults and print a warning.
Each project should have its own copy of this file with appropriate paths and language settings.
`deploy_hq.py --init --apply` seeds a fresh copy with PROJECT_ROOT already set to that deploy's
own path — this local copy (in the `tools` repo itself, used for developing/testing the tools) is
deliberately left NEUTRAL: it travels to other people testing this repo, whose paths differ. For
local dev/testing against real data, prefer an explicit fixture dir passed in code (see
`test/test_cardstamp.py`'s `_PR`) over editing this file.

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
    # "/project/<your-project>", r"C:\path\to\<your-project>"
]) or "."

# ---------------------------------------------------------------------------
# LANGUAGE: default language handler to use
# Change this according to your project's primary language.
# Supported values depend on each tool — find_code_usage supports:
#   python, typescript (ts), js, csharp (cs)
#
# A POLYGLOT project may set a LIST instead of a single string:
#   LANGUAGE = ["python", "typescript"]
# make_interface_card --all then stamps both; with a single value it stamps only
# that language and says nothing about the files it skipped, which is how a
# python+JS tree quietly gets half a map. Per-file analysis is polyglot either
# way (the language comes from the file's extension) — this setting only picks
# what a BULK pass looks at. `--language py,ts` (or `all`) overrides per run.
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
# boundaries) for the card stamp (make_interface_card.py) on brace-languages (TS/JS).
#   "auto"       -> tree-sitter if installed, else the built-in regex heuristic
#   "treesitter" -> force tree-sitter (falls back to regex + a stderr note if missing)
#   "regex"      -> force the built-in zero-dependency regex fallback
# Python always uses stdlib `ast` (show_pyfile_api), regardless of this setting.
# tree-sitter is an OPTIONAL dependency: `pip install tree-sitter tree-sitter-typescript`.
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# BLACKLIST_DIRS: directories to skip during file scanning (relative paths).
# These are excluded from search results to avoid modifying internal/system files.
# Example usage in tools: check if any component of the resolved path matches these.
# ---------------------------------------------------------------------------
BLACKLIST_DIRS = [
    ".git",
    "__pycache__",
]

# ---------------------------------------------------------------------------
# WHITELIST_DIRS: allowed directories for file operations (absolute paths).
# If a tool resolves a file path that is NOT under any of these dirs, it will be blocked.
# Use ["*"] as default to allow all paths (no restriction).
# Example restrictive config:
#   WHITELIST_DIRS = ["/workspace/SRC/memohood", "/project/tools/test"]
# ---------------------------------------------------------------------------
WHITELIST_DIRS = ["*"]

DECL_BACKEND = "auto"
