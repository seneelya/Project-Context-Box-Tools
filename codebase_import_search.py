#!/usr/bin/env python3
"""
codebase_import_search — find what symbols from a target module are actually used outside it.

Usage:
    codebase_import_search --file "_core/auth.py" [--module-names "alt1,alt2"] [--project-root "."] [--language python|typescript]

Output (plain text):
    src/api/client.py: [CONSTANT, db_connect] [lazy: foo.function] [fallback: bar]
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

# ---------------------------------------------------------------------------
# Load shared config (optional) — cascade: CLI > tools_config > hardcoded defaults
# ---------------------------------------------------------------------------
_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

try:
    import tools_config

    CFG_PROJECT_ROOT = getattr(tools_config, "PROJECT_ROOT", None)
    CFG_LANGUAGE = getattr(tools_config, "LANGUAGE", "python")
    CFG_TEST_DIRS = getattr(tools_config, "TEST_DIRS", [])
except ImportError:
    print("Warning: tools_config.py missing — using defaults.", file=sys.stderr)
    CFG_PROJECT_ROOT = None
    CFG_LANGUAGE = "python"
    CFG_TEST_DIRS = []



def main():
    # Minimal parser to detect --file/--module before full parsing (for auto-detect)
    mini = argparse.ArgumentParser(add_help=False)
    mini.add_argument("--file")
    mini.add_argument("--language")  # Also check if language is explicitly set
    
    known, _ = mini.parse_known_args()
    
    # Auto-detect language from file extension only if --file provided and no explicit --language
    auto_lang = None
    if known.file and not known.language:
        ext = Path(known.file).suffix.lower()
        LANG_MAP = {".ts": "typescript", ".js": "typescript", ".cs": "csharp", ".py": "python"}
        auto_lang = LANG_MAP.get(ext)

    parser = argparse.ArgumentParser(
        description="Find where symbols from a target module are imported or used across the project.",
        usage="%(prog)s --file PATH [--module-names N1,N2,...] [--language LNG] [--project-root ROOT] [--incoming] [--verbose] [--tests-only] [--symbol NAME]"
    )
    parser.add_argument("--file", help="Path to target file (relative or absolute)")
    parser.add_argument("--module", help="Module name instead of file path")
    parser.add_argument(
        "--module-names",
        default="",
        help="Comma-separated additional names by which this module can be imported"
    )
    
    parser.add_argument(
        "--language",
        default=auto_lang or CFG_LANGUAGE,
        help=f"Language handler/resolver. Auto-detected from extension if omitted. Supported: python, typescript, csharp (default: {CFG_LANGUAGE})"
    )
    cfg_root = CFG_PROJECT_ROOT if CFG_PROJECT_ROOT else "."
    parser.add_argument(
        "--project-root",
        default=cfg_root,
        help=f"Root directory to scan. Defaults from tools_config.py PROJECT_ROOT or '.' (current: {cfg_root})"
    )
    parser.add_argument(
        "--tests-only",
        action="store_true",
        help="Show usages only from files under TEST_DIRS (configured in tools_config.py)"
    )
    parser.add_argument(
        "--incoming",
        action="store_true",
        help="Resolve target file's upstream dependencies (requires --file)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Per-symbol detail with usage line numbers and code block levels. Default mode: where each symbol is used across the project. With --incoming: where each imported symbol is used inside the target file."
    )
    parser.add_argument(
        "--symbol",
        default="",
        help="Comma-separated symbol name(s) to filter output to (post-filter, works in every mode)"
    )
    args = parser.parse_args()

    symbol_filter = {s.strip() for s in args.symbol.split(",") if s.strip()} or None

    # Validate project-root
    project_root = os.path.abspath(args.project_root)
    if not os.path.isdir(project_root):
        print(f"Error: --project-root is not a directory: {project_root}", file=sys.stderr)
        sys.exit(1)

    if not args.file and not args.module:
        print("Find where symbols from a target module are imported or used across the project.")
        print("Usage: codebase_import_search.py --file PATH [--module-names N1,N2,...] [--language LNG] [--incoming|--verbose|--tests-only] [--symbol NAME]")
        print(f"Current PROJECT_ROOT=\"{cfg_root}\"")
        print()
        print("Full help with --help")
        sys.exit(1)

    sys.path.insert(0, str(_TOOLS_DIR))
    from codebase_import_search.core import resolve_target_names, scan_downstream, scan_incoming
    from codebase_import_search.handlers import get_handler
    from codebase_import_search import report

    try:
        target_path, target_names = resolve_target_names(args.file, args.module, args.module_names, project_root)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Validate --file if provided (required for --incoming mode)
    target_path_abs = ""
    if args.file:
        file_arg = args.file if os.path.isabs(args.file) else os.path.join(project_root, args.file)
        target_path_abs = os.path.abspath(file_arg)
        if not os.path.isfile(target_path_abs):
            print(f"Error: --file does not exist or is not a file: {target_path_abs}", file=sys.stderr)
            sys.exit(1)
    elif args.incoming:
        print("Error: --incoming requires --file to be specified", file=sys.stderr)
        sys.exit(1)

    # ----- Incoming mode: what the target imports (upstream) -----
    if args.incoming:
        from codebase_import_search.resolvers import get_resolver
        try:
            resolver = get_resolver(args.language)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        handler = None
        if args.verbose:
            try:
                handler = get_handler(args.language)
            except ValueError:
                handler = None

        resolved, externals, usages, stats = scan_incoming(
            resolver, target_path_abs, project_root, handler=handler, verbose=args.verbose
        )
        report.format_incoming(
            resolved, externals, usages, stats, project_root, target_path_abs,
            verbose=args.verbose, symbol_filter=symbol_filter,
        )
        return

    # ----- Default mode: who consumes the target's symbols (downstream) -----
    try:
        handler = get_handler(args.language)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # For C#, the target's own namespace(s) are additional target names.
    if args.language.lower() in {"csharp", "cs"} and hasattr(handler, "_extract_namespace"):
        ns = handler._extract_namespace(target_path_abs)
        if ns:
            target_names.add(ns)
            parts = ns.split(".")
            for i in range(1, len(parts)):
                target_names.add(".".join(parts[:i]))

    data, dynamic = scan_downstream(
        project_root, handler, target_names, target_path_abs, args.language,
        bool(args.file), CFG_TEST_DIRS, args.tests_only,
    )
    report.format_downstream(
        data, dynamic, project_root, verbose=args.verbose, symbol_filter=symbol_filter,
    )


if __name__ == "__main__":
    main()
