# split_monster

v0. Moves named top-level blocks between files WITHOUT you retyping their content twice. You
decide the grouping (`line -> target_file`); it expands that into a throwaway, hand-editable
Python script; you review/tweak it (cheaply — append short override lines, never rewrite
existing ones) and run it. See `__dev/vision/Vision06__monster-file-split.md` /
`__dev/plans/Plan04__split_monster.md` for the full rationale — this is just the quick reference.

**Target:** `split_monster.py --file <monster.js> --split <LINE> <target.py> [--split ... ...] --out-script <out.py>`
— `LINE` is a block's start line (get it from `get_codeblock --outline` first), `--split` repeats
per block, order in the flags doesn't matter (the generator restores source order on its own).

## Quick use

```
get_codeblock.py --file monster.js --outline                        # find block start lines first
split_monster.py --file monster.js --split 123 "a.js" --split 456 "b.js" --out-script move.py
python move.py            # dry-run — prints the plan, writes nothing
python move.py --apply     # actually cuts monster.js and writes a.js/b.js
```

## What's in the generated script

* one `cut(file, line)` call per block + a `#N` tag (a stable id for `Edit`-anchoring, not a live
  line number) — the descriptive comment (block's own signature/preview) lives on its OWN line
  ABOVE the code, never mixed into it;
* a cheap **best-effort grep hint** per block ("who else in the file mentions this name",
  "which other top-level names does this block's body use") — NOT a real reference graph, just a
  textual scan. Verify it yourself; it will have false positives/negatives;
* `monster.write(target, blocks, imports)` / `monster.cut(source, blocks)` at the bottom — these
  do the actual byte-for-byte move, gated behind `--apply` on the SCRIPT's own invocation.

To drop something from the plan: **append** a short reassignment at the bottom (e.g.
`SOME_BLOCKS = [c01]` to keep only `c01`) — never edit/comment an existing line, that means
retyping it in full for no reason.

## Not built yet

`--investigate` (graph block<->block with a real resolver, instead of the grep hint above) is a
documented stub — running it just prints that it isn't implemented (v1, see Vision06's "v1"
section). Imports are never auto-detected on v0 either — you still decide them, just via
`add_import(...)` lines in the generated script rather than a separate manual edit pass.
