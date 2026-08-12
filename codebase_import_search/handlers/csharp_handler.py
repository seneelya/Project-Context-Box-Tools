"""C# language handler for codebase_import_search.

Supports using directives, namespace aliases, and type-level usage detection via regex heuristics.
"""

import os
import re
from typing import Dict, List, Set, Tuple

from ..core import LanguageHandler, get_import_kind_generic


class CSharpHandler(LanguageHandler):
    """Handles C# using statements to find which symbols from a target module are used elsewhere."""

    def __init__(self):
        self._attr_pattern_cache = {}
        # Cache for namespace→types mapping (computed once per project)
        self._namespace_types_cache: Dict[str, Set[str]] = {}
        # Cache: target file path → its declared namespace (avoid re-reading per consumer)
        self._target_ns_cache: Dict[str, str | None] = {}
        
        # Block patterns for import kind detection (using context)
        self.BLOCK_PATTERNS: Dict[str, re.Pattern] = {
            "lazy": re.compile(r"\s*(?:public\s+)?(?:void|int|string|Task<\w+>|bool|\w+)\s+\w+\s*\("),
            "conditional": re.compile(r"\s*if\s*\("),
            "fallback": re.compile(r"\s*(?:try\b|catch\b|finally\b)"),
        }

    def get_extensions(self) -> Set[str]:
        return {".cs"}

    def matches_target(self, imported_module: str, target_names: Set[str]) -> bool:
        """Check if a C# using namespace refers to one of the target namespaces."""
        cleaned = imported_module.strip()

        # Exact match or ends with .target (subnamespace)
        for name in target_names:
            if cleaned == name:
                return True
            if cleaned.endswith("." + name):
                return True
            if name.startswith(cleaned + "."):
                return True

        return False

    def _build_attr_pattern(self, aliases: Set[str]) -> re.Pattern:
        """Build regex for attribute access after alias."""
        key = tuple(sorted(aliases))
        if key in self._attr_pattern_cache:
            return self._attr_pattern_cache[key]
        joined = "|".join(re.escape(a) for a in aliases)
        pat = re.compile(rf"\b({joined})\.(\w+)")
        self._attr_pattern_cache[key] = pat
        return pat

    def _extract_public_types(self, filepath: str) -> Set[str]:
        """Extract public type names from a C# file (classes, structs, enums, interfaces)."""
        types_found: Set[str] = set()
        try:
            with open(filepath, "r", encoding="utf-8-sig") as f:
                content = f.read()

            # Match type definitions ONLY at line start (after attributes/modifiers), so
            # prose like "// a class that does X" does not yield a phantom type "that".
            # `record class`/`record struct` (C# 10) → take the name after the optional combo.
            type_pattern = re.compile(
                r"^[ \t]*(?:\[[^\]]*\][ \t]*)*"
                r"(?:(?:public|internal|protected|private|abstract|sealed|static|partial|readonly)[ \t]+)*"
                r"(?:class|struct|enum|interface|record)(?:[ \t]+(?:class|struct))?[ \t]+(\w+)",
                re.MULTILINE,
            )
            for m in type_pattern.finditer(content):
                types_found.add(m.group(1))

        except (OSError, UnicodeDecodeError):
            pass

        return types_found

    def _target_namespace(self, target_file_path: str | None) -> str | None:
        """Cached declared namespace of the target file (or None if unknown)."""
        if not target_file_path:
            return None
        if target_file_path not in self._target_ns_cache:
            self._target_ns_cache[target_file_path] = self._extract_namespace(target_file_path)
        return self._target_ns_cache[target_file_path]

    def _extract_namespace(self, filepath: str) -> str | None:
        """Extract namespace declaration from a C# file."""
        try:
            with open(filepath, "r", encoding="utf-8-sig") as f:
                content = f.read()

            # Match namespace declaration (both block and file-scoped styles)
            ns_pattern = re.compile(r"namespace\s+([\w.]+)")
            m = ns_pattern.search(content)
            if m:
                return m.group(1)
        except (OSError, UnicodeDecodeError):
            pass

        return None

    def _get_target_types_cached(
        self, target_names: Set[str], project_root: str, target_file_path: str = None
    ) -> Set[str]:
        """Get all public types from target namespaces — computed once per run via cache."""
        # Use a combined key for all target names to avoid recomputation
        cache_key = tuple(sorted(target_names)) + (project_root,)
        
        if cache_key in self._namespace_types_cache:
            return self._namespace_types_cache[cache_key]

        result_types: Set[str] = set()
        
        # OPTIMIZATION: If we have an actual target file path, extract types directly from it.
        # This avoids expensive glob.glob("**/*.cs") on large projects like Unity with thousands of files.
        if target_file_path and os.path.isfile(target_file_path):
            result_types.update(self._extract_public_types(target_file_path))
        else:
            # Fallback: search via glob patterns (--module mode or no specific file)
            # This is slower but necessary when we don't know the exact source file.
            import glob
            
            seen_files: Set[str] = set()
            
            for tname in target_names:
                try:
                    basename = tname.split(".")[-1]
                    patterns = [
                        os.path.join(project_root, "**", f"{tname}.cs"),
                        os.path.join(project_root, "**", f"{basename}.cs"),
                        os.path.join(project_root, "**", tname.replace(".", "/") + "*.cs"),
                    ]
                    for pattern in patterns:
                        for cs_file in glob.glob(pattern, recursive=True):
                            real_path = os.path.realpath(cs_file)
                            if real_path not in seen_files:
                                seen_files.add(real_path)
                                result_types.update(self._extract_public_types(cs_file))
                except Exception:
                    pass
        
        self._namespace_types_cache[cache_key] = result_types
        return result_types

    def find_symbol_usages(self, filepath: str, content_lines: List[str], names: Set[str]) -> Dict[str, List[int]]:
        """Where each name is USED as real code in this file (1-based lines).

        Excludes `using` directives and `//` / full-line `/* */` comments. Shared by
        --incoming --verbose (usages inside the target file).
        """
        result: Dict[str, List[int]] = {}
        if not names or not content_lines:
            return result

        sorted_syms = sorted(names, key=len, reverse=True)
        usage_pattern = re.compile(r'\b(' + '|'.join(re.escape(s) for s in sorted_syms) + r')\b')

        for idx, line in enumerate(content_lines):
            stripped = line.strip()
            if stripped.startswith('\ufeff'):
                stripped = stripped[1:].strip()
            if not stripped or stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
                continue
            if stripped.startswith("using "):
                continue
            for m in usage_pattern.finditer(stripped):
                sym = m.group(1)
                if sym in names:
                    result.setdefault(sym, []).append(idx + 1)
        return result

    def analyze_file(
        self, filepath: str, content_lines: List[str], target_names: Set[str], project_root: str, target_file_path: str = None
    ) -> Tuple[Dict[str, str], Dict[str, List[int]], Set[str]]:
        """Analyze a C# file and return (symbols_dict, symbol_lines, dynamic_patterns)."""
        used_symbols: Dict[str, str] = {}
        symbol_lines: Dict[str, List[int]] = {}
        dyn_patterns: Set[str] = set()

        # Track aliases that refer to target namespaces (for attribute access)
        import_aliases: Dict[str, Tuple[str, str]] = {}

        # Track which target namespaces are imported via standard using directives
        imported_target_ns: List[Tuple[str, str]] = []  # (namespace, kind)

        for idx, line in enumerate(content_lines):
            stripped = line.strip()

            # Remove UTF-8 BOM if present (common in .NET projects)
            if stripped.startswith('\ufeff'):
                stripped = stripped[1:].strip()

            # Skip comments and empty lines
            if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
                continue

            kind = get_import_kind_generic(line, content_lines, idx, self.BLOCK_PATTERNS)

            # Pattern: using Alias = Namespace; (namespace alias)
            m = re.match(r"using\s+(\w+)\s*=\s*(\S+?);\s*$", stripped)
            if m:
                alias_name = m.group(1)
                ns = m.group(2).rstrip(";")

                # Check if this namespace refers to a target
                for tname in target_names:
                    if ns == tname or ns.endswith("." + tname):
                        import_aliases[alias_name] = (ns, kind)
                        break
                continue

            # Pattern: using Namespace; (standard using directive)
            m = re.match(r"using\s+(\S+?);\s*$", stripped)
            if m:
                ns = m.group(1).rstrip(";")

                for tname in target_names:
                    if self.matches_target(ns, {tname}):
                        # If it's an exact match or subnamespace of target
                        if ns == tname or ns.endswith("." + tname):
                            # Track that this target namespace is imported (types accessible without prefix)
                            imported_target_ns.append((ns, kind))
                        break
                continue

            # Dynamic type loading: Type.GetType("Namespace.Class") or Assembly.Load(...)
            if 'Type.GetType("' in line and any(tname.replace(".", "\\\\.") in line for tname in target_names):
                dyn_patterns.add('Type.GetType()')
            if 'Assembly.Load' in line and 'CreateInstance' in line:
                dyn_patterns.add("Assembly.CreateInstance()")

        # Second pass: attribute access for aliases — track line numbers
        if import_aliases:
            pattern = self._build_attr_pattern(set(import_aliases.keys()))

            for idx, line in enumerate(content_lines):
                stripped = line.strip()
                if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
                    continue

                for m in pattern.finditer(line):
                    alias = m.group(1)
                    member = m.group(2)
                    attr_path = f"{alias}.{member}"

                    mock_suffixes = {"Mock", "Setup", "Verify", "Returns", "Object"}
                    if any(member == s or member.startswith(s + ".") for s in mock_suffixes):
                        continue

                    _, kind = import_aliases[alias]
                    used_symbols[attr_path] = kind
                    symbol_lines.setdefault(attr_path, []).append(idx + 1)

        # Implicit visibility: C# types in the target's namespace are visible WITHOUT a
        # `using` from the SAME namespace and from any DESCENDANT namespace (an inner
        # namespace sees its ancestors). If this file's namespace is the target's namespace
        # or a descendant of it, treat it as an implicit import so the type-usage scan runs —
        # this is how C# "who uses this file" works (type references, not import lines).
        if not imported_target_ns:
            consumer_ns = None
            for line in content_lines:
                s = line.strip()
                if s.startswith('﻿'):
                    s = s[1:].strip()
                m = re.match(r"namespace\s+([\w.]+)", s)
                if m:
                    consumer_ns = m.group(1)
                    break
            target_ns = self._target_namespace(target_file_path)
            visible = False
            if consumer_ns:
                if target_ns and (consumer_ns == target_ns or consumer_ns.startswith(target_ns + ".")):
                    visible = True
                elif consumer_ns in target_names:   # --module mode fallback (no target file)
                    visible = True
            if visible:
                imported_target_ns.append((consumer_ns, "top-level"))

        # Third pass: if target namespace is imported via using directive,
        # check for usage of types from that namespace — track line numbers
        if imported_target_ns:
            # Use cached target types — pass target_file_path to avoid expensive glob.glob on large projects
            target_types = self._get_target_types_cached(target_names, project_root, target_file_path)

            if not target_types:
                for ns, kind in imported_target_ns:
                    used_symbols[f"[namespace:{ns}]"] = kind
                return used_symbols, symbol_lines, dyn_patterns

            # Scan file for type usages with line numbers
            excluded_identifiers = {
                "System", "String", "Int32", "Int64", "Boolean", "Double", "Float",
                "Object", "Array", "List", "Dictionary", "Task", "Action", "Func",
                "IEnumerable", "IList", "ICollection", "IDictionary", "KeyValuePair",
                "Console", "DateTime", "Guid", "Exception", "StringComparison",
            }

            candidate_types = target_types - excluded_identifiers

            # Collect using directive lines to exclude from usage results
            using_line_indices = set()
            for idx, line in enumerate(content_lines):
                stripped = line.strip()
                if stripped.startswith("using "):
                    using_line_indices.add(idx)

            for type_name in candidate_types:
                pattern = re.compile(rf"\b{re.escape(type_name)}\b")
                for idx, line in enumerate(content_lines):
                    if idx in using_line_indices:
                        continue  # Skip using directive lines — we want actual type usages
                    if pattern.search(line):
                        _, kind = imported_target_ns[0]
                        used_symbols[type_name] = kind
                        symbol_lines.setdefault(type_name, []).append(idx + 1)

        return used_symbols, symbol_lines, dyn_patterns
