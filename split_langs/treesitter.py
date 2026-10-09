"""Generic tree-sitter languages for split_monster — names, identifiers, import band — all taken
from get_codeblock (its `Spec` says what a landmark/frame is, its backend parses). No per-language
code here: C# and C/C++ get name hints for free, and any language added to get_codeblock's registry
only needs its extensions listed below.

What it does NOT do yet: `source_imports` / `render_import` (imports of the source file — the
find_code_usage resolvers are the donor, next step), so no import propagation and no graph.
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


def source_imports(lines):
    return {}      # next step: find_code_usage handlers (C# using, C++ #include)


def render_import(specifier, kind, items):
    raise ValueError("import syntax for this language is not wired yet")


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
