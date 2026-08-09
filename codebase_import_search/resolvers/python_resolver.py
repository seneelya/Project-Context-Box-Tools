"""Python import resolver for codebase_import_search (--incoming mode).

Given a target .py file, resolves its imports to source files within project_root.
Only returns imports that resolve to files inside the project (ignores stdlib/third-party).
"""

import os
import re
from pathlib import Path
from typing import List, Set

from ..core import ImportInfo, ImportResolver


class PythonResolver(ImportResolver):
    """Resolve Python imports in a target file to source files within project_root."""

    IMPORT_RE = re.compile(r"^\s*import\s+(.+)$")
    FROM_IMPORT_RE = re.compile(r"^\s*from\s+(\.*)([\w.]*)\s+import\s+(.+)")

    def get_extensions(self) -> Set[str]:
        return {".py"}

    def resolve_imports(self, target_file: str, project_root: str) -> List[ImportInfo]:
        """Resolve imports from target_file to files inside project_root."""
        target_file = os.path.abspath(target_file)
        project_root = os.path.abspath(project_root)
        importing_dir = os.path.dirname(target_file)

        with open(target_file, "r", encoding="utf-8-sig") as f:
            content_lines = f.readlines()

        results: List[ImportInfo] = []
        seen_raw_lines: Set[str] = set()  # Deduplicate identical imports

        for idx, line in enumerate(content_lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # from X import Y, Z as W  (including relative imports)
            m = self.FROM_IMPORT_RE.match(line)
            if m:
                dots_str = m.group(1)
                from_module = m.group(2)
                items_text = m.group(3).strip()

                # Remove inline comment from the opening line BEFORE multiline collection
                if "#" in items_text:
                    items_text = items_text.split("#")[0].strip()

                # Handle multi-line imports (parentheses): collect full import line
                if "(" in items_text and ")" not in items_text:
                    for next_line in content_lines[idx + 1 :]:
                        items_text += " " + next_line.strip()
                        if ")" in next_line:
                            break

                # Parse symbol names (ignore trailing comments, parentheses)
                symbols = self._parse_from_import_items(items_text)
                dots = len(dots_str)

                # Resolve module name to dotted form or path-like form
                if dots > 0:
                    # Relative import: resolve relative to importing_dir
                    resolved_module = self._resolve_relative_import(
                        importing_dir, from_module, dots, project_root
                    )
                else:
                    resolved_module = from_module

                # Build display line: for multiline imports, show compact "from X import (...)" 
                # instead of the raw first line with dangling "("
                base_import_line = stripped.split("#")[0].strip()
                if symbols and "(" in items_text:
                    raw_line = f"from {dots_str}{from_module} import ({len(symbols)} symbols)"
                else:
                    raw_line = base_import_line

                # Deduplicate: skip if we've seen this exact import line before
                if raw_line in seen_raw_lines:
                    continue
                seen_raw_lines.add(raw_line)

                abs_path = self._module_to_file(resolved_module, importing_dir, project_root)

                results.append(ImportInfo(
                    raw_line=raw_line,
                    module_name=resolved_module or (dots_str + from_module),
                    symbol_names=symbols,
                    resolved_path=abs_path,
                ))
                continue

            # import X [as Y], Z as W
            m = self.IMPORT_RE.match(line)
            if m:
                raw_line = stripped.split("#")[0].strip()

                # Deduplicate: skip if we've seen this exact import line before
                if raw_line in seen_raw_lines:
                    continue
                seen_raw_lines.add(raw_line)

                for item in m.group(1).split(","):
                    item = item.strip()
                    if not item or item.startswith("#"):
                        continue

                    module_name = item.split(" as ")[0].strip()
                    abs_path = self._module_to_file(module_name, importing_dir, project_root)

                    results.append(ImportInfo(
                        raw_line=raw_line,
                        module_name=module_name,
                        symbol_names=[],  # whole-module import
                        resolved_path=abs_path,
                    ))
                continue

        return results

    def _parse_from_import_items(self, text: str) -> List[str]:
        """Parse 'Y, Z as W' into list of original names."""
        text = text.strip().strip("()").split("#")[0].strip()
        if not text or text == "*":
            return []

        symbols = []
        for item in text.split(","):
            item = item.strip()
            if not item:
                continue
            # Keep original name (before 'as')
            name = item.split(" as ")[0].strip()
            if name and name != "*":
                symbols.append(name)
        return symbols

    def _resolve_relative_import(self, importing_dir: str, module_name: str, dots: int, project_root: str) -> str:
        """Resolve a relative import to an absolute dotted module name within project_root."""
        # For 'from ..X import Y': dots=2 means go up 1 level from current package (the file's dir)
        # Then append module_name if present.
        base_dir = importing_dir
        for _ in range(dots - 1):
            base_dir = os.path.dirname(base_dir)

        if not module_name:
            # 'from .. import X' — the target is base_dir itself as a package
            init_path = os.path.join(base_dir, "__init__.py")
            if os.path.isfile(init_path) and self._is_inside_project(init_path, project_root):
                return self._path_to_module(init_path, project_root) or ""
            # Fallback: try without __init__ as implicit namespace package
            if os.path.isdir(base_dir) and self._is_inside_project(base_dir, project_root):
                candidate_init = os.path.join(base_dir, "__init__.py")
                return self._path_to_module(candidate_init, project_root) or ""
            return ""

        # Convert dotted module to path and try to find it under base_dir
        candidate_path = os.path.join(base_dir, *module_name.split("."))

        # Try as package or file
        for suffix in ["/__init__.py", ".py"]:
            full_candidate = candidate_path + suffix
            if os.path.isfile(full_candidate) and self._is_inside_project(full_candidate, project_root):
                return self._path_to_module(full_candidate, project_root)

        # Fallback: try as directory (package without __init__ in Python 3.3+)
        if os.path.isdir(candidate_path) and self._is_inside_project(candidate_path, project_root):
            return self._path_to_module(candidate_path + "/__init__.py", project_root) or ""

        # Return dotted name even if not found (caller will show as unresolved)
        return module_name

    def _module_to_file(self, module_name: str, importing_dir: str, project_root: str) -> str | None:
        """Convert a dotted module name to an absolute file path inside project_root."""
        project_root = os.path.abspath(project_root)

        # Strategy 1: try as relative path from importing_dir (handles local packages like './foo')
        if "/" in module_name or "\\" in module_name:
            candidate = os.path.normpath(os.path.join(importing_dir, module_name.replace(".", "/")))
            for suffix in ["/__init__.py", ".py"]:
                full_candidate = candidate + suffix
                if os.path.isfile(full_candidate) and self._is_inside_project(full_candidate, project_root):
                    return full_candidate
            return None

        # Strategy 2: dotted module name -> try under importing_dir first (local package)
        local_candidates = [
            os.path.join(importing_dir, *module_name.split(".")),
        ]

        # Strategy 3: try from project_root (top-level package)
        top_level_candidates = [
            os.path.join(project_root, *module_name.split(".")),
        ]

        all_candidates = local_candidates + top_level_candidates

        for base_candidate in all_candidates:
            for suffix in ["/__init__.py", ".py"]:
                full_candidate = base_candidate + suffix
                if os.path.isfile(full_candidate) and self._is_inside_project(full_candidate, project_root):
                    return full_candidate

        # Not found inside project_root -> None (stdlib/third-party)
        return None

    def _path_to_module(self, filepath: str, project_root: str) -> str | None:
        """Convert an absolute file path to a dotted module name relative to project_root."""
        try:
            rel = os.path.relpath(filepath, project_root)
            parts = Path(rel).with_suffix("").parts
            # Handle __init__.py -> package name (without trailing .__init__)
            result = ".".join(parts)
            return result
        except ValueError:
            return None

    def _is_inside_project(self, filepath: str, project_root: str) -> bool:
        """Check if filepath is inside project_root."""
        try:
            rel = os.path.relpath(filepath, project_root)
            return not rel.startswith("..")
        except ValueError:
            return False
