#!/usr/bin/env python3
"""Plan14: `Why for importers:` in a module's own card -> `(auto)` Why line in every importer's card,
kept on re-stamp, checked by validate_cards, followed by check_cards_freshness. Synthetic tree."""

import os
import sys
import tempfile
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)
sys.stdout.reconfigure(encoding="utf-8")

import CARD_FORMAT as cf
import check_cards_freshness as ccf
import graph_from_cards as gfc
import make_interface_card as mic
import validate_cards as vc

TREE = {
    "src/vec3.h": "#pragma once\nstruct Vec3 { double x, y, z; };\n",
    "src/y.h": "#pragma once\nint g();\n",
    "src/x.h": '#pragma once\n#include "vec3.h"\nVec3 f(Vec3 v);\n',
    "src/x.cpp": '#include "x.h"\n#include "vec3.h"\n#include "y.h"\nVec3 f(Vec3 v) { g(); return v; }\n',
    "src/z.cpp": '#include "vec3.h"\n#include "y.h"\nint z() { Vec3 v{}; return g() + (int)v.x; }\n',
}
FIELD = "Why for importers: 3D vector type used for every position."
FIELD2 = "Why for importers: 3D vector and its arithmetic."
FAILS = []
N = 0


def check(name, ok, detail=""):
    global N
    N += 1
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f"\n     {detail}"))
    if not ok:
        FAILS.append(name)


def _why(card):
    return [ln for ln in card.split("### Why", 1)[1].split("\n## ", 1)[0].splitlines() if ln.startswith("- ")]


def _auto(field_line):
    return f"{cf.AUTO_MARK} {cf.for_importers_text(field_line)}"


def main():
    with tempfile.TemporaryDirectory() as root:
        for rel, text in TREE.items():
            p = os.path.join(root, *rel.split("/"))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
        cards = os.path.join(root, "__map")
        cpath = lambda rel: mic._card_path(cards, rel)
        read = lambda rel: open(cpath(rel), encoding="utf-8").read()

        def stamp(rel):
            return mic._stamp_to_file(root, rel, cpath(rel), False)[0]

        def write(rel, text):
            with open(cpath(rel), "w", encoding="utf-8") as fh:
                fh.write(text)

        for rel in TREE:
            stamp(rel)

        # the module's own card: summary + field (a person/agent writes them)
        base = read("src/vec3.h")
        summary_dir = next(ln for ln in base.splitlines() if cf.is_agent_directive(ln.strip()))
        write("src/vec3.h", base.replace(summary_dir, "Vec3 value type.\n" + FIELD, 1))
        stamp("src/vec3.h")              # renumbers the directives (summary filled)
        before = read("src/vec3.h")
        check("field right under the summary", "Vec3 value type.\n" + FIELD + "\n" in before)
        stamp("src/vec3.h")
        check("field kept on re-stamp, byte for byte", read("src/vec3.h") == before)
        y_before = read("src/y.h")
        stamp("src/y.h")
        check("card without the field unchanged", read("src/y.h") == y_before)

        p = mic._parse_old_prose(base.replace(summary_dir, summary_dir + "\n" + FIELD, 1), "cpp")
        check("field is never the summary", p["summary"] is None and p["for_importers"] == FIELD, p)
        gpath = Path(cpath("src/vec3.h"))
        check("graph summary skips the field", gfc.parse_card(gpath, Path(cards))["summary"] == "Vec3 value type.")

        # importers
        stamp("src/z.cpp")
        why = _why(read("src/z.cpp"))
        check("importer gets (auto) field", f"- `vec3` — {_auto(FIELD)}" in why, why)
        check("dep without field -> directive", any(ln.startswith("- `y` — <|fill") for ln in why), why)

        write("src/x.h", read("src/x.h").replace(next(ln for ln in read("src/x.h").splitlines()
                                                      if cf.is_agent_directive(ln.strip())),
                                                 "Declares f.\nWhy for importers: declares f.", 1))
        stamp("src/x.cpp")
        why = _why(read("src/x.cpp"))
        check("own header wins over its field", f"- `x` — {cf.OWN_PAIR_WHY}" in why, why)
        check("x.cpp gets vec3 (auto)", f"- `vec3` — {_auto(FIELD)}" in why, why)

        # freshness: in step
        fields = {}
        check("freshness: in step", ccf._auto_why_stale(Path(cpath("src/z.cpp")), Path(cards), fields) is None)

        # an agent rewrites x.cpp's vec3 line (mark dropped) — then the field changes
        agent = "- `vec3` — f takes and returns positions."
        write("src/x.cpp", read("src/x.cpp").replace(f"- `vec3` — {_auto(FIELD)}", agent))
        write("src/vec3.h", read("src/vec3.h").replace(FIELD, FIELD2))
        stale = ccf._auto_why_stale(Path(cpath("src/z.cpp")), Path(cards), {})
        check("freshness: changed field flagged", stale and "changed" in stale, stale)
        check("freshness: agent line not judged",
              ccf._auto_why_stale(Path(cpath("src/x.cpp")), Path(cards), {}) is None)
        stamp("src/z.cpp")
        stamp("src/x.cpp")
        check("(auto) line follows the field", f"- `vec3` — {_auto(FIELD2)}" in _why(read("src/z.cpp")))
        check("agent line stays", agent in _why(read("src/x.cpp")), _why(read("src/x.cpp")))
        check("freshness: re-stamped is in step",
              ccf._auto_why_stale(Path(cpath("src/z.cpp")), Path(cards), {}) is None)

        # field written to y.h after its importer was stamped: the directive is stale
        write("src/y.h", read("src/y.h").replace(next(ln for ln in read("src/y.h").splitlines()
                                                      if cf.is_agent_directive(ln.strip())),
                                                 "Declares g.\nWhy for importers: the g counter.", 1))
        stale = ccf._auto_why_stale(Path(cpath("src/z.cpp")), Path(cards), {})
        check("freshness: directive under a field flagged", stale and "directive" in stale, stale)
        # field removed: the (auto) line is stale, re-stamp gives the directive back
        write("src/vec3.h", read("src/vec3.h").replace(FIELD2 + "\n", ""))
        stamp("src/z.cpp")
        why = _why(read("src/z.cpp"))
        check("field removed -> directive back", any(ln.startswith("- `vec3` — <|fill") for ln in why), why)

        # validate
        def issues(rel):
            return vc.validate_card(Path(cpath(rel)), Path(cards), {}, Path(root))[0]
        ok = issues("src/y.h")
        check("validate accepts the field", not any("Why for importers" in i or "summary" in i for i in ok), ok)
        write("src/y.h", read("src/y.h").replace("Why for importers: the g counter.",
                                                 "Why for importers:\nWhy for importers: twice."))
        bad = issues("src/y.h")
        check("validate flags empty and duplicate",
              any("twice" in i for i in bad) and any("without a value" in i for i in bad), bad)

    print(f"{N - len(FAILS)}/{N} passed")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
