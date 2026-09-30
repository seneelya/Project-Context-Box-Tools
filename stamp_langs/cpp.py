"""C/C++ (and CUDA) for the stamp — Plan08 / Vision09.

Facts only, conditions TAGGED not resolved:
- declared surface from tree-sitter (`get_codeblock/handlers/cpp_treesitter.py`) after cutting
  export macros (`CPP_STRIP_MACROS`, `CPP_WRAPPER_MACROS`); every declaration carries the `#if`
  condition it sits under (`cond`);
- a HEADER exports everything it declares (static inline helpers too — includers see them);
- an IMPLEMENTATION exports only external definitions NOT declared in any header it includes —
  the rest is the header's API and is not duplicated (the card says where it is declared);
- `## Build facts` (fact section, re-stamped every time): header<->impl pair, which headers
  declare what this file defines, `#if` zones, who includes it in the WHOLE tree (not only the
  stamped zone), seam hints, regions tree-sitter could not read.
"""

import os
import re
import sys

from . import _common

NAME = "cpp"
EXTENSIONS = (".h", ".hh", ".hpp", ".hxx", ".cuh", ".inl",
              ".c", ".cc", ".cpp", ".cxx", ".c++", ".cu")
ALIASES = ("c", "c++", "cxx", "cuda", "cu")
DECORATORS = ("static", "inline", "extern", "const", "constexpr", "virtual", "explicit",
              "struct", "class", "union", "enum", "typedef", "volatile", "typename")

_KIND = {"struct": "struct", "union": "struct", "class": "class", "enum": "enum", "type": "type",
         "var": "var", "function": "function", "macro": "macro", "namespace": "namespace"}
# `#ifdef __cplusplus extern "C" { #endif` — a C/C++ linkage idiom, not a build switch
_IDIOM_CONDS = {"__cplusplus", "!__cplusplus"}
_MAX_LIST = 25          # cap for long fact lists (includers, zones, seam hints)
_WARNED = set()


def import_line(line):
    return line.startswith("#include")


def _engine():
    from find_code_usage import cpp_includes
    return cpp_includes


def _is_header(path):
    return os.path.splitext(path)[1].lower() in _engine().HEADER_EXTS


_AN_CACHE = {}


def _analysis(project_root, target_abs):
    """(analysis dict, scan) for a file — cached per (path, mtime)."""
    ci = _engine()
    try:
        mt = os.path.getmtime(target_abs)
    except OSError:
        return None, None
    key = (os.path.normcase(target_abs), mt)
    if key in _AN_CACHE:
        return _AN_CACHE[key]
    from get_codeblock.handlers import cpp_treesitter as ct
    if not ct.available():
        if "cpp" not in _WARNED:
            _WARNED.add("cpp")
            sys.stderr.write("[make_interface_card] WARNING: tree-sitter-cpp not installed - C/C++ "
                             "declarations are EMPTY (no regex fallback for C/C++). Install:  "
                             "pip install tree-sitter tree-sitter-cpp\n")
        res = ({"decls": [], "opaque": []}, ci.scan_file(target_abs))
        _AN_CACHE[key] = res
        return res
    src = _common.read_source(target_abs)
    if src is None:
        return None, None
    cfg = ci.cpp_config(project_root)
    from get_codeblock import cpp_source
    prepared = cpp_source.prepare(src, cfg["strip_macros"], cfg["wrapper_macros"])
    an = ct.analyze(prepared, ci.prepare_for_second_parse)
    res = (an, ci.scan_file(target_abs))
    _AN_CACHE[key] = res
    return res


def _decls(project_root, target_abs):
    an, scan = _analysis(project_root, target_abs)
    if an is None:
        return [], scan
    guard = scan.guard if scan else None
    cfg = _engine().cpp_config(project_root)
    noise = set(cfg["strip_macros"]) | set(cfg["wrapper_macros"])   # export/attribute macro defs
    src = _common.read_source(target_abs)
    if src:
        from get_codeblock import cpp_source
        auto_strip, auto_wrap = cpp_source.detect_macros(src)
        noise |= set(auto_strip) | set(auto_wrap)
    out = []
    for d in an["decls"]:
        if d["kind"] == "macro" and (d["name"] == guard or d["name"] in noise):
            continue
        d = dict(d)
        d["cond"] = scan.cond_at(d["line"]) if scan else None
        out.append(d)
    return out, scan


def _methods(d, scan):
    ms = [{"name": m["name"], "signature": m["signature"]} for m in d.get("methods", [])]
    for v in d.get("variants", []):
        c = scan.cond_at(v["line"]) if scan else None
        ms.append({"name": v["name"], "signature": v["signature"] + (f"  — if {c}" if c else "")})
    return ms


def _header_decl_names(project_root, target_abs):
    """{name: header rel} for declarations of every in-tree header the file includes, transitively."""
    ci = _engine()
    tree = ci.tree_for(project_root)
    fwd = tree.forward()
    seen, stack, out = set(), [os.path.abspath(target_abs)], {}
    while stack:
        node = stack.pop()
        for tgt, _c, _l in fwd.get(node, []):
            k = os.path.normcase(tgt)
            if k in seen:
                continue
            seen.add(k)
            stack.append(tgt)
            if _is_header(tgt):
                decls, _s = _decls(project_root, tgt)
                for d in decls:
                    out.setdefault(d["name"], tree.rel(tgt))
    return out


def declared(project_root, target_abs):
    decls, scan = _decls(project_root, target_abs)
    header = _is_header(target_abs)
    declared_in = {} if header else _header_decl_names(project_root, target_abs)
    exports, all_defs = [], {}
    for d in decls:
        if d["kind"] == "namespace":
            continue
        all_defs.setdefault(d["name"], d["signature"])
        if header:
            keep = True
        else:
            keep = (d["kind"] in ("function", "var") and d["definition"] and not d["static"]
                    and d["name"] not in declared_in)
        if keep:
            exports.append({"name": d["name"], "kind": _KIND.get(d["kind"], d["kind"]),
                            "signature": d["signature"], "methods": _methods(d, scan),
                            "cond": d["cond"]})
    return {"docstring_first": None, "exports": exports, "all_defs": all_defs, "reexports": []}


# --------------------------------------------------------------------------- API families
# Vision10 §4 / Plan09 step 2: a header's API grouped MECHANICALLY (the stamp owns it, so an
# agent's regrouping would be overwritten), in order of trust: the author's section comments ->
# a shared name prefix -> the declaration kind. Stable between stamps: same source, same groups.

FAMILY_MIN = 4       # a prefix group needs at least this many declarations
FAMILY_BIG = 30      # a group larger than this is split further by prefix
_TOP = "(top of file)"
_WHOLE = "(whole file)"
_KIND_FAMILY = {"function": "functions", "type": "types", "struct": "types", "class": "types",
                "enum": "types", "macro": "macros", "var": "variables"}


def sections(text):
    """[(line, title)] — the author's section frames: `//` / `// Title` / `//` opening a comment
    block (not inside one — a doc paragraph like `// TODO` is not a heading; a doc may FOLLOW, as
    in `llama.h` Sampling API), a short title that is not a sentence (Memory, Vocab…)."""
    lines = [ln.strip() for ln in text.splitlines()]

    def com(k):
        return 0 <= k < len(lines) and lines[k].startswith("//")

    out = []
    for i in range(1, len(lines) - 1):
        s = lines[i]
        if (lines[i - 1] == "//" and lines[i + 1] == "//" and s.startswith("//") and s != "//"
                and not com(i - 2)):
            title = s[2:].strip()
            if title and len(title) <= 60 and not title.endswith((":", ";", ".", ",")):
                out.append((i + 1, title))
    return out


def _tokens(name):
    return [t for t in name.split("_") if t] or [name]


def _prefix_groups(items, depth=0):
    """items [(line, name, kind)] -> ([(prefix, items)], leftovers). Names grouped by their first
    depth+1 `_`-tokens; a group holding more than FAMILY_BIG goes one token deeper (ggml ->
    ggml_backend -> ggml_backend_sched); groups under FAMILY_MIN are leftovers."""
    by = {}
    for it in items:
        tk = _tokens(it[1])
        if len(tk) <= depth:
            by.setdefault(None, []).append(it)
        else:
            by.setdefault("_".join(tk[:depth + 1]), []).append(it)
    groups, left = [], list(by.pop(None, []))
    for key, its in by.items():
        if len(its) > FAMILY_BIG and depth < 4:
            sub, rest = _prefix_groups(its, depth + 1)
            groups.extend(sub)
            if len(rest) >= FAMILY_MIN and sub:
                groups.append(("other " + key + "_*", rest))
            elif not sub:
                groups.append((key + "_*", its))
            else:
                left.extend(rest)
        elif len(its) >= FAMILY_MIN:
            groups.append((key + "_*", its))
        else:
            left.extend(its)
    return groups, left


def _by_kind(items, label=""):
    by = {}
    for it in items:
        by.setdefault(_KIND_FAMILY.get(it[2], "other"), []).append(it)
    return [((f"{label} — other {k}" if label else f"Other {k}"), its) for k, its in by.items()]


def _family(name, how, its, first=None):
    lines = [it[0] for it in its]
    return {"name": name, "how": how, "decls": [it[1] for it in its],
            "first": min([first] + lines if first else lines), "last": max(lines)}


def source_edges(project_root):
    """The whole include graph of the root (scan cache — ~0.3 s warm on llama.cpp)."""
    tree = _engine().tree_for(project_root)
    return {tree.rel(src): [(tree.rel(t), c) for t, c, _l in edges]
            for src, edges in tree.forward().items()}


def api_families(project_root, target_abs, declared_surface):
    """A header IS the interface -> families (card form "API: in source"); an implementation
    keeps H4 entries (only its external definitions not declared in a header)."""
    if not _is_header(target_abs):
        return None
    return families(project_root, target_abs, declared_surface["exports"])


def families(project_root, target_abs, exports=None):
    """[{name, how: section|prefix|kind|file, decls: [names], first, last}] in file order.
    `exports` = declared()["exports"] (computed when omitted)."""
    if exports is None:
        exports = declared(project_root, target_abs)["exports"]
    decls, _scan = _decls(project_root, target_abs)
    line_of = {}
    for d in decls:
        line_of.setdefault(d["name"], d["line"])
    items = sorted((line_of.get(e["name"], 0), e["name"], e["kind"]) for e in exports)
    if not items:
        return []
    src = _common.read_source(target_abs) or ""
    secs = sections(src)
    out = []

    def split(label, how, its, first=None):
        if len(its) <= FAMILY_BIG:
            out.append(_family(label or _WHOLE, how if label else "file", its, first))
            return
        groups, left = _prefix_groups(its)
        if not groups:
            out.append(_family(label or _WHOLE, how if label else "file", its, first))
            return
        for key, g in groups:
            out.append(_family(f"{label} / {key}" if label else key, "prefix", g))
        for name, g in _by_kind(left, label):
            out.append(_family(name, "kind", g))

    by_sec = {}
    for it in items:
        cur = None
        for sl, title in secs:
            if sl <= it[0]:
                cur = (sl, title)
        by_sec.setdefault(cur, []).append(it)
    if sum(1 for k in by_sec if k is not None) >= 2:
        for key in sorted(by_sec, key=lambda k: k[0] if k else 0):
            its = by_sec[key]
            split(key[1] if key else _TOP, "section", its, key[0] if key else None)
    else:
        split("", "prefix", items)
    out.sort(key=lambda f: (f["first"], f["name"]))
    seen = {}
    for f in out:                 # the name is the prose key -> unique within the card
        n = seen[f["name"]] = seen.get(f["name"], 0) + 1
        if n > 1:
            f["name"] = f"{f['name']} ({n})"
    return out


# --------------------------------------------------------------------------- entry key

_ID = r"[A-Za-z_]\w*"


def entry_key(sig):
    """Name of a C/C++ declaration from ITS signature text (the generic position rule picks
    `void` in `typedef void (*cb)(int)` and `#define` in `#define X 4`)."""
    s = re.sub(r"\{…\}", " ", sig).strip()
    s = re.sub(r"^template\s*<[^>]*>\s*", "", s)
    m = re.match(r"#define\s+(" + _ID + ")", s)
    if m:
        return m.group(1)
    m = re.search(r"\(\s*\*\s*(" + _ID + r")\s*\)\s*\(", s)          # function pointer: (*name)(
    if m:
        return m.group(1)
    m = re.match(r"using\s+(" + _ID + r")\s*=", s)
    if m:
        return m.group(1)
    if s.startswith("typedef"):
        body = re.sub(r"\[[^\]]*\]", "", s).rstrip(" ;")
        ids = re.findall(_ID, body)
        return ids[-1] if ids else None
    m = re.match(r"(?:(?:struct|class|union|enum)\s+(?:class\s+)?)(" + _ID + ")", s)
    if m and "(" not in s:
        return m.group(1)
    m = re.search(r"(" + _ID + r"(?:::~?" + _ID + r")*)\s*\(", s)   # function: name(
    if m:
        return m.group(1).split("::")[-1]
    body = re.split(r"[=\[]", s, 1)[0]
    ids = re.findall(_ID, body)
    return ids[-1] if ids else None


# --------------------------------------------------------------------------- build facts

def _pair(project_root, target_abs):
    """Paired file(s): CPP_PAIRS (either direction) first, else same stem — same folder, then
    anywhere in the tree when unique. -> [rel]"""
    ci = _engine()
    tree = ci.tree_for(project_root)
    rel = tree.rel(target_abs)
    pairs = tree.cfg["pairs"]
    hits = [v for k, v in pairs.items() if k == rel] + [k for k, v in pairs.items() if v == rel]
    if hits:
        return hits
    stem = os.path.splitext(os.path.basename(target_abs))[0].lower()
    want = ci.IMPL_EXTS if _is_header(target_abs) else ci.HEADER_EXTS
    cands = [p for p in tree.files if os.path.splitext(os.path.basename(p))[0].lower() == stem
             and os.path.splitext(p)[1].lower() in want]
    same_dir = [p for p in cands if os.path.dirname(p) == os.path.dirname(os.path.abspath(target_abs))]
    pick = same_dir or (cands if len(cands) == 1 else [])
    return [tree.rel(p) for p in pick]


# numeric literals (0xFFFFFFFF, 201703L, 1u, 1.5f) — their letters are NOT identifiers
_NUMBER = re.compile(r"\b(?:0[xX][0-9a-fA-F]+|\d[\w.]*)")


def _flags(conds):
    names = set()
    for c in conds:
        for ident in re.findall(_ID, _NUMBER.sub(" ", c or "")):
            if ident not in ("defined", "__has_include") and not ident.isdigit():
                names.add(ident)
    return sorted(names)


def _cap(items, render):
    lines = [render(x) for x in items[:_MAX_LIST]]
    if len(items) > _MAX_LIST:
        lines.append(f"- … +{len(items) - _MAX_LIST} more")
    return lines


def fact_sections(project_root, target_abs, declared_surface):
    """-> [(title, [lines])] — the `## Build facts` section (pure fact, re-stamped)."""
    import seam_scanner
    ci = _engine()
    tree = ci.tree_for(project_root)
    an, scan = _analysis(project_root, target_abs)
    lines = []
    header = _is_header(target_abs)

    pair = _pair(project_root, target_abs)
    if pair:
        verb = "implemented in" if header else "implements"
        lines.append(f"pair: {verb} " + ", ".join(f"`{p}`" for p in pair))

    if not header:
        declared_in = _header_decl_names(project_root, target_abs)
        defs, _s = _decls(project_root, target_abs)
        per = {}
        for d in defs:
            if d["definition"] and not d["static"] and d["name"] in declared_in:
                per[declared_in[d["name"]]] = per.get(declared_in[d["name"]], 0) + 1
        if per:
            lines.append("defines what these headers declare: "
                         + ", ".join(f"`{h}` {n}" for h, n in sorted(per.items(), key=lambda x: -x[1])))

    blocks = [x for x in (scan.blocks if scan else []) if x[0] not in _IDIOM_CONDS]
    if blocks:
        by_cond = {}
        for cond, a, b in blocks:
            by_cond.setdefault(cond, []).append((a, b))
        flags = _flags(by_cond)
        lines.append(f"build conditions ({len(blocks)} #if-branches): "
                     + (", ".join(f"`{f}`" for f in flags) if flags else "(none named)"))
        zones = sorted(by_cond.items(), key=lambda kv: kv[1][0][0])
        lines.extend(_cap(zones, lambda kv: f"- `{kv[0]}`: " + ", ".join(
            f"L{a}-{b}" for a, b in kv[1][:6]) + (f" +{len(kv[1]) - 6}" if len(kv[1]) > 6 else "")))

    incl = tree.includers(target_abs)
    if header:
        lines.append(f"included by ({len(incl)}, whole tree):" if incl else "included by: 0 (whole tree)")
        rows = sorted(incl, key=lambda x: tree.rel(x[0]))
        lines.extend(_cap(rows, lambda x: f"- `{tree.rel(x[0])}`" + (f" [if {x[1]}]" if x[1] else "")))
        reach = tree.reach(target_abs)
        more = len(reach) - len({os.path.normcase(x[0]) for x in incl})
        if more > 0:
            lines.append(f"reached transitively by {more} more file(s)")

    hits = seam_scanner.scan(target_abs, "cpp")
    if hits:
        lines.append(f"seam hints ({len(hits)}, grep — confirm in code):")
        lines.extend(_cap(hits, lambda h: f"- L{h[0]} {h[1]}: `{h[2][:100]}`"
                          + (f" [if {scan.cond_at(h[0])}]" if scan and scan.cond_at(h[0]) else "")))

    if an and an["opaque"]:
        lines.append("opaque (tree-sitter could not read — read the code; a macro wrapping declarations? "
                     "add it to CPP_WRAPPER_MACROS / CPP_STRIP_MACROS): "
                     + ", ".join(f"L{a}" if a == b else f"L{a}-{b}" for a, b in an["opaque"][:10]))

    return [("Build facts", lines)] if lines else []
