"""Python for split_monster: stdlib `ast` (no grammar needed, exact)."""

import ast
import io
import os
import re
import tokenize
from pathlib import Path

from ._common import WORD_RE, dedup

NAME = "python"
EXTENSIONS = (".py",)
CONSUMERS = True
GRAPH = True


def _parse(text):
    try:
        return ast.parse(text)
    except SyntaxError:
        return None


def _target_names(node):
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        return [n for e in node.elts for n in _target_names(e)]
    return []


def _declared(tree):
    names = []
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(n.name)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                names.extend(_target_names(t))
        elif isinstance(n, (ast.AnnAssign, ast.AugAssign)):
            names.extend(_target_names(n.target))
    return dedup(names)


def declared_names(text, ext=""):
    """Top-level names a block declares, in order (a banded range carries several)."""
    tree = _parse(text)
    return _declared(tree) if tree else []


def top_level_names(lines, ext=""):
    tree = _parse("\n".join(lines))
    return set(_declared(tree)) if tree else set()


def identifiers(text, ext=""):
    """Names the snippet USES (never words inside comments/strings): ast Name nodes; tokenize
    when the snippet does not parse."""
    tree = _parse(text)
    if tree is not None:
        return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    try:
        return {t.string for t in tokenize.generate_tokens(io.StringIO(text).readline)
                if t.type == tokenize.NAME}
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return set(WORD_RE.findall(text))


def decl_line(text, ext=""):
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"(async\s+def|def|class)\s", stripped) or \
                re.match(r"[A-Za-z_]\w*\s*(:[^=]*)?=[^=]", stripped):
            return stripped
    return text.splitlines()[0].strip() if text else ""


def name_from_decl(decl):
    m = re.match(r"(?:async\s+def|def|class)\s+(\w+)", decl)
    if m:
        return m.group(1)
    m = re.match(r"([A-Za-z_]\w*)\s*(?::[^=]*)?=", decl)
    return m.group(1) if m else None


def source_imports(lines, ext=""):
    """{specifier: {"kind": "named"|"module", "items": [(original, local), ...]}} for the TOP-LEVEL
    `import` / `from … import` statements. A relative import keeps its dots in the specifier;
    `from __future__` and `*` are skipped."""
    tree = _parse("\n".join(lines))
    imports = {}
    if tree is None:
        return imports
    for n in tree.body:
        if isinstance(n, ast.ImportFrom) and n.module != "__future__":
            spec = "." * n.level + (n.module or "")
            entry = imports.setdefault(spec, {"kind": "named", "items": []})
            for a in n.names:
                if a.name == "*":
                    continue
                pair = (a.name, a.asname or a.name)
                if pair not in entry["items"]:
                    entry["items"].append(pair)
        elif isinstance(n, ast.Import):
            for a in n.names:
                local = a.asname or a.name.split(".")[0]
                entry = imports.setdefault(a.name, {"kind": "module", "items": []})
                if (a.name, local) not in entry["items"]:
                    entry["items"].append((a.name, local))
    return {k: v for k, v in imports.items() if v["items"]}


def render_import(specifier, kind, items):
    if kind == "named":
        parts = [orig if orig == local else f"{orig} as {local}" for orig, local in items]
        return f"from {specifier} import {', '.join(parts)}"
    if kind == "module":
        return "\n".join(
            f"import {orig}" if local == orig.split(".")[0] else f"import {orig} as {local}"
            for orig, local in items)
    raise ValueError(f"unknown import kind {kind!r}")


def file_spec(from_file, to_file):
    """Module path `from_file` imports `to_file` by: relative when its folder is a package."""
    fdir = Path(from_file).resolve().parent
    tpath = Path(to_file).resolve()
    rel = Path(os.path.relpath(tpath.parent, fdir))
    parts = [p for p in rel.parts if p != "."]
    ups = sum(1 for p in parts if p == "..")
    downs = [p for p in parts if p != ".."]
    if (fdir / "__init__.py").exists():
        return "." * (1 + ups) + ".".join(downs + [tpath.stem])
    return ".".join(downs + [tpath.stem]) if not ups else tpath.stem


def import_insert_index(segs, ext=""):
    """After the last top-level import, else after the module docstring, else the top."""
    tree = _parse("".join(segs))
    if tree is None:
        return 0
    last = max([n.end_lineno for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))] or [0])
    if last:
        return last
    if tree.body and isinstance(tree.body[0], ast.Expr) and \
            isinstance(getattr(tree.body[0], "value", None), ast.Constant) and \
            isinstance(tree.body[0].value.value, str):
        return tree.body[0].end_lineno
    return 0


def syntax_ok(data, ext):
    try:
        ast.parse(data.decode("utf-8", "replace").lstrip("﻿"))
        return True
    except SyntaxError:
        return False


def exported_names(text):
    """The module's public surface: the `__all__` list when there is one, else every top-level
    name not starting with an underscore (the convention `from m import *` and readers rely on)."""
    tree = _parse(text)
    if tree is None:
        return set()
    for n in tree.body:
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in n.targets) \
                and isinstance(n.value, (ast.List, ast.Tuple)):
            return {e.value for e in n.value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    return {n for n in _declared(tree) if not n.startswith("_")}


def dangling_exports(lines, names):
    """Names of `names` still listed in the REMAINING source's `__all__` (they would not resolve)."""
    return sorted(exported_names_from_all("\n".join(lines)) & set(names))


def exported_names_from_all(text):
    tree = _parse(text)
    if tree is None:
        return set()
    for n in tree.body:
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in n.targets) \
                and isinstance(n.value, (ast.List, ast.Tuple)):
            return {e.value for e in n.value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    return set()


def reexport_line(names, spec):
    return f"from {spec} import {', '.join(names)}  # re-export"
