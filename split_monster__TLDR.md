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
* **imports** (ESM `.js` `.mjs` `.ts` `.tsx` `.jsx`, and Python): leading imports of `--file` are
  read and matching `add_import(...)` calls are emitted per target — only names the moved blocks
  actually USE (identifier scan: words in comments/strings do not count). **`require()` is not
  auto-added**; Markdown — none.
* **split-set graph** (Python, JS/TS): since every moved name is known, the script also gets
  (a) imports BETWEEN the new files (`from h import helper`) and from the source into the targets
  for names that stay there, (b) `SOURCE_IMPORTS` — imports the REMAINING source now needs from the
  files its blocks moved to (`monster.cut(src, blocks, imports=SOURCE_IMPORTS)` inserts them after
  the cut), (c) comment warnings: `WARNING export:` (a private JS name now crosses a file
  boundary — add `export` by hand; the tool never edits block text) and `WARNING cycle:`
  (circular import among the new files). Identifier scan, not a full resolver.
* **safety (always on)**: `monster.expect_source(file, hash)` only WARNS if `--file` changed since
  generation; every `cut(..., expect=<block fingerprint>)` re-checks its own block text — same text
  (file changed elsewhere) = proceeds, different text (lines shifted/edited) = stops, unless
  `move.py --apply --force` (warning, cuts anyway); `--apply` keeps each file's EOL/BOM byte-for-byte;
  after the closing cut/replace `verify()` checks no non-blank line was lost or invented and nothing
  stopped parsing — on failure **every touched file is rolled back** (exit 1).

## Supported (smoke-checked)

| Kind | Cut blocks | Auto `add_import` |
| --- | --- | --- |
| `.js` `.mjs` `.ts` `.tsx` `.jsx` | top-level landmarks (`get_codeblock --outline`) | ESM `import` only |
| `.py` | top-level (classes/functions, assignments) | `import` / `from … import` (via `ast`) |
| `.md` | heading sections (prefer heading line; `--outline --level 4+`) | no; hint = other sections linking `#anchor` |
| `.cs` `.c` `.h` `.cpp` `.cc` `.cxx` `.hpp` `.cu` `.cuh` … (generic tree-sitter module) | cut/replace + name hints (names/identifiers come from get_codeblock; namespace/`extern "C"`/`#ifdef` frames are looked into) | **not yet** (donor: find_code_usage, next step) |
| other get_codeblock languages (css, sh, …) | cut/replace work; **no name hints / auto imports** (script says so) | no |

Fixtures used: `test/topLevel/*`, `test/mdSRC/*`, `test/tsSRC/dyn/*.mjs`. Regression:
`test/test_split_monster.py`.

**Markdown stub links:** generated scripts use `replace(file, line, STUB_XX)` (same addressing as
`cut`) and `monster.replace(source, blocks)` instead of `cut`/`monster.cut`. Fill each `STUB_XX`
(one string, may contain `\n`) before `--apply` — e.g. `> See [Section](part.md#…)`. Empty
`STUB_XX` deletes the range (same as cut).

**Source changed after the script was made?** Don't regenerate (that would lose your hand edits):
`split_monster.py --rebase move.py` (report only) / `--rebase move.py --write` re-anchors each
generated `cut`/`replace` line number by the block's recorded fingerprint and touches nothing else.
Same text elsewhere = moved; same name but edited text = shown as CHANGED, taken only with
`--accept-changed`; not found = left as is (the run will still refuse it). Hand-written calls
without `expect=` are listed for you to check.

To drop something from the plan: **append** a short reassignment at the bottom (e.g.
`SOME_BLOCKS = [c01]` to keep only `c01`) — never edit/comment an existing line, that means
retyping it in full for no reason.

## Taking only this tool out of the toolkit

Keep the folder layout, run from the folder that holds `split_monster.py` (Python >= 3.10,
`pip install -r get_codeblock/requirements.txt`). Verified in a clean copy (py / js / md moves,
`--apply`, verify all pass):

* **required:** `split_monster.py`, `split_langs/`, `get_codeblock/`, `find_code_usage/`
  (JS/TS import parsing reuses its `ts_handler`);
* **optional:** the "who outside imports these names" report (`monster.consumers`) also needs
  `make_interface_card.py`, `stamp_langs/`, `CARD_FORMAT.py`, `graph_from_cards.py`, `seam_scanner/`,
  `termstyle.py` — without them it prints one line and is skipped; `CONFIG__TOOLS.py` is only for
  the usage log (missing = log off);
* not needed: `test/`, `__dev/`. The same list sits at the top of `split_monster.py`.
* generated `move.py` files hold the tool's absolute path — regenerate them after moving it.

## Languages (`split_langs/`)

One module per language (python, javascript = js/ts/tsx/jsx/mjs, markdown, treesitter = the generic
one for C#/C/C++ built on get_codeblock) behind a registry; the
core has no `if language == …`. A new language = a new module + its name in `_MODULES` — see
`split_langs/CONTRACT.md` (required hooks fail loudly at load). Unclaimed extensions fall back to
`other`: cut/replace work, no hints/imports/graph.

## Usage log

Same opt-in mechanism as the other tools (`CONFIG__TOOLS.LOG_ENABLED_TOOLS` contains
`"split_monster"`, `LOG_DIR` → `<LOG_DIR>/split_monster.log.jsonl`, JSONL, diagnostic only — never
block text). Three record kinds: `generate` (lang, blocks, targets, imports), `rebase` (moved /
accepted / same / unresolved / hand-written counts, write flag) and `run` — one per `move.py`
execution, with `apply`, `force`, `stale_warning`, blocks/targets/imports and `outcome`
(`dry-run` / `applied_verified` / `verify_failed` / `refused_block_mismatch` / `incomplete`).
Tests set `SPLIT_MONSTER_NO_LOG=1` so they never touch the real log.

## Not built yet

`--investigate` (graph block<->block with a real resolver, instead of the grep hint above) is a
documented stub — running it just prints that it isn't implemented (v1, see Vision06's "v1"
section). Anything ESM auto-import misses (`require`, path aliases, side-effect imports you
still need) — append `add_import(...)` in the script by hand.
