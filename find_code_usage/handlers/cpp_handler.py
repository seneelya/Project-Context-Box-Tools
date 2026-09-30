"""C/C++ language handler for find_code_usage (downstream: who uses the target's symbols).

C/C++ has no per-symbol import: `#include "x.h"` brings the whole header. So:
1. a consumer is any file that includes the target DIRECTLY or through a chain of in-tree
   includes (reverse include graph over the whole root, `cpp_includes.Tree.reach`);
2. which of the target's declared names it uses = word match of those names in the consumer.
Kind per symbol: `include` (direct, unconditional), `include [if X]` (direct, under #if),
`via <header>` (through a chain). Files outside the reach are never opened (`wants_file`).
"""

import bisect
import os
import re
from typing import Dict, List, Set, Tuple

from ..core import LanguageHandler
from ..cpp_includes import CPP_EXTS, tree_for


class CppHandler(LanguageHandler):

    def __init__(self):
        self._reach_cache: Dict[Tuple[str, str], Dict[str, str]] = {}
        self._names_cache: Dict[Tuple[str, str], Tuple[Set[str], object]] = {}
        self._project_root = None
        self._target = None

    def get_extensions(self) -> Set[str]:
        return set(CPP_EXTS)

    def matches_target(self, imported_module: str, target_names: Set[str]) -> bool:
        return False   # includes are matched by resolved PATH, not by name

    # -- scan_downstream hook: skip files that cannot reach the target without reading them
    def prepare(self, project_root: str, target_abs: str):
        self._project_root, self._target = project_root, target_abs

    def wants_file(self, fpath: str) -> bool:
        if not (self._project_root and self._target):
            return True
        return os.path.abspath(fpath) in self._reach(self._project_root, self._target)

    def _reach(self, project_root, target_abs):
        key = (os.path.normcase(project_root), os.path.normcase(target_abs))
        if key not in self._reach_cache:
            self._reach_cache[key] = tree_for(project_root).reach(target_abs)
        return self._reach_cache[key]

    def _names(self, project_root, target_abs):
        key = (os.path.normcase(project_root), os.path.normcase(target_abs))
        if key not in self._names_cache:
            names: Set[str] = set()
            try:
                from stamp_langs import cpp as cpp_lang
                decls, _scan = cpp_lang._decls(project_root, target_abs)
                names = {d["name"] for d in decls if d["kind"] != "namespace"
                         and re.match(r"^[A-Za-z_]\w*$", d["name"])}
            except Exception:
                names = set()
            rx = re.compile(r"\b(" + "|".join(sorted(map(re.escape, names), key=len, reverse=True)) + r")\b") \
                if names else None
            self._names_cache[key] = (names, rx)
        return self._names_cache[key]

    def analyze_file(self, filepath: str, content_lines: List[str], target_names: Set[str],
                     project_root: str, target_abs: str = None):
        if not target_abs:
            return {}, {}, set()
        reach = self._reach(project_root, target_abs)
        fpath = os.path.abspath(filepath)
        if fpath not in reach:
            return {}, {}, set()
        tree = tree_for(project_root)
        via = reach[fpath]
        if via:
            kind = f"via {via}"
        else:
            conds = [c for t, c, _l in tree.forward().get(fpath, [])
                     if os.path.normcase(t) == os.path.normcase(os.path.abspath(target_abs))]
            cond = next((c for c in conds if c), None) if conds and all(conds) else None
            kind = f"include [if {cond}]" if cond else "include"
        _names, rx = self._names(project_root, target_abs)
        symbols, lines = {}, {}
        if rx is None:
            return symbols, lines, set()
        # One regex pass over the whole text (a per-line loop dominated the zone stamp);
        # line numbers only for the hits.
        text = "".join(content_lines)
        starts = None
        skip: Dict[int, bool] = {}
        for m in rx.finditer(text):
            if starts is None:
                starts, pos = [], 0
                for ln in content_lines:
                    starts.append(pos)
                    pos += len(ln)
            i = bisect.bisect_right(starts, m.start()) - 1
            if i not in skip:
                s = content_lines[i].lstrip()
                skip[i] = s.startswith("#include") or s.startswith("//")
            if skip[i]:
                continue
            nm = m.group(1)
            symbols[nm] = kind
            lines.setdefault(nm, []).append(i + 1)
        return symbols, lines, set()
