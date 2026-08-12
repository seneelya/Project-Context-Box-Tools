"""TypeScript/JavaScript language handler for codebase_import_search.

Supports ES module imports and CommonJS require() patterns via regex heuristics.
"""

import os
import re
from typing import Dict, List, Set, Tuple

from ..core import LanguageHandler

# ESM/NodeNext: an import path may carry a .js extension while the file on disk is .ts
# (`import x from "./util.js"` → util.ts). Strip these before matching/resolving.
_MODULE_EXTS = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}


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

    # Symbols that are clearly NOT from the target module (Jest mock methods, etc.)
    MOCK_METHODS = {"mock", "mockImplementation", "mockResolvedValue", "mockRejectedValue",
                    "mockReturnValue", "mockClear", "mockReset", "mockRestore",
                    "mock.calls", "mock.instances", "mock.results"}

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
        # Candidate spellings of the specifier: as-is, slash-normalized, and with a trailing
        # module extension stripped (`./util.js` → `./util`, to match extensionless target names).
        specs = {imported_specifier, imported_specifier.replace("\\", "/")}
        for s in list(specs):
            root, ext = os.path.splitext(s)
            if ext.lower() in _MODULE_EXTS:
                specs.add(root)
        for normalized in specs:
            if normalized in target_names:
                return True
            # Sub-module check (e.g., 'foo/bar' when target is 'foo')
            for tn in target_names:
                tnorm = tn.replace("\\", "/").rstrip("/")
                if normalized == tnorm or normalized.startswith(tnorm + "/"):
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

    def find_symbol_usages(self, filepath: str, content_lines: List[str], names: Set[str]) -> Dict[str, List[int]]:
        """Where each name is USED as real code in this file (1-based lines).

        Excludes import/require lines and line/JSDoc comments. Shared by analyze_file
        (downstream) and by --incoming --verbose (usages inside the target file).
        """
        result: Dict[str, List[int]] = {}
        if not names or not content_lines:
            return result

        sorted_syms = sorted(names, key=len, reverse=True)
        usage_pattern = re.compile(r'\b(' + '|'.join(re.escape(s) for s in sorted_syms) + r')\b')

        import_line_indices = {
            idx for idx, line in enumerate(content_lines)
            if line.strip().startswith("import ") or line.strip().startswith("from ") or "require(" in line.strip()
        }

        for idx, line in enumerate(content_lines):
            if idx in import_line_indices:
                continue
            stripped = line.strip()
            if not stripped or stripped.startswith("//") or stripped.startswith("*"):
                continue
            for m in usage_pattern.finditer(stripped):
                sym = m.group(1)
                if sym in names:
                    result.setdefault(sym, []).append(idx + 1)
        return result

    def analyze_file(
        self, filepath: str, content_lines: List[str], target_names: Set[str], project_root: str, target_file_path: str = None
    ) -> Tuple[Dict[str, str], Dict[str, List[int]], Set[str]]:
        """Analyze a TS/JS file and return (symbols_dict, symbol_lines, dynamic_patterns).

        Args:
            target_file_path: Optional path to the target file being analyzed (used by some handlers for optimization).
        """
        used_symbols: Dict[str, str] = {}
        symbol_lines: Dict[str, List[int]] = {}
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
                    base_path = module_specifier.rstrip("/") or "."
                    full_path = f"{base_path}/{original}"

                    if self.matches_target(module_specifier, target_names):
                        used_symbols[original] = kind
                        symbol_lines.setdefault(original, []).append(idx + 1)
                    elif self.matches_target(full_path, target_names):
                        used_symbols[original] = kind
                        symbol_lines.setdefault(original, []).append(idx + 1)

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
                        symbol_lines.setdefault(original, []).append(idx + 1)

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

        # Second pass: attribute access for aliases — track line numbers via full text scan
        if import_aliases:
            pattern = self._build_attr_pattern(set(import_aliases.keys()))
            if pattern:
                # content_lines is keepends=True → join without adding newlines,
                # otherwise "\n".join doubles line breaks and shifts line numbers.
                full_text = "".join(content_lines)
                for m in pattern.finditer(full_text):
                    alias = m.group(1)
                    attr_path = m.group(2).strip()
                    if import_aliases.get(alias) and attr_path:
                        first_token = attr_path.split(".")[0]
                        if len(first_token) <= 3 and first_token.isalpha():
                            continue
                        if first_token in self.MOCK_METHODS or any(attr_path.startswith(mp + ".") for mp in self.MOCK_METHODS):
                            continue
                        pos = m.start()
                        line_num = full_text[:pos].count("\n") + 1
                        line_idx = line_num - 1
                        # Skip mentions inside line/JSDoc comments — guarding
                        # used_symbols (not just symbol_lines) avoids phantom symbols.
                        if 0 <= line_idx < len(content_lines):
                            ls = content_lines[line_idx].lstrip()
                            if ls.startswith("//") or ls.startswith("*"):
                                continue
                        _, kind = import_aliases[alias]
                        used_symbols[attr_path] = kind
                        symbol_lines.setdefault(attr_path, []).append(line_num)

        # Post-processing: filter out attribute access that is clearly on a direct named import
        to_remove = []
        for sym in list(used_symbols.keys()):
            if "." in sym:
                first_token = sym.split(".")[0]
                if first_token in used_symbols:
                    rest = sym[len(first_token)+1:]
                    if rest.startswith("mock") or rest.startswith("test"):
                        to_remove.append(sym)

        for sym in to_remove:
            del used_symbols[sym]

        # Second pass for direct named imports: find where symbols are actually USED (not just imported)
        direct_imported_names = set(used_symbols.keys())
        for sym_name, lns in self.find_symbol_usages(filepath, content_lines, direct_imported_names).items():
            symbol_lines.setdefault(sym_name, []).extend(lns)

        # Third pass: dynamic import() detection
        full_text = "\n".join(content_lines)
        dynamic_patterns: Set[str] = set()
        for m in self.DYNAMIC_IMPORT_RE.finditer(full_text):
            module_str = m.group(1).strip().rstrip("/")
            if self.matches_target(module_str, target_names):
                dynamic_patterns.add("import()")

        return used_symbols, symbol_lines, dynamic_patterns
