"""Python language handler for codebase_import_search."""

import io
import re
import tokenize
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

    def _get_non_docstring_indices(self, content_lines):
        """Return the set of 0-based line indices that carry real CODE.

        A line counts as code if it holds at least one code token (NAME / NUMBER /
        OP). Lines that are entirely string/docstring content or comment-only carry
        no such token and are excluded — so a symbol mentioned inside a docstring or
        comment is not mistaken for a usage.

        Uses stdlib ``tokenize`` (exact: handles multi-line strings, f-strings, raw,
        implicit concatenation, CRLF). Fails OPEN — on any tokenize error every line
        is treated as code, because dropping a real usage is worse than an occasional
        phantom from a doc mention.
        """
        n = len(content_lines)
        all_idx = set(range(n))
        code_lines: Set[int] = set()
        code_types = {tokenize.NAME, tokenize.NUMBER, tokenize.OP}
        try:
            src = "".join(content_lines)
            for tok in tokenize.generate_tokens(io.StringIO(src).readline):
                if tok.type in code_types:
                    for row in range(tok.start[0], tok.end[0] + 1):
                        code_lines.add(row - 1)  # tokenize rows are 1-based
        except (tokenize.TokenError, IndentationError, SyntaxError, ValueError):
            return all_idx  # fail open: never drop a real usage on a parse error
        return code_lines

    def find_symbol_usages(self, filepath: str, content_lines: List[str], names: Set[str]) -> Dict[str, List[int]]:
        """Where each name in `names` is USED as real code in this file (1-based lines).

        Excludes import lines, comments and docstrings. Shared by analyze_file
        (downstream) and by --incoming --verbose (usages inside the target file).
        """
        result: Dict[str, List[int]] = {}
        if not names or not content_lines:
            return result

        sorted_syms = sorted(names, key=len, reverse=True)
        usage_pattern = re.compile(r'\b(' + '|'.join(re.escape(s) for s in sorted_syms) + r')\b')

        import_line_indices = {
            idx for idx, line in enumerate(content_lines)
            if line.strip().startswith("import ") or line.strip().startswith("from ")
        }
        code_indices = self._get_non_docstring_indices(content_lines)

        for idx in sorted(code_indices):
            if idx in import_line_indices:
                continue
            stripped = content_lines[idx].strip()
            if not stripped or stripped.startswith("#"):
                continue
            for m in usage_pattern.finditer(stripped):
                sym = m.group(1)
                if sym in names:
                    result.setdefault(sym, []).append(idx + 1)
        return result

    def analyze_file(
        self, filepath: str, content_lines: List[str], target_names: Set[str], project_root: str, target_file_path: str = None
    ) -> Tuple[Dict[str, str], Dict[str, List[int]], Set[str]]:
        """Analyze a Python file for target symbol usages.

        Returns:
            Tuple of (symbol_kinds, symbol_lines, dynamic_patterns) where:
                - symbol_kinds: {symbol_name: import_kind}
                - symbol_lines: {symbol_name: [line_numbers]}
                - dynamic_patterns: set of dynamic access labels found

        Args:
            target_file_path: Optional path to the target file being analyzed (used by some handlers for optimization).
        """
        from ..core import get_import_kind_generic

        used_symbols: Dict[str, str] = {}
        symbol_lines: Dict[str, List[int]] = {}
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
                            # Don't track import line here — second pass will find actual usages

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

        # Attribute access for aliases — track line numbers via full text scan
        if import_aliases:
            pattern = self._build_attr_pattern(set(import_aliases.keys()))
            if pattern:
                # Read raw file to preserve exact line endings (CRLF vs LF matters!)
                with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                    full_text = f.read()

                # Get set of valid lines (not inside docstrings) for usage scanning
                non_docstring_indices = self._get_non_docstring_indices(content_lines)

                for m in pattern.finditer(full_text):
                    alias = m.group(1)
                    attr_path = m.group(2).strip()
                    if import_aliases.get(alias) and attr_path:
                        first_token = attr_path.split(".")[0]
                        if len(first_token) <= 3 and first_token.isalpha():
                            continue
                        # Calculate line number from position in full_text (preserves exact line endings)
                        pos = m.start()
                        line_num = full_text[:pos].count("\n") + 1
                        line_idx = line_num - 1  # Convert to 0-based index

                        # Register the symbol ONLY for real-code access — not inside a
                        # docstring, not a full-line '#' comment. Guarding used_symbols
                        # here (not just symbol_lines) prevents phantom empty symbols
                        # from mere mentions in docs/comments.
                        if line_idx not in non_docstring_indices:
                            continue
                        if 0 <= line_idx < len(content_lines) and content_lines[line_idx].lstrip().startswith("#"):
                            continue
                        _, kind = import_aliases[alias]
                        used_symbols[attr_path] = kind
                        symbol_lines.setdefault(attr_path, []).append(line_num)

        # Second pass for direct named imports: find where symbols are actually USED (not just imported)
        direct_imported_names = set(used_symbols.keys())
        for sym_name, lns in self.find_symbol_usages(filepath, content_lines, direct_imported_names).items():
            symbol_lines.setdefault(sym_name, []).extend(lns)

        # Dynamic access — exclude docstrings by building text from valid lines only
        non_docstring_text = "\n".join(
            content_lines[i] for i in sorted(self._get_non_docstring_indices(content_lines))
        )
        dynamic_patterns = self._detect_dynamic_access(non_docstring_text, target_names)

        return used_symbols, symbol_lines, dynamic_patterns
