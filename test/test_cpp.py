#!/usr/bin/env python3
"""Регресс C/C++ (Plan08): препроцессорные факты, include-рёбра с условием, объявления, штамп
(Build facts, Kind=conditional(...)), граф --flags, зона --all --path. Самопроверяющие ассерты на
фикстуре test/cppSRC (llama.cpp @ 7fee17846, см. её README) + синтетика во временных папках.

    py test/test_cpp.py            # точки + сводка
    py test/test_cpp.py --fails    # только провалы

Exit 0 = всё ок, 1 = есть провал. Нужен tree-sitter-cpp (без него C++-объявлений нет вовсе).
"""

import os
import sys
import tempfile
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
for p in (_TOOLS, _HERE):
    if p not in sys.path:
        sys.path.insert(0, p)
sys.stdout.reconfigure(encoding="utf-8")

import make_interface_card as mic
import validate_cards as vc
import seam_scanner
import stamp_langs
from find_code_usage import cpp_includes as ci
from find_code_usage.handlers import language_for_file
from graph_from_cards import build_graph, flag_evaluator, split_cells, escape_cell
from get_codeblock.handlers import cpp_treesitter as ct

_PR = os.path.join(_HERE, "cppSRC")
_PASS = 0
_FAIL = 0
_FAILS_ONLY = "--fails" in sys.argv


def check(name, cond):
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        if not _FAILS_ONLY:
            sys.stdout.write(".")
    else:
        _FAIL += 1
        sys.stdout.write(f"\nFAIL: {name}\n")


def _abs(rel):
    return os.path.join(_PR, *rel.split("/"))


# --------------------------------------------------------------------------- preprocessor

def test_conditions_synthetic():
    s = ci.scan_text(
        "#ifndef X_H\n#define X_H\n"            # guard -> dropped
        "#include \"a.h\"\n"                     # 3 unconditional
        "#ifdef A\n#include \"b.h\"\n"          # 5 A
        "#elif defined(B) || C\n#include <c.h>\n"  # 7 !A && (defined(B) || C)
        "#else\n#include \"d.h\"\n#endif\n"     # 9 !A && !(defined(B) || C)
        "#if 0\n#include \"dead.h\"\n#endif\n"  # 12 0
        "#include MACRO_H\n"                     # 14 computed
        "#endif\n")
    inc = {i.spec: i for i in s.includes}
    check("guard recognised", s.guard == "X_H")
    check("guard not a condition", inc["a.h"].cond is None)
    check("#ifdef A", inc["b.h"].cond == "A")
    check("#elif chain", inc["c.h"].cond == "!A && (defined(B) || C)" and not inc["c.h"].quoted)
    check("#else chain", inc["d.h"].cond == "!A && !(defined(B) || C)")
    check("#if 0 tagged, not resolved", inc["dead.h"].cond == "0")
    check("computed include", inc["MACRO_H"].computed)
    check("cond_at inside branch", s.cond_at(5) == "A" and s.cond_at(3) is None)
    s2 = ci.scan_text("#if !defined(FOO)\n#include \"x.h\"\n#endif\n#include \"y.h\"\n")
    check("not a guard when code follows", s2.guard is None and s2.includes[0].cond == "!FOO")
    s3 = ci.scan_text("/* #include \"no.h\" */\n// #include \"no2.h\"\n#include \\\n  \"yes.h\"\n")
    check("comments hide directives, continuation joins", [i.spec for i in s3.includes] == ["yes.h"])


def test_fixture_includes():
    t = ci.tree_for(_PR)
    reg = _abs("ggml/src/ggml-backend-reg.cpp")
    s = ci.scan_file(reg)
    by_line = {i.line: i for i in s.includes}
    check("reg.cpp 33 includes", len(s.includes) == 33)
    check("L34 cuda under GGML_USE_CUDA", by_line[34].spec == "ggml-cuda.h" and by_line[34].cond == "GGML_USE_CUDA")
    check("L21 nested platform cond", by_line[21].cond == "!_WIN32 && __APPLE__")
    how = {i.spec: t.resolve(reg, i)[1] for i in s.includes}
    check("own-dir", how["ggml-backend-impl.h"] == "own-dir")
    check("include-dir", how["ggml-backend.h"] == "include-dir")
    check("not in tree", how["ggml-impl.h"] == "not-in-tree")
    check("external", how["vector"] == "external")
    cu = _abs("ggml/src/ggml-cuda/ggml-cuda.cu")
    cuh = [i for i in ci.scan_file(cu).includes if i.spec.startswith("ggml-cuda/")]
    check("68 ggml-cuda/*.cuh", len(cuh) == 68)
    reach = t.reach(_abs("ggml/include/ggml-vulkan.h"))
    vk = _abs("ggml/src/ggml-vulkan/ggml-vulkan.cpp")
    check("vulkan impl reaches its header only transitively", vk in reach and reach[vk].endswith("ggml-vulkan-types.h"))
    check("includers of ggml-cuda.h", sorted(t.rel(a) for a, _c, _l in t.includers(_abs("ggml/include/ggml-cuda.h")))
          == ["ggml/src/ggml-backend-reg.cpp", "ggml/src/ggml-cuda/ggml-cuda.cu"])


def test_resolution_fallbacks():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "lib" / "sub").mkdir(parents=True)
        (root / "lib" / "sub" / "u.h").write_text("int u(void);\n")
        (root / "a" ).mkdir()
        (root / "b").mkdir()
        (root / "a" / "dup.h").write_text("\n")
        (root / "b" / "dup.h").write_text("\n")
        (root / "m.c").write_text('#include "sub/u.h"\n#include "dup.h"\n')
        t = ci.Tree(str(root))
        incs = ci.scan_file(str(root / "m.c")).includes
        check("unique suffix without config", t.resolve(str(root / "m.c"), incs[0])[1] == "unique-suffix")
        check("ambiguous reported, not guessed", t.resolve(str(root / "m.c"), incs[1]) == (None, "ambiguous"))


def test_second_parse_prep_keeps_lines():
    src = open(_abs("ggml/src/ggml-vulkan/ggml-vulkan.cpp"), encoding="utf-8").read()
    check("first_branch_only keeps lines", ci.first_branch_only(src).count("\n") == src.count("\n"))
    check("blank bodies keeps lines", ci.blank_function_bodies(src).count("\n") == src.count("\n"))
    check("strip keeps #define of the macro", "define GGML_API" in ci.strip_macros(
        "#    define GGML_API extern\nGGML_API void f(void);\n", ["GGML_API"]))
    out = ci.strip_macros("GGML_DEPRECATED(GGML_API void g(int x),\n  \"use h\");\n", ["GGML_API"], ["GGML_DEPRECATED"])
    check("wrapper unwrapped, lines kept", "void g(int x)" in out and out.count("\n") == 2 and "use h" not in out)


# --------------------------------------------------------------------------- declarations

def _decls(rel):
    from stamp_langs import cpp
    return cpp._decls(_PR, _abs(rel))


def test_declarations():
    if not ct.available():
        check("tree-sitter-cpp installed (needed for C++ declarations)", False)
        return
    d, _s = _decls("ggml/include/ggml-cuda.h")
    kinds = [x["kind"] for x in d]
    check("cuda.h 11 functions", kinds.count("function") == 11)
    names = {x["name"]: x for x in d}
    check("macro variants kept", len(names["GGML_CUDA_NAME"].get("variants", [])) == 2)
    check("macro condition", names["GGML_CUDA_NAME"]["cond"] == "GGML_USE_HIP")
    d, _s = _decls("ggml/include/ggml.h")
    check("ggml.h >= 370 functions", sum(x["kind"] == "function" for x in d) >= 370)
    check("GGML_DEPRECATED unwrapped", "ggml_graph_compute_with_ctx" in {x["name"] for x in d}
          or any(x["kind"] == "function" for x in d))
    d, _s = _decls("ggml/include/ggml-backend.h")
    nm = {x["name"] for x in d}
    check("no bogus `extern`", "extern" not in nm)
    check("export macro defs not API", "GGML_BACKEND_API" not in nm)
    an, _s = __import__("stamp_langs.cpp", fromlist=["x"])._analysis(_PR, _abs("ggml/src/ggml-vulkan/ggml-vulkan.cpp"))
    check("vulkan.cpp: second parse leaves no opaque range", an["opaque"] == [])
    check("vulkan.cpp: >= 290 functions", sum(x["kind"] == "function" for x in an["decls"]) >= 290)


def test_entry_key():
    k = stamp_langs.get("cpp").entry_key
    cases = {
        "ggml_backend_t ggml_backend_cuda_init(int device)": "ggml_backend_cuda_init",
        "typedef void (*ggml_log_callback)(enum ggml_log_level level, const char * text)": "ggml_log_callback",
        "typedef struct ggml_backend * ggml_backend_t": "ggml_backend_t",
        "#define GGML_MAX_DIMS 4": "GGML_MAX_DIMS",
        "#define GGML_PAD(x, n) (((x) + (n) - 1) & ~((n) - 1))": "GGML_PAD",
        "struct ggml_tensor {…}": "ggml_tensor",
        "enum ggml_type {…}": "ggml_type",
        "using Alias = int": "Alias",
        "template <typename T> T maxv(T a, T b)": "maxv",
        "extern int ggml_counter": "ggml_counter",
        "void ns::Widget::run()": "run",
    }
    for sig, want in cases.items():
        check(f"entry_key {sig!r}", k(sig) == want)
    check("stamp routes to the lang hook", mic._entry_key("#### `#define GGML_MAX_DIMS 4`", "cpp") == "GGML_MAX_DIMS")


# --------------------------------------------------------------------------- stamp / card

def test_stamp_cards():
    reg = mic.build_card(_PR, "ggml/src/ggml-backend-reg.cpp")
    check("Kind carries #if", "| `ggml-cuda` | `ggml/include/ggml-cuda.h` |  | conditional(GGML_USE_CUDA) |" in reg)
    check("impl: API not duplicated", "## Public API\n\n(none)" in reg)
    check("defines what headers declare", "defines what these headers declare: `ggml/include/ggml-backend.h` 16" in reg)
    check("registry seam tagged with flag", "register_backend(ggml_backend_cuda_reg());` [if GGML_USE_CUDA]" in reg)
    check("not-in-tree + cond on external", '#include "ggml-metal.h"  [not in tree; if GGML_USE_METAL]' in reg)
    cuda_h = mic.build_card(_PR, "ggml/include/ggml-cuda.h")
    check("pair from header", "pair: implemented in `ggml/src/ggml-cuda/ggml-cuda.cu`" in cuda_h)
    check("included by with cond", "- `ggml/src/ggml-backend-reg.cpp` [if GGML_USE_CUDA]" in cuda_h)
    check("__cplusplus idiom filtered", "`__cplusplus`" not in cuda_h)
    check("header: API in source, no signatures copied",
          "API: in source — `get_codeblock --file ggml/include/ggml-cuda.h --outline` (14 declarations)" in cuda_h
          and "#### " not in cuda_h)
    check("header: family table with consumers by folder",
          "| Family | Decls | Lines | Used from (by folder) |" in cuda_h
          and "| (whole file) | 14 | L" in cuda_h and "ggml/src 1" in cuda_h)
    check("header: #if zones still in Build facts", "GGML_USE_HIP" in cuda_h.split("## Build facts", 1)[1])
    vk = mic.build_card(_PR, "ggml/src/ggml-vulkan/ggml-vulkan.cpp")
    check("pair from impl", "pair: implements `ggml/include/ggml-vulkan.h`" in vk)
    check("transitive declare facts", "`ggml/src/ggml-vulkan/ggml-vulkan-common.h` 191" in vk)


def test_merge_and_validate():
    with tempfile.TemporaryDirectory() as d:
        cards = Path(d)
        out = cards / "ggml/include/ggml-cuda.h.md"
        st, _ = mic._stamp_to_file(_PR, "ggml/include/ggml-cuda.h", str(out), force=False)
        check("fresh stamp", st == "new")
        text = out.read_text(encoding="utf-8")
        filled = text.replace("- `(whole file)` — <|Agent:02 what this family is for — one line |>",
                              "- `(whole file)` — CUDA backend entry points.", 1)
        # a family that no longer exists + an old-form H4 entry with prose (pre-1.3.0 card)
        filled = filled.replace("\n## In-Project Dependencies",
                                "- `Gone family` — old family prose.\n\n### Functions\n"
                                "#### `ggml_backend_t ggml_backend_cuda_init(int device)`\n"
                                "Creates the CUDA backend.\n\n## In-Project Dependencies", 1)
        out.write_text(filled, encoding="utf-8")
        st, _ = mic._stamp_to_file(_PR, "ggml/include/ggml-cuda.h", str(out), force=False)
        again = out.read_text(encoding="utf-8")
        check("merge keeps family prose", st == "merged" and "- `(whole file)` — CUDA backend entry points." in again)
        salv = again.split("## Salvage", 1)[1] if "## Salvage" in again else ""
        check("vanished family -> Salvage", "family `Gone family` — old family prose." in salv)
        check("old H4 entry prose -> Salvage", "Creates the CUDA backend." in salv
              and "#### " not in again.split("## Salvage", 1)[0])
        check("merge rebuilds Build facts once", again.count("## Build facts") == 1)
        st, _ = mic._stamp_to_file(_PR, "ggml/include/ggml-cuda.h", str(out), force=False)
        check("family form re-stamp is idempotent", out.read_text(encoding="utf-8") == again)
        issues, _p, _a = vc.validate_card(out, cards, [], Path(_PR))
        check("card validates", issues == [])
        out.write_text(again.replace("--file ggml/include/ggml-cuda.h --outline", "--file ggml/include/nope.h --outline"),
                       encoding="utf-8")
        issues, _p, _a = vc.validate_card(out, cards, [], Path(_PR))
        check("validator: API in source must name an existing file", any("missing source" in i for i in issues))
        out.write_text(again.replace("| Family | Decls |", "| Group | Decls |"), encoding="utf-8")
        issues, _p, _a = vc.validate_card(out, cards, [], Path(_PR))
        check("validator: fixed family table columns", any("family table columns" in i for i in issues))


def test_zone_and_graph():
    with tempfile.TemporaryDirectory() as d:
        cards = Path(d)
        rc = mic._stamp_all(_PR, force=False, cards_dir=str(cards), paths=["ggml/include"])
        made = sorted(p.relative_to(cards).as_posix() for p in cards.rglob("*.md"))
        check("zone stamps only its subtree", rc == 0 and made == [
            "ggml/include/ggml-backend.h.md", "ggml/include/ggml-cuda.h.md",
            "ggml/include/ggml-vulkan.h.md", "ggml/include/ggml.h.md"])
        check("links from outside the zone still seen",
              "`ggml/src/ggml-backend-reg.cpp` [if GGML_USE_CUDA]" in (cards / "ggml/include/ggml-cuda.h.md").read_text(encoding="utf-8"))
        mic._stamp_all(_PR, force=False, cards_dir=str(cards), paths=["ggml/src/ggml-backend-reg.cpp"])
        g = build_graph(cards)
        n = g["nodes"]["ggml/src/ggml-backend-reg.cpp"]
        check("graph keeps cond", n["dep_conds"].get("ggml/include/ggml-vulkan.h") == "GGML_USE_VULKAN")
        g2 = build_graph(cards, ["GGML_USE_CUDA"])
        deps = g2["nodes"]["ggml/src/ggml-backend-reg.cpp"]["deps"]
        check("--flags drops the off family edge", "ggml/include/ggml-vulkan.h" not in deps
              and "ggml/include/ggml-cuda.h" in deps)
        check("pair parsed", g["nodes"]["ggml/include/ggml-cuda.h"]["pair"] == [] )   # impl card not in this map


def test_graph_source_nodes():
    from graph_from_cards import add_source_nodes, file_zone, format_file_zone, fold_by_folder
    with tempfile.TemporaryDirectory() as d:
        cards = Path(d)
        mic._stamp_all(_PR, force=False, cards_dir=str(cards), paths=["ggml/include"])
        g = build_graph(cards)
        n_cards = len(g["nodes"])
        rdeps_cards = [i for i, n in g["nodes"].items() if "ggml/include/ggml-cuda.h" in n["deps"]]
        added = add_source_nodes(g, Path(_PR))
        nodes = g["nodes"]
        check("source nodes: files without cards join, marked", added > 0
              and len(nodes) == n_cards + added and nodes["ggml/src/ggml-backend-reg.cpp"]["card"] is False
              and nodes["ggml/include/ggml-cuda.h"].get("card", True) is True)
        z = file_zone(g, "ggml/include/ggml-cuda.h", 1)
        check("source nodes: used-by sees files outside the zone", rdeps_cards == []
              and {"ggml/src/ggml-backend-reg.cpp", "ggml/src/ggml-cuda/ggml-cuda.cu"} <= z["up"])
        check("source nodes: edge condition from the scan",
              nodes["ggml/src/ggml-backend-reg.cpp"]["dep_conds"].get("ggml/include/ggml-cuda.h") == "GGML_USE_CUDA")
        txt = format_file_zone(g, z, 0)
        check("source nodes: rendered with (no card)", "ggml/src/ggml-backend-reg.cpp (no card) [if GGML_USE_CUDA]" in txt)
        g2 = build_graph(cards)
        add_source_nodes(g2, Path(_PR), ["GGML_USE_VULKAN"])
        check("source nodes: --flags apply to scanned edges",
              "ggml/include/ggml-cuda.h" not in g2["nodes"]["ggml/src/ggml-backend-reg.cpp"]["deps"])
        check("fold_by_folder: adaptive", fold_by_folder(["a/b/x.c", "a/b/y.c", "c/z.c"]) == "a/b 2, c 1")


def test_evaluator_and_cells():
    ev = flag_evaluator(["GGML_USE_CUDA", "GGML_USE_VULKAN", "!NDEBUG"])
    check("on", ev.run("GGML_USE_CUDA") is True)
    check("family off", ev.run("GGML_USE_METAL") is False)
    check("explicit off", ev.run("NDEBUG") is False)
    check("unknown stays unknown", ev.run("_WIN32") is None)
    check("kleene or", ev.run("defined(GGML_USE_CUDA) || defined(_WIN32)") is True)
    check("kleene and", ev.run("_WIN32 && GGML_USE_METAL") is False)
    check("comparison unknown", ev.run("VK_HEADER_VERSION >= 287") is None)
    check("has_include unknown", ev.run("__has_include(<spirv.hpp>)") is None)
    check("escaped pipe roundtrip", split_cells("| a | " + escape_cell("A || B") + " |") == [" a ", " A || B "])


def test_consumers_folding():
    few = {"f": [(f"a/x{i}.cpp", "include", [1]) for i in range(mic.CONSUMERS_LIST_MAX)]}
    check("<= max: listed file by file", mic._consumers_fact("f", few)[0] == f"consumers {mic.CONSUMERS_LIST_MAX}:"
          and len(mic._consumers_fact("f", few)) == mic.CONSUMERS_LIST_MAX + 1)
    many = {"g": [(f"src/models/m{i}.cpp", "include", [1]) for i in range(12)]
                 + [("ggml/src/ggml-cuda/k.cu", "include", [1]), ("tools/server/s.cpp", "include", [1])]}
    out = mic._consumers_fact("g", many, "ggml/include/ggml.h")
    check("> max: one folded line", len(out) == 1)
    check("folded: most-used folder first", out[0].startswith("consumers 14 (by folder): src/models 12, "))
    check("folded: points to the full list", out[0].endswith("find_code_usage --file ggml/include/ggml.h --symbol g"))
    op = mic._parse_old_prose("# x.h\n\ns.\n\n## Public API\n\n#### `void g(void)`\n" + out[0] + "\nMy prose.\n")
    check("folded line is fact, not prose", op["entries"]["g"]["desc"] == ["My prose."])


def test_flags_skip_numbers():
    from stamp_langs import cpp
    got = cpp._flags(["UINTPTR_MAX == 0xFFFFFFFF", "__cplusplus >= 201703L", "defined(GGML_USE_CUDA) && X > 1u"])
    check("numeric literals are not flags", got == ["GGML_USE_CUDA", "UINTPTR_MAX", "X", "__cplusplus"])


def test_scan_cache():
    from find_code_usage.scan_cache import ScanCache
    with tempfile.TemporaryDirectory() as d:
        os.environ["TOOLS_CACHE_DIR"] = os.path.join(d, "cache")
        root = Path(d) / "proj"
        root.mkdir()
        (root / "a.h").write_text("#pragma once\n", encoding="utf-8")
        (root / "b.h").write_text('#include "a.h"\n', encoding="utf-8")
        (root / "c.cpp").write_text('#include "b.h"\n#include <vector>\n', encoding="utf-8")
        t = ci.Tree(str(root))
        t.forward()
        check("cache: cold run scans all", t.cache_stats == (0, 3))
        t = ci.Tree(str(root))
        f1 = t.forward()
        check("cache: warm run scans nothing", t.cache_stats == (3, 0))
        check("cache: same edges from cache",
              [(os.path.basename(x), c, l) for x, c, l in f1[str(root / "c.cpp")]] == [("b.h", None, 1)])
        (root / "c.cpp").write_text('#include "a.h"\n', encoding="utf-8")
        t = ci.Tree(str(root))
        f2 = t.forward()
        check("cache: changed file rescanned alone", t.cache_stats == (2, 1)
              and [os.path.basename(x) for x, _c, _l in f2[str(root / "c.cpp")]] == ["a.h"])
        (root / "b.h").unlink()
        (root / "d.h").write_text("#pragma once\n", encoding="utf-8")
        t = ci.Tree(str(root))
        t.forward()
        c = ScanCache(str(root), "cpp_scan", ci_version())
        check("cache: deleted dropped, new scanned", t.cache_stats == (2, 1)
              and sorted(c.entries) == ["a.h", "c.cpp", "d.h"])
        c2 = ScanCache(str(root), "cpp_scan", "other-version")
        check("cache: other producer version -> empty", c2.entries == {})
        os.environ["TOOLS_NO_CACHE"] = "1"
        t = ci.Tree(str(root))
        t.forward()
        check("cache: TOOLS_NO_CACHE scans all", t.cache_stats == (0, 0))
        del os.environ["TOOLS_NO_CACHE"]
        # git root (the fixture is tracked by the tools repo): blob ids as fingerprints
        t = ci.Tree(_PR)
        t.forward()
        t = ci.Tree(_PR)
        t.forward()
        check("cache: git fingerprints -> warm run all hits", t.cache_stats == (len(t.files), 0))
        del os.environ["TOOLS_CACHE_DIR"]


def ci_version():
    from find_code_usage.scan_cache import source_version
    return source_version(ci.__file__)


def test_restamp_idempotent():
    # External Dependencies: `#include <...>` is FACT (hook import_line), not prose — a re-stamp
    # of an untouched card must not change a byte (the list used to duplicate on every merge).
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "ggml/src/ggml-backend-dl.h.md"
        mic._stamp_to_file(_PR, "ggml/src/ggml-backend-dl.h", str(out), force=False)
        first = out.read_text(encoding="utf-8")
        mic._stamp_to_file(_PR, "ggml/src/ggml-backend-dl.h", str(out), force=False)
        second = out.read_text(encoding="utf-8")
        check("fresh card has external includes", "#include <" in first)
        check("re-stamp is idempotent", first == second)
        check("import_line hook per language",
              stamp_langs.get("cpp").import_line("#include <x>")
              and stamp_langs.get("csharp").import_line("using System;")
              and stamp_langs.get("python").import_line("import os")
              and not stamp_langs.get("cpp").import_line("uses dlopen on Linux"))


def test_families():
    from stamp_langs import cpp
    text = "\n".join([
        "int a;", "", "//", "// Buffers", "//", "", "int b;",
        "    // doc block", "    //", "    // TODO", "    //", "    // more doc",   # paragraph, not a heading
        "", "//", "// Sampling API", "//", "// Sample usage:", "int c;",          # heading + doc after
        "", "//", "// this is a sentence.", "//",                                  # sentence -> not a heading
    ])
    check("sections: frames only, doc paragraphs and sentences skipped",
          cpp.sections(text) == [(4, "Buffers"), (15, "Sampling API")])
    root = _PR
    fb = cpp.families(root, os.path.join(root, "ggml/include/ggml-backend.h"))
    names = [f["name"] for f in fb]
    check("families: author sections of ggml-backend.h", names[:4] == [
        "(top of file)", "Backend buffer type", "Backend buffer", "Backend (stream)"]
        and "Backend scheduler" in names and all(f["how"] == "section" for f in fb))
    sched = next(f for f in fb if f["name"] == "Backend scheduler")
    check("families: line range starts at the section frame", sched["first"] == 263
          and "ggml_backend_sched_new" in sched["decls"])
    exports = cpp.declared(root, os.path.join(root, "ggml/include/ggml.h"))["exports"]
    fg = cpp.families(root, os.path.join(root, "ggml/include/ggml.h"), exports)
    flat = [d for f in fg for d in f["decls"]]
    check("families: every declaration in exactly one family",
          sorted(flat) == sorted(e["name"] for e in exports) and len(flat) == len(set(flat)))
    check("families: big sections split by name prefix (ggml.h)",
          any(f["name"].endswith("/ ggml_rope_*") and f["how"] == "prefix" for f in fg)
          and all(len(f["decls"]) <= cpp.FAMILY_BIG or f["name"].split(" / ")[-1].startswith("other ")
                  for f in fg if f["how"] == "prefix"))
    check("families: stable between runs",
          fg == cpp.families(root, os.path.join(root, "ggml/include/ggml.h"), exports))
    fc = cpp.families(root, os.path.join(root, "ggml/include/ggml-cuda.h"))
    check("families: small file without sections = one family",
          [(f["name"], f["how"]) for f in fc] == [("(whole file)", "file")])


def test_misc_registry():
    check("find_code_usage: .cu -> cpp", language_for_file("x/k.cu") == "cpp")
    check("find_code_usage: .py still python", language_for_file("a.py") == "python")
    rx = dict(seam_scanner.PATTERNS["cpp"])["vtable: fn-table entry"]
    check("vtable hit", bool(rx.search("/* .get_name = */ ggml_backend_vk_name,")))
    check("vtable skips nullptr", not rx.search("/* .context  = */ nullptr,"))


def main():
    test_conditions_synthetic()
    test_fixture_includes()
    test_resolution_fallbacks()
    test_second_parse_prep_keeps_lines()
    test_declarations()
    test_entry_key()
    test_stamp_cards()
    test_merge_and_validate()
    test_zone_and_graph()
    test_graph_source_nodes()
    test_evaluator_and_cells()
    test_consumers_folding()
    test_flags_skip_numbers()
    test_scan_cache()
    test_restamp_idempotent()
    test_families()
    test_misc_registry()
    sys.stdout.write(f"\n{'-' * 50}\n{_PASS} passed, {_FAIL} failed\n")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
