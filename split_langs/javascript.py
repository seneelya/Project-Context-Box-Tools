"""JavaScript / TypeScript (ESM) for split_monster: tree-sitter via get_codeblock for identifiers,
find_code_usage's ts_handler regexes for imports. `require()` is not handled."""

import os
import re
from pathlib import Path

from ._common import WORD_RE

NAME = "javascript"
EXTENSIONS = (".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx")
CONSUMERS = True
GRAPH = True

_TOP_LEVEL_NAME_RE = re.compile(
    r"^(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s+(\w+)"
    r"|^(?:export\s+)?const\s+(\w+)\s*="
    r"|^(?:export\s+)?class\s+(\w+)"
    r"|^(?:export\s+)?let\s+(\w+)\s*="
)
# node types meaning "a name is USED/declared here" (not a property key, comment or string content)
_IDENT_TYPES = frozenset({"identifier", "type_identifier", "shorthand_property_identifier",
                          "shorthand_property_identifier_pattern"})


def _first_group(m):
    return next(g for g in m.groups() if g)


def declared_names(text):
    names = []
    for line in text.splitlines():
        if line[:1].isspace():
            continue
        m = _TOP_LEVEL_NAME_RE.match(line)
        if m and _first_group(m) not in names:
            names.append(_first_group(m))
    return names


def top_level_names(lines):
    names = set()
    for line in lines:
        if line[:1].isspace():
            continue
        m = _TOP_LEVEL_NAME_RE.match(line)
        if m:
            names.add(_first_group(m))
    return names


def identifiers(text, ext=".js"):
    """Names the snippet USES — tree-sitter identifier nodes (comments and strings do not count);
    plain words if the grammar for `ext` is unavailable."""
    try:
        from get_codeblock.reader.registry import resolve
        backend, _spec = resolve(ext)
        found, stack = set(), [backend.root(text.encode("utf-8"))]
        while stack:
            n = stack.pop()
            if n.type in _IDENT_TYPES:
                found.add(n.text())
            stack.extend(n.children())
        return found
    except Exception:
        return set(WORD_RE.findall(text))


def decl_line(text):
    for line in text.splitlines():
        if _TOP_LEVEL_NAME_RE.match(line.strip()):
            return line.strip()
    return text.splitlines()[0].strip() if text else ""


def name_from_decl(decl):
    m = _TOP_LEVEL_NAME_RE.match(decl)
    return _first_group(m) if m else None


def source_imports(lines):
    """{specifier: {"kind": "named"|"default"|"namespace", "items": [(original, local), ...]}} —
    the LEADING ES imports (stops at the first line that is neither blank, comment nor import),
    read with find_code_usage's own ts_handler regexes; multi-line `import {...}` collapsed first."""
    from find_code_usage.handlers.ts_handler import TypeScriptHandler

    handler = TypeScriptHandler()
    joined = handler._join_multiline_imports(list(lines))
    imports = {}

    def add(specifier, kind, items):
        entry = imports.setdefault(specifier, {"kind": kind, "items": []})
        for pair in items:
            if pair not in entry["items"]:
                entry["items"].append(pair)

    for line in joined:
        stripped = line.strip()
        if not stripped or stripped.startswith(("//", "*", "/*")):
            continue
        m = TypeScriptHandler.ES_NAMED_RE.match(line)
        if m:
            add(m.group(2).strip(), "named", handler._parse_named_items(m.group(1)))
            continue
        m = TypeScriptHandler.ES_DEFAULT_RE.match(line)
        if m:
            add(m.group(2).strip(), "default", [(m.group(1), m.group(1))])
            continue
        m = TypeScriptHandler.ES_NAMESPACE_RE.match(line)
        if m:
            add(m.group(2).strip(), "namespace", [(m.group(1), m.group(1))])
            continue
        if not stripped.startswith("import"):
            break
    return imports


def render_import(specifier, kind, items):
    if kind == "named":
        parts = [orig if orig == local else f"{orig} as {local}" for orig, local in items]
        return f"import {{ {', '.join(parts)} }} from '{specifier}'"
    if kind == "default":
        return f"import {items[0][1]} from '{specifier}'"
    if kind == "namespace":
        return f"import * as {items[0][1]} from '{specifier}'"
    raise ValueError(f"unknown import kind {kind!r}")


def file_spec(from_file, to_file):
    fdir = Path(from_file).resolve().parent
    tpath = Path(to_file).resolve()
    spec = Path(os.path.relpath(tpath, fdir)).as_posix()
    if tpath.suffix.lower() in (".ts", ".tsx"):
        spec = spec[: -len(tpath.suffix)]
    return spec if spec.startswith(".") else "./" + spec


def import_insert_index(segs):
    """After the leading import block (single- or multi-line statements)."""
    i = last = 0
    while i < len(segs):
        st = segs[i].strip()
        if not st or st.startswith(("//", "/*", "*")):
            i += 1
            continue
        if not st.startswith("import"):
            break
        j = i
        while j < len(segs) and not re.search(r"""['"]\s*;?\s*$""", segs[j].rstrip()):
            j += 1
        if j >= len(segs):
            break
        last = i = j + 1
    return last


def export_problem(name, block_text):
    if not re.search(rf"^\s*export\b[^\n]*\b{re.escape(name)}\b", block_text, re.M):
        return "not exported"
    return None
