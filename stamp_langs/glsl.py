"""GLSL shaders for the stamp — REQ-021.

Facts only, conditions TAGGED not resolved (as C/C++):
- declared surface from tree-sitter (`find_code_usage/glsl_tree.analyze`): functions, the shader
  interface (buffer / uniform / push_constant blocks with their fields — H3 "Interfaces"),
  structs, specialization constants, `shared` and other globals. Global `const`s go to
  `all_defs` and a count by prefix in the facts (a part may hold 200 field indices — one entry
  each would bury the API);
- `## Shader facts` (fact section, re-stamped every time): the stage and `local_size`, the
  compile units the file belongs to, who includes it, push-constant size (std430), `#if` zones,
  the CALL SITES of each function defined here in every unit (a GLSL call site is a full inlined
  copy in the driver compile — the count is the cost), the functions it calls from other files of
  the unit, and forward declarations.
"""

import os
import re

NAME = "glsl"
EXTENSIONS = (".comp", ".glsl", ".vert", ".frag", ".geom", ".tesc", ".tese")
ALIASES = ("shader", "shaders")
DECORATORS = ("const", "shared", "uniform", "buffer", "readonly", "writeonly", "coherent",
              "volatile", "restrict", "in", "out", "inout", "highp", "mediump", "lowp", "precise",
              "flat", "smooth", "noperspective", "struct")

_MAX_LIST = 40
_NAMES_MAX = 8
_ID = re.compile(r"[A-Za-z_]\w*")


def import_line(line):
    return line.startswith("#include")


def _engine():
    from find_code_usage import glsl_tree
    return glsl_tree


def _analysis(target_abs):
    g = _engine()
    if not g.available():
        from get_codeblock.env_check import ensure_language
        try:
            ensure_language("glsl")          # raises with the exact pip install of the shipped wheel
        except Exception as e:
            import sys
            sys.stderr.write(f"[make_interface_card] WARNING: GLSL grammar missing - declarations are EMPTY. {e}\n")
        return None
    return g.analyze(target_abs)


def _fields(b):
    return [{"name": f["name"], "signature": f["signature"]} for f in b["fields"]]


def declared(project_root, target_abs):
    from . import _common
    a = _analysis(target_abs)
    if a is None:
        return _common.empty()
    items = []
    for f in a["functions"]:
        items.append((f["line"], {"name": f["name"], "kind": "function", "signature": f["signature"],
                                  "methods": [], "cond": f["cond"]}))
    for b in a["blocks"]:
        sig = b["signature"] + (f" {{…}} {b['instance']}" if b["instance"] else "")
        items.append((b["line"], {"name": b["name"], "kind": "interface", "signature": sig,
                                  "methods": _fields(b), "cond": b["cond"]}))
    for s in a["structs"]:
        items.append((s["line"], {"name": s["name"], "kind": "struct", "signature": s["signature"],
                                  "methods": _fields(s), "cond": s["cond"]}))
    for k, kind in (("spec", "const"), ("shared", "var"), ("vars", "var")):
        for v in a[k]:
            items.append((v["line"], {"name": v["name"], "kind": kind, "signature": v["signature"],
                                      "methods": [], "cond": v["cond"]}))
    items.sort(key=lambda x: x[0])
    exports = [e for _l, e in items]
    all_defs = {}
    for e in exports:
        all_defs.setdefault(e["name"], e["signature"])
    for c in a["consts"]:
        all_defs.setdefault(c["name"], c["signature"])
    return {"docstring_first": None, "exports": exports, "all_defs": all_defs, "reexports": []}


def entry_key(sig):
    """Name of a GLSL signature: `layout(...)` is never the name; a function -> the word before
    `(`; `T x = v` -> x; a block `... buffer Meta {…} meta` -> Meta; `struct S` -> S."""
    s = re.sub(r"^\s*layout\s*\([^)]*\)\s*", "", sig or "")
    s = s.split("{", 1)[0]
    if "(" in s:
        ids = _ID.findall(s.split("(", 1)[0])
    elif "=" in s:
        ids = _ID.findall(s.split("=", 1)[0])
    else:
        ids = _ID.findall(re.sub(r"\[[^\]]*\]", "", s))
    return ids[-1] if ids else None


def source_edges(project_root):
    tree = _engine().tree_for(project_root)
    return {tree.rel(src): [(tree.rel(t), c) for t, c, _l in edges]
            for src, edges in tree.forward().items()}


# --------------------------------------------------------------------------- shader facts

def _names(items):
    items = list(dict.fromkeys(items))
    head = ", ".join(f"`{x}`" for x in items[:_NAMES_MAX])
    return head + (f" +{len(items) - _NAMES_MAX} more" if len(items) > _NAMES_MAX else "")


def _cap(lines):
    if len(lines) <= _MAX_LIST:
        return lines
    return lines[:_MAX_LIST] + [f"- … +{len(lines) - _MAX_LIST} more"]


def _spec_tags(guards, spec_names):
    """Runtime guards that name a specialization constant -> `!kX` / `kX` tags."""
    tags = []
    for gexp in guards:
        neg = gexp.startswith("!(")
        for nm in _ID.findall(gexp):
            if nm in spec_names:
                tags.append(("!" if neg else "") + nm)
    return list(dict.fromkeys(tags))


def _site_tag(call, spec_names):
    parts = []
    if call["cond"]:
        parts.append(f"if {call['cond']}")
    sp = _spec_tags(call["guards"], spec_names)
    if sp:
        parts.append("spec " + " && ".join(sp))
    return f" [{'; '.join(parts)}]" if parts else ""


def _where(calls, spec_names):
    """`scan_events` ×2, `main` [if BATCH_OP == 1] — call sites grouped by function + tags."""
    groups = {}
    for c in calls:
        key = (c["in"], _site_tag(c, spec_names))
        groups[key] = groups.get(key, 0) + 1
    rows = [f"`{fn}`" + (f" ×{n}" if n > 1 else "") + tag for (fn, tag), n in groups.items()]
    head = ", ".join(rows[:_NAMES_MAX])
    return head + (f" +{len(rows) - _NAMES_MAX} more" if len(rows) > _NAMES_MAX else "")


def _const_groups(consts):
    by = {}
    for c in consts:
        tk = c["name"].split("_")
        key = (tk[0] + "_*") if len(tk) > 1 and tk[0] else c["name"]
        by.setdefault(key, []).append(c["name"])
    big = sorted(((k, v) for k, v in by.items() if len(v) >= 3), key=lambda kv: -len(kv[1]))
    rest = [n for k, v in by.items() if len(v) < 3 for n in v]
    parts = [f"`{k}` {len(v)}" for k, v in big]
    if rest:
        parts.append(_names(rest))
    return ", ".join(parts)


_SITES_DETAIL = 30      # above this many call sites a function is summarised per file
_UNITS_DETAIL = 3       # from this many units on, call sites are one row per function across units
_SITES_HEAD = ("call sites of the functions defined here (each is a full inlined copy; "
               "copies from `main` = through every caller, all #if variants together):")


def _n_fn(calls):
    n = len({c["in"] for c in calls})
    return f"{n} function{'s' if n != 1 else ''}"


def _copies(edges):
    """{function: inlined copies when `main` is compiled} = sum over its call sites of the copies
    of the caller; main = 1. GLSL forbids recursion; a cycle (bad source) just stops the walk."""
    rev = {}
    for caller, cs in edges.items():
        for callee, n in cs.items():
            rev.setdefault(callee, []).append((caller, n))
    memo, busy = {"main": 1}, set()

    def count(fn):
        if fn in memo:
            return memo[fn]
        if fn in busy:
            return 0
        busy.add(fn)
        memo[fn] = sum(n * count(caller) for caller, n in rev.get(fn, []))
        busy.discard(fn)
        return memo[fn]

    return {fn: count(fn) for fn in rev}


def _unit_lines(tree, target_abs, entry, files, a, ana):
    """Call facts of the target inside one unit -> (called rows, {fn: (sites, copies|None)},
    uncalled names, the other lines: calls into other files, reached through, forward decls)."""
    g = _engine()
    tkey = os.path.normcase(os.path.abspath(target_abs))
    spec = set()
    defined = {}                     # function name -> rel file defining it (first in include order)
    per_file = {}
    for f in files:
        fa = ana(f)
        if fa is None:
            continue
        per_file[os.path.normcase(f)] = (f, fa)
        spec.update(s["name"] for s in fa["spec"])
        for fn in fa["functions"]:
            defined.setdefault(fn["name"], f)
    mine = [fn["name"] for fn in a["functions"] if fn["name"] != "main"]
    entry_fa = per_file.get(os.path.normcase(entry), (None, {}))[1] or {}
    has_main = any(fn["name"] == "main" for fn in entry_fa.get("functions", []))
    # the call graph of the unit: caller -> {callee: sites} (functions defined in the unit only)
    edges = {}
    for _k, (_f, fa) in per_file.items():
        for c in fa["calls"]:
            if c["name"] in defined:
                d = edges.setdefault(c["in"], {})
                d[c["name"]] = d.get(c["name"], 0) + 1
    copies = _copies(edges) if has_main else {}
    out = []
    summ = {}
    # calls OF the functions defined here
    called, uncalled = [], []
    for name in dict.fromkeys(mine):
        sites = []
        for k, (f, fa) in per_file.items():
            cs = [c for c in fa["calls"] if c["name"] == name]
            if cs:
                sites.append(("here" if k == tkey else f"`{tree.rel(f)}`", cs))
        n = sum(len(cs) for _w, cs in sites)
        summ[name] = (n, copies.get(name) if has_main and n else None)
        if not n:
            uncalled.append(name)
            continue
        if n > _SITES_DETAIL:          # `get` ×391: per file only, the full list is a grep away
            where = "; ".join(f"{w} ×{len(cs)} in {_n_fn(cs)}"
                              for w, cs in sites)
        else:
            where = "; ".join(f"{w}: {_where(cs, spec)}" for w, cs in sites)
        cp = copies.get(name)
        cps = f", {cp} copies from `main`" if has_main and cp is not None and cp != n else ""
        called.append(f"- `{name}` ×{n}{cps} — {where}")
    # calls FROM here into other files of the unit
    into = {}
    for c in a["calls"]:
        f = defined.get(c["name"])
        if f is None or os.path.normcase(f) == tkey:
            continue
        into.setdefault((tree.rel(f), c["name"]), []).append(c)
    if into:
        out.append("calls into other files of the unit:")
        rows = [f"- `{name}` ← `{rel}` ×{len(cs)} — {_where(cs, spec)}"
                for (rel, name), cs in sorted(into.items(), key=lambda kv: (kv[0][0], kv[1][0]["line"]))]
        out.extend(_cap(rows))
    # reached only THROUGH those calls: other files' functions that get inlined via this file
    direct = {c["name"] for c in a["calls"]}
    own = [fn["name"] for fn in a["functions"]]          # main too, when the target is the entry
    via, stack = {}, [(n, None) for n in dict.fromkeys(own) if n in edges]
    seen = set()
    while stack:
        fn, first = stack.pop()
        for callee in edges.get(fn, {}):
            cf_ = defined.get(callee)
            # via = the first function of ANOTHER file on the path (where the chain leaves here)
            hop = first or (callee if cf_ is not None and os.path.normcase(cf_) != tkey else None)
            if callee in seen:
                continue
            seen.add(callee)
            f = defined.get(callee)
            if f is not None and os.path.normcase(f) != tkey and callee not in direct:
                via.setdefault((tree.rel(f), callee), hop)
            stack.append((callee, hop))
    if via:
        rows = [f"`{name}` ← `{rel}` (via `{hop}`)" for (rel, name), hop in sorted(via.items())]
        out.append(f"reached through those calls ({len(rows)}): " + ", ".join(rows[:_MAX_LIST])
                   + (f" +{len(rows) - _MAX_LIST} more" if len(rows) > _MAX_LIST else ""))
    # forward declarations: where the declared function is defined
    protos = []
    for p in a["protos"]:
        f = defined.get(p["name"])
        at = "here" if f and os.path.normcase(f) == tkey else (f"`{tree.rel(f)}`" if f else "not in this unit")
        protos.append(f"`{p['name']}` (defined {at})")
    if protos:
        out.append("forward declarations: " + ", ".join(protos))
    return called, summ, uncalled, out


def _host_lines(project_root, target_abs, tree):
    """How the host gets this entry (REQ-021 p.3): the builds made from it (defines), the embedded
    header, and the C++ functions that use the array (`find_code_usage/glsl_host.py`)."""
    from find_code_usage.glsl_host import host_for
    host = host_for(project_root)
    names = host.builds_of(target_abs)
    if not host.on:
        return []
    if not names:
        return ["host: no C++ file includes a header built from it (not embedded, or GLSL_HOST "
                "does not match the build)"]
    out = [f"built as ({len(names)}):"]
    for n in names:
        b = host.builds[n]
        defs = "".join(f" -D{d}" for d in b["defines"])
        used = []
        for u, fns in host.uses(n):
            used.append(f"`{tree.rel(u)}`" + (" in " + ", ".join(f"`{x}`" for x in fns[:_NAMES_MAX]) if fns else ""))
        out.append(f"- `{n}`{defs} → `{host.header(n)}` (`{host.symbol(n)}`), used by " + "; ".join(used))
    return out


def fact_sections(project_root, target_abs, declared_surface):
    """-> [(title, [lines])] — the `## Shader facts` section (pure fact, re-stamped)."""
    g = _engine()
    a = _analysis(target_abs)
    if a is None:
        return []
    tree = g.tree_for(project_root)
    lines = []
    ext = os.path.splitext(target_abs)[1].lower()
    if ext in g.STAGE_EXTS:
        st = f"entry point: {g.STAGE_NAME[ext]} shader"
        if a["local_size"]:
            st += f", `{a['local_size']}`"
        lines.append(st)
    units = tree.units_of(target_abs)
    tkey = os.path.normcase(os.path.abspath(target_abs))
    others = [e for e in units if os.path.normcase(e) != tkey]
    if others:
        lines.append("compiled in: " + ", ".join(f"`{tree.rel(e)}`" for e in sorted(others)))
    elif ext not in g.STAGE_EXTS:
        lines.append("compiled in: no shader includes it (checked on its own)")
    incl = tree.includers(target_abs)
    if incl:
        lines.append("included by: " + ", ".join(
            f"`{tree.rel(s)}`" + (f" [if {c}]" if c else "")
            for s, c, _l in sorted(incl, key=lambda x: tree.rel(x[0]))))

    if ext in g.STAGE_EXTS:
        lines.extend(_host_lines(project_root, target_abs, tree))

    for b in a["blocks"]:
        if b["kind"] == "push_constant" or "std430" in [x.replace(" ", "") for x in b["layout"]] \
                and not any(f["signature"].endswith("[]") for f in b["fields"]):
            size = g.std430_size(b["fields"])
            nm = f"`{b['name']}`" + (f" ({b['instance']})" if b["instance"] else "")
            what = "push_constant" if b["kind"] == "push_constant" else "block"
            lines.append(f"{what} {nm}: {len(b['fields'])} fields, "
                         + (f"{size} bytes (std430 — the host struct must match)" if size is not None
                            else "size not computed (a type the table does not know)"))
    if a["consts"]:
        lines.append(f"global constants ({len(a['consts'])}): {_const_groups(a['consts'])}")

    scan = g.scan_file(target_abs)
    blocks = scan.blocks if scan else []
    if blocks:
        by_cond = {}
        for cond, x, y in blocks:
            by_cond.setdefault(cond, []).append((x, y))
        rows = []
        for cond, rs in sorted(by_cond.items(), key=lambda kv: kv[1][0][0]):
            fns = [f["name"] for f in a["functions"]
                   if any(f["line"] <= x <= f["end"] for x, _y in rs)]
            rows.append(f"- `{cond}` ({len(rs)} zone{'s' if len(rs) > 1 else ''})"
                        + (f": in {_names(fns)}" if fns else ": top level"))
        lines.append(f"build conditions ({len(blocks)} #if-branches, not resolved):")
        lines.extend(_cap(rows))

    cache = {}

    def ana(p):
        k = os.path.normcase(p)
        if k not in cache:
            cache[k] = g.analyze(p)
        return cache[k]

    res = [(tree.rel(e),) + _unit_lines(tree, target_abs, e, units[e], a, ana)
           for e in sorted(units, key=tree.rel)]
    if len(res) < _UNITS_DETAIL:
        for rel, called, _summ, uncalled, rest in res:
            if not (called or uncalled or rest):
                continue
            if len(res) > 1:
                lines.append(f"in unit `{rel}`:")
            if called:
                lines.append(_SITES_HEAD)
                lines.extend(_cap(called))
            if uncalled:
                lines.append("not called in this unit: " + _names(uncalled))
            lines.extend(rest)
    else:
        # a shared library part (math64 in 7 units): one row per function across the units —
        # the callers themselves are in the callers' cards ("calls into other files")
        mine = list(dict.fromkeys(fn["name"] for fn in a["functions"] if fn["name"] != "main"))
        if mine:
            lines.append(f"call sites per unit (×sites/copies from `main`; each unit is compiled on its "
                         f"own, all #if variants together; the callers are in their own cards):")
            rows = []
            for name in mine:
                parts = []
                for rel, _c, summ, _u, _r in res:
                    n, cp = summ.get(name, (0, None))
                    parts.append(f"`{os.path.basename(rel)}` ×{n}" + (f"/{cp}" if cp is not None else ""))
                rows.append(f"- `{name}` — " + ", ".join(parts))
            lines.extend(_cap(rows))
        groups = {}
        for rel, _c, _s, _u, rest in res:
            if rest:
                groups.setdefault(tuple(rest), []).append(rel)
        for rest, rels in groups.items():
            lines.append(("in units " if len(rels) > 1 else "in unit ")
                         + ", ".join(f"`{r}`" for r in rels) + ":")
            lines.extend(rest)
    if a["errors"]:
        lines.append(f"parse errors: {a['errors']} region(s) tree-sitter could not read — read the code")
    return [("Shader facts", lines)] if lines else []
