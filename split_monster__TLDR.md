# split_monster

v0. Moves named top-level blocks between files WITHOUT you retyping their content twice. You
decide the grouping (`line -> target_file`); it expands that into a throwaway, hand-editable
Python script; you review/tweak it (cheaply — append short override lines, never rewrite
existing ones) and run it. See `__dev/vision/Vision06__monster-file-split.md` /
`__dev/plans/Plan04__split_monster.md` for the full rationale — this is just the quick reference.

**Target:** `split_monster.py --file <monster.js> --split <LINE> <target.py> [--split ... ...] --out-script <out.py>`
— `LINE` is a block's start line (get it from `get_codeblock --outline` first), or several lines
for the **same** target in one flag: `--split 12,34,45 "part.md"`. Repeat `--split` for other
target files; order in the flags doesn't matter (the generator restores source order on its own).

**Markdown:** same CLI; use heading lines from `get_codeblock --file FILE --outline --level 4`
(or higher). Each `--split` cuts the **heading section** that contains that line (H1..H6), not
the whole document. Prefer the heading row itself, not a body line (body-only lines can resolve
to a `~content` slice without the `##` title).

## Quick use

```
get_codeblock.py --file monster.js --outline                        # find block start lines first
split_monster.py --file monster.js --split 123 "a.js" --split 456 "b.js" --out-script move.py
python move.py            # dry-run — prints the plan, writes nothing
python move.py --apply     # actually cuts monster.js and writes a.js/b.js
```

Markdown example:

```
get_codeblock.py --file big.md --outline --level 4
split_monster.py --file big.md --split 120 "part-a.md" --split 340 "part-b.md" --out-script move.py
python move.py --apply
```

## What's in the generated script

* the same **API header** in every `move.py` (full palette: `cut` / `replace` / `monster.*`, plus
  that `replacement` strings may contain `\n` — you can leave a stub instead of deleting);
  body uses **`cut` + `monster.cut` for code**, **`replace` + `STUB_XX` + `monster.replace` for `.md`**
* one `cut(file, line)` or `replace(file, line, STUB_XX)` call per block + a `#N` tag (a stable id for `Edit`-anchoring, not a live
  line number) — the descriptive comment (block's own signature/preview) lives on its OWN line
  ABOVE the code, never mixed into it;
* a cheap **best-effort grep hint** per block ("who else in the file mentions this name",
  "which other top-level names does this block's body use") — NOT a real reference graph, just a
  textual scan. Verify it yourself; it will have false positives/negatives;
* `monster.write(target, blocks, imports)` / `monster.cut(source, blocks)` at the bottom — these
  do the actual byte-for-byte move, gated behind `--apply` on the SCRIPT's own invocation.
* for **ESM** sources (`.js` `.mjs` `.ts` `.tsx` `.jsx`): leading `import … from` lines from
  `--file` are scanned and matching `add_import(...)` calls are emitted per target (subset of
  names the moved blocks mention — grep, not a resolver). **`require()` is not auto-added**;
  Python / Markdown — no auto imports.

## Supported (smoke-checked)

| Kind | Cut blocks | Auto `add_import` |
| --- | --- | --- |
| `.js` `.mjs` `.ts` `.tsx` `.jsx` | top-level landmarks (`get_codeblock --outline`) | ESM `import` only |
| `.py` | top-level (classes/functions, …) | no |
| `.md` | heading sections (prefer heading line; `--outline --level 4+`) | no |

Fixtures used: `test/topLevel/*`, `test/mdSRC/*`, `test/tsSRC/dyn/*.mjs`. Regression:
`test/test_split_monster.py`.

**Markdown stub links:** generated scripts use `replace(file, line, STUB_XX)` (same addressing as
`cut`) and `monster.replace(source, blocks)` instead of `cut`/`monster.cut`. Fill each `STUB_XX`
(one string, may contain `\n`) before `--apply` — e.g. `> See [Section](part.md#…)`. Empty
`STUB_XX` deletes the range (same as cut).

To drop something from the plan: **append** a short reassignment at the bottom (e.g.
`SOME_BLOCKS = [c01]` to keep only `c01`) — never edit/comment an existing line, that means
retyping it in full for no reason.

## Not built yet

`--investigate` (graph block<->block with a real resolver, instead of the grep hint above) is a
documented stub — running it just prints that it isn't implemented (v1, see Vision06's "v1"
section). Anything ESM auto-import misses (`require`, path aliases, side-effect imports you
still need) — append `add_import(...)` in the script by hand.
