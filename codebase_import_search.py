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
import sys
from pathlib import Path
from typing import Dict, List, Set

# ---------------------------------------------------------------------------
# Load shared config (optional) — cascade: CLI > tools_config > hardcoded defaults
# ---------------------------------------------------------------------------
_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

try:
    import tools_config

    CFG_PROJECT_ROOT = getattr(tools_config, "PROJECT_ROOT", None)
    CFG_LANGUAGE = getattr(tools_config, "DEFAULT_LANGUAGE", "python")
except ImportError:
    print("Warning: tools_config.py missing — using defaults.", file=sys.stderr)
    CFG_PROJECT_ROOT = None
    CFG_LANGUAGE = "python"


def main():
    parser = argparse.ArgumentParser(
        description="Find which symbols from a target module are actually imported/used elsewhere in the project."
    )
    parser.add_argument("--file", help="Path to target file (e.g., '_core/auth.py')")
    parser.add_argument("--module", help="Module name (alternative to --file)")
    parser.add_argument(
        "--module-names",
        default="",
        help="Comma-separated additional names by which this module can be imported.",
    )
    parser.add_argument(
        "--language",
        default=CFG_LANGUAGE,
        help=f"Language of the codebase (default: {CFG_LANGUAGE}). Supported: python, typescript, csharp.",
    )
    cfg_root = CFG_PROJECT_ROOT if CFG_PROJECT_ROOT else "."
    parser.add_argument(
        "--project-root",
        default=cfg_root,
        help=f"Root directory to scan for imports (default from tools_config.py or '.'): {cfg_root}",
    )

    args = parser.parse_args()

    # Validate project-root
    project_root = os.path.abspath(args.project_root)
    if not os.path.isdir(project_root):
        print(f"Error: --project-root is not a directory: {project_root}", file=sys.stderr)
        sys.exit(1)

    if not args.file and not args.module:
        parser.print_help(sys.stderr)
        print("\nError: must specify --file or --module", file=sys.stderr)
        sys.exit(1)

    # Import shared utilities and handler registry from the package structure
    sys.path.insert(0, str(_TOOLS_DIR))
    from codebase_import_search.core import collect_files, resolve_target_names, rel_path
    from codebase_import_search.handlers import get_handler

    try:
        target_path, target_names = resolve_target_names(args.file, args.module, args.module_names, project_root)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Validate --file if provided
    target_path_abs = ""
    if args.file:
        file_arg = args.file
        if not os.path.isabs(file_arg):
            file_arg = os.path.join(project_root, file_arg)
        target_path_abs = os.path.abspath(file_arg)
        if not os.path.isfile(target_path_abs):
            print(f"Error: --file does not exist or is not a file: {target_path_abs}", file=sys.stderr)
            sys.exit(1)

    # Get handler for the requested language
    try:
        handler = get_handler(args.language)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # For C#, extract namespace from target file and add to target_names
    if args.language.lower() in {"csharp", "cs"} and hasattr(handler, "_extract_namespace"):
        ns = handler._extract_namespace(target_path_abs)
        if ns:
            target_names.add(ns)
            # Also add parent namespaces (for using directives that reference parent namespace)
            parts = ns.split(".")
            for i in range(1, len(parts)):
                target_names.add(".".join(parts[:i]))

    # Collect files matching the handler's extensions
    all_files = collect_files(project_root, handler.get_extensions())

    results: Dict[str, Dict[str, str]] = {}       # rel_path -> {symbol: kind}
    dynamic_results: Dict[str, Set[str]] = {}     # rel_path -> set of dynamic pattern labels

    for fpath in all_files:
        if os.path.abspath(fpath) == target_path_abs:
            continue

        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
        except Exception:
            continue

        symbols_dict, dyn_patterns = handler.analyze_file(fpath, lines, target_names, project_root)

        rp = rel_path(fpath, project_root)
        if symbols_dict:
            results[rp] = symbols_dict
        if dyn_patterns:
            dynamic_results[rp] = dyn_patterns

    # Output sorted by file path, symbols alphabetically within each file
    all_symbols = set()
    for syms_dict in results.values():
        all_symbols.update(syms_dict.keys())
    num_files = len(results)
    num_symbols = len(all_symbols)
    num_dynamic = len(dynamic_results)

    if not results and not dynamic_results:
        print("# No external usages found.")
        return

    # Summary line (with dynamic access count if any) — colored when in terminal (if still TTY)
    _IS_TTY = sys.stdout.isatty()
    _YELLOW = "\033[93m" if _IS_TTY else ""
    _RESET = "\033[0m" if _IS_TTY else ""

    summary_suffix = f" (+{num_dynamic} with dynamic access)" if num_dynamic else ""
    static_part = "# No static imports," if not results else f"# {num_files} file{'s' if num_files != 1 else ''}, {num_symbols} unique symbol{'s' if num_symbols != 1 else ''}"
    print(f"{_YELLOW}{static_part}{summary_suffix}{_RESET}")

    # Static imports first — group symbols by kind within each file
    for fpath in sorted(results.keys()):
        syms_dict = results[fpath]

        # Group symbols by import kind (priority order: top-level, lazy, conditional, fallback)
        groups: Dict[str, List[str]] = {}
        for sym, kind in syms_dict.items():
            groups.setdefault(kind, []).append(sym)

        parts = []
        for kind in ["top-level", "lazy", "conditional", "fallback"]:
            if kind in groups:
                syms = sorted(groups[kind])
                if kind == "top-level":
                    parts.append("[" + ", ".join(syms) + "]")
                else:
                    parts.append(f"[{kind}: " + ", ".join(syms) + "]")

        print(f"{fpath}: {' '.join(parts)}")

    # Dynamic/runtime access (separate section)
    if dynamic_results:
        for fpath in sorted(dynamic_results.keys()):
            patterns = sorted(dynamic_results[fpath])
            print(f"{fpath}: Possible Dynamic import [{', '.join(patterns)}]")


if __name__ == "__main__":
    main()
