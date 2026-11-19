#!/usr/bin/env python3
"""The Why line of a C/C++ file's own header (`x.cpp` -> `x.h`) is stamped ready, not asked
(REQ-018 p.3: 236 of 2138 Why lines on a real project were "its own header"). Synthetic tree."""

import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)
sys.stdout.reconfigure(encoding="utf-8")

import make_interface_card as mic

TREE = {
    "src/x.h": "#pragma once\nint f(int x);\n",
    "src/y.h": "#pragma once\nint g();\n",
    "src/x.cpp": '#include "x.h"\n#include "y.h"\nint f(int x) { return x + g(); }\n',
    "src/z.cpp": '#include "y.h"\nint z() { return g(); }\n',
}
READY = f"- `x` — {mic.OWN_PAIR_WHY}"
assert mic.OWN_PAIR_WHY.startswith("(auto) ")
FAILS = []


def check(name, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f"\n     {detail}"))
    if not ok:
        FAILS.append(name)


def _why(card):
    return [ln for ln in card.split("### Why", 1)[1].split("\n## ", 1)[0].splitlines() if ln.startswith("- ")]


def main():
    with tempfile.TemporaryDirectory() as root:
        for rel, text in TREE.items():
            p = os.path.join(root, *rel.split("/"))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)

        card = mic.build_card(root, "src/x.cpp")
        why = _why(card)
        check("own header ready", READY in why, why)
        check("other import still asked", any(ln.startswith("- `y` — <|fill") for ln in why), why)

        again = mic.build_card(root, "src/x.cpp", old_prose=mic._parse_old_prose(card, "cpp"))
        check("re-stamp byte-stable", again == card)

        edited = card.replace(READY, "- `x` — declares f; also the shared tolerance.")
        kept = mic.build_card(root, "src/x.cpp", old_prose=mic._parse_old_prose(edited, "cpp"))
        check("agent's own text kept", "- `x` — declares f; also the shared tolerance." in _why(kept), _why(kept))

        stale = card.replace(READY, "- `x` — (auto) an older wording of the stamp.")
        fresh = mic.build_card(root, "src/x.cpp", old_prose=mic._parse_old_prose(stale, "cpp"))
        check("(auto) line rewritten", READY in _why(fresh) and "older wording" not in fresh, _why(fresh))

        old_form = card.replace(READY, "- `x` — <|fill9|>")
        upgraded = mic.build_card(root, "src/x.cpp", old_prose=mic._parse_old_prose(old_form, "cpp"))
        check("old directive -> ready line", READY in _why(upgraded), _why(upgraded))

        other = _why(mic.build_card(root, "src/z.cpp"))
        check("not own header -> asked", other and all("<|fill" in ln for ln in other), other)
        header = mic.build_card(root, "src/x.h")
        check("header has no ready line", mic.OWN_PAIR_WHY not in header)

    print(f"{8 - len(FAILS)}/8 passed")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
