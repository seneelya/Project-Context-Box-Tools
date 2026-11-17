#!/usr/bin/env python3
"""Регресс штампа GLSL (REQ-021): объявления и интерфейс шейдера, include-дерево и единицы
компиляции, места вызова с условиями `#if` и спец-констант, копии от `main`, мерж прозы.
Только синтетика (дерево шейдеров пишется во временную папку) — настоящие шейдеры проекта
приватны и в коммитящиеся тесты не попадают.

    py test/test_glsl_stamp.py            # точки + сводка
    py test/test_glsl_stamp.py --fails    # только провалы

Exit 0 = всё ок, 1 = есть провал. Нужна грамматика GLSL (колесо `wheels/`, см. CONTEXT_RESTORE).
"""

import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
for p in (_TOOLS, _HERE):
    if p not in sys.path:
        sys.path.insert(0, p)
sys.stdout.reconfigure(encoding="utf-8")

import make_interface_card as mic
import stamp_langs
from find_code_usage import glsl_tree as gt
from find_code_usage.handlers import language_for_file

_PASS = 0
_FAIL = 0
_FAILS_ONLY = "--fails" in sys.argv

TREE = {
    "shaders/main.comp": """#version 450
#extension GL_GOOGLE_include_directive : require
layout(local_size_x = 32) in;
layout(constant_id = 0) const bool kFast = true;
layout(push_constant) uniform Push {
    uint n;        // count
    float scale;
    dvec3 origin;
} pc;
layout(std430, binding = 0) readonly buffer In { float v[]; } src;
layout(std430, binding = 1) writeonly buffer Out { float v[]; } dst;
shared float tile[32];
#include "common.glsl"
#include "heavy.glsl"

void main() {
    float x = src.v[gl_GlobalInvocationID.x];
#if MODE == 1
    x = heavy(x);
#endif
    if (kFast) {
        x = light(x);
    } else {
        x = use_heavy(x);
    }
    dst.v[0] = light(x); // light(x) in a comment does not count
}
""",
    "shaders/common.glsl": """// shared helpers
const uint K_A = 1;
const uint K_B = 2;
const uint K_C = 3;
struct Pair {
    float a;
    float b;
};
float heavy(float x);
float light_impl(float x) { return x + src.v[0]; }
float light(float x) { return light_impl(x) + light_impl(x * 2.0); }
float use_heavy(float x) { return heavy(x); }
""",
    "shaders/heavy.glsl": """#include "inner.glsl"
float heavy(float x) {
    return core(x) * core(x + 1.0);
}
""",
    "shaders/inner.glsl": """float core(float x) { return x * x; }
""",
    "shaders/orphan.glsl": """float lonely() { return 1.0; }
""",
}


def check(name, cond):
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        if not _FAILS_ONLY:
            sys.stdout.write(".")
    else:
        _FAIL += 1
        sys.stdout.write(f"\nFAIL: {name}\n")


def _write(root):
    for rel, text in TREE.items():
        p = os.path.join(root, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)


def _card(root, rel):
    return mic.build_card(root, rel)


def _facts(card):
    body = card.split("## Shader facts", 1)[1].split("\n## ", 1)[0] if "## Shader facts" in card else ""
    return body


def test_registry():
    check("stamp lang for .comp", stamp_langs.for_file("a/b.comp").NAME == "glsl")
    check("stamp lang for .glsl", stamp_langs.for_file("x.glsl").NAME == "glsl")
    check("alias shader", stamp_langs.get("shader").NAME == "glsl")
    check("find_code_usage handler for .frag", language_for_file("x.frag") == "glsl")
    check("normalize list with glsl", stamp_langs.normalize(["cpp", "glsl"]) == ["cpp", "glsl"])


def test_entry_key():
    ek = stamp_langs.get("glsl").entry_key
    check("block -> block name", ek("layout(std430, binding = 0) readonly buffer In {…} src") == "In")
    check("push -> block name", ek("layout(push_constant) uniform Push {…} pc") == "Push")
    check("function", ek("float light(float x)") == "light")
    check("spec const", ek("layout(constant_id = 0) const bool kFast = true") == "kFast")
    check("shared array", ek("shared float tile[32]") == "tile")
    check("struct", ek("struct Pair") == "Pair")


def test_std430():
    f = lambda *sigs: [{"name": s.split()[-1], "signature": s} for s in sigs]
    check("scalars", gt.std430_size(f("uint a", "float b")) == 8)
    check("dvec3 aligns to 32", gt.std430_size(f("uint n", "float scale", "dvec3 origin")) == 64)
    check("vec3 + float pack", gt.std430_size(f("vec3 a", "float b")) == 16)
    check("fixed array", gt.std430_size(f("float a[4]")) == 16)
    check("runtime array -> None", gt.std430_size(f("float v[]")) is None)
    check("unknown type -> None", gt.std430_size(f("Pair p")) is None)
    check("mat4", gt.std430_size(f("mat4 m")) == 64)


def test_cards(root):
    main = _card(root, "shaders/main.comp")
    fm = _facts(main)
    check("main: entry + local size", "entry point: compute shader, `local_size_x = 32`" in fm)
    check("main: push size", "push_constant `Push` (pc): 3 fields, 64 bytes" in fm)
    check("main: block entry with binding", "#### `layout(std430, binding = 0) readonly buffer In {…} src`" in main)
    check("main: push fields listed", "    - `uint n`" in main and "    - `dvec3 origin`" in main)
    check("main: spec const entry", "#### `layout(constant_id = 0) const bool kFast = true`" in main)
    check("main: shared entry", "#### `shared float tile[32]`" in main)
    check("main: MODE zone", "- `MODE == 1` (1 zone): in `main`" in fm)
    check("main: heavy call tagged #if", "`heavy` ← `shaders/heavy.glsl` ×1 — `main` [if MODE == 1]" in fm)
    check("main: light ×2, one under spec",
          "`light` ← `shaders/common.glsl` ×2 — `main` [spec kFast], `main`" in fm)
    check("main: else branch is !spec", "`use_heavy` ← `shaders/common.glsl` ×1 — `main` [spec !kFast]" in fm)
    check("main: In-Project deps", "| `common` | `shaders/common.glsl` |" in main)

    common = _card(root, "shaders/common.glsl")
    fc = _facts(common)
    check("common: compiled in main", "compiled in: `shaders/main.comp`" in fc)
    check("common: const groups", "global constants (3): `K_*` 3" in fc)
    check("common: struct entry + fields", "#### `struct Pair`" in common and "    - `float a`" in common)
    check("common: light sites (comment ignored)",
          "- `light` ×2 — `shaders/main.comp`: `main` [spec kFast], `main`" in fc)
    check("common: light_impl copies", "- `light_impl` ×2, 4 copies from `main` — here: `light` ×2" in fc)
    check("common: forward decl", "forward declarations: `heavy` (defined `shaders/heavy.glsl`)" in fc)
    check("common: reached through", "`core` ← `shaders/inner.glsl` (via `heavy`)" in fc)
    check("common: block consumer by instance name",
          "consumers 1:\n- shaders/common.glsl" in main.split("buffer In", 1)[1][:200])

    inner = _card(root, "shaders/inner.glsl")
    fi = _facts(inner)
    check("inner: included by heavy", "included by: `shaders/heavy.glsl`" in fi)
    check("inner: compiled in main (transitively)", "compiled in: `shaders/main.comp`" in fi)
    check("inner: core ×2, copies through heavy ×2", "- `core` ×2, 4 copies from `main`" in fi)

    heavy = _card(root, "shaders/heavy.glsl")
    check("heavy: consumers main + common",
          "consumers 2:\n- shaders/common.glsl\n- shaders/main.comp" in heavy)
    orphan = _card(root, "shaders/orphan.glsl")
    check("orphan: nobody includes it", "no shader includes it" in _facts(orphan))
    check("orphan: not called", "not called in this unit: `lonely`" in _facts(orphan))


def test_many_units():
    """A library part in 3+ units: one row per function across the units; identical per-unit
    blocks merge; a global const used by others is NOT a Consumed-internals entry."""
    lib = "const uint K_ONE = 1;\nfloat sq(float x) { return x * x; }\nfloat quad(float x) { return sq(sq(x)); }\n"
    ent = '#include "lib.glsl"\nvoid main() { float y = quad(%s) + float(K_ONE); }\n'
    files = {"s/lib.glsl": lib, "s/a.comp": ent % "1.0", "s/b.comp": ent % "2.0",
             "s/c.comp": '#include "lib.glsl"\nvoid main() { float y = sq(3.0); }\n'}
    with tempfile.TemporaryDirectory() as root:
        for rel, text in files.items():
            p = os.path.join(root, *rel.split("/"))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
        card = _card(root, "s/lib.glsl")
        f = _facts(card)
        check("units: compact header", "call sites per unit (×sites/copies from `main`" in f)
        # c.comp: quad is not called there, yet its 2 sites of sq are compiled -> 3 sites, 1 copy
        check("units: sq row", "- `sq` — `a.comp` ×2/2, `b.comp` ×2/2, `c.comp` ×3/1" in f)
        check("units: quad row (0 in c)", "- `quad` — `a.comp` ×1/1, `b.comp` ×1/1, `c.comp` ×0" in f)
        check("units: no per-unit detail", "in unit `" not in f)
        check("const not a consumed internal", "Consumed internals" not in card and "K_ONE" in f)


def test_merge(root):
    """Prose survives a re-stamp; a second re-stamp is byte-stable."""
    import re
    rel = "shaders/inner.glsl"
    fresh = _card(root, rel)
    filled = re.sub(r"<\|fill\d+\|>", "Squares a value.", fresh, count=1)
    op = mic._parse_old_prose(filled, "glsl")
    again = mic.build_card(root, rel, old_prose=op)
    check("merge keeps summary", "\n# inner.glsl\n\nSquares a value.\n" in again)
    op2 = mic._parse_old_prose(again, "glsl")
    check("re-stamp byte-stable", mic.build_card(root, rel, old_prose=op2) == again)


def main():
    if not gt.available():
        sys.stdout.write("SKIP: GLSL grammar missing (install the wheel from wheels/)\n")
        return 0
    test_registry()
    test_entry_key()
    test_std430()
    with tempfile.TemporaryDirectory() as root:
        _write(root)
        test_cards(root)
        test_merge(root)
    test_many_units()
    sys.stdout.write(f"\n{'-' * 50}\n{_PASS} passed, {_FAIL} failed\n")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
