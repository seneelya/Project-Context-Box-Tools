"""C# import resolver for codebase_import_search (--incoming mode).

Given a target .cs file, resolves its using directives to source files within project_root.
Only returns imports that resolve to files inside project-root (filters out System.*, NuGet packages, etc.).
"""

import os
import re
from typing import Dict, List, Set, Tuple

from ..core import ImportInfo, ImportResolver


class CSharpResolver(ImportResolver):
    """Resolves C# using directives and namespace aliases to files within project_root."""

    def get_extensions(self) -> Set[str]:
        return {".cs"}

    def resolve_imports(self, target_file: str, project_root: str) -> List[ImportInfo]:
        """Resolve using directives in target_file to files inside project_root."""

        # Build namespace -> files mapping for the entire project_root first
        ns_to_files = self._build_namespace_map(project_root)

        with open(target_file, "r", encoding="utf-8-sig") as f:
            content_lines = f.readlines()

        results: List[ImportInfo] = []
        seen_raw_lines: Set[str] = set()

        for idx, line in enumerate(content_lines):
            stripped = line.strip()

            # Remove UTF-8 BOM if present
            if stripped.startswith('\ufeff'):
                stripped = stripped[1:].strip()

            # Skip comments and empty lines
            if not stripped or stripped.startswith("//"):
                continue

            raw_line = stripped.split("//")[0].strip()

            # Deduplicate identical imports
            if raw_line in seen_raw_lines:
                continue

            # Pattern 1: using Alias = Namespace; (namespace alias)
            m = re.match(r"^using\s+(\w+)\s*=\s*(\S+?);\s*$", raw_line)
            if m:
                alias_name = m.group(1)
                namespace = m.group(2).rstrip(";")
                resolved_path, symbols = self._resolve_namespace(namespace, ns_to_files, project_root)
                symbol_display = f"[symbols: {alias_name}]" if not symbols else f"[aliases: {alias_name}, symbols: {', '.join(symbols)}]"
                results.append(ImportInfo(
                    raw_line=raw_line,
                    module_name=f"{namespace} (aliased as {alias_name})",
                    symbol_names=symbols,
                    resolved_path=resolved_path,
                ))
                seen_raw_lines.add(raw_line)
                continue

            # Pattern 2: using Namespace; (standard using directive)
            m = re.match(r"^using\s+(\S+?);\s*$", raw_line)
            if m:
                namespace = m.group(1).rstrip(";")
                resolved_path, symbols = self._resolve_namespace(namespace, ns_to_files, project_root)
                results.append(ImportInfo(
                    raw_line=raw_line,
                    module_name=namespace,
                    symbol_names=symbols,
                    resolved_path=resolved_path,
                ))
                seen_raw_lines.add(raw_line)
                continue

        return results

    def _build_namespace_map(self, project_root: str) -> Dict[str, List[Tuple[str, Set[str]]]]:
        """Build a mapping from namespace names to (file_path, {types_defined}) for all .cs files."""
        ns_to_sources: Dict[str, List[Tuple[str, Set[str]]]] = {}

        def _add_ns(ns: str, filepath: str, types: Set[str]):
            if ns not in ns_to_sources:
                ns_to_sources[ns] = []
            ns_to_sources[ns].append((filepath, types))

        for root_dir, dirs, files in os.walk(project_root):
            # Skip common exclusion directories
            dirs[:] = [d for d in dirs if d not in {".git", "bin", "obj", ".vs"}]

            for filename in files:
                if not filename.endswith(".cs"):
                    continue

                filepath = os.path.join(root_dir, filename)
                namespace, types = self._extract_file_info(filepath)
                if namespace:
                    _add_ns(namespace, filepath, types)
                    # Also add parent namespaces (for partial matches)
                    parts = namespace.split(".")
                    for i in range(len(parts) - 1):
                        parent_ns = ".".join(parts[:i + 1])
                        _add_ns(parent_ns, filepath, types)

        return ns_to_sources

    def _extract_file_info(self, filepath: str) -> Tuple[str | None, Set[str]]:
        """Extract namespace and public type names from a C# file."""
        try:
            with open(filepath, "r", encoding="utf-8-sig") as f:
                content = f.read()

            # Extract namespace (both block and file-scoped styles)
            ns_match = re.search(r"^\s*namespace\s+([\w.]+)", content, re.MULTILINE)
            namespace = ns_match.group(1) if ns_match else None

            # Extract public type names (classes, structs, enums, interfaces)
            types: Set[str] = set()
            type_pattern = re.compile(
                r"(?:public\s+)?(?:static\s+)?(?:partial\s+)*(class|struct|enum|interface)\s+(\w+)",
                re.MULTILINE,
            )
            for m in type_pattern.finditer(content):
                types.add(m.group(2))

            return namespace, types

        except (OSError, UnicodeDecodeError):
            return None, set()

    def _resolve_namespace(self, namespace: str, ns_to_files: Dict[str, List[Tuple[str, Set[str]]]], project_root: str) -> Tuple[str | None, List[str]]:
        """Resolve a C# namespace to files within project_root.

        Returns (resolved_path_or_none, list_of_symbols).
        """
        # Filter out common framework namespaces that won't be in project_root
        if namespace.startswith(("System", "Microsoft", "Newtonsoft", "NUnit")):
            return None, []

        # Try exact match first
        sources = ns_to_files.get(namespace)
        if sources and len(sources) == 1:
            filepath, symbols = sources[0]
            return filepath, list(symbols)

        # If multiple files share this namespace, pick the most specific one
        # (prefer files whose basename matches the last segment of the namespace)
        if sources:
            last_segment = namespace.split(".")[-1].lower()
            for filepath, symbols in sources:
                basename = os.path.splitext(os.path.basename(filepath))[0].lower()
                if basename == last_segment or basename.startswith(last_segment.lower()):
                    return filepath, list(symbols)
            # Fallback to first file found
            filepath, symbols = sources[0]
            return filepath, list(symbols)

        # Try subnamespace match: if we import "A.B.C", maybe it's defined in "A.B.C.D"
        for ns_key, key_sources in ns_to_files.items():
            if ns_key.startswith(namespace + "."):
                sources = key_sources
                break

        if sources and len(sources) == 1:
            filepath, symbols = sources[0]
            return filepath, list(symbols)

        return None, []


# For display formatting — called from CLI to format C# import output lines
def _format_csharp_import(info: ImportInfo) -> str:
    """Format a single C# import info for output."""
    raw_line = info.raw_line

    # If resolved successfully, show path with optional symbol count hint
    if info.resolved_path is not None:
        rel = os.path.relpath(info.resolved_path, start=os.path.dirname(info.resolved_path))
        # Actually we want relative to project_root — handled by caller

    return raw_line
