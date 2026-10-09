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
    MAP_DIR            -> str  # card folder, relative to the HQ (this file's grandparent)
    LANGUAGE           -> str  # default language for tools that support --language flag
    TEST_DIRS          -> list # test directories excluded from scanning by default

Two roots (Vision08, `__dev/vision/Vision08__hq-as-anchor.md` in ProjectStarter):
    PROJECT_ROOT = the SOURCES being studied (card IDs are paths relative to it);
    HQ           = our own folder (`__HQ`): cards, logs, plans, tools. A tool always knows its HQ
                   by itself (`<HQ>/tools/<tool>.py`) — it is never read from here. The HQ
                   usually lives inside the sources but doesn't have to, and the agent may start
                   anywhere (e.g. one level above the project).
Our own paths (MAP_DIR, LOG_DIR) are relative to the HQ; explicit CLI flags always win.
"""

# CONFIG_SCHEMA_VERSION: bump whenever this template gains a new recognized key/section
# (a project's own copy never gets these automatically — deploy_hq.py never overwrites
# CONFIG__TOOLS.py, see HOW_TO_DEPLOY__README.txt). deploy_hq.py reads this constant (by
# regex, no import) from both the template and the target project's copy; a project whose
# number is lower gets a STALE-CONFIG signal telling it which settings are missing — it
# never merges automatically, only flags it. Bump this on any change to what's below.
CONFIG_SCHEMA_VERSION = 2   # 2: MAP_DIR added; LOG_DIR anchored to the HQ


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
# MAP_DIR: where the cards live, RELATIVE TO THE HQ (or absolute). "__map" -> <HQ>/__map.
# Card tools use it only when the project root came from this config; an explicit
# --project-root <path> means <path>/__map, and --cards-dir beats both.
# No MAP_DIR at all (a schema-1 project copy) -> legacy <PROJECT_ROOT>/__map.
# ---------------------------------------------------------------------------
MAP_DIR = "__map"

# ---------------------------------------------------------------------------
# LANGUAGE: default language(s) for tools that support --language / bulk scans.
#
# THREE canonical languages exist right now — "js"/"ts"/"tsx" are NOT separate
# languages, they're all just spellings for ONE canonical language:
#
#   canonical      accepted short forms (any of these, case-insensitive)
#   ---------      -----------------------------------------------------
#   "python"       "py"
#   "typescript"   "ts", "js", "tsx"      <- .js/.jsx/.ts/.tsx are ALL this one
#   "csharp"       "cs"
#
# TypeScript and JavaScript are handled as the exact same language on purpose
# (one parser/handler covers both) — write "typescript" (or "ts"/"js", they're
# interchangeable) for a JS-only project too; there is no separate "js" language
# to pick.
#
# Single language (most projects):
#   LANGUAGE = "python"
#
# A POLYGLOT project sets a LIST instead of a single string — this is the
# two-language example: a Python backend + a JS/TS frontend in the same tree:
#   LANGUAGE = ["python", "typescript"]
# make_interface_card --all then stamps both; with a single value it stamps only
# that language and says nothing about the files it skipped, which is how a
# python+JS tree quietly gets half a map. Per-file analysis is polyglot either
# way (the language comes from the file's extension) — this setting only picks
# what a BULK pass looks at. `--language py,ts` (or `all`) overrides per run,
# same short forms as above.
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

# ---------------------------------------------------------------------------
# C/C++/CUDA (Plan08) — read by the C++ modules of make_interface_card / find_code_usage /
# graph_from_cards. All optional; empty = generic behaviour.
#   CPP_INCLUDE_DIRS   -> where `#include "x.h"` is looked up after the file's own folder,
#                         root-relative, in order (copy from CMake target_include_directories).
#                         Empty -> a UNIQUE path-suffix match in the tree (ambiguous = reported).
#   CPP_STRIP_MACROS   -> export/attribute macros cut before parsing: GGML_API, LLAMA_API,
#                         X_ATTRIBUTE_FORMAT(1, 2) (a call right after the name goes too).
#                         CUDA qualifiers (__device__, __global__ ...) are always cut.
#   CPP_WRAPPER_MACROS -> function-like macros wrapping a whole declaration:
#                         DEPRECATED(decl, "hint") -> decl.
#   CPP_PAIRS          -> header <-> implementation the same-stem rule misses {"a.h": "b.cpp"}.
#   STAMP_DIRS         -> default ZONE of `make_interface_card --all` (subpaths); empty = whole
#                         root. Only limits WHERE cards are written — links use the whole root.
# ---------------------------------------------------------------------------
CPP_INCLUDE_DIRS = []
CPP_STRIP_MACROS = []
CPP_WRAPPER_MACROS = []
CPP_PAIRS = {}
STAMP_DIRS = []

# ---------------------------------------------------------------------------
# ESCALATE_*: get_codeblock --query escalation thresholds (Vision05 — expand a
# too-small/uninformative --query result instead of returning a near-empty
# block). Only affects --query; --force bypasses escalation for one call.
#   ESCALATE_FLOOR   -> non-blank lines below this count as "too small"
#   ESCALATE_TARGET  -> desired size to aim for once escalating
#   ESCALATE_CEILING -> hard cap; never grows the result past this many lines
#   ESCALATE_K       -> asymmetry: falling short of TARGET costs K x as much as
#                       overshooting it by the same amount (K > 1 favors overshoot)
# If this file (or these names) is missing, get_codeblock/escalate.py falls back
# to the same numbers hardcoded — editing here just lets you tune per-project.
# ---------------------------------------------------------------------------
ESCALATE_FLOOR = 12
ESCALATE_TARGET = 18
ESCALATE_CEILING = 40
ESCALATE_K = 1.5

# ---------------------------------------------------------------------------
# LOGGING: opt-in diagnostic call-logging for individual tools. ON by default
# for get_codeblock/make_interface_card (2026-09-14) — remove a name to turn it
# back off for a given project.
#
#   LOG_ENABLED_TOOLS -> list of tool names (script stem, e.g. "get_codeblock")
#                         that should log every invocation. Empty = logging off.
#   LOG_DIR           -> directory each enabled tool writes its log file into
#                         (one file per tool: "<tool_name>.log.jsonl"). Created
#                         automatically if missing. A relative path is anchored
#                         to the HQ (schema >= 2; schema 1 copies: PROJECT_ROOT),
#                         never the process's cwd — tools get invoked from all
#                         over, cwd-relative would scatter log files.
#
# Format is JSONL (one JSON object per line) — diagnostic only: argv, exit code,
# duration, error (if any); make_interface_card also logs its own status
# (new/merged/forced/blocked), seam-hint flags, and --all summary counts. Never
# the actual code/text a call returned or a card's content. A tool's logging
# call is wrapped so it can never raise — a logging failure must never break or
# change the tool's own behavior/exit code.
# ---------------------------------------------------------------------------
LOG_ENABLED_TOOLS = [
    "get_codeblock",
    "make_interface_card",
    "split_monster",
]
# Relative to the HQ, so the same value is right in every copy — this neutral one (whose
# PROJECT_ROOT is ".") and a deployed project alike. The old PROJECT_ROOT-anchored value
# "__HQ/tools/_logs" doubled into "__HQ/tools/__HQ/tools/_logs" here (2026-09-14).
LOG_DIR = "tools/_logs"
