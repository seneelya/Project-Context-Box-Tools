"""C/C++ preprocessor facts — `#include` edges and the `#if` condition each line sits under
(Plan08 / Vision09). One shared engine for the C++ handler/resolver of find_code_usage, the C++
module of the stamp (`stamp_langs/cpp.py`) and the graph's reverse scan.

Conditions are TAGGED, never resolved: `#include "ggml-cuda.h"` inside `#ifdef GGML_USE_CUDA`
becomes an edge with condition `GGML_USE_CUDA`. Line-based directive scan, not tree-sitter:
preprocessor directives are line-based by definition, so this is exact for them, needs no
grammar, and scans a 3600-file tree in seconds (Vision09 said tree-sitter — deviation, see Plan08).

Include guards (`#ifndef X / #define X ... #endif` around the whole file) are recognised and
dropped, otherwise every line of every header would be "conditional on !X_H".
"""

import bisect
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

HEADER_EXTS = {".h", ".hh", ".hpp", ".hxx", ".cuh", ".inl"}
IMPL_EXTS = {".c", ".cc", ".cpp", ".cxx", ".c++", ".cu"}
CPP_EXTS = HEADER_EXTS | IMPL_EXTS

_DIRECTIVE_RE = re.compile(r"^\s*#\s*([a-z_]+)\b(.*)$")
_INCLUDE_RE = re.compile(r'^\s*([<"])([^>"]+)[>"]')
_IDENT_RE = re.compile(r"^[A-Za-z_]\w*$")
_DEFINED_RE = re.compile(r"^defined\s*\(\s*([A-Za-z_]\w*)\s*\)$|^defined\s+([A-Za-z_]\w*)$")


# --------------------------------------------------------------------------- lexing

def _logical_lines(text: str) -> List[Tuple[int, str]]:
    """[(first_line_no, text)] with `\\`-continuations joined and comments blanked.

    Only what the directive scan needs: comments must not hide/fake a directive, and string
    literals are left alone (a `//` inside a string on a directive line is vanishingly rare)."""
    out = []
    in_block = False
    pending, pending_no = "", 0
    for no, raw in enumerate(text.splitlines(), 1):
        line, i, buf = raw, 0, []
        while i < len(line):
            if in_block:
                j = line.find("*/", i)
                if j == -1:
                    i = len(line)
                    break
                in_block = False
                buf.append(" ")
                i = j + 2
                continue
            if line.startswith("/*", i):
                in_block = True
                i += 2
                continue
            if line.startswith("//", i):
                break
            buf.append(line[i])
            i += 1
        clean = "".join(buf)
        if pending:
            clean = pending + clean
        else:
            pending_no = no
        if clean.endswith("\\"):
            pending = clean[:-1] + " "
            continue
        out.append((pending_no, clean))
        pending = ""
    if pending:
        out.append((pending_no, pending))
    return out


# --------------------------------------------------------------------------- conditions

def normalize_expr(expr: str) -> str:
    """`defined(X)` / `defined X` alone -> `X`; whitespace collapsed; otherwise kept as written."""
    e = " ".join(expr.split())
    m = _DEFINED_RE.match(e)
    if m:
        return m.group(1) or m.group(2)
    if e.startswith("!"):
        inner = e[1:].strip()
        m = _DEFINED_RE.match(inner)
        if m:
            return "!" + (m.group(1) or m.group(2))
    return e


def _is_atom(c: str) -> bool:
    c = c.strip()
    if _IDENT_RE.match(c) or (c.startswith("!") and _IDENT_RE.match(c[1:])):
        return True
    if c.startswith("!(") and c.endswith(")") and _balanced_outer(c[1:]):
        return True
    return c.startswith("(") and c.endswith(")") and _balanced_outer(c)


def _balanced_outer(c: str) -> bool:
    depth = 0
    for i, ch in enumerate(c):
        depth += ch == "("
        depth -= ch == ")"
        if depth == 0 and i != len(c) - 1:
            return False
    return depth == 0


def negate(c: str) -> str:
    c = c.strip()
    if _IDENT_RE.match(c):
        return "!" + c
    if c.startswith("!") and _IDENT_RE.match(c[1:]):
        return c[1:]
    if c in ("0", "1"):
        return "1" if c == "0" else "0"
    return f"!({c})"


def conj(parts: List[str]) -> Optional[str]:
    """AND of parts; compound parts get parens. None/empty list -> None (unconditional)."""
    parts = [p for p in parts if p]
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return " && ".join(p if _is_atom(p) or ("||" not in p and "?" not in p) else f"({p})" for p in parts)


@dataclass
class _Frame:
    raws: List[str] = field(default_factory=list)   # conditions of branches seen so far
    in_else: bool = False
    guard: bool = False

    def current(self) -> Optional[str]:
        if self.guard:
            return None
        negs = [negate(r) for r in (self.raws if self.in_else else self.raws[:-1])]
        return conj(negs + ([] if self.in_else else [self.raws[-1]]))


# --------------------------------------------------------------------------- scan

@dataclass
class Include:
    line: int
    spec: str            # what is written between the quotes/brackets (or the macro name)
    quoted: bool         # "..." (True) vs <...> (False)
    cond: Optional[str]  # None = unconditional
    computed: bool = False   # `#include SOME_MACRO` — target not knowable without the preprocessor

    def raw(self) -> str:
        if self.computed:
            return f"#include {self.spec}"
        return f'#include "{self.spec}"' if self.quoted else f"#include <{self.spec}>"


@dataclass
class Scan:
    includes: List[Include]
    guard: Optional[str]
    seg_lines: List[int]                 # sorted start lines of condition segments
    seg_conds: List[Optional[str]]       # condition from that line on
    blocks: List[Tuple[str, int, int]]   # (branch condition, first line, last line) — every #if branch
    n_lines: int

    def cond_at(self, line: int) -> Optional[str]:
        i = bisect.bisect_right(self.seg_lines, line) - 1
        return self.seg_conds[i] if i >= 0 else None


def _directives(text: str):
    out = []
    for no, ln in _logical_lines(text):
        m = _DIRECTIVE_RE.match(ln)
        if m:
            out.append((no, m.group(1), m.group(2).strip()))
    return out


def _guard_name(dirs) -> Optional[str]:
    """Classic include guard: first directive `#ifndef X` / `#if !defined(X)`, the next one
    `#define X`, and the matching `#endif` is the file's LAST directive."""
    if len(dirs) < 3:
        return None
    _no, kind, arg = dirs[0]
    name = None
    if kind == "ifndef":
        name = arg.split()[0] if arg.split() else None
    elif kind == "if":
        e = normalize_expr(arg)
        if e.startswith("!") and _IDENT_RE.match(e[1:]):
            name = e[1:]
    if not name:
        return None
    if not (dirs[1][1] == "define" and dirs[1][2].split()[:1] == [name]):
        return None
    depth = 0
    for i, (_n, k, _a) in enumerate(dirs):
        if k in ("if", "ifdef", "ifndef"):
            depth += 1
        elif k == "endif":
            depth -= 1
            if depth == 0:
                return name if i == len(dirs) - 1 else None
    return None


def scan_text(text: str) -> Scan:
    dirs = _directives(text)
    guard = _guard_name(dirs)
    stack: List[_Frame] = []
    open_start: List[int] = []   # first line of the current branch, per frame
    includes: List[Include] = []
    seg_lines, seg_conds = [1], [None]
    blocks: List[Tuple[str, int, int]] = []

    def effective():
        return conj([f.current() for f in stack])

    def mark(line):
        c = effective()
        if seg_conds[-1] != c:
            if seg_lines[-1] == line:
                seg_conds[-1] = c
            else:
                seg_lines.append(line)
                seg_conds.append(c)

    def close_branch(no):
        if stack and not stack[-1].guard:
            c = stack[-1].current()
            if c is not None:
                blocks.append((c, open_start[-1], no))

    first = True
    for no, kind, arg in dirs:
        if kind in ("if", "ifdef", "ifndef"):
            if kind == "ifdef":
                raw = arg.split()[0] if arg.split() else "?"
            elif kind == "ifndef":
                raw = negate(arg.split()[0]) if arg.split() else "?"
            else:
                raw = normalize_expr(arg)
            f = _Frame(raws=[raw], guard=(first and guard is not None))
            stack.append(f)
            open_start.append(no)
            mark(no + 1)
        elif kind in ("elif", "elifdef", "elifndef") and stack:
            close_branch(no - 1)
            if kind == "elifdef":
                raw = arg.split()[0] if arg.split() else "?"
            elif kind == "elifndef":
                raw = negate(arg.split()[0]) if arg.split() else "?"
            else:
                raw = normalize_expr(arg)
            stack[-1].raws.append(raw)
            open_start[-1] = no
            mark(no + 1)
        elif kind == "else" and stack:
            close_branch(no - 1)
            stack[-1].in_else = True
            open_start[-1] = no
            mark(no + 1)
        elif kind == "endif" and stack:
            close_branch(no - 1)
            stack.pop()
            open_start.pop()
            mark(no + 1)
        elif kind == "include":
            c = effective()
            m = _INCLUDE_RE.match(arg)
            if m:
                includes.append(Include(no, m.group(2).strip(), m.group(1) == '"', c))
            elif arg:
                includes.append(Include(no, arg.split()[0], False, c, computed=True))
        first = False
    return Scan(includes, guard, seg_lines, seg_conds, blocks, text.count("\n") + 1)


_SCAN_CACHE: Dict[str, Tuple[float, Scan]] = {}


def scan_file(path: str) -> Optional[Scan]:
    try:
        mt = os.path.getmtime(path)
    except OSError:
        return None
    hit = _SCAN_CACHE.get(path)
    if hit and hit[0] == mt:
        return hit[1]
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            s = scan_text(fh.read())
    except OSError:
        return None
    _SCAN_CACHE[path] = (mt, s)
    return s


def scan_to_json(s: Scan) -> dict:
    return {"inc": [[i.line, i.spec, i.quoted, i.cond, i.computed] for i in s.includes],
            "guard": s.guard, "sl": s.seg_lines, "sc": s.seg_conds,
            "bl": [list(b) for b in s.blocks], "n": s.n_lines}


def scan_from_json(d: dict) -> Scan:
    return Scan(includes=[Include(*i) for i in d["inc"]], guard=d["guard"],
                seg_lines=d["sl"], seg_conds=d["sc"], blocks=[tuple(b) for b in d["bl"]],
                n_lines=d["n"])


# --------------------------------------------------------------------------- config / tree

def cpp_config(project_root: str) -> dict:
    """CPP_* keys of the TARGET project's config (REQ-007 / Vision08 via load_config_at)."""
    mod = None
    try:
        from graph_from_cards import load_config_at
        mod = load_config_at(project_root)
    except Exception:
        mod = None
    g = (lambda k, d: getattr(mod, k, d) if mod else d)
    return {
        "include_dirs": list(g("CPP_INCLUDE_DIRS", []) or []),
        "strip_macros": list(g("CPP_STRIP_MACROS", []) or []),
        "wrapper_macros": list(g("CPP_WRAPPER_MACROS", []) or []),
        "pairs": dict(g("CPP_PAIRS", {}) or {}),
    }


class Tree:
    """All C/C++ files under a root + include resolution + the forward/reverse include graph.
    Built once per root per process (cheap: directive scan only)."""

    def __init__(self, project_root: str):
        from .core import collect_files
        self.root = os.path.abspath(project_root)
        self.cfg = cpp_config(self.root)
        self.files = [os.path.abspath(p) for p in collect_files(self.root, CPP_EXTS)]
        self.fileset = {os.path.normcase(p) for p in self.files}
        self.by_base: Dict[str, List[str]] = {}
        for p in self.files:
            self.by_base.setdefault(os.path.basename(p).lower(), []).append(p)
        self.inc_dirs = []
        for d in self.cfg["include_dirs"]:
            d = d if os.path.isabs(d) else os.path.join(self.root, d)
            self.inc_dirs.append(os.path.abspath(d))
        self._fwd: Optional[Dict[str, List[Tuple[str, Optional[str], int]]]] = None
        self._rev = None
        self._isfile: Dict[str, bool] = {}
        self.cache_stats = (0, 0)   # (hits, misses) of the on-disk scan cache

    def rel(self, p: str) -> str:
        return os.path.relpath(p, self.root).replace(os.sep, "/")

    def _exists(self, p: str) -> bool:
        k = os.path.normcase(os.path.abspath(p))
        if k in self.fileset:
            return True
        hit = self._isfile.get(k)
        if hit is None:
            hit = self._isfile[k] = os.path.isfile(p)
        return hit

    def resolve(self, including_abs: str, inc: Include) -> Tuple[Optional[str], str]:
        """-> (abs path or None, how): how = own-dir | include-dir | unique-suffix | external |
        not-in-tree | ambiguous | computed."""
        if inc.computed:
            return None, "computed"
        spec = inc.spec.replace("\\", "/")
        if inc.quoted:
            cand = os.path.join(os.path.dirname(including_abs), spec)
            if self._exists(cand):
                return os.path.abspath(cand), "own-dir"
        for d in self.inc_dirs:
            cand = os.path.join(d, spec)
            if self._exists(cand):
                return os.path.abspath(cand), "include-dir"
        # Fallback: a unique file in the tree whose path ends with the spec. Makes a tree without
        # CPP_INCLUDE_DIRS usable; ambiguity is reported, never guessed.
        base = spec.rsplit("/", 1)[-1].lower()
        suffix = "/" + spec.lower()
        hits = [p for p in self.by_base.get(base, [])
                if ("/" + self.rel(p).lower()).endswith(suffix)]
        if len(hits) == 1:
            return hits[0], "unique-suffix"
        if len(hits) > 1:
            return None, "ambiguous"
        return None, ("not-in-tree" if inc.quoted else "external")

    def forward(self) -> Dict[str, List[Tuple[str, Optional[str], int]]]:
        """{abs file: [(abs target, cond, line)]} — resolved in-tree includes of every file."""
        if self._fwd is None:
            # Directive scans come from the on-disk cache (Plan09 step 1); resolution is always
            # redone — it depends on the set of files and CPP_INCLUDE_DIRS, and is cheap.
            from .scan_cache import ScanCache, source_version
            cache = ScanCache(self.root, "cpp_scan", source_version(__file__))
            fwd = {}
            for p in self.files:
                d = cache.get(p)
                if d is not None:
                    s = scan_from_json(d)
                else:
                    s = scan_file(p)
                    if s is not None:
                        cache.put(p, scan_to_json(s))
                edges = []
                for inc in (s.includes if s else []):
                    tgt, _how = self.resolve(p, inc)
                    if tgt:
                        edges.append((tgt, inc.cond, inc.line))
                fwd[p] = edges
            cache.save()
            self.cache_stats = (cache.hits, cache.misses)
            self._fwd = fwd
        return self._fwd

    def reverse(self) -> Dict[str, List[Tuple[str, Optional[str], int]]]:
        """{abs target: [(abs includer, cond, line)]}."""
        if self._rev is None:
            rev: Dict[str, List[Tuple[str, Optional[str], int]]] = {}
            for src, edges in self.forward().items():
                for tgt, cond, line in edges:
                    rev.setdefault(os.path.normcase(tgt), []).append((src, cond, line))
            self._rev = rev
        return self._rev

    def includers(self, target_abs: str):
        return self.reverse().get(os.path.normcase(os.path.abspath(target_abs)), [])

    def reach(self, target_abs: str) -> Dict[str, str]:
        """{abs file: via} — every file that includes target directly (via = '') or through a
        chain (via = the directly-included file that leads to target). BFS on reverse edges."""
        out: Dict[str, str] = {}
        start = os.path.abspath(target_abs)
        frontier = [(src, "") for src, _c, _l in self.includers(start)]
        for src, _ in frontier:
            out.setdefault(src, "")
        while frontier:
            nxt = []
            for node, via in frontier:
                for src, _c, _l in self.includers(node):
                    if src not in out and os.path.normcase(src) != os.path.normcase(start):
                        out[src] = via or self.rel(node)
                        nxt.append((src, out[src]))
            frontier = nxt
        return out


_TREES: Dict[str, Tree] = {}


def tree_for(project_root: str) -> Tree:
    key = os.path.normcase(os.path.abspath(project_root))
    t = _TREES.get(key)
    if t is None:
        t = _TREES[key] = Tree(project_root)
    return t


# --------------------------------------------------------------------------- source prep

def first_branch_only(text: str) -> str:
    """Blank every `#elif`/`#else` branch (keep the first branch of each conditional), keeping all
    newlines. `#if A  if (x) {  #else  if (y) {  #endif` splits braces across branches — tree-sitter
    then loses the rest of the file; with one branch per conditional the braces balance again.
    Used ONLY as a second parse for regions the full parse could not read."""
    dirs = _directives(text)
    blank_ranges, stack = [], []   # stack: line where blanking of this frame started, or None
    for no, kind, _arg in dirs:
        if kind in ("if", "ifdef", "ifndef"):
            stack.append(None)
        elif kind in ("elif", "elifdef", "elifndef", "else") and stack:
            if stack[-1] is None:
                stack[-1] = no
        elif kind == "endif" and stack:
            start = stack.pop()
            if start is not None:
                blank_ranges.append((start, no - 1))
    if not blank_ranges:
        return text
    lines = text.split("\n")
    for a, b in blank_ranges:
        for i in range(a - 1, min(b, len(lines))):
            lines[i] = ""
    return "\n".join(lines)


_BODY_OPENER = re.compile(
    r"\)\s*(?:(?:const|noexcept|override|final|volatile|mutable|&&|&)\s*)*"
    r"(?:noexcept\s*\([^()]*\)\s*)?(?:->\s*[\w:<>,\s*&]+?)?\s*$")


def blank_function_bodies(text: str) -> str:
    """Empty the inside of every function body `) {...}` (newlines kept). The declared surface
    never needs a body, and bodies are where macro-generated code (X-macros without `;`) makes
    tree-sitter give up on the WHOLE function. Comments, strings, char literals, raw strings and
    preprocessor lines are skipped so their braces don't count."""
    out = list(text)
    n, i = len(text), 0
    line_start = True

    def skip_ws_comment_string(j):
        """Advance over one non-code unit starting at j; return new j or None if code char."""
        c = text[j]
        if text.startswith("//", j):
            k = text.find("\n", j)
            return n if k == -1 else k
        if text.startswith("/*", j):
            k = text.find("*/", j + 2)
            return n if k == -1 else k + 2
        if c == "R" and j + 1 < n and text[j + 1] == '"':
            m = re.match(r'R"([^()\\\s]{0,16})\(', text[j:j + 20])
            if m:
                end = text.find(")" + m.group(1) + '"', j)
                return n if end == -1 else end + len(m.group(1)) + 2
        if c in "\"'":
            k = j + 1
            while k < n and text[k] != c:
                if text[k] == "\\":
                    k += 1
                elif text[k] == "\n":
                    break
                k += 1
            return k + 1
        return None

    def skip_preproc(j):
        while j < n:
            k = text.find("\n", j)
            if k == -1:
                return n
            if text[k - 1] == "\\" or (k >= 2 and text[k - 2:k] == "\\\r"):
                j = k + 1
                continue
            return k
        return n

    while i < n:
        c = text[i]
        if line_start and c in " \t":
            i += 1
            continue
        if line_start and c == "#":
            i = skip_preproc(i)
            continue
        line_start = c == "\n"
        j = skip_ws_comment_string(i)
        if j is not None:
            i = j
            continue
        if c == "{" and _BODY_OPENER.search(text[max(0, i - 300):i]):
            depth, k, ls = 1, i + 1, False
            while k < n and depth:
                ch = text[k]
                if ls and ch in " \t":
                    k += 1
                    continue
                if ls and ch == "#":
                    k = skip_preproc(k)
                    continue
                ls = ch == "\n"
                jj = skip_ws_comment_string(k)
                if jj is not None:
                    k = jj
                    continue
                depth += ch == "{"
                depth -= ch == "}"
                k += 1
            for p in range(i + 1, k - 1):
                if out[p] != "\n":
                    out[p] = " "
            i = k
            continue
        i += 1
    return "".join(out)


def prepare_for_second_parse(text: str) -> str:
    """One branch per #if (braces balance) + empty function bodies (macro noise gone)."""
    return blank_function_bodies(first_branch_only(text))


# Macro handling lives in get_codeblock (the lowest layer — how a C/C++ file is READ); kept
# importable from here for existing callers.
from get_codeblock.cpp_source import strip_macros, _unwrap  # noqa: E402,F401
