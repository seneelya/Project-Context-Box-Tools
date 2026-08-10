"""Shared utilities and base classes for codebase_import_search."""

import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


@dataclass(frozen=True)
class ImportInfo:
    """Information about a single import resolved by --incoming mode."""
    raw_line: str                # original import line (trimmed)
    module_name: str             # dotted name or path from the import
    symbol_names: List[str]      # specific symbols imported (empty if whole module)
    resolved_path: Optional[str] # absolute path to source file inside project-root, or None


# Directories to skip during project scan
EXCLUDED_DIRS = {".git", "__pycache__", ".venv", "node_modules", "dist", "build", "__map", "__HQ"}
EXCLUDED_SUFFIXES = {".egg-info"}


def collect_files(project_root: str, extensions: Set[str], test_dirs: List[str] = None, tests_only: bool = False) -> List[str]:
    """Recursively collect files with given extensions under project_root.
    
    Args:
        project_root: Root directory to scan
        extensions: File extensions to include (e.g. {'.py'})
        test_dirs: List of test directories relative to project_root (excluded by default)
        tests_only: If True, only include files from test_dirs
    """
    root_path = Path(project_root).resolve()
    test_paths = [root_path / d for d in (test_dirs or [])]
    result = []
    for dirpath, dirnames, filenames in os.walk(root_path):
        dirnames[:] = [d for d in dirnames if should_include_dir(d)]
        current = Path(dirpath)
        
        # Check if this directory is a test directory
        is_in_test = any(current.is_relative_to(tp) for tp in test_paths if tp.exists())
        
        # Filter logic: exclude tests by default, include only with tests_only
        if tests_only and not is_in_test:
            continue
        elif not tests_only and is_in_test:
            continue
            
        for fname in sorted(filenames):
            if any(fname.endswith(ext) for ext in extensions):
                result.append(str(current / fname))
    return result


def collect_py_files(project_root: str, test_dirs: List[str] = None, tests_only: bool = False) -> List[str]:
    """Backward compat wrapper."""
    return collect_files(project_root, {".py"}, test_dirs or [], tests_only)


def should_include_dir(dirname: str) -> bool:
    """Check whether a directory name is excluded from scanning."""
    if dirname in EXCLUDED_DIRS:
        return False
    for suffix in EXCLUDED_SUFFIXES:
        if dirname.endswith(suffix):
            return False
    return True


def rel_path(filepath: str, project_root: str) -> str:
    """Return filepath relative to project_root, normalized to forward slashes.

    Canonical stored/printed form is always '/', regardless of OS — so output is
    stable cross-platform and joinable with card File Path addresses. Native '\\'
    is only for actual filesystem calls, which happen elsewhere.
    """
    return os.path.relpath(filepath, project_root).replace(os.sep, "/")


class LanguageHandler(ABC):
    """Abstract handler for a specific language's import syntax."""

    @abstractmethod
    def get_extensions(self) -> Set[str]:
        """File extensions this handler supports (e.g. {'.py'})."""

    @abstractmethod
    def matches_target(self, imported_module: str, target_names: Set[str]) -> bool:
        """Check if an imported module name refers to one of the target modules."""

    @abstractmethod
    def analyze_file(
        self, filepath: str, content_lines: List[str], target_names: Set[str], project_root: str
    ) -> Tuple[Dict[str, str], Dict[str, List[int]], Set[str]]:
        """Analyze a file and return (symbols_dict, symbol_lines, dynamic_patterns).

        - symbols_dict: {symbol_name: import_kind}
          where kind is 'top-level', 'lazy', 'conditional', or 'fallback'
        - symbol_lines: {symbol_name: [line_numbers]} — line numbers where each symbol is used
        - dynamic_patterns: set of pattern labels for runtime/dynamic access
        """


def resolve_target_names(
    file_arg: str | None,
    module_arg: str | None,
    extra_names_str: str | None,
    project_root: str,
) -> Tuple[str, Set[str]]:
    """Resolve target file path and the set of module names by which it can be imported.

    Returns (target_file_path, set_of_target_names).
    target_names includes auto-resolved names from the file path plus user-provided ones.
    """
    extra = {n.strip() for n in (extra_names_str or "").split(",") if n.strip()}

    # Detect project-root package name (Python: __init__.py; TS/JS: index.ts/js)
    pr_path = Path(project_root).resolve()
    project_pkg_name = None
    if os.path.isfile(str(pr_path / "__init__.py")) or os.path.isfile(str(pr_path / "index.ts")) or os.path.isfile(str(pr_path / "index.js")):
        project_pkg_name = pr_path.name

    # Determine target file and base names
    if file_arg:
        # Resolve relative paths against project_root first
        if os.path.isabs(file_arg):
            file_path = os.path.abspath(file_arg)
        else:
            file_path = os.path.abspath(os.path.join(project_root, file_arg))
        basename_no_ext = Path(file_arg).stem

        is_init = basename_no_ext in {"__init__", "index"}

        try:
            rel = os.path.relpath(os.path.dirname(file_path), pr_path)
            if rel != ".":
                parts = [p for p in Path(rel).parts if p != ".."]
                dotted = ".".join(parts) if parts else basename_no_ext
            else:
                dotted = basename_no_ext
        except Exception:
            rel = "."
            dotted = basename_no_ext

        file_in_root = rel == "."

        names = set()
        if is_init:
            names.add(dotted)
        elif file_in_root:
            names.add(basename_no_ext)
        else:
            names.add(f"{dotted}.{basename_no_ext}")

        # Basename for simple imports
        if is_init and dotted:
            pkg_basename = dotted.split(".")[-1]
            names.add(pkg_basename)
        elif not is_init:
            names.add(basename_no_ext)

        # If project-root itself is a package, add prefixed versions too
        if project_pkg_name:
            if is_init and dotted:
                names.add(f"{project_pkg_name}.{dotted}")
            elif file_in_root:
                names.add(f"{project_pkg_name}.{basename_no_ext}")
            else:
                full_path = f"{dotted}.{basename_no_ext}"
                names.add(f"{project_pkg_name}.{full_path}")

        # For TS/JS projects also add relative-path style specifiers
        # (e.g., "./analyzer", "./src/analyzer") which are common in ES modules
        try:
            rel_dir = os.path.relpath(os.path.dirname(file_path), pr_path)
            if rel_dir == ".":
                names.add(f"./{basename_no_ext}")
            else:
                ts_rel = "/" + rel_dir.replace("\\", "/")  # e.g., "src/analyzer" -> "/src/analyzer"
                names.add(ts_rel)                          # without ./ prefix (for imports like 'from "src/analyzer"')
                names.add(f"./{ts_rel.lstrip('/')}")       # with ./ prefix (for 'from "./src/analyzer"')

            # Add path-without-extension variants for subdirs too
            if not is_init and rel_dir != ".":
                parts_ts = ts_rel.strip("/").split("/") + [basename_no_ext]
                names.add("/".join(parts_ts))              # "src/analyzer"
                names.add("./" + "/".join(parts_ts))       # "./src/analyzer"

            # For files in subdirs, sibling imports use just "./basename"
            # (e.g., from src/presenter.ts: import { x } from "./analyzer")
            if not is_init:
                names.add(f"./{basename_no_ext}")          # "./analyzer" — sibling import style

        except Exception:
            pass

        # For C# projects add namespace-style dotted paths
        # e.g., MyProject.Core/Services/AuthService.cs -> "MyProject.Core.Services.AuthService"
        try:
            rel_dir = os.path.relpath(os.path.dirname(file_path), pr_path)
            if rel_dir != "." and rel_dir != "..":
                parts = [p for p in Path(rel_dir).parts if p not in {".", ".."}]
                if parts:
                    ns_dotted = ".".join(parts) + "." + basename_no_ext
                    names.add(ns_dotted)  # Full namespace path like "Core.Services.AuthService"
                    
                    # Also add parent namespaces (for using directives that reference the namespace, not type)
                    for i in range(1, len(parts) + 2):
                        ns_prefix = ".".join(parts[:i])
                        names.add(ns_prefix)  # "Core", "Core.Services", etc.
        except Exception:
            pass

    elif module_arg:
        file_path = None
        basename_no_ext = Path(module_arg).stem.replace(".", os.sep)
        names = {module_arg, basename_no_ext}
    else:
        raise ValueError("Must specify --file or --module")

    names.update(extra)
    return file_path, names


def resolve_relative_import(importing_file: str, from_module: str, dots: int) -> str | None:
    """Resolve a relative import like 'from ..foo.bar import X' to an absolute module name.

    importing_file: path of the file containing the import
    from_module: e.g. 'foo.bar' (without leading dots)
    dots: number of leading dots (1 for '.', 2 for '..', etc.)

    Returns resolved dotted module name like '_core.foo.bar', or None if resolution fails.
    """
    if not from_module and dots == 0:
        return None

    file_dir = Path(importing_file).parent
    target_dir = file_dir
    for _ in range(dots - 1):
        parent = target_dir.parent
        if str(parent) == str(target_dir):
            return None
        target_dir = parent

    parts = []
    current = target_dir
    while True:
        name = current.name
        has_init = (
            os.path.isfile(str(current / "__init__.py"))
            or os.path.isfile(str(current / "index.ts"))
            or os.path.isfile(str(current / "index.js"))
        )
        if name and not name.startswith(".") and has_init:
            parts.append(name)
        elif name == "" or len(parts) > 0:
            break
        else:
            break
        parent = current.parent
        if str(parent) == str(current):
            break
        current = parent

    parts.reverse()
    base = ".".join(parts) if parts else ""

    if from_module:
        return f"{base}.{from_module}" if base else from_module
    elif base:
        return base
    return None


def get_import_kind_generic(line: str, content_lines: List[str], idx: int, block_patterns: Dict[str, re.Pattern]) -> str:
    r"""Generic import kind detection based on indentation and block openers.

    Args:
        line: current import line (raw with whitespace)
        content_lines: all lines in the file
        idx: index of current line
        block_patterns: dict mapping kind name to regex for block opener, e.g.:
            {
                "lazy": re.compile(r"\s*(?:def|async def|function)\s+\w+"),
                "conditional": re.compile(r"\s*if\s+.+:"),
                "fallback": re.compile(r"\s*(?:try\b|\bexcept|\bfinally)"),
            }

    Returns one of the kind labels or 'top-level'.
    """
    stripped = line.strip()
    indent_len = len(line) - len(stripped)

    base_indent = _get_file_base_indent(content_lines)
    relative_indent = indent_len - base_indent

    if relative_indent <= 0:
        return "top-level"

    for prev_idx in range(idx - 1, -1, -1):
        prev_line = content_lines[prev_idx]
        prev_stripped = prev_line.strip()
        if not prev_stripped or prev_stripped.startswith("#") or prev_stripped.startswith("//"):
            continue

        prev_indent = len(prev_line) - len(prev_stripped)
        prev_relative = prev_indent - base_indent

        if prev_relative < relative_indent:
            for kind, pattern in block_patterns.items():
                if pattern.match(prev_line):
                    return kind
            # Default fallback when inside some non-trivial block
            return "lazy"

    return "lazy"


def _get_file_base_indent(content_lines: List[str]) -> int:
    """Determine the base indentation level of a file from its first code lines."""
    for line in content_lines[:20]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("//"):
            continue
        return len(line) - len(stripped)
    return 0


class ImportResolver(ABC):
    """Abstract resolver for upstream dependencies (--incoming mode).
    
    Given a target file, finds where its imports originate from within project_root.
    """

    @abstractmethod
    def get_extensions(self) -> Set[str]:
        """File extensions this resolver supports (e.g. {'.py'})."""

    @abstractmethod
    def resolve_imports(
        self, target_file: str, project_root: str
    ) -> List[ImportInfo]:
        """Resolve imports in target_file to files inside project_root.

        Args:
            target_file: Absolute path to the file whose imports we're resolving.
            project_root: Root directory — only return resolved paths within this dir.

        Returns:
            List of ImportInfo for each import found (including unresolved ones).
        """


# ---------------------------------------------------------------------------
# Data producers — separate WHAT we found from HOW we print it.
# main() wires args -> producer -> formatter; producers return plain structures.
# ---------------------------------------------------------------------------

def _fast_filter_symbols(target_content: str, language: str, target_names: Set[str]) -> List[str]:
    """Candidate public symbols of the target file, used to skip files that can't
    reference it. Cheap regex heuristics; over-inclusion only costs a wasted scan.
    """
    syms: List[str] = []
    lang = language.lower()

    if lang in {"python"}:
        for m in re.finditer(r'^class\s+(\w+)', target_content, re.MULTILINE):
            syms.append(m.group(1))
        for m in re.finditer(r'^(?:async\s+)?def\s+(\w+)\s*\(', target_content, re.MULTILINE):
            syms.append(m.group(1))
        for m in re.finditer(r'^(\w+)\s*=', target_content, re.MULTILINE):
            name = m.group(1)
            if name.isupper() or (name[0].isupper() and '_' in name):
                syms.append(name)
        all_match = re.search(r'__all__\s*=\s*\[(.*?)\]', target_content, re.DOTALL)
        if all_match:
            for item in re.findall(r'''['"](\w+)['"]''', all_match.group(1)):
                syms.append(item)

    elif lang in {"typescript", "ts", "js"}:
        for m in re.finditer(r'(?:export\s+)?class\s+(\w+)', target_content, re.MULTILINE):
            syms.append(m.group(1))
        for m in re.finditer(r'(?:export\s+)?interface\s+(\w+)', target_content, re.MULTILINE):
            syms.append(m.group(1))
        for m in re.finditer(r'(?:export\s+)?type\s+(\w+)', target_content, re.MULTILINE):
            syms.append(m.group(1))
        for m in re.finditer(r'(?:export\s+)?(?:async\s+)?function\s+(\w+)', target_content, re.MULTILINE):
            syms.append(m.group(1))
        for m in re.finditer(r'export\s+\{([^}]+)\}', target_content):
            for item in m.group(1).split(','):
                name = item.split(' as ')[-1].strip()
                if name:
                    syms.append(name)

    elif lang in {"csharp", "cs"}:
        for m in re.finditer(r'(?:public\s+)?(?:partial\s+)*(?:class|struct|interface|enum)\s+(\w+)', target_content, re.MULTILINE):
            syms.append(m.group(1))
        for m in re.finditer(r'public\s+(?:static\s+)?(?:async\s+)?\w+\s+(\w+)\s*\(', target_content):
            syms.append(m.group(1))

    # Module-name fallback (some files import the module directly), skipping
    # ultra-generic short names that would match too much.
    for name in sorted(target_names, key=len):
        if len(name) >= 4 and not re.match(r'^[A-Z]$', name):
            syms.append(name)

    return sorted(set(syms), key=len, reverse=True)


def scan_downstream(
    project_root: str,
    handler: "LanguageHandler",
    target_names: Set[str],
    target_path_abs: str,
    language: str,
    has_file: bool,
    test_dirs: List[str],
    tests_only: bool,
) -> Tuple[Dict[str, Dict[str, dict]], Dict[str, Set[str]]]:
    """Find downstream consumers of the target's symbols across the project.

    Returns (data, dynamic):
      data    = {rel_file: {symbol: {"kind": str, "lines": [int]}}}  (lines=[] → dangling import)
      dynamic = {rel_file: {dynamic_label, ...}}
    """
    all_files = collect_files(project_root, handler.get_extensions(), test_dirs, tests_only)

    fast_syms: List[str] = []
    if has_file and target_path_abs and os.path.isfile(target_path_abs):
        try:
            with open(target_path_abs, "r", encoding="utf-8", errors="replace") as fh:
                fast_syms = _fast_filter_symbols(fh.read(), language, target_names)
        except OSError:
            fast_syms = []
    fast_re = re.compile("|".join(re.escape(s) for s in fast_syms)) if fast_syms else None

    data: Dict[str, Dict[str, dict]] = {}
    dynamic: Dict[str, Set[str]] = {}

    for fpath in all_files:
        if os.path.abspath(fpath) == target_path_abs:
            continue
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
                lines = content.splitlines(keepends=True)
        except OSError:
            continue

        if fast_re is not None and not fast_re.search(content):
            continue

        symbols_dict, symbol_lines_dict, dyn = handler.analyze_file(
            fpath, lines, target_names, project_root, target_path_abs if has_file else None
        )

        rp = rel_path(fpath, project_root)
        if symbols_dict:
            data[rp] = {
                sym: {"kind": kind, "lines": sorted(set(symbol_lines_dict.get(sym, [])))}
                for sym, kind in symbols_dict.items()
            }
        if dyn:
            dynamic[rp] = dyn

    return data, dynamic


def scan_incoming(
    resolver: "ImportResolver",
    target_path_abs: str,
    project_root: str,
    handler: "LanguageHandler" = None,
    verbose: bool = False,
) -> Tuple[List[dict], List[str], Dict[str, dict], Dict[str, int]]:
    """Resolve the target file's upstream imports.

    Returns (resolved, externals, usages, stats):
      resolved  = [{"file": rel_src, "symbols": [names]}]  (sorted)
      externals = [raw_line, ...]  (imports not resolved inside project_root)
      usages    = {symbol: {"source": rel_src, "lines": [int]}}  (only when verbose;
                  where each imported symbol is used INSIDE the target file)
      stats     = {"total": import-statements, "resolved": ..., "sources": unique-files}
    """
    imports = resolver.resolve_imports(target_path_abs, project_root)
    stats = {
        "total": len(imports),
        "resolved": sum(1 for i in imports if i.resolved_path),
        "sources": len({i.resolved_path for i in imports if i.resolved_path}),
    }

    from collections import defaultdict
    by_file: Dict[str, List[str]] = defaultdict(list)
    sym_source: Dict[str, str] = {}
    externals: List[str] = []

    for imp in imports:
        if imp.resolved_path:
            rel_src = rel_path(imp.resolved_path, project_root)
            by_file[rel_src].extend(imp.symbol_names)
            for s in imp.symbol_names:
                sym_source.setdefault(s, rel_src)
        else:
            externals.append(imp.raw_line)

    resolved = [{"file": f, "symbols": sorted(set(by_file[f]))} for f in sorted(by_file)]

    usages: Dict[str, dict] = {}
    if verbose and handler is not None and sym_source:
        try:
            with open(target_path_abs, "r", encoding="utf-8", errors="replace") as fh:
                tlines = fh.read().splitlines(keepends=True)
            found = handler.find_symbol_usages(target_path_abs, tlines, set(sym_source.keys()))
        except (OSError, AttributeError):
            found = {}
        for sym, src in sym_source.items():
            usages[sym] = {"source": src, "lines": sorted(set(found.get(sym, [])))}

    return resolved, externals, usages, stats