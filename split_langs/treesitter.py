"""Generic tree-sitter languages for split_monster — names, identifiers, import band — all taken
from get_codeblock (its `Spec` says what a landmark/frame is, its backend parses). No per-language
code here: C# and C/C++ get name hints for free, and any language added to get_codeblock's registry
only needs its extensions listed below.

Imports: C#/C/C++ carry the source's top-level `using` / unconditional `#include` lines into every
target (kind "always" — there is no name -> import map without a compile; the author prunes). No
graph: cross-file references in these languages need no import (same namespace / header
declarations) — a different problem.
"""

import os
import re
import tempfile

NAME = "treesitter"
EXTENSIONS = (".cs", ".c", ".h", ".cpp", ".cc", ".cxx", ".c++", ".hpp", ".hh", ".hxx", ".cu", ".cuh")
CONSUMERS = True     # make_interface_card's consumer scan understands these

# node types that carry a name; `field_identifier` (obj.member) is a member access, not a use
_NAME_LEAF = frozenset({"identifier", "type_identifier", "destructor_name", "operator_name",
                        "namespace_identifier", "qualified_identifier"})
_IDENT_TYPES = frozenset({"identifier", "type_identifier", "namespace_identifier"})


def _parse(text, ext):
    from get_codeblock.reader.registry import resolve
    backend, spec = resolve(ext)
    return backend.root(text.encode("utf-8")), spec


def _role(spec, node):
    r = spec.role(node)
    return getattr(r, "value", r)


def _def_name(d):
    """Bare name of a definition node: its `name` field, else drill through `declarator` fields
    (C/C++ functions: function_definition -> function_declarator -> identifier)."""
    n = d.field("name")
    decl = d.field("declarator")
    while n is None and decl is not None:
        if decl.type in _NAME_LEAF:
            n = decl
            break
        decl = decl.field("declarator")
    if n is None:
        return None
    return re.split(r"::|\.", n.text().strip())[-1] or None


def _landmarks(spec, nodes):
    """(node, definition) for every landmark, descending through frames (namespace, extern "C",
    #ifdef guards) the way get_codeblock's level 1 does."""
    for n in nodes:
        role = _role(spec, n)
        if role == "landmark":
            yield n, spec.unwrap_def(n)
        elif role == "frame":
            body = spec.body(n)
            yield from _landmarks(spec, (body or n).children())


def declared_names(text, ext=""):
    try:
        root, spec = _parse(text, ext)
        names = []
        for _n, d in _landmarks(spec, root.children()):
            nm = _def_name(d)
            if nm and nm not in names:
                names.append(nm)
        return names
    except Exception:
        return []


def top_level_names(lines, ext=""):
    return set(declared_names("\n".join(lines), ext))


def identifiers(text, ext=""):
    """Names the snippet USES — identifier nodes only (comments, strings, member names excluded)."""
    try:
        root, _spec = _parse(text, ext)
        found, stack = set(), [root]
        while stack:
            n = stack.pop()
            if n.type in _IDENT_TYPES:
                found.add(n.text())
            stack.extend(n.children())
        return found
    except Exception:
        from ._common import WORD_RE
        return set(WORD_RE.findall(text))


def decl_line(text, ext=""):
    try:
        root, spec = _parse(text, ext)
        for n, _d in _landmarks(spec, root.children()):
            return spec.name(n)
    except Exception:
        pass
    for line in text.splitlines():
        if line.strip() and not line.strip().startswith(("//", "/*", "*", "#")):
            return line.strip()
    return text.splitlines()[0].strip() if text else ""


_KEYWORD_NAME_RE = re.compile(r"\b(?:class|struct|enum|interface|record|union|namespace)\s+(\w+)")
_CALL_NAME_RE = re.compile(r"(\w+)\s*\(")


def name_from_decl(decl):
    """Name out of a preview line (`public class Foo : Bar`, `int main(int argc)`), best effort."""
    m = _KEYWORD_NAME_RE.search(decl)
    if m:
        return m.group(1)
    m = _CALL_NAME_RE.search(decl)
    return m.group(1) if m else None


_CS_EXTS = (".cs",)
_USING_RE = re.compile(r"^(?:global\s+)?using\s+(?:static\s+)?[^(;]+;\s*$")
_NAMESPACE_RE = re.compile(r"^\s*namespace\s+([\w.:]+)", re.M)


def source_imports(lines, ext=""):
    """Imports a moved block may need. These languages have no name -> import map without a full
    compile (a `using` names a NAMESPACE, an `#include` a header), so EVERY top-level
    `using` (C#) / unconditional `#include` (C/C++) of the source is carried — kind "always";
    over-inclusion is harmless, the author prunes. Donor for C/C++: find_code_usage.cpp_includes."""
    out = {}
    if ext in _CS_EXTS:
        for line in lines:                       # column 0 only: `using (var x = ...)` is a statement
            if line[:1].isspace() or not _USING_RE.match(line.strip()):
                continue
            raw = line.strip()
            out[raw] = {"kind": "using", "always": True, "items": [(raw, raw)]}
        return out
    try:
        from find_code_usage.cpp_includes import scan_text
        scan = scan_text(chr(10).join(lines))
    except Exception:
        return out
    for inc in scan.includes:
        if inc.cond is None and not inc.computed:
            out.setdefault(inc.raw(), {"kind": "include", "always": True, "items": [(inc.raw(), inc.raw())]})
    return out


def render_import(specifier, kind, items):
    if kind in ("using", "include"):
        return items[0][0]
    raise ValueError(f"unknown import kind {kind!r}")


def notes(lines, ext=""):
    """What the author must know before moving blocks out of this file."""
    out = []
    text = chr(10).join(lines)
    carried = source_imports(lines, ext)
    if carried:
        out.append(f"# {len(carried)} top-level {'using' if ext in _CS_EXTS else '#include'}(s) of the source are "
                   f"carried into every target (no name -> import map for this language) — prune unused by hand")
    if ext not in _CS_EXTS:
        try:
            from find_code_usage.cpp_includes import scan_text
            cond = [i for i in scan_text(text).includes if i.cond is not None]
        except Exception:
            cond = []
        if cond:
            out.append(f"# WARNING: {len(cond)} conditional #include(s) are NOT carried (add by hand): "
                       + ", ".join(sorted({i.raw() for i in cond}))[:200])
    m = _NAMESPACE_RE.search(text)
    if m:
        out.append(f"# WARNING namespace: the source declares `namespace {m.group(1)}`; moved blocks land OUTSIDE it — "
                   f"wrap each target in the same namespace by hand (else the names change)")
    return out


def import_insert_index(segs, ext=""):
    """0-based index after the file's leading import band: get_codeblock's own `imports:` outline
    row (C# `using`, ...); C/C++ `#include` lines when that has no such row; else the top."""
    path = None
    try:
        from get_codeblock.reader.classify import outline_rows
        fd, path = tempfile.mkstemp(suffix=ext or ".txt")
        with os.fdopen(fd, "wb") as f:
            f.write("".join(segs).encode("utf-8"))
        for row in outline_rows(path):
            if row["text"].startswith("imports: "):
                return row["end"]
    except Exception:
        pass
    finally:
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass
    last = 0
    for i, seg in enumerate(segs[:200]):
        if re.match(r"\s*#\s*include\b", seg):
            last = i + 1
    return last
