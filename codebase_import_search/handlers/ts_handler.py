"""TypeScript/JavaScript language handler for codebase_import_search.

Supports ES module imports and CommonJS require() patterns via regex heuristics.
"""

import re
from typing import Dict, List, Set, Tuple

from ..core import LanguageHandler


class TypeScriptHandler(LanguageHandler):
    """TypeScript/JavaScript import analysis using regex heuristics (not full AST).

    Patterns detected:
      - ES named:  import { foo, bar } from './module'
      - ES default: import Foo from './module'
      - ES namespace: import * as ns from './module'
      - CJS const x = require('./module')
      - CJS destructured: const { foo } = require('./module')
      - Dynamic import(): flagged but exact symbols unknown
    """

    # ES named imports (single-line): import { a, b as c } from '...'
    ES_NAMED_RE = re.compile(
        r'^\s*import\s*\{([^}]+)\}\s*from\s+["\']([^"\']+)["\']'
    )

    # ES default import: import Foo from '...'
    ES_DEFAULT_RE = re.compile(
        r'^\s*import\s+(\w+)\s+from\s+["\']([^"\']+)["\']'
    )

    # ES namespace import: import * as ns from '...'
    ES_NAMESPACE_RE = re.compile(
        r'^\s*import\s+\*\s+as\s+(\w+)\s+from\s+["\']([^"\']+)["\']'
    )

    # ES side-effect import: import '...' (no symbols captured)
    # Not used for symbol detection but could be flagged in the future.

    # CommonJS: const x = require('...') or var/let
    CJS_REQUIRE_RE = re.compile(
        r'^\s*(?:const|let|var)\s+(\w+)\s*=\s*require\s*\(\s*["\']([^"\']+)["\']'
    )

    # CJS destructured: const { foo, bar as b } = require('...')
    CJS_DESTRUCTURE_RE = re.compile(
        r'^\s*(?:const|let|var)\s*\{([^}]+)\}\s*=\s*require\s*\(\s*["\']([^"\']+)["\']'
    )

    # Dynamic import(): detect module name strings used at runtime
    DYNAMIC_IMPORT_RE = re.compile(
        r'import\s*\(\s*["\']([^"\']+)["\']'
    )

    # Attribute access after alias: ALIAS.something
    # Built dynamically per-file based on collected aliases.

    BLOCK_PATTERNS = {
        "lazy": re.compile(r'\s*(?:function|async function|const\s+\w+\s*=.*=>|let\s+\w+\s*=.*=>)'),
        "fallback": re.compile(r'\s*(?:try\b|\bcatch\b|\bfinally\b)'),
        "conditional": re.compile(r'\s*if\s+\('),
    }

    def __init__(self):
        self._attr_pattern_cache = {}

    def get_extensions(self) -> Set[str]:
        return {".ts", ".tsx", ".js", ".jsx"}

    def matches_target(self, imported_specifier: str, target_names: Set[str]) -> bool:
        """Check if an import specifier refers to one of the target modules.

        For TS/JS we compare against:
          - exact path-like names (e.g., './src/utils', 'lib/helpers')
          - dotted names (for package-style imports)
        """
        if not imported_specifier:
            return False
        # Exact match
        if imported_specifier in target_names:
            return True
        # Normalize slashes for comparison
        normalized = imported_specifier.replace("\\", "/")
        if normalized in target_names:
            return True
        # Sub-module check (e.g., 'foo/bar' when target is 'foo')
        for tn in target_names:
            tnorm = tn.replace("\\", "/").rstrip("/")
            if normalized == tnorm:
                return True
            if normalized.startswith(tnorm + "/"):
                return True
        # Also try dotted form (for package-style names like "pkg.module")
        dotted = normalized.replace("/", ".")
        for tn in target_names:
            if dotted == tn or dotted.startswith(tn + "."):
                return True
        return False

    def _build_attr_pattern(self, aliases: Set[str]) -> re.Pattern | None:
        key = frozenset(aliases)
        if key in self._attr_pattern_cache:
            return self._attr_pattern_cache[key]
        if not aliases:
            self._attr_pattern_cache[key] = None
            return None
        sorted_aliases = sorted(aliases, key=len, reverse=True)
        escaped = [re.escape(a) for a in sorted_aliases]
        pattern_str = r'\b(' + '|'.join(escaped) + r')\.([a-zA-Z_$]\w*(?:\.\w+)*)'
        pat = re.compile(pattern_str)
        self._attr_pattern_cache[key] = pat
        return pat

    def _get_import_kind(self, line: str, content_lines: List[str], idx: int) -> str:
        from ..core import get_import_kind_generic
        return get_import_kind_generic(line, content_lines, idx, self.BLOCK_PATTERNS)

    def _parse_named_items(self, items_text: str):
        """Parse 'foo, bar as b' into list of (original_name, local_name)."""
        result = []
        for item in items_text.split(","):
            item = item.strip()
            if not item:
                continue
            parts = item.split(" as ")
            original = parts[0].strip()
            local = parts[1].strip() if len(parts) > 1 else original
            if original and local != "*":
                result.append((original, local))
        return result

    def analyze_file(
        self, filepath: str, content_lines: List[str], target_names: Set[str], project_root: str
    ) -> Tuple[Dict[str, str], Set[str]]:
        """Analyze a TS/JS file and return (symbols_dict, dynamic_patterns)."""
        used_symbols: Dict[str, str] = {}
        import_aliases: Dict[str, Tuple[str, str]] = {}  # local_alias -> (module_specifier, kind)

        for idx, line in enumerate(content_lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("//"):
                continue

            # ES named imports: import { foo } from '...'
            m = self.ES_NAMED_RE.match(line)
            if m:
                items_text = m.group(1)
                module_specifier = m.group(2).strip().rstrip("/")
                kind = self._get_import_kind(line, content_lines, idx)

                for original, local in self._parse_named_items(items_text):
                    # Build full path for sub-module check (e.g., 'from "./src" -> Analyzer' where target is './src/analyzer')
                    base_path = module_specifier.rstrip("/") or "."
                    full_path = f"{base_path}/{original}"

                    if self.matches_target(module_specifier, target_names):
                        # Importing symbols directly FROM the target module
                        used_symbols[original] = kind
                    elif self.matches_target(full_path, target_names):
                        # The imported name itself IS a submodule of our target
                        used_symbols[original] = kind

                continue

            # ES default import: import Foo from '...'
            m = self.ES_DEFAULT_RE.match(line)
            if m:
                local_alias = m.group(1)
                module_specifier = m.group(2).strip().rstrip("/")
                kind = self._get_import_kind(line, content_lines, idx)

                if self.matches_target(module_specifier, target_names):
                    import_aliases[local_alias] = (module_specifier, kind)

                continue

            # ES namespace import: import * as ns from '...'
            m = self.ES_NAMESPACE_RE.match(line)
            if m:
                local_alias = m.group(1)
                module_specifier = m.group(2).strip().rstrip("/")
                kind = self._get_import_kind(line, content_lines, idx)

                if self.matches_target(module_specifier, target_names):
                    import_aliases[local_alias] = (module_specifier, kind)

                continue

            # CJS destructured: const { foo } = require('...')
            m = self.CJS_DESTRUCTURE_RE.match(line)
            if m:
                items_text = m.group(1)
                module_specifier = m.group(2).strip().rstrip("/")
                kind = self._get_import_kind(line, content_lines, idx)

                if self.matches_target(module_specifier, target_names):
                    for original, local in self._parse_named_items(items_text):
                        used_symbols[original] = kind

                continue

            # CJS require: const x = require('...')
            m = self.CJS_REQUIRE_RE.match(line)
            if m:
                local_alias = m.group(1)
                module_specifier = m.group(2).strip().rstrip("/")
                kind = self._get_import_kind(line, content_lines, idx)

                if self.matches_target(module_specifier, target_names):
                    import_aliases[local_alias] = (module_specifier, kind)

                continue

        # Second pass: attribute access for aliases (namespace/default/CJS require targets)
        if import_aliases:
            pattern = self._build_attr_pattern(set(import_aliases.keys()))
            if pattern:
                full_text = "\n".join(content_lines)
                for m in pattern.finditer(full_text):
                    alias = m.group(1)
                    attr_path = m.group(2).strip()
                    if import_aliases.get(alias) and attr_path:
                        first_token = attr_path.split(".")[0]
                        # Filter obvious false positives like file extensions in strings
                        if len(first_token) <= 3 and first_token.isalpha():
                            continue
                        _, kind = import_aliases[alias]
                        used_symbols[attr_path] = kind

        # Third pass: dynamic import() detection
        full_text = "\n".join(content_lines)
        dynamic_patterns: Set[str] = set()
        for m in self.DYNAMIC_IMPORT_RE.finditer(full_text):
            module_str = m.group(1).strip().rstrip("/")
            if self.matches_target(module_str, target_names):
                dynamic_patterns.add("import()")

        return used_symbols, dynamic_patterns
