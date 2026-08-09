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

            # Match public class/struct/enums/interface definitions
            type_pattern = re.compile(
                r"(?:public\s+)?(?:static\s+)?(?:partial\s+)*(class|struct|enum|interface)\s+(\w+)",
                re.MULTILINE,
            )
            for m in type_pattern.finditer(content):
                types_found.add(m.group(2))

        except (OSError, UnicodeDecodeError):
            pass

        return types_found

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

    def analyze_file(
        self, filepath: str, content_lines: List[str], target_names: Set[str], project_root: str
    ) -> Tuple[Dict[str, str], Set[str]]:
        """Analyze a C# file and return (symbols_dict, dynamic_patterns)."""
        used_symbols: Dict[str, str] = {}
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
            if 'Type.GetType("' in line and any(tname.replace(".", "\\.") in line for tname in target_names):
                dyn_patterns.add('Type.GetType()')
            if 'Assembly.Load' in line and 'CreateInstance' in line:
                dyn_patterns.add("Assembly.CreateInstance()")

        # Second pass: attribute access for aliases (namespace segments used as prefixes)
        if import_aliases:
            pattern = self._build_attr_pattern(set(import_aliases.keys()))

            for line in content_lines:
                stripped = line.strip()
                if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
                    continue

                for m in pattern.finditer(line):
                    alias = m.group(1)
                    member = m.group(2)
                    attr_path = f"{alias}.{member}"

                    # Filter common C# test/mock methods (similar to Jest mocks in TS)
                    mock_suffixes = {"Mock", "Setup", "Verify", "Returns", "Object"}
                    if any(member == s or member.startswith(s + ".") for s in mock_suffixes):
                        continue

                    _, kind = import_aliases[alias]
                    used_symbols[attr_path] = kind

        # Third pass: if target namespace is imported via using directive,
        # check for usage of types from that namespace
        if imported_target_ns:
            # Extract all public type names from the target file(s)
            target_types = set()
            for tname in target_names:
                # Try to find corresponding file path and extract types
                try:
                    # Search for .cs files with matching name (handle both dotted names and basenames)
                    basename = tname.split(".")[-1]  # Last segment of namespace or filename
                    import glob
                    patterns = [
                        os.path.join(project_root, "**", f"{tname}.cs"),
                        os.path.join(project_root, "**", f"{basename}.cs"),
                        os.path.join(project_root, "**", tname.replace(".", "/") + "*.cs"),
                    ]
                    for pattern in patterns:
                        for cs_file in glob.glob(pattern, recursive=True):
                            target_types.update(self._extract_public_types(cs_file))
                except Exception:
                    pass

            if not target_types:
                # Fallback: mark namespace usage without specific types
                for ns, kind in imported_target_ns:
                    used_symbols[f"[namespace:{ns}]"] = kind
                return used_symbols, dyn_patterns

            # Now scan file for type usages (PascalCase identifiers that match target types)
            content_text = "\n".join(content_lines)

            # Common keywords/types to exclude from detection
            excluded_identifiers = {
                "System", "String", "Int32", "Int64", "Boolean", "Double", "Float",
                "Object", "Array", "List", "Dictionary", "Task", "Action", "Func",
                "IEnumerable", "IList", "ICollection", "IDictionary", "KeyValuePair",
                "Console", "DateTime", "Guid", "Exception", "StringComparison",
            }

            candidate_types = target_types - excluded_identifiers

            for type_name in candidate_types:
                # Check if this type name appears as a word boundary match
                pattern = re.compile(rf"\b{re.escape(type_name)}\b")
                matches = pattern.findall(content_text)
                if matches and len(matches) > 1:  # More than just declaration context
                    _, kind = imported_target_ns[0]
                    used_symbols[type_name] = kind

        return used_symbols, dyn_patterns
