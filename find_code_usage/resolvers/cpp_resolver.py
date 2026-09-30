"""C/C++ include resolver for find_code_usage (--incoming): the target's own `#include`s.

Every include becomes one ImportInfo; the `#if` condition it sits under travels in `kind`
(`conditional(GGML_USE_CUDA)`) for resolved ones and as a `[if …]` tag on the raw line for
unresolved ones. Resolution rules — `cpp_includes.Tree.resolve` (own folder for "…", then
CPP_INCLUDE_DIRS, then a unique path-suffix match in the tree).
"""

from typing import List, Set

from ..core import ImportInfo, ImportResolver
from ..cpp_includes import CPP_EXTS, scan_file, tree_for

# "not in tree" = generated at build time, or outside the scanned root / CPP_INCLUDE_DIRS
_TAG = {"not-in-tree": "not in tree",
        "ambiguous": "ambiguous: several files match, set CPP_INCLUDE_DIRS",
        "computed": "computed include (macro)"}


class CppResolver(ImportResolver):

    def get_extensions(self) -> Set[str]:
        return set(CPP_EXTS)

    def resolve_imports(self, target_file: str, project_root: str) -> List[ImportInfo]:
        scan = scan_file(target_file)
        if scan is None:
            return []
        tree = tree_for(project_root)
        out = []
        for inc in scan.includes:
            tgt, how = tree.resolve(target_file, inc)
            raw = inc.raw()
            if tgt is None:
                tags = [t for t in (_TAG.get(how), f"if {inc.cond}" if inc.cond else None) if t]
                if tags:
                    raw = f"{raw}  [{'; '.join(tags)}]"
            out.append(ImportInfo(raw_line=raw, module_name=inc.spec, symbol_names=[],
                                  resolved_path=tgt,
                                  kind=f"conditional({inc.cond})" if inc.cond else None))
        return out
