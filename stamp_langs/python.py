"""Python для штемпеля: объявления через show_pyfile_api (ast — точные типы параметров)."""

from pathlib import Path

NAME = "python"
EXTENSIONS = (".py",)
ALIASES = ("py",)
DECORATORS = ("async",)


def declared(project_root, target_abs):
    import show_pyfile_api
    c = show_pyfile_api.collect(Path(target_abs))
    exports = [{"name": f["name"], "kind": "function", "signature": f["signature"], "methods": []}
               for f in c["functions"]]
    exports += [{"name": cl["name"], "kind": "class", "signature": cl["name"], "methods": cl["methods"]}
                for cl in c["classes"]]
    exports += [{"name": g["name"], "kind": "const", "signature": g["signature"], "methods": []}
                for g in c["constants"]]
    all_defs = dict(c["all_defs"])
    for g in c["module_globals"]:
        all_defs.setdefault(g["name"], g["signature"])
    reexports = [{"name": nm, "source": "." * imp["level"] + imp["module"],
                  "module": imp["module"], "level": imp["level"]}
                 for imp in c["import_froms"] if imp["level"] >= 1 for nm in imp["names"]]
    return {"docstring_first": c["docstring_first"], "exports": exports,
            "all_defs": all_defs, "reexports": reexports}


def reexport_signature(target_abs, reexport):
    """Best-effort signature of a re-exported name from a relative import
    `from <dots><module> import name` — resolve to a sibling .py and read its ast."""
    if "module" not in reexport:
        return None
    module, level, name = reexport["module"], reexport["level"], reexport["name"]
    if level <= 0:
        return None
    base = Path(target_abs).parent
    for _ in range(level - 1):
        base = base.parent
    parts = module.split(".") if module else []
    cand = base.joinpath(*parts)
    for p in (cand.with_suffix(".py"), cand / "__init__.py"):
        if p.is_file():
            try:
                import show_pyfile_api
                return show_pyfile_api.collect(p).get("all_defs", {}).get(name)
            except Exception:
                return None
    return None
