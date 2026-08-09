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
        default=auto_lang or CFG_LANGUAGE,
        help=f"Language of the codebase (default: auto-detect from extension or '{CFG_LANGUAGE}'). Supported: python, typescript, csharp.",
    )
    cfg_root = CFG_PROJECT_ROOT if CFG_PROJECT_ROOT else "."
    parser.add_argument(
        "--project-root",
        default=cfg_root,
        help=f"Root directory to scan for imports (default from tools_config.py or '.'): {cfg_root}",
    )
    parser.add_argument(
        "--tests-only",
        action="store_true",
        help="Show usages only from configured test directories (reveals API covered by tests)"
    )
    parser.add_argument(
        "--incoming",
        action="store_true",
        help="Show where the target file's imports come from (upstream dependencies within project-root)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Group output by symbol with line numbers instead of by file"
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

    # Import shared utilities (needed by both modes)
    sys.path.insert(0, str(_TOOLS_DIR))
    from codebase_import_search.core import collect_files, resolve_target_names, rel_path
    from codebase_import_search.handlers import get_handler

    try:
        target_path, target_names = resolve_target_names(args.file, args.module, args.module_names, project_root)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Validate --file if provided (required for --incoming mode)
    target_path_abs = ""
    if args.file:
        file_arg = args.file
        if not os.path.isabs(file_arg):
            file_arg = os.path.join(project_root, file_arg)
        target_path_abs = os.path.abspath(file_arg)
        if not os.path.isfile(target_path_abs):
            print(f"Error: --file does not exist or is not a file: {target_path_abs}", file=sys.stderr)
            sys.exit(1)
    elif args.incoming:
        print("Error: --incoming requires --file to be specified", file=sys.stderr)
        sys.exit(1)

    # ---------------------------------------------------------------------------
    # Incoming mode (--incoming): resolve imports of the target file
    # ---------------------------------------------------------------------------
    if args.incoming:
        from codebase_import_search.resolvers import get_resolver

        try:
            resolver = get_resolver(args.language)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        imports = resolver.resolve_imports(target_path_abs, project_root)
        if not imports:
            print("# No imports found in target file.")
            return

        # Separate resolved vs unresolved imports
        resolved = [imp for imp in imports if imp.resolved_path]
        unresolved = [imp for imp in imports if not imp.resolved_path]
        unique_resolved_files = set(imp.resolved_path for imp in resolved)

        num_total = len(imports)
        num_resolved = len(resolved)
        num_unique_sources = len(unique_resolved_files)

        _IS_TTY = sys.stdout.isatty()
        _YELLOW = "\033[93m" if _IS_TTY else ""
        _RESET = "\033[0m" if _IS_TTY else ""

        summary_parts = [f"# {num_total} import{'s' if num_total != 1 else ''} in target"]
        if resolved:
            summary_parts.append(
                f"{num_resolved} resolved to {num_unique_sources} unique source{'s' if num_unique_sources != 1 else ''}"
            )
        print(_YELLOW + ", ".join(summary_parts) + _RESET)

        # Group by source file: show as "file: [symbols]" (same format as default mode)
        from collections import defaultdict
        file_symbols: Dict[str, List[str]] = defaultdict(list)
        for imp in resolved:
            rel_src = rel_path(imp.resolved_path, project_root)
            file_symbols[rel_src].extend(imp.symbol_names)

        # Show resolved imports first, sorted by file path
        for src_file in sorted(file_symbols.keys()):
            symbols_sorted = sorted(set(file_symbols[src_file]))
            print(f"{src_file}: [{', '.join(symbols_sorted)}]")

        # Show unresolved imports grouped together at the end
        if unresolved:
            for imp in unresolved:
                print(f"[external]: {imp.raw_line}")

        return

    # ---------------------------------------------------------------------------
    # Default mode (downstream consumers of target's public API) — existing logic below
    # ---------------------------------------------------------------------------

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
    all_files = collect_files(
        project_root, 
        handler.get_extensions(), 
        CFG_TEST_DIRS, 
        args.tests_only
    )

    results: Dict[str, Dict[str, str]] = {}       # rel_path -> {symbol: kind}
    symbol_lines_global: Dict[str, Dict[str, List[int]]] = {}  # rel_path -> {symbol: [lines]}
    dynamic_results: Dict[str, Set[str]] = {}     # rel_path -> set of dynamic pattern labels

    for fpath in all_files:
        if os.path.abspath(fpath) == target_path_abs:
            continue

        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
        except Exception:
            continue

        symbols_dict, symbol_lines_dict, dyn_patterns = handler.analyze_file(fpath, lines, target_names, project_root)

        rp = rel_path(fpath, project_root)
        if symbols_dict:
            results[rp] = symbols_dict
        if symbol_lines_dict:
            symbol_lines_global[rp] = symbol_lines_dict
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

    # Verbose mode: group by symbol with line numbers
    if args.verbose and results:
        from collections import defaultdict
        symbol_usages: Dict[str, List[Tuple[str, str, int]]] = defaultdict(list)  # sym -> [(file, kind, line)]

        for fpath in sorted(results.keys()):
            syms_dict = results[fpath]
            lines_map = symbol_lines_global.get(fpath, {})
            for sym, kind in syms_dict.items():
                lines_for_sym = lines_map.get(sym, [])
                if lines_for_sym:
                    for line_num in lines_for_sym:
                        symbol_usages[sym].append((fpath, kind, line_num))
                else:
                    # Fallback: symbol detected but no specific line tracked — use first occurrence of that kind
                    symbol_usages[sym].append((fpath, kind, 0))

        for sym in sorted(symbol_usages.keys()):
            usages = symbol_usages[sym]
            # Group by (file, kind) to avoid duplicates
            seen: Set[Tuple[str, str]] = set()
            parts = []
            for fpath, kind, line_num in sorted(usages):
                key = (fpath, kind)
                if key not in seen:
                    seen.add(key)
                    prefix = "" if kind == "top-level" else f"{kind}: "
                    if line_num > 0:
                        parts.append(f"{prefix}{fpath}: lines=[{line_num}]")
                    else:
                        parts.append(f"{prefix}{fpath}")

            print(f"\n{sym}:")
            for part in parts:
                print(f"  {part}")

        # Dynamic/runtime access section (unchanged)
        if dynamic_results:
            print("\n# Dynamic/runtime access:")
            for fpath in sorted(dynamic_results.keys()):
                patterns = sorted(dynamic_results[fpath])
                print(f"{fpath}: Possible Dynamic import [{', '.join(patterns)}]")
    else:
        # Static imports first — group symbols by kind within each file (original format)
        for fpath in sorted(results.keys()):
            syms_dict = results[fpath]

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
