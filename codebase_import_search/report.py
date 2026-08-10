"""Formatters for codebase_import_search — turn producer data into text output.

Kept separate from the data producers (core.scan_*) so output can change without
touching detection logic, and so `--symbol` is a pure post-filter over the data.
"""

import os
import sys
from typing import Dict, List, Optional, Set

# Level annotation is a bonus (from the sibling get_codeblock tool). Degrade
# gracefully: without it we simply omit the levels=[...] part.
try:
    from get_codeblock.core import get_line_levels
    _HAS_LEVELS = True
except ImportError:
    _HAS_LEVELS = False


def _tty() -> bool:
    return sys.stdout.isatty()


def _yellow(s: str) -> str:
    return f"\033[93m{s}\033[0m" if _tty() else s


def _match(symbol: str, symbol_filter: Optional[Set[str]]) -> bool:
    """Whether a symbol passes the --symbol filter (exact, or by first/last token
    for dotted attribute paths like 'alias.attr')."""
    if not symbol_filter:
        return True
    parts = symbol.split(".")
    return symbol in symbol_filter or parts[0] in symbol_filter or parts[-1] in symbol_filter


def _levels_for(abs_file: str, lines: List[int]) -> str:
    """Return ' levels=[...]' for the given lines, or '' if unavailable."""
    if not (_HAS_LEVELS and lines):
        return ""
    try:
        lv = get_line_levels(abs_file, lines)
        # Real depths are 1,2,3,... — a missing/root line is level 1, never 0.
        return f" levels={[lv.get(ln) if lv.get(ln) is not None else 1 for ln in lines]}"
    except Exception:
        return ""


def _lines_field(lines: List[int]) -> str:
    return f"lines=[{lines[0]}]" if len(lines) == 1 else f"lines={lines}"


# ---------------------------------------------------------------------------
# Downstream (default mode): who consumes the target's symbols
# ---------------------------------------------------------------------------

def format_downstream(
    data: Dict[str, Dict[str, dict]],
    dynamic: Dict[str, Set[str]],
    project_root: str,
    verbose: bool,
    symbol_filter: Optional[Set[str]] = None,
) -> None:
    # Apply --symbol filter over the produced structure.
    if symbol_filter:
        data = {
            f: {s: v for s, v in syms.items() if _match(s, symbol_filter)}
            for f, syms in data.items()
        }
        data = {f: syms for f, syms in data.items() if syms}
        dynamic = {}  # a symbol filter means "just this symbol" — dynamic is noise

    all_symbols = {s for syms in data.values() for s in syms}
    num_files, num_symbols, num_dynamic = len(data), len(all_symbols), len(dynamic)

    if not data and not dynamic:
        print("# No external usages found.")
        return

    suffix = f" (+{num_dynamic} with dynamic access)" if num_dynamic else ""
    static = "# No static imports," if not data else \
        f"# {num_files} file{'s' if num_files != 1 else ''}, {num_symbols} unique symbol{'s' if num_symbols != 1 else ''}"
    print(_yellow(static + suffix))

    if verbose:
        _format_downstream_verbose(data, project_root)
    else:
        _format_downstream_grouped(data)

    if dynamic:
        if not verbose:
            for f in sorted(dynamic):
                print(f"{f}: Possible Dynamic import [{', '.join(sorted(dynamic[f]))}]")
        else:
            print("\n# Dynamic/runtime access:")
            for f in sorted(dynamic):
                print(f"{f}: Possible Dynamic import [{', '.join(sorted(dynamic[f]))}]")


def _format_downstream_grouped(data: Dict[str, Dict[str, dict]]) -> None:
    for f in sorted(data):
        groups: Dict[str, List[str]] = {}
        for sym, v in data[f].items():
            groups.setdefault(v["kind"], []).append(sym)
        parts = []
        for kind in ["top-level", "lazy", "conditional", "fallback"]:
            if kind in groups:
                syms = ", ".join(sorted(groups[kind]))
                parts.append(f"[{syms}]" if kind == "top-level" else f"[{kind}: {syms}]")
        print(f"{f}: {' '.join(parts)}")


def _format_downstream_verbose(data: Dict[str, Dict[str, dict]], project_root: str) -> None:
    legend = "# Format: Symbol -> load_type: file_path: lines=[usage_line_numbers]"
    print(legend + (" levels=[block_depths]" if _HAS_LEVELS else ""))
    print()

    # Invert to per-symbol; split real usages from dangling (imported, never used).
    files_by_symbol: Dict[str, List[str]] = {}
    for f in data:
        for sym in data[f]:
            files_by_symbol.setdefault(sym, []).append(f)

    dangling: List[str] = []  # "sym <- file (kind)"
    for sym in sorted(files_by_symbol):
        parts = []
        for f in sorted(files_by_symbol[sym]):
            entry = data[f][sym]
            if entry["lines"]:
                abs_f = os.path.abspath(os.path.join(project_root, f))
                parts.append(f"{entry['kind']}: {f}: {_lines_field(entry['lines'])}{_levels_for(abs_f, entry['lines'])}")
            else:
                dangling.append(f"{sym} <- {f} ({entry['kind']})")
        if parts:
            print(f"{sym}:")
            for p in parts:
                print(f"  {p}")

    if dangling:
        print("\n# dangling imports (imported, no usage found):")
        for d in sorted(dangling):
            print(f"  {d}")


# ---------------------------------------------------------------------------
# Incoming mode: what the target imports (upstream)
# ---------------------------------------------------------------------------

def format_incoming(
    resolved: List[dict],
    externals: List[str],
    usages: Dict[str, dict],
    stats: Dict[str, int],
    project_root: str,
    target_path_abs: str,
    verbose: bool,
    symbol_filter: Optional[Set[str]] = None,
) -> None:
    if not resolved and not externals:
        print("# No imports found in target file.")
        return

    summary = f"# {stats['total']} import{'s' if stats['total'] != 1 else ''} in target"
    if stats["resolved"]:
        summary += f", {stats['resolved']} resolved to {stats['sources']} unique source{'s' if stats['sources'] != 1 else ''}"
    print(_yellow(summary))

    if verbose:
        _format_incoming_verbose(usages, target_path_abs, symbol_filter)
    else:
        for item in resolved:
            syms = [s for s in item["symbols"] if _match(s, symbol_filter)]
            if symbol_filter and not syms:
                continue
            print(f"{item['file']}: [{', '.join(syms)}]")

    # External section (skip entirely when a symbol filter is active).
    if externals and not symbol_filter:
        print(f"\n# external ({len(externals)} not resolved in project):")
        for raw in externals:
            print(f"  {raw}")


def _format_incoming_verbose(
    usages: Dict[str, dict],
    target_path_abs: str,
    symbol_filter: Optional[Set[str]],
) -> None:
    # Incoming analyses ONE target file: many source files feed into it, so group
    # by source file and nest the symbols under it (mirror of default verbose,
    # which groups by symbol because there the "many" is the consumer files).
    print("# Format: source_file -> symbol: used in target lines=[..]" +
          (" levels=[..]" if _HAS_LEVELS else ""))
    print()

    by_source: Dict[str, List[tuple]] = {}   # source -> [(symbol, lines)]  (symbols in sorted order)
    dangling: List[tuple] = []               # (source, symbol)
    for sym in sorted(usages):
        if not _match(sym, symbol_filter):
            continue
        info = usages[sym]
        if info["lines"]:
            by_source.setdefault(info["source"], []).append((sym, info["lines"]))
        else:
            dangling.append((info["source"], sym))

    for src in sorted(by_source):
        print(f"{src}:")
        for sym, lines in by_source[src]:
            print(f"  {sym}: {_lines_field(lines)}{_levels_for(target_path_abs, lines)}")

    if dangling:
        print("\n# dangling imports (imported, not used in target):")
        for src, sym in sorted(dangling):
            print(f"  {sym} <- {src}")
