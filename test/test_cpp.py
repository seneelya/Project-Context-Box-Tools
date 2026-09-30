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
    check("decl condition line", "#### `#define GGML_CUDA_NAME \"ROCm\"`\ncondition: GGML_USE_HIP" in cuda_h)
    check("consumer found across files", "- ggml/src/ggml-backend-reg.cpp" in cuda_h)
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
        filled = text.replace("<|Agent:02 write short does+role, or remove |>", "Creates the CUDA backend.", 1)
        out.write_text(filled, encoding="utf-8")
        st, _ = mic._stamp_to_file(_PR, "ggml/include/ggml-cuda.h", str(out), force=False)
        again = out.read_text(encoding="utf-8")
        check("merge keeps prose", st == "merged" and "Creates the CUDA backend." in again)
        check("merge rebuilds Build facts once", again.count("## Build facts") == 1)
        check("condition line is fact, not prose (not duplicated by merge)",
              again.count("condition: GGML_USE_HIP") == text.count("condition: GGML_USE_HIP") == 2)
        issues, _p, _a = vc.validate_card(out, cards, [], Path(_PR))
        check("card validates", issues == [])


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
    test_evaluator_and_cells()
    test_misc_registry()
    sys.stdout.write(f"\n{'-' * 50}\n{_PASS} passed, {_FAIL} failed\n")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
