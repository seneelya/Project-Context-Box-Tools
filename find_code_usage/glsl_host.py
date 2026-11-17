"""Shader <-> host link (REQ-021 point 3): a GLSL entry is not included by C++, CMake compiles it
(`glslc ... X.comp -o name.spv`) and embeds it as a header (`name_spv.h` with an array `name_spv`)
that a C++ file includes. The facts are in files — this module reads them:

- BUILD NAMES come from the C++ side: every `#include "<header pattern>"` that is not in the tree
  (`{name}_spv.h` by default) names a build;
- a build's SOURCE and DEFINES, in order of trust:
  1. `GLSL_HOST["builds"]` in CONFIG__TOOLS: {"name": {"source": "shaders/x.comp", "defines": [...]}};
  2. the CMake files (`GLSL_HOST["cmake"]`): a branch `if(<var> STREQUAL "name") ... endif/elseif`
     whose `set(...)` names a GLSL file stem (the source) and whose `-DX=Y` tokens are the defines
     (contact_lab: `foreach(shader ...)` with three batch builds of one `batch.comp`);
  3. the name itself: a unique GLSL stage file with that stem (`kepler` -> `shaders/kepler.comp`).
  Nothing found -> the build is reported unresolved, never guessed.
- USES: the C++ files that include the header, and the functions in them that mention the symbol.

Active only when the project's LANGUAGE has `glsl` (no cost and no change for other projects).
"""

import os
import re
from typing import Dict, List, Optional

_DEFAULT = {"header": "{name}_spv.h", "symbol": "{name}_spv", "cmake": ["CMakeLists.txt"], "builds": {}}
_DEFINE = re.compile(r"(?<![\w$])-D\s*([A-Za-z_]\w*(?:=[^\s)\"]+)?)")
_BRANCH = re.compile(r"\b(?:else)?if\s*\(\s*\"?\$?\{?\w+\}?\"?\s+STREQUAL\s+\"?([\w.-]+)\"?\s*\)", re.I)
_BRANCH_END = re.compile(r"\b(?:elseif|else|endif)\s*\(", re.I)
_SET = re.compile(r"\bset\s*\(\s*\w+\s+([^)]*)\)", re.I)


def _cfg_module(project_root):
    try:
        from graph_from_cards import load_config_at
        return load_config_at(project_root)
    except Exception:
        return None


def enabled(project_root) -> bool:
    mod = _cfg_module(project_root)
    if mod is None:
        return False
    try:
        import stamp_langs
        return "glsl" in stamp_langs.normalize(getattr(mod, "LANGUAGE", "") or "")
    except Exception:
        return False


def host_config(project_root) -> dict:
    mod = _cfg_module(project_root)
    cfg = dict(_DEFAULT)
    cfg.update(getattr(mod, "GLSL_HOST", {}) or {} if mod else {})
    return cfg


def _header_re(cfg):
    pat = re.escape(cfg["header"]).replace(re.escape("{name}"), r"(?P<name>[\w.-]+)")
    return re.compile(r"(?:^|/)" + pat + r"$")


def _cmake_branches(project_root, cfg) -> Dict[str, dict]:
    """{name: {"words": [set() values], "defines": [...]}} from `STREQUAL "name"` branches."""
    out = {}
    for rel in cfg["cmake"]:
        p = os.path.join(project_root, rel)
        try:
            text = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        text = "\n".join(ln.split("#", 1)[0] for ln in text.splitlines())   # CMake comments
        for m in _BRANCH.finditer(text):
            end = _BRANCH_END.search(text, m.end())
            body = text[m.end(): end.start() if end else len(text)]
            words = [w for s in _SET.findall(body) for w in s.split()]
            rec = out.setdefault(m.group(1), {"words": [], "defines": [], "file": rel})
            rec["words"] += words
            rec["defines"] += _DEFINE.findall(" ".join(words))
    return out


class Host:
    """All shader builds of a root and their C++ users. Built once per root per process."""

    def __init__(self, project_root):
        from . import cpp_includes, glsl_tree
        self.root = os.path.abspath(project_root)
        self.cfg = host_config(self.root)
        self.on = enabled(self.root)
        self.builds: Dict[str, dict] = {}     # name -> {source abs|None, defines, how, users: [abs]}
        if not self.on:
            return
        hre = _header_re(self.cfg)
        ctree = cpp_includes.tree_for(self.root)
        gtree = glsl_tree.tree_for(self.root)
        stems = {}
        for p in gtree.files:
            if os.path.splitext(p)[1].lower() in glsl_tree.STAGE_EXTS:
                stems.setdefault(os.path.splitext(os.path.basename(p))[0], []).append(p)
        cm = None
        for f in ctree.files:
            scan = cpp_includes.scan_file(f)
            for inc in (scan.includes if scan else []):
                m = hre.search(inc.spec.replace("\\", "/"))
                if not m:
                    continue
                tgt, _how = ctree.resolve(f, inc)
                if tgt is not None:                     # a real header in the tree — not generated
                    continue
                name = m.group("name")
                b = self.builds.get(name)
                if b is None:
                    if cm is None:
                        cm = _cmake_branches(self.root, self.cfg)
                    b = self.builds[name] = self._resolve(name, cm, stems)
                b["users"].append(f)

    def _resolve(self, name, cm, stems) -> dict:
        conf = (self.cfg.get("builds") or {}).get(name)
        if conf:
            src = conf.get("source")
            src = os.path.abspath(os.path.join(self.root, src)) if src else None
            return {"source": src, "defines": list(conf.get("defines", [])), "how": "config", "users": []}
        br = cm.get(name)
        if br:
            hits = [stems[w][0] for w in br["words"] if len(stems.get(w, [])) == 1]
            if hits:
                return {"source": hits[0], "defines": br["defines"], "how": f"cmake {br['file']}",
                        "users": []}
        if len(stems.get(name, [])) == 1:
            return {"source": stems[name][0], "defines": br["defines"] if br else [], "how": "name",
                    "users": []}
        return {"source": None, "defines": [], "how": "unresolved", "users": []}

    def header(self, name):
        return self.cfg["header"].replace("{name}", name)

    def symbol(self, name):
        return self.cfg["symbol"].replace("{name}", name)

    def build_for_spec(self, spec) -> Optional[str]:
        if not self.on:
            return None
        m = _header_re(self.cfg).search(spec.replace("\\", "/"))
        return m.group("name") if m and m.group("name") in self.builds else None

    def builds_of(self, source_abs) -> List[str]:
        k = os.path.normcase(os.path.abspath(source_abs))
        return [n for n, b in sorted(self.builds.items())
                if b["source"] and os.path.normcase(b["source"]) == k]

    def uses(self, name) -> List[tuple]:
        """[(user abs, [function names that mention the symbol])]."""
        sym = self.symbol(name)
        rx = re.compile(r"\b" + re.escape(sym) + r"\b")
        out = []
        for f in dict.fromkeys(self.builds[name]["users"]):
            fns = []
            try:
                lines = open(f, encoding="utf-8", errors="replace").read().splitlines()
                from get_codeblock.name_resolver import container_at, declarations
                decls = declarations(f)
                for i, ln in enumerate(lines, 1):
                    if rx.search(ln) and not ln.lstrip().startswith("#"):
                        c = container_at(decls, i)
                        fns.append("::".join(list(c.quals) + [c.name]) if c else "(top level)")
            except Exception:
                pass
            out.append((f, list(dict.fromkeys(fns))))
        return out


_HOSTS: Dict[str, Host] = {}


def host_for(project_root) -> Host:
    key = os.path.normcase(os.path.abspath(project_root))
    h = _HOSTS.get(key)
    if h is None:
        h = _HOSTS[key] = Host(project_root)
    return h
