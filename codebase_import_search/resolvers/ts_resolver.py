"""TypeScript/JavaScript import resolver for codebase_import_search (--incoming mode).

Given a target .ts/.tsx/.js/.jsx file, resolves its imports to source files within project_root.
Only returns imports that resolve to files inside the project (ignores node_modules/external packages).

Patterns supported:
- ES named imports:  import { foo, bar } from './module'
- ES default import: import Foo from './module'
- ES namespace:      import * as ns from './module'
- CJS require:       const x = require('./module')
- CJS destructured:  const { foo } = require('./module')
- Dynamic import():  flagged but exact symbols unknown
"""

import os
import re
from typing import List, Set

from ..core import ImportInfo, ImportResolver


class TypeScriptResolver(ImportResolver):
    """Resolve TS/JS imports in a target file to source files within project_root."""

    # ES named imports: import { foo } from '...'   (also `import type { … }`)
    ES_NAMED_RE = re.compile(r'^\s*import\s*(?:type\s+)?\{([^}]+)\}\s+from\s+[\'"]([^\'"]+)[\'"]')

    # ES default import: import Foo from '...'       (also `import type Foo`)
    ES_DEFAULT_RE = re.compile(r'^\s*import\s+(?:type\s+)?(\w+)\s+from\s+[\'"]([^\'"]+)[\'"]')

    # ES namespace import: import * as ns from '...'  (also `import type * as ns`)
    ES_NAMESPACE_RE = re.compile(r'^\s*import\s+(?:type\s+)?\*\s+as\s+(\w+)\s+from\s+[\'"]([^\'"]+)[\'"]')

    # CJS: const x = require('...')
    CJS_REQUIRE_RE = re.compile(
        r'^\s*(?:const|let|var)\s+(\w+)\s*=\s*require\s*\(\s*[\'"]([^\'"]+)[\'"]'
    )

    # CJS destructured: const { foo } = require('...')
    CJS_DESTRUCTURE_RE = re.compile(
        r'^\s*(?:const|let|var)\s*\{([^}]+)\}\s*=\s*require\s*\(\s*[\'"]([^\'"]+)[\'"]'
    )

    # Dynamic import(): detect module name strings used at runtime
    DYNAMIC_IMPORT_RE = re.compile(r'import\s*\(\s*[\'"]([^\'"]+)[\'"]')

    def get_extensions(self) -> Set[str]:
        return {".ts", ".tsx", ".js", ".jsx"}

    def resolve_imports(self, target_file: str, project_root: str) -> List[ImportInfo]:
        """Resolve imports from target_file to files inside project_root."""
        target_file = os.path.abspath(target_file)
        project_root = os.path.abspath(project_root)
        importing_dir = os.path.dirname(target_file)

        with open(target_file, "r", encoding="utf-8-sig") as f:
            content_lines = f.readlines()

        results: List[ImportInfo] = []
        seen_raw_lines: Set[str] = set()

        for idx, line in enumerate(content_lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("//"):
                continue

            raw_line = stripped.split("//")[0].strip()

            # ES named imports: import { foo } from '...' (with multiline support)
            import_start_match = re.match(r'^\s*import\s*(?:type\s+)?\{', stripped)
            if import_start_match:
                full_text = stripped.split("//")[0].strip()
                
                # Only continue collecting if this line doesn't already have closing } and "from"
                if not ("}" in full_text and "from" in full_text):
                    for next_line in content_lines[idx + 1 :]:
                        nl_stripped = next_line.strip()
                        # Skip pure comment lines inside the multiline block
                        if nl_stripped.startswith("//"):
                            continue
                        # Take content before any inline comment
                        if "//" in nl_stripped:
                            nl_content = nl_stripped.split("//")[0].strip()
                        else:
                            nl_content = nl_stripped
                        
                        full_text += " " + nl_content
                        # Stop when we have } followed by from
                        if re.search(r'\}\s*from\s+', full_text):
                            break
                
                m = re.match(r'^import\s*(?:type\s+)?\{([^}]+)\}\s+from\s+[\'"]([^\'"]+)[\'"]', full_text)
                if not m:
                    continue
                    
                items_text = m.group(1)
                module_specifier = m.group(2).strip()
                
                # Build display line: for multiline imports show compact form instead of dangling "import {"
                base_import_line = stripped.split("//")[0].strip()
                symbols_count = len(self._parse_named_items(items_text))
                if symbols_count > 3 and not ("}" in base_import_line and "from" in base_import_line):
                    # Multiline import without closing on first line — show compact form
                    raw_line = f'import {{({symbols_count} symbols) from "{module_specifier}"}};'
                else:
                    raw_line = base_import_line

                if raw_line in seen_raw_lines:
                    continue
                seen_raw_lines.add(raw_line)

                symbols = self._parse_named_items(items_text)
                resolved_path = self._resolve_module(module_specifier, importing_dir, project_root)

                results.append(ImportInfo(
                    raw_line=raw_line,
                    module_name=module_specifier,
                    symbol_names=symbols,
                    resolved_path=resolved_path,
                ))
                continue

            # ES default import: import Foo from '...'
            m = self.ES_DEFAULT_RE.match(line)
            if m:
                local_alias = m.group(1)
                module_specifier = m.group(2).strip()

                if raw_line in seen_raw_lines:
                    continue
                seen_raw_lines.add(raw_line)

                resolved_path = self._resolve_module(module_specifier, importing_dir, project_root)

                results.append(ImportInfo(
                    raw_line=raw_line,
                    module_name=module_specifier,
                    symbol_names=[],  # default import of whole module
                    resolved_path=resolved_path,
                ))
                continue

            # ES namespace import: import * as ns from '...'
            m = self.ES_NAMESPACE_RE.match(line)
            if m:
                local_alias = m.group(1)
                module_specifier = m.group(2).strip()

                if raw_line in seen_raw_lines:
                    continue
                seen_raw_lines.add(raw_line)

                resolved_path = self._resolve_module(module_specifier, importing_dir, project_root)

                results.append(ImportInfo(
                    raw_line=raw_line,
                    module_name=module_specifier,
                    symbol_names=[],  # namespace import of whole module
                    resolved_path=resolved_path,
                ))
                continue

            # CJS destructured: const { foo } = require('...')
            m = self.CJS_DESTRUCTURE_RE.match(line)
            if m:
                items_text = m.group(1)
                module_specifier = m.group(2).strip()

                if raw_line in seen_raw_lines:
                    continue
                seen_raw_lines.add(raw_line)

                symbols = self._parse_named_items(items_text)
                resolved_path = self._resolve_module(module_specifier, importing_dir, project_root)

                results.append(ImportInfo(
                    raw_line=raw_line,
                    module_name=module_specifier,
                    symbol_names=symbols,
                    resolved_path=resolved_path,
                ))
                continue

            # CJS require: const x = require('...')
            m = self.CJS_REQUIRE_RE.match(line)
            if m:
                local_alias = m.group(1)
                module_specifier = m.group(2).strip()

                if raw_line in seen_raw_lines:
                    continue
                seen_raw_lines.add(raw_line)

                resolved_path = self._resolve_module(module_specifier, importing_dir, project_root)

                results.append(ImportInfo(
                    raw_line=raw_line,
                    module_name=module_specifier,
                    symbol_names=[],  # whole-module require
                    resolved_path=resolved_path,
                ))
                continue

        # Dynamic imports: scan non-comment lines only for import('...') patterns
        in_block_comment = False
        for idx, line in enumerate(content_lines):
            stripped = line.strip()
            if not stripped:
                continue

            # Handle block comments /* ... */
            clean_line = ""
            i = 0
            while i < len(stripped):
                if in_block_comment:
                    end_pos = stripped.find("*/", i)
                    if end_pos != -1:
                        in_block_comment = False
                        i = end_pos + 2
                    else:
                        break
                elif stripped[i:i+2] == "/*":
                    in_block_comment = True
                    i += 2
                elif stripped[i:i+2] == "//":
                    break
                else:
                    clean_line += stripped[i]
                    i += 1

            if not clean_line.strip():
                continue

            for m in self.DYNAMIC_IMPORT_RE.finditer(clean_line):
                module_specifier = m.group(1).strip()
                dynamic_raw = f"import('{module_specifier}') [dynamic]"
                if dynamic_raw in seen_raw_lines:
                    continue
                seen_raw_lines.add(dynamic_raw)

                resolved_path = self._resolve_module(module_specifier, importing_dir, project_root)

                results.append(ImportInfo(
                    raw_line=dynamic_raw,
                    module_name=module_specifier,
                    symbol_names=[],
                    resolved_path=resolved_path,
                ))

        return results

    def _parse_named_items(self, text: str) -> List[str]:
        """Parse 'foo, bar as b' into list of original names."""
        result = []
        for item in text.split(","):
            item = item.strip()
            if not item:
                continue
            parts = item.split(" as ")
            original = parts[0].strip()
            if original and original != "*":
                result.append(original)
        return result

    def _resolve_module(self, specifier: str, importing_dir: str, project_root: str) -> str | None:
        """Resolve a module specifier to an absolute file path inside project_root.

        Rules:
        - Relative imports ('./foo', '../bar') are resolved from importing_dir
        - Bare specifiers without path separators are treated as external (node_modules) and ignored
        - Extensions .ts/.tsx/.js/.jsx are tried, plus index files in directories

        Returns None if the module is outside project_root or cannot be found.
        """
        # Ignore bare specifiers (external packages like 'lodash', 'react')
        if not specifier.startswith(("./", "../")):
            return None

        base_candidate = os.path.normpath(os.path.join(importing_dir, specifier))

        candidates = [base_candidate]  # 1. exact (specifier already carries a real extension)

        # 2. ESM/NodeNext: specifier ends in .js/.mjs/... but the file on disk is .ts/.tsx —
        #    strip the extension and retry the TS/JS set on the stem.
        stem, ext = os.path.splitext(base_candidate)
        if ext.lower() in {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}:
            candidates += [stem + e for e in (".ts", ".tsx", ".js", ".jsx")]

        # 3. specifier had no extension — append the TS/JS set.
        candidates += [base_candidate + e for e in (".ts", ".tsx", ".js", ".jsx")]

        # 4. directory with an index file.
        candidates += [os.path.join(base_candidate, "index" + e) for e in (".ts", ".tsx", ".js", ".jsx")]

        for candidate in candidates:
            if os.path.isfile(candidate) and self._is_inside_project(candidate, project_root):
                return candidate

        # Not found inside project_root
        return None

    def _is_inside_project(self, filepath: str, project_root: str) -> bool:
        """Check if filepath is inside project_root."""
        try:
            rel = os.path.relpath(filepath, project_root)
            return not rel.startswith("..")
        except ValueError:
            return False

