"""GLSL language handler for find_code_usage (downstream: who uses the target's symbols), REQ-021.

GLSL has no linker and no per-symbol import: a part sees what the entry point included before
it. So a consumer is any OTHER file of a compile unit that contains the target
(`glsl_tree.GlslTree.units_of`) and that uses one of the target's names:
- a function — by its CALLS (tree-sitter `function_call`, comments and prototypes never count);
- any other declared name (block instance, struct, const, spec constant, shared) — by a word
  match on code lines.
Kind: `unit <entry>` (several units: comma-joined). Files outside the units are never opened.
"""

import os
import re
from typing import Dict, List, Set, Tuple

from ..core import LanguageHandler
from ..glsl_tree import GLSL_EXTS, analyze, tree_for

_IDENT_RE = re.compile(r"[A-Za-z_]\w*")


def target_names(target_abs: str) -> Tuple[Set[str], Dict[str, str]]:
    """(function names, {other word in code: symbol of the card}) the target defines. A block is
    used through its INSTANCE name (`items.data`) but listed in the card by its block name."""
    a = analyze(target_abs) or {}
    funcs = {f["name"] for f in a.get("functions", []) if f["name"] != "main"}
    other: Dict[str, str] = {}
    for b in a.get("blocks", []):
        if b.get("instance"):
            other[b["instance"]] = b["name"]
        else:                                   # an unnamed block exposes its fields directly
            for f in b["fields"]:
                other[f["name"]] = b["name"]
    for k in ("structs", "spec", "shared", "consts", "vars"):
        for x in a.get(k, []):
            other.setdefault(x["name"], x["name"])
    return funcs, {w: s for w, s in other.items() if w not in funcs}


class GlslHandler(LanguageHandler):

    def __init__(self):
        self._project_root = None
        self._target = None
        self._unit_cache: Dict[Tuple[str, str], Dict[str, List[str]]] = {}

    def get_extensions(self) -> Set[str]:
        return set(GLSL_EXTS)

    def matches_target(self, imported_module: str, target_names: Set[str]) -> bool:
        return False

    def prepare(self, project_root: str, target_abs: str):
        self._project_root, self._target = project_root, target_abs

    def _members(self, project_root, target_abs) -> Dict[str, List[str]]:
        """{normcase file: [entry rel]} — files that share a unit with the target."""
        key = (os.path.normcase(project_root), os.path.normcase(target_abs))
        if key not in self._unit_cache:
            tree = tree_for(project_root)
            out: Dict[str, List[str]] = {}
            for entry, files in tree.units_of(target_abs).items():
                for f in files:
                    out.setdefault(os.path.normcase(f), []).append(tree.rel(entry))
            self._unit_cache[key] = out
        return self._unit_cache[key]

    def wants_file(self, fpath: str) -> bool:
        if not (self._project_root and self._target):
            return True
        return os.path.normcase(os.path.abspath(fpath)) in self._members(self._project_root, self._target)

    def analyze_file(self, filepath: str, content_lines: List[str], target_names_: Set[str],
                     project_root: str, target_abs: str = None):
        if not target_abs:
            return {}, {}, set()
        fpath = os.path.abspath(filepath)
        if os.path.normcase(fpath) == os.path.normcase(os.path.abspath(target_abs)):
            return {}, {}, set()
        units = self._members(project_root, target_abs).get(os.path.normcase(fpath))
        if not units:
            return {}, {}, set()
        kind = "unit " + ", ".join(sorted(set(units)))
        funcs, other = target_names(target_abs)
        symbols, lines = {}, {}
        a = analyze(fpath) or {}
        own = {f["name"] for f in a.get("functions", [])}
        for c in a.get("calls", []):
            if c["name"] in funcs and c["name"] not in own:
                symbols[c["name"]] = kind
                lines.setdefault(c["name"], []).append(c["line"])
        if other:
            text = "".join(content_lines)
            hits = set(other).intersection(_IDENT_RE.findall(text))
            if hits:
                rx = re.compile(r"\b(" + "|".join(sorted(map(re.escape, hits), key=len, reverse=True)) + r")\b")
                in_block = False
                for i, ln in enumerate(content_lines, 1):
                    code, in_block = _strip_comments(ln, in_block)
                    if code.lstrip().startswith("#"):
                        continue
                    for m in rx.finditer(code):
                        sym = other[m.group(1)]
                        symbols[sym] = kind
                        lines.setdefault(sym, []).append(i)
        for k in lines:
            lines[k] = sorted(set(lines[k]))
        return symbols, lines, set()


def _strip_comments(line: str, in_block: bool) -> Tuple[str, bool]:
    out, i = [], 0
    while i < len(line):
        if in_block:
            j = line.find("*/", i)
            if j < 0:
                return "".join(out), True
            in_block, i = False, j + 2
            continue
        if line.startswith("/*", i):
            in_block, i = True, i + 2
            continue
        if line.startswith("//", i):
            break
        out.append(line[i])
        i += 1
    return "".join(out), in_block
