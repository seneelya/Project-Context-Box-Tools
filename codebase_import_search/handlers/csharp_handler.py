"""C# language handler for codebase_import_search.

Supports using directives and namespace aliases via regex heuristics.
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

    def analyze_file(
        self, filepath: str, content_lines: List[str], target_names: Set[str], project_root: str
    ) -> Tuple[Dict[str, str], Set[str]]:
        """Analyze a C# file and return (symbols_dict, dynamic_patterns)."""
        used_symbols: Dict[str, str] = {}
        dyn_patterns: Set[str] = set()

        # Track aliases that refer to target namespaces (for attribute access)
        import_aliases: Dict[str, Tuple[str, str]] = {}

        for idx, line in enumerate(content_lines):
            stripped = line.strip()

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
                            # The namespace itself is used — track as alias for attribute access
                            last_segment = ns.split(".")[-1]
                            import_aliases[last_segment] = (ns, kind)
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
            direct_imported_names = set(used_symbols.keys())

            for line in content_lines:
                stripped = line.strip()
                if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
                    continue

                for m in pattern.finditer(line):
                    alias = m.group(1)
                    member = m.group(2)
                    attr_path = f"{alias}.{member}"

                    # Skip if this is a direct import already tracked
                    if member in direct_imported_names:
                        continue

                    # Filter common C# test/mock methods (similar to Jest mocks in TS)
                    mock_suffixes = {"Mock", "Setup", "Verify", "Returns", "Object"}
                    if any(member == s or member.startswith(s + ".") for s in mock_suffixes):
                        continue

                    _, kind = import_aliases[alias]
                    used_symbols[attr_path] = kind

        return used_symbols, dyn_patterns
