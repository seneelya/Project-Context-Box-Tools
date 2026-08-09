"""Python language handler for codebase_import_search."""

import re
from typing import Dict, List, Set, Tuple

from ..core import LanguageHandler, resolve_relative_import


class PythonHandler(LanguageHandler):
    """Python import analysis using regex heuristics (not full AST)."""

    IMPORT_RE = re.compile(r'^\s*import\s+(.+)$')
    FROM_IMPORT_RE = re.compile(r'^\s*from\s+(\.*)([\w\.]*)\s+import\s+(.+)\s*$')

    DYNAMIC_PATTERNS = [
        ("__import__", re.compile(r'__import__\s*\(\s*["\']([^"\']+)["\']')),
        ("sys.modules[]", re.compile(r'sys\.modules\s*\[\s*["\']([^"\']+)["\']')),
        ("getattr(sys.modules)", re.compile(r'getattr\s*\(\s*sys\.modules\s*\[\s*["\']([^"\']+)["\']')),
        ("import_module", re.compile(r'import_module\s*\(\s*["\']([^"\']+)["\']')),
    ]

    BLOCK_PATTERNS = {
        "lazy": re.compile(r'\s*(?:def|async def|class)\s+\w+'),
        "fallback": re.compile(r'\s*(?:try\s*:|\bexcept\b|\bfinally\s*:)'),
        "conditional": re.compile(r'\s*if\s+.+:'),
    }

    def __init__(self):
        self._attr_pattern_cache = {}

    def get_extensions(self) -> Set[str]:
        return {".py"}

    def matches_target(self, imported_module: str, target_names: Set[str]) -> bool:
        if not imported_module:
            return False
        if imported_module in target_names:
            return True
        for tn in target_names:
            if imported_module.startswith(tn + "."):
                return True
            normalized = tn.replace("/", ".").replace("\\", ".")
            if imported_module == normalized or imported_module.startswith(normalized + "."):
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
        pattern_str = r'\b(' + '|'.join(escaped) + r')\.([a-zA-Z_]\w*(?:\.\w+)*)'

        pat = re.compile(pattern_str)
        self._attr_pattern_cache[key] = pat
        return pat

    def _detect_dynamic_access(self, full_text: str, target_names: Set[str]) -> Set[str]:
        found_patterns: Set[str] = set()
        for label, pat in self.DYNAMIC_PATTERNS:
            for m in pat.finditer(full_text):
                module_str = m.group(1)
                if self.matches_target(module_str, target_names):
                    found_patterns.add(label)
        return found_patterns

    def _collect_from_import_items(self, content_lines: List[str], start_idx: int) -> str | None:
        line = content_lines[start_idx].strip()
        m = re.search(r'\bimport\s+(.*)', line)
        if not m:
            return None

        imports_text = m.group(1).strip()
        if not imports_text.startswith("("):
            return imports_text.rstrip(")").split("#")[0].strip()

        parts = []
        in_paren = True
        idx = start_idx + 1
        while idx < len(content_lines) and in_paren:
            l = content_lines[idx].strip().split("#")[0].strip()
            if ")" in l:
                parts.append(l.split(")", 1)[0])
                in_paren = False
            elif l:
                parts.append(l)
            idx += 1

        return ", ".join(parts).strip(", ") or None

    def analyze_file(
        self, filepath: str, content_lines: List[str], target_names: Set[str], project_root: str
    ) -> Tuple[Dict[str, str], Set[str]]:
        from ..core import get_import_kind_generic

        used_symbols: Dict[str, str] = {}
        import_aliases: Dict[str, Tuple[str, str]] = {}  # local_alias -> (module_name, kind)

        for idx, line in enumerate(content_lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # from X import Y, Z as W
            m = self.FROM_IMPORT_RE.match(line)
            if m:
                dots_str = m.group(1)
                from_module = m.group(2)
                dots = len(dots_str)

                resolved_base = resolve_relative_import(filepath, from_module, dots) if dots > 0 else from_module
                if not resolved_base:
                    continue

                imports_text = self._collect_from_import_items(content_lines, idx)
                if not imports_text:
                    continue

                for item in imports_text.split(","):
                    item = item.strip()
                    if not item or item == "*":
                        continue

                    parts = item.split(" as ")
                    original_name = parts[0].strip()
                    local_name = parts[1].strip() if len(parts) > 1 else original_name

                    full_module_path = f"{resolved_base}.{original_name}" if resolved_base else original_name
                    base_matches = self.matches_target(resolved_base, target_names)
                    full_matches = self.matches_target(full_module_path, target_names)

                    if base_matches or full_matches:
                        kind = get_import_kind_generic(line, content_lines, idx, self.BLOCK_PATTERNS)
                        if full_matches and not base_matches:
                            import_aliases[local_name] = (full_module_path, kind)
                        else:
                            used_symbols[original_name] = kind

                continue

            # import X [as Y]
            m = self.IMPORT_RE.match(line)
            if m:
                kind = get_import_kind_generic(line, content_lines, idx, self.BLOCK_PATTERNS)
                for item in m.group(1).split(","):
                    item = item.strip()
                    if not item:
                        continue
                    parts = item.split(" as ")
                    module_name = parts[0].strip()
                    local_alias = parts[1].strip() if len(parts) > 1 else module_name

                    if self.matches_target(module_name, target_names):
                        import_aliases[local_alias] = (module_name, kind)

                continue

        # Attribute access for aliases
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
                        _, kind = import_aliases[alias]
                        used_symbols[attr_path] = kind

        # Dynamic access
        full_text = "\n".join(content_lines)
        dynamic_patterns = self._detect_dynamic_access(full_text, target_names)

        return used_symbols, dynamic_patterns
