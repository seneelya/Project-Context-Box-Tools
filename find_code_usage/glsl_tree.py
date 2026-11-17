"""GLSL facts — one engine for the GLSL handler/resolver of find_code_usage and the stamp module
`stamp_langs/glsl.py` (REQ-021).

- The `#include` graph (GL_GOOGLE_include_directive) is the C/C++ directive scan
  (`cpp_includes.Tree`) over GLSL extensions; `#if` conditions are TAGGED, never resolved.
- A COMPILE UNIT = an entry point (a stage file `.comp/.vert/...`, or a file nobody includes)
  plus everything it includes, transitively. GLSL has no linker: a `.glsl` part sees the
  functions of its siblings because the entry includes them before it. So "who uses a function"
  is answered inside the unit(s) that contain the file, not by its own includes.
- Per file (tree-sitter, `get_codeblock`'s GLSL profile): functions, prototypes, structs,
  interface blocks (buffer / uniform / push_constant with layout and fields), specialization
  constants, `shared`, global `const`, `local_size_*`, and every CALL with the function it sits
  in and its guards: the `#if` condition (from the scan) and the runtime conditions on the way up
  (`if`, `&&`, `?:`) — the stamp keeps those that name a specialization constant.
"""

import os
import re
from typing import Dict, List, Optional

from .cpp_includes import Tree, scan_file

STAGE_EXTS = {".comp", ".vert", ".frag", ".geom", ".tesc", ".tese"}
PART_EXTS = {".glsl"}
GLSL_EXTS = STAGE_EXTS | PART_EXTS
STAGE_NAME = {".comp": "compute", ".vert": "vertex", ".frag": "fragment", ".geom": "geometry",
              ".tesc": "tessellation control", ".tese": "tessellation evaluation"}

_WS = re.compile(r"\s+")


def glsl_config(project_root: str) -> dict:
    mod = None
    try:
        from graph_from_cards import load_config_at
        mod = load_config_at(project_root)
    except Exception:
        mod = None
    dirs = list(getattr(mod, "GLSL_INCLUDE_DIRS", []) or []) if mod else []
    return {"include_dirs": dirs, "strip_macros": [], "wrapper_macros": [], "pairs": {}}


class GlslTree(Tree):
    EXTS = GLSL_EXTS
    CACHE = "glsl_scan"

    def _config(self) -> dict:
        return glsl_config(self.root)

    def entries(self) -> List[str]:
        """Stage files + parts nobody includes (each is compiled, or at least read, on its own)."""
        rev = self.reverse()
        out = []
        for p in self.files:
            ext = os.path.splitext(p)[1].lower()
            if ext in STAGE_EXTS or not rev.get(os.path.normcase(p)):
                out.append(p)
        return out

    def closure(self, entry: str) -> List[str]:
        """The unit of `entry`: the entry and its includes, transitively, in include order."""
        fwd = self.forward()
        seen, order = set(), []

        def visit(node):
            k = os.path.normcase(node)
            if k in seen:
                return
            seen.add(k)
            order.append(node)
            for tgt, _c, _l in sorted(fwd.get(node, []), key=lambda e: e[2]):
                visit(tgt)

        visit(os.path.abspath(entry))
        return order

    def units_of(self, target_abs: str) -> Dict[str, List[str]]:
        """{entry abs: [unit files]} for every unit that contains the target."""
        if self._units is None:
            self._units = {e: self.closure(e) for e in self.entries()}
        k = os.path.normcase(os.path.abspath(target_abs))
        return {e: fs for e, fs in self._units.items()
                if any(os.path.normcase(f) == k for f in fs)}

    _units = None


_TREES: Dict[str, GlslTree] = {}


def tree_for(project_root: str) -> GlslTree:
    key = os.path.normcase(os.path.abspath(project_root))
    t = _TREES.get(key)
    if t is None:
        t = _TREES[key] = GlslTree(project_root)
    return t


# --------------------------------------------------------------------------- per-file analysis

_PARSER = None


def available() -> bool:
    try:
        _parser()
        return True
    except Exception:
        return False


def _parser():
    global _PARSER
    if _PARSER is None:
        from tree_sitter import Parser
        from get_codeblock.reader.profiles.glsl import _load_glsl
        _PARSER = Parser(_load_glsl())
    return _PARSER


def _flat(b: bytes) -> str:
    return _WS.sub(" ", b.decode("utf-8", errors="replace")).strip()


def _text(src: bytes, n) -> str:
    return _flat(src[n.start_byte:n.end_byte])


def _code_text(src: bytes, n) -> str:
    """Node text without its comment children (a field line carries a trailing // comment)."""
    parts, pos = [], n.start_byte

    def walk(m):
        nonlocal pos
        if m.type == "comment":
            parts.append(src[pos:m.start_byte])
            pos = m.end_byte
            return
        for c in m.children:
            walk(c)

    walk(n)
    parts.append(src[pos:n.end_byte])
    return _flat(b"".join(parts))


def _kids(n, t):
    return [c for c in n.children if c.type == t]


def _find(n, t):
    """First descendant of type t (depth-first), or None."""
    for c in n.children:
        if c.type == t:
            return c
        hit = _find(c, t)
        if hit is not None:
            return hit
    return None


def _layout_args(src, n) -> List[str]:
    """`layout(std430, binding = 0)` -> ['std430', 'binding = 0'] for every layout_qualifier under n
    (not inside a field list)."""
    out = []

    def walk(m):
        if m.type == "field_declaration_list":
            return
        if m.type == "layout_qualifier":
            out.extend(_text(src, a) for a in _kids(m, "layout_argument"))
            return
        for c in m.children:
            walk(c)

    walk(n)
    return out


def _qualifiers(src, n) -> List[str]:
    """Storage / memory qualifier words under n (not inside a field list or a layout)."""
    out = []

    def walk(m):
        if m.type in ("field_declaration_list", "layout_qualifier", "compound_statement"):
            return
        if m.type == "storage_qualifier" or m.type.endswith("_qualifier") and m.type != "type_qualifier":
            if m.type != "layout_qualifier":
                out.append(_text(src, m))
            return
        for c in m.children:
            walk(c)

    walk(n)
    return out


def _fields(src, fl) -> List[dict]:
    out = []
    for fd in _kids(fl, "field_declaration"):
        sig = _code_text(src, fd).rstrip(";").strip()
        names = [_text(src, x) for x in _find_all(fd, "field_identifier")] or \
                [_text(src, x) for x in _find_all(fd, "identifier")][-1:]
        out.append({"name": names[0] if names else sig, "signature": sig})
    return out


def _find_all(n, t):
    out = []
    for c in n.children:
        if c.type == t:
            out.append(c)
        out.extend(_find_all(c, t))
    return out


def _guards(src, node, stop) -> List[str]:
    """Runtime conditions on the way from a call up to its function: `if`, `&&`, `?:`."""
    out = []
    child, parent = node, node.parent
    while parent is not None and parent is not stop:
        if parent.type == "if_statement":
            cond = parent.child_by_field_name("condition")
            if cond is not None and child.id != cond.id:
                alt = parent.child_by_field_name("alternative")
                c = _text(src, cond).strip("() ")
                out.append(f"!({c})" if alt is not None and alt.id == child.id else c)
        elif parent.type == "binary_expression":
            op = parent.child_by_field_name("operator")
            left = parent.child_by_field_name("left")
            if op is not None and _text(src, op) in ("&&", "||") and left is not None \
                    and child.id != left.id:
                c = _text(src, left)
                out.append(c if _text(src, op) == "&&" else f"!({c})")
        elif parent.type == "conditional_expression":
            cond = parent.child_by_field_name("condition")
            alt = parent.child_by_field_name("alternative")
            if cond is not None and child.id != cond.id:
                c = _text(src, cond)
                out.append(f"!({c})" if alt is not None and alt.id == child.id else c)
        child, parent = parent, parent.parent
    return out


def _declaration(src, n, a, cond_at):
    """Classify one top-level `declaration` node into the analysis dict `a`."""
    line = n.start_point[0] + 1
    cond = cond_at(line)
    fd = next((c for c in n.children if c.type == "function_declarator"), None)
    if fd is not None:
        name = fd.child_by_field_name("name")
        a["protos"].append({"name": _text(src, name) if name else "?", "line": line,
                            "signature": _code_text(src, fd)})
        return
    fl = next((c for c in n.children if c.type == "field_declaration_list"), None)
    name = n.child_by_field_name("name")
    if fl is not None and name is not None:                       # interface block
        inst = n.child_by_field_name("instance_name")
        quals = _qualifiers(src, n)
        storage = next((q for q in quals if q in ("buffer", "uniform", "in", "out", "shared")), "")
        lay = _layout_args(src, n)
        head = _code_text(src, n)
        head = head[:head.find("{")].strip() if "{" in head else head
        kind = "push_constant" if any(x.replace(" ", "") == "push_constant" for x in lay) else storage
        a["blocks"].append({"name": _text(src, name), "instance": _text(src, inst) if inst else None,
                            "signature": head, "line": line, "end": n.end_point[0] + 1,
                            "kind": kind, "layout": lay,
                            "access": [q for q in quals if q in ("readonly", "writeonly", "coherent",
                                                                 "volatile", "restrict")],
                            "fields": _fields(src, fl), "cond": cond})
        return
    dl = next((c for c in n.children if c.type == "declarator_list"), None)
    if dl is None:
        lay = _layout_args(src, n)
        ls = [x for x in lay if x.replace(" ", "").startswith("local_size")]
        if ls:
            a["local_size"] = ", ".join(ls)
        return
    last_type = None
    for d in _kids(dl, "declarator"):
        t = d.child_by_field_name("type") or next((c for c in d.children if c.type == "type"), None)
        if t is not None:
            last_type = t
        nm = d.child_by_field_name("name")
        st = _find(t, "struct_specifier") if t is not None else None
        if st is not None and st.child_by_field_name("name") is not None:
            sfl = next((c for c in st.children if c.type == "field_declaration_list"), None)
            sname = _text(src, st.child_by_field_name("name"))
            a["structs"].append({"name": sname, "signature": f"struct {sname}", "line": line,
                                 "fields": _fields(src, sfl) if sfl is not None else [], "cond": cond})
            if nm is None:
                continue
        if nm is None:
            continue
        name = _text(src, nm)
        tt = last_type
        lay = _layout_args(src, tt) if tt is not None else []
        quals = _qualifiers(src, tt) if tt is not None else []
        sig = _code_text(src, d)
        if t is None and last_type is not None:     # `const uint A = 1, B = 2;` — B has no own type
            sig = f"{_code_text(src, last_type)} {sig}"
        spec = next((x for x in lay if x.replace(" ", "").startswith("constant_id=")), None)
        rec = {"name": name, "signature": sig, "line": line, "cond": cond}
        if spec:
            rec["id"] = spec.split("=", 1)[1].strip()
            a["spec"].append(rec)
        elif "shared" in quals:
            a["shared"].append(rec)
        elif "const" in quals:
            a["consts"].append(rec)
        else:
            a["vars"].append(rec)


_AN: Dict[str, tuple] = {}


def analyze(path: str) -> Optional[dict]:
    """Facts of one GLSL file (cached per path+mtime); None = unreadable or no grammar."""
    try:
        mt = os.stat(path).st_mtime_ns
    except OSError:
        return None
    hit = _AN.get(path)
    if hit and hit[0] == mt:
        return hit[1]
    try:
        with open(path, "rb") as fh:
            src = fh.read()
        from get_codeblock.glsl_source import preprocess_bytes
        from get_codeblock.reader.profiles.glsl import PARAMETERIZED_TYPES
        tree = _parser().parse(preprocess_bytes(src, type_parameters=PARAMETERIZED_TYPES))
    except Exception:
        return None
    scan = scan_file(path)
    cond_at = scan.cond_at if scan else (lambda _l: None)
    a = {"functions": [], "protos": [], "structs": [], "blocks": [], "spec": [], "shared": [],
         "consts": [], "vars": [], "local_size": None, "calls": [], "errors": 0}

    def top(n):
        for c in n.children:
            if c.type in ("preproc_if", "preproc_ifdef", "preproc_else", "preproc_elif",
                          "preproc_elifdef"):
                top(c)
            elif c.type == "function_definition":
                fd = c.child_by_field_name("declarator") or \
                    next((x for x in c.children if x.type == "function_declarator"), None)
                nm = fd.child_by_field_name("name") if fd is not None else None
                name = _text(src, nm) if nm is not None else "?"
                line = c.start_point[0] + 1
                a["functions"].append({"name": name, "signature": _code_text(src, fd) if fd else name,
                                       "line": line, "end": c.end_point[0] + 1,
                                       "cond": cond_at(line)})
                for call in _find_all(c, "function_call"):
                    f = call.child_by_field_name("function")
                    if f is None or f.type != "identifier":
                        continue
                    cl = call.start_point[0] + 1
                    a["calls"].append({"name": _text(src, f), "line": cl, "in": name,
                                       "cond": cond_at(cl), "guards": _guards(src, call, c)})
            elif c.type == "declaration":
                _declaration(src, c, a, cond_at)
            elif c.type == "ERROR":
                a["errors"] += 1

    top(tree.root_node)
    _AN[path] = (mt, a)
    return a


# --------------------------------------------------------------------------- std430 size

_SCALAR = {"bool": 4, "int": 4, "uint": 4, "float": 4, "double": 8, "int64_t": 8, "uint64_t": 8,
           "int16_t": 2, "uint16_t": 2, "float16_t": 2, "int8_t": 1, "uint8_t": 1}
_VEC = re.compile(r"^(b|i|u|d|f16|i64|u64)?vec([234])$")
_MAT = re.compile(r"^(d)?mat([234])(?:x([234]))?$")


def _type_layout(t: str):
    """(size, align) of a std430 member type, or None when not computed (a struct, an array of
    unknown length, a type this table does not know)."""
    if t in _SCALAR:
        s = _SCALAR[t]
        return s, s
    m = _VEC.match(t)
    if m:
        base = {"b": 4, "i": 4, "u": 4, None: 4, "d": 8, "f16": 2, "i64": 8, "u64": 8}[m.group(1)]
        n = int(m.group(2))
        return base * n, base * (4 if n == 3 else n)
    m = _MAT.match(t)
    if m:
        base = 8 if m.group(1) else 4
        cols = int(m.group(2))
        rows = int(m.group(3) or m.group(2))
        col_size, col_align = base * rows, base * (4 if rows == 3 else rows)
        return col_align * (cols - 1) + col_size, col_align
    return None


_FIELD = re.compile(r"^(?:(?:highp|mediump|lowp|precise|readonly|writeonly|coherent|volatile|restrict)\s+)*"
                    r"([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s*(?:\[\s*(\d*)\s*\])?$")


def std430_size(fields: List[dict]) -> Optional[int]:
    """Byte size of a std430 / push_constant block from its field signatures, or None."""
    off, max_align = 0, 1
    for f in fields:
        sig = f["signature"]
        if "," in sig:                       # `uint a, b;` — count every name
            head, *rest = [s.strip() for s in sig.split(",")]
            m0 = _FIELD.match(head)
            if not m0:
                return None
            parts = [head] + [f"{m0.group(1)} {r}" for r in rest]
        else:
            parts = [sig]
        for p in parts:
            m = _FIELD.match(p)
            if not m:
                return None
            lay = _type_layout(m.group(1))
            if lay is None:
                return None
            size, align = lay
            if m.group(3) is not None:
                if m.group(3) == "":
                    return None              # runtime-sized array: no fixed size
                stride = -(-size // align) * align
                size = stride * int(m.group(3))
            off = -(-off // align) * align + size
            max_align = max(max_align, align)
    return -(-off // max_align) * max_align
