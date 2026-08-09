"""Shared utilities and base classes for codebase_import_search."""

import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Set, Tuple


# Directories to skip during project scan
EXCLUDED_DIRS = {".git", "__pycache__", ".venv", "node_modules", "dist", "build", "__map", "__HQ"}
EXCLUDED_SUFFIXES = {".egg-info"}


def collect_files(project_root: str, extensions: Set[str]) -> List[str]:
    """Recursively collect files with given extensions under project_root."""
    root_path = Path(project_root).resolve()
    result = []
    for dirpath, dirnames, filenames in os.walk(root_path):
        dirnames[:] = [d for d in dirnames if should_include_dir(d)]
        for fname in sorted(filenames):
            if any(fname.endswith(ext) for ext in extensions):
                result.append(str(Path(dirpath) / fname))
    return result


def collect_py_files(project_root: str) -> List[str]:
    """Backward compat wrapper."""
    return collect_files(project_root, {".py"})


def should_include_dir(dirname: str) -> bool:
    """Check whether a directory name is excluded from scanning."""
    if dirname in EXCLUDED_DIRS:
        return False
    for suffix in EXCLUDED_SUFFIXES:
        if dirname.endswith(suffix):
            return False
    return True


def rel_path(filepath: str, project_root: str) -> str:
    """Return filepath relative to project_root."""
    return os.path.relpath(filepath, project_root)


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
    ) -> Tuple[Dict[str, str], Set[str]]:
        """Analyze a file and return (symbols_dict, dynamic_patterns).

        - symbols_dict: {symbol_name: import_kind}
          where kind is 'top-level', 'lazy', 'conditional', or 'fallback'
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
        file_path = os.path.abspath(file_arg)
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
    """Generic import kind detection based on indentation and block openers.

    Args:
        line: current import line (raw with whitespace)
        content_lines: all lines in the file
        idx: index of current line
        block_patterns: dict mapping kind name to regex for block opener, e.g.:
            {
                'lazy': re.compile(r'\s*(?:def|async def|function)\s+\w+'),
                'conditional': re.compile(r'\s*if\s+.+:'),
                'fallback': re.compile(r'\s*(?:try\b|\bexcept|\bfinally)'),
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
