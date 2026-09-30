"""C# для штемпеля: объявления через get_codeblock declarations; namespace — доп. имена цели."""

from . import _common

NAME = "csharp"
EXTENSIONS = (".cs",)
ALIASES = ("cs",)
DECORATORS = ("public", "private", "protected", "internal", "static", "virtual",
              "override", "sealed", "abstract", "async", "readonly", "partial",
              "new", "class", "interface", "struct", "enum", "record", "const")

_TS_MODULE = "get_codeblock.handlers.cs_treesitter"
_TS_PKG = "tree-sitter-c-sharp"


def import_line(line):
    return line.startswith(("using ", "global using "))


def declared(project_root, target_abs):
    src = _common.read_source(target_abs)
    if src is None:
        return _common.empty()
    exports, all_defs = [], {}
    for d in _common.brace_declarations(NAME, _TS_MODULE, _TS_PKG, src, project_root):
        all_defs[d["name"]] = d["signature"]
        if d["exported"]:
            exports.append({"name": d["name"], "kind": d["kind"],
                            "signature": d["signature"], "methods": d.get("methods", [])})
    return {"docstring_first": None, "exports": exports, "all_defs": all_defs, "reexports": []}


def extra_target_names(handler, target_abs):
    """C# импортирует namespace, а не файл: namespace цели и все его префиксы — тоже её имена."""
    out = set()
    if not hasattr(handler, "_extract_namespace"):
        return out
    ns = handler._extract_namespace(target_abs)
    if ns:
        out.add(ns)
        parts = ns.split(".")
        for i in range(1, len(parts)):
            out.add(".".join(parts[:i]))
    return out
