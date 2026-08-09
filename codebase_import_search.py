#!/usr/bin/env python3
"""
codebase_import_search — find what symbols from a target module are actually used outside it.

Usage:
    codebase_import_search --file "_core/auth.py" [--module-names "alt1,alt2"] [--project-root "."]

Output (plain text):
    src/api/client.py: [CONSTANT, db_connect, foo.function]
"""

import argparse
import os
import re
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Set, Tuple


# Directories to skip during project scan
EXCLUDED_DIRS = {".git", "__pycache__", ".venv", "node_modules", "dist", "build", "__map", "__HQ"}
EXCLUDED_SUFFIXES = {".egg-info"}


def collect_py_files(project_root: str) -> List[str]:
    """Recursively collect all .py files under project_root, excluding known dirs."""
    root_path = Path(project_root).resolve()
    result = []
    for dirpath, dirnames, filenames in os.walk(root_path):
        # Prune excluded directories (in-place modification of dirnames)
        dirnames[:] = [d for d in dirnames if should_include_dir(d)]
        for fname in sorted(filenames):
            if fname.endswith(".py"):
                result.append(str(Path(dirpath) / fname))
    return result


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


def resolve_target_names(file_arg: str | None, module_arg: str | None, extra_names_str: str | None, project_root: str) -> Tuple[str, Set[str]]:
    """
    Resolve target file path and the set of module names by which it can be imported.

    Returns (target_file_path, set_of_target_names).
    target_names includes auto-resolved names from the file path plus user-provided ones.
    """
    extra = {n.strip() for n in (extra_names_str or "").split(",") if n.strip()}

    # Detect the project-root package name (if it's a Python package)
    pr_path = Path(project_root).resolve()
    project_pkg_name = None
    if os.path.isfile(str(pr_path / "__init__.py")):
        project_pkg_name = pr_path.name

    # Determine target file and base names
    if file_arg:
        file_path = os.path.abspath(file_arg)
        basename_no_ext = Path(file_arg).stem

        # Special case: __init__.py → the package name, not "__init__"
        is_init = basename_no_ext == "__init__"

        # Try to resolve dotted path relative to project_root
        dotted = None
        try:
            rel = os.path.relpath(os.path.dirname(file_path), pr_path)
            if rel != ".":
                parts = [p for p in Path(rel).parts if p != ".."]
                if parts:
                    dotted = ".".join(parts)  # directory path as package name
                else:
                    # File directly in project root (e.g., "foo.py")
                    dotted = basename_no_ext
            else:
                dotted = basename_no_ext
        except Exception:
            pass

        # Determine what 'dotted' represents:
        # - For files in subdirs (rel != "."): dotted = directory path (e.g., "_engine.backends")
        # - For files in root (rel == "."): dotted = module name itself (e.g., "db")
        file_in_root = rel == "."

        names = set()
        if is_init:
            # __init__.py → the importable name IS the directory path
            names.add(dotted)
        elif file_in_root:
            # File directly in project root (e.g., "db.py") → just its name
            names.add(basename_no_ext)
        else:
            # File in subdir → directory.path.module_name
            names.add(dotted + "." + basename_no_ext)

        # Also add just the module/package basename for simple imports
        if is_init and dotted:
            pkg_basename = dotted.split(".")[-1]
            names.add(pkg_basename)
        elif not is_init:
            names.add(basename_no_ext)

        # If project-root itself is a Python package, add prefixed versions too
        # (relative imports inside the package resolve with the package prefix)
        if project_pkg_name:
            if is_init and dotted:
                # Package __init__.py
                names.add(f"{project_pkg_name}.{dotted}")
            elif file_in_root:
                # File in root of package
                names.add(f"{project_pkg_name}.{basename_no_ext}")
            else:
                # File in subdir
                full_path = dotted + "." + basename_no_ext
                names.add(f"{project_pkg_name}.{full_path}")

    elif module_arg:
        file_path = None  # Not used in v1; could be resolved by importing the module
        basename_no_ext = Path(module_arg).stem.replace(".", os.sep)
        names = {module_arg, basename_no_ext}
    else:
        raise ValueError("Must specify --file or --module")

    names.update(extra)
    return file_path, names


def resolve_relative_import(importing_file: str, from_module: str, dots: int) -> str | None:
    """
    Resolve a relative import like 'from ..foo.bar import X' to an absolute module name.

    importing_file: path of the file containing the import
    from_module: e.g. 'foo.bar' (without leading dots)
    dots: number of leading dots (1 for '.', 2 for '..', etc.)

    Returns resolved dotted module name like '_core.foo.bar', or None if resolution fails.
    """
    if not from_module and dots == 0:
        return None

    file_dir = Path(importing_file).parent

    # Go up 'dots - 1' directories (for '.', dots=1, so we stay in current package)
    target_dir = file_dir
    for _ in range(dots - 1):
        parent = target_dir.parent
        if str(parent) == str(target_dir):
            return None  # Went above filesystem root or mount point
        target_dir = parent

    # Collect package names from target_dir going up, but STOP at the first directory
    # that is clearly a project root (has __init__.py or common project markers).
    parts = []
    current = target_dir

    while True:
        name = current.name
        # If this dir has __init__.py it's a Python package; include its name
        if name and not name.startswith(".") and os.path.isfile(str(current / "__init__.py")):
            parts.append(name)
        elif name == "" or len(parts) > 0:
            # Reached top of package tree or filesystem root
            break
        else:
            # Directory without __init__.py — likely project root, stop here
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


class LanguageHandler(ABC):
    """Abstract handler for a specific language's import syntax."""

    @abstractmethod
    def matches_target(self, imported_module: str, target_names: Set[str]) -> bool:
        """Check if an imported module name refers to one of the target modules."""

    @abstractmethod
    def analyze_file(self, filepath: str, content_lines: List[str], target_names: Set[str], project_root: str) -> Set[str]:
        """Analyze a file and return the set of symbols from target modules that it uses."""


class PythonHandler(LanguageHandler):
    """Python import analysis using regex heuristics (not full AST)."""

    # Patterns for import lines
    IMPORT_RE = re.compile(r'^\s*import\s+(.+)$')
    FROM_IMPORT_RE = re.compile(r'^\s*from\s+(\.*)([\w\.]*)\s+import\s+(.+)\s*$')

    # Runtime/dynamic import patterns — detect when module name appears as string argument
    DYNAMIC_PATTERNS = [
        ("__import__",    re.compile(r'__import__\s*\(\s*["\']([^"\']+)["\']')),
        ("sys.modules[]", re.compile(r'sys\.modules\s*\[\s*["\']([^"\']+)["\']')),
        ("getattr(sys.modules)", re.compile(r'getattr\s*\(\s*sys\.modules\s*\[\s*["\']([^"\']+)["\']')),
        ("import_module", re.compile(r'import_module\s*\(\s*["\']([^"\']+)["\']')),
    ]

    def __init__(self):
        self._attr_pattern_cache = {}

    def matches_target(self, imported_module: str, target_names: Set[str]) -> bool:
        """Check if imported_module refers to any of the target names."""
        if not imported_module:
            return False
        # Exact match
        if imported_module in target_names:
            return True
        # Check if it's a sub-module of a target (e.g., 'foo.bar' when target is 'foo')
        for tn in target_names:
            if imported_module.startswith(tn + "."):
                return True
            # Also match dotted path like '_core.auth' vs file-based name '_core/auth'
            normalized = tn.replace("/", ".").replace("\\", ".")
            if imported_module == normalized or imported_module.startswith(normalized + "."):
                return True
        return False

    def _build_attr_pattern(self, aliases: Set[str]) -> re.Pattern | None:
        """Build regex pattern to match attribute access for given aliases."""
        key = frozenset(aliases)
        if key in self._attr_pattern_cache:
            return self._attr_pattern_cache[key]

        if not aliases:
            self._attr_pattern_cache[key] = None
            return None

        # Sort by length descending so longer aliases match first (avoid 'fa' matching inside 'fake')
        sorted_aliases = sorted(aliases, key=len, reverse=True)
        escaped = [re.escape(a) for a in sorted_aliases]
        # Match ALIAS.something where something is identifiers separated by dots, ending with identifier char
        # This ensures no trailing dot: foo.bar.baz OK, foo.bar. NOT OK
        pattern_str = r'\b(' + '|'.join(escaped) + r')\.([a-zA-Z_]\w*(?:\.\w+)*)'

        pat = re.compile(pattern_str)
        self._attr_pattern_cache[key] = pat
        return pat

    def _detect_dynamic_access(self, full_text: str, target_names: Set[str]) -> Set[str]:
        """Detect runtime/dynamic access to target modules via string module names."""
        found_patterns: Set[str] = set()
        
        for label, pat in self.DYNAMIC_PATTERNS:
            for m in pat.finditer(full_text):
                module_str = m.group(1)
                if self.matches_target(module_str, target_names):
                    found_patterns.add(label)
        
        return found_patterns

    def _get_import_kind(self, line: str, content_lines: List[str], idx: int) -> str:
        """
        Determine the semantic kind of an import based on its location.

        Returns one of: 'top-level', 'lazy' (inside function/method),
                        'conditional' (inside if block), 'fallback' (try/except).

        Heuristic approach — not full AST parsing.
        """
        stripped = line.strip()
        indent_len = len(line) - len(stripped)

        # Determine the base indentation level of this file (first non-empty, non-comment line with code)
        # This handles files that use consistent leading whitespace or are inside a block themselves.
        base_indent = self._get_file_base_indent(content_lines)

        relative_indent = indent_len - base_indent

        # If import is at the base indentation level → top-level
        if relative_indent <= 0:
            return "top-level"

        # Check if we're inside a function/method definition (lazy import)
        # Look backwards from current line to find the nearest block opener at lower indent
        func_pattern = re.compile(r'\s*(?:def|async def)\s+\w+')
        class_pattern = re.compile(r'\s*class\s+\w+')
        if_pattern = re.compile(r'\s*if\s+.+:')
        try_pattern = re.compile(r'\s*try\s*:')
        except_pattern = re.compile(r'\s*(?:except\b|\bfinally\s*:)')  # except [Type] [: msg]: or finally:

        # Walk backwards to find what block this import belongs to
        for prev_idx in range(idx - 1, -1, -1):
            prev_line = content_lines[prev_idx]
            prev_stripped = prev_line.strip()
            prev_indent = len(prev_line) - len(prev_stripped)
            prev_relative = prev_indent - base_indent

            # Skip empty lines and comments
            if not prev_stripped or prev_stripped.startswith("#"):
                continue

            # If we hit a line at lesser relative indentation → that's the parent block
            if prev_relative < relative_indent:
                # This is the parent block — check what kind it is
                if func_pattern.match(prev_line) or class_pattern.match(prev_line):
                    return "lazy"
                elif try_pattern.match(prev_line):
                    return "fallback"
                elif except_pattern.match(prev_line):
                    return "fallback"
                elif if_pattern.match(prev_line):
                    return "conditional"
                else:
                    # Some other statement at parent level — treat as lazy (inside something non-trivial)
                    return "lazy"

            # If same or greater relative indent → keep looking up past siblings

        # Default: if we can't determine precisely, it's indented so likely inside function/class
        return "lazy"

    def _get_file_base_indent(self, content_lines: List[str]) -> int:
        """Determine the base indentation level of a file from its first code lines."""
        for line in content_lines[:20]:  # Check first ~20 lines
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            return len(line) - len(stripped)
        return 0

    def _collect_from_import_items(self, content_lines: List[str], start_idx: int) -> str | None:
        """
        Collect the full list of imported items from a 'from X import ...' statement,
        handling both single-line and parenthesized multi-line forms.

        Returns the combined imports text (e.g., "a, b as c, d"), or None if parsing fails.
        """
        line = content_lines[start_idx].strip()

        # Extract everything after 'import' keyword
        m = re.search(r'\bimport\s+(.*)', line)
        if not m:
            return None

        imports_text = m.group(1).strip()

        # Single-line case: no opening paren or already closed on same line
        if not imports_text.startswith("("):
            return imports_text.rstrip(")").split("#")[0].strip()

        # Multi-line with parentheses: collect until closing ')'
        parts = []
        in_paren = True
        idx = start_idx + 1
        while idx < len(content_lines) and in_paren:
            l = content_lines[idx].strip().split("#")[0].strip()
            if ")" in l:
                # Take part before ')'
                parts.append(l.split(")", 1)[0])
                in_paren = False
            elif l:
                parts.append(l)
            idx += 1

        return ", ".join(parts).strip(", ") or None

    def analyze_file(self, filepath: str, content_lines: List[str], target_names: Set[str], project_root: str) -> Tuple[Dict[str, str], Set[str]]:
        """Analyze a Python file and return symbols from target modules that it uses.

        Returns (symbols_dict, dynamic_patterns):
            - symbols_dict: {symbol_name: import_kind} where kind is 'top-level', 'lazy', 'conditional', or 'fallback'
            - dynamic_patterns: set of pattern labels for runtime/dynamic access
        """
        used_symbols: Dict[str, str] = {}  # symbol -> import kind
        import_aliases: Dict[str, str] = {}  # local_alias -> imported_module_name

        for idx, line in enumerate(content_lines):
            stripped = line.strip()

            # Skip comments and empty lines
            if not stripped or stripped.startswith("#"):
                continue

            # Handle 'from X import Y, Z as W' (including multi-line)
            m = self.FROM_IMPORT_RE.match(line)
            if m:
                dots_str = m.group(1)
                from_module = m.group(2)
                dots = len(dots_str)

                # Resolve the base module name
                resolved_base = None
                if dots > 0:
                    resolved_base = resolve_relative_import(filepath, from_module, dots)
                else:
                    resolved_base = from_module

                if not resolved_base:
                    continue

                # Collect all imported items (handles multi-line with parentheses)
                imports_text = self._collect_from_import_items(content_lines, idx)
                if not imports_text:
                    continue

                # Parse imported symbols
                for item in imports_text.split(","):
                    item = item.strip()
                    if not item or item == "*":
                        continue
                    # Handle 'name as alias' — we care about original name from target module
                    parts = item.split(" as ")
                    original_name = parts[0].strip()
                    local_name = parts[1].strip() if len(parts) > 1 else original_name

                    # The full module being imported could be:
                    # resolved_base.original_name (e.g., 'from ._engine import backends' → '_engine.backends')
                    full_module_path = f"{resolved_base}.{original_name}" if resolved_base else original_name

                    base_matches = self.matches_target(resolved_base, target_names)
                    full_matches = self.matches_target(full_module_path, target_names)

                    if base_matches or full_matches:
                        # Determine import kind based on location in file
                        kind = self._get_import_kind(line, content_lines, idx)

                        if full_matches and base_matches is False:
                            # Package itself imported → track alias for attribute access later
                            import_aliases[local_name] = (full_module_path, kind)
                        else:
                            # Specific symbol from target module
                            used_symbols[original_name] = kind

                continue

            # Handle 'import X', 'import X as Y', 'import X, Y as Z'
            m = self.IMPORT_RE.match(line)
            if m:
                kind = self._get_import_kind(line, content_lines, idx)
                imports_part = m.group(1)
                for item in imports_part.split(","):
                    item = item.strip()
                    if not item:
                        continue

                    parts = item.split(" as ")
                    module_name = parts[0].strip()
                    local_alias = parts[1].strip() if len(parts) > 1 else module_name

                    if self.matches_target(module_name, target_names):
                        import_aliases[local_alias] = (module_name, kind)

                continue

        # Second pass: find attribute accesses for our aliases
        if import_aliases:
            pattern = self._build_attr_pattern(set(import_aliases.keys()))
            if pattern:
                full_text = "\n".join(content_lines)
                for m in pattern.finditer(full_text):
                    alias = m.group(1)
                    attr_path = m.group(2).strip()
                    if import_aliases.get(alias) and attr_path:
                        first_token = attr_path.split(".")[0]
                        if len(first_token) <= 3 and first_token.isalpha():
                            continue
                        # Attribute access inherits the import kind of its parent alias
                        _, kind = import_aliases[alias]
                        used_symbols[attr_path] = kind

        # Third pass: detect runtime/dynamic access via string module names
        full_text = "\n".join(content_lines)
        dynamic_patterns = self._detect_dynamic_access(full_text, target_names)

        return used_symbols, dynamic_patterns


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
        default="python",
        help="Language of the codebase (default: python). Only python supported in v1.",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Root directory to scan for imports (default: current directory).",
    )

    args = parser.parse_args()

    if not args.file and not args.module:
        parser.print_help(sys.stderr)
        print("\nError: must specify --file or --module", file=sys.stderr)
        sys.exit(1)

    try:
        target_path, target_names = resolve_target_names(args.file, args.module, args.module_names, args.project_root)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.language != "python":
        print(f"Error: language '{args.language}' not supported yet (only 'python' in v1)", file=sys.stderr)
        sys.exit(1)

    # Validate inputs before scanning
    project_root = os.path.abspath(args.project_root)
    if not os.path.isdir(project_root):
        print(f"Error: --project-root is not a directory: {project_root}", file=sys.stderr)
        sys.exit(1)

    target_path_abs = ""
    if args.file:
        # Resolve relative path against project_root or cwd
        file_arg = args.file
        if not os.path.isabs(file_arg):
            file_arg = os.path.join(project_root, file_arg)
        target_path_abs = os.path.abspath(file_arg)
        if not os.path.isfile(target_path_abs):
            print(f"Error: --file does not exist or is not a file: {target_path_abs}", file=sys.stderr)
            sys.exit(1)

    handler = PythonHandler()

    # Collect all .py files in the project
    all_files = collect_py_files(project_root)

    results: Dict[str, Dict[str, str]] = {}        # rel_path -> {symbol: kind}
    dynamic_results: Dict[str, Set[str]] = {}      # rel_path -> set of dynamic pattern labels

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

    # Summary line (with dynamic access count if any)
    summary_suffix = f" (+{num_dynamic} with dynamic access)" if num_dynamic else ""
    static_part = "# No static imports," if not results else f"# {num_files} file{'s' if num_files != 1 else ''}, {num_symbols} unique symbol{'s' if num_symbols != 1 else ''}"
    print(f"{static_part}{summary_suffix}")

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
