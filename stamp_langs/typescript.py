"""TS/JS для штемпеля: объявления через get_codeblock declarations (tree-sitter / regex)."""

from . import _common

NAME = "typescript"
EXTENSIONS = (".ts", ".tsx", ".js", ".jsx")
ALIASES = ("ts", "js", "tsx")
DECORATORS = ("export", "default", "declare", "async", "function", "class",
              "interface", "enum", "type", "namespace", "abstract", "public",
              "private", "protected", "readonly", "static", "const", "let", "var")

_TS_MODULE = "get_codeblock.handlers.ts_treesitter"
_TS_PKG = "tree-sitter-typescript"


def import_line(line):
    return line.startswith(("import ", "import{", "export ")) or "require(" in line


def declared(project_root, target_abs):
    src = _common.read_source(target_abs)
    if src is None:
        return _common.empty()
    exports, all_defs, reexports = [], {}, []
    for d in _common.brace_declarations(NAME, _TS_MODULE, _TS_PKG, src, project_root):
        if d["kind"] == "reexport":
            reexports.append({"name": d["name"], "source": d["reexport_from"]})
            continue
        all_defs[d["name"]] = d["signature"]
        if d["exported"]:
            exports.append({"name": d["name"], "kind": d["kind"],
                            "signature": d["signature"], "methods": []})
    return {"docstring_first": None, "exports": exports, "all_defs": all_defs, "reexports": reexports}
