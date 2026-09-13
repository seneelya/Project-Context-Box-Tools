# get_codeblock — Claude agent feedback log

Log of findings while using the tool as an agent context reader.
Entries are fixed over time; append new ones at the top (below this header).

---

### 2026-09-04 — flat const-file + `--line 1 --ancestor-level 0 --query` returns almost nothing useful
- **Severity:** ux
- **Cmd:** `python get_codeblock.py --file src/abstractions/inspections/checklist/utilitiesAndBuildingFunctions/electricalCapacityOptions.ts --line 1 --level 1 --query --numbered`
- **File:** electricalCapacityOptions.ts (60 lines, all top-level sibling `export const X = {...}` declarations, no outline yet taken)
- **Expected:** something close to the whole file, or at least a hint that 5 more sibling `export const` blocks follow at the same level.
- **Got:** just the 2-line `import` statement block (lines 1-2), since line 1 sits inside that block and ancestor-level 0 is "the block itself". Had to fall back to `Read` to actually see the option tables I needed.
- **Note:** Technically correct per the tool's own semantics, but it's a footgun for a very common file shape in this codebase (option/constant tables, enum-like dictionaries): short, flat, made of independent sibling statements rather than nested blocks. Picking line 1 to "get oriented" on such a file gives almost no signal. Two ideas: (a) when `--query` on a block shorter than ~5 lines is requested without having run `--outline` first, print a one-line nudge ("this file has N more top-level siblings; try `--outline`"); (b) a `--whole-file`/`--dump` flag that just prints the numbered raw file, for exactly this case, so the fallback to `Read` isn't needed.
- **Decided:** 2026-09-13 — covered by Vision05 query-escalation (`get_codeblock/escalate.py`),
  NOT the literal `--dump` idea below (rejected — conflicts with the tool's block-based
  philosophy; `Read` already exists for whole-file needs). Verified live on this exact file:
  `--line 1 --query` now auto-escalates 2→25 lines (grabs the `ampsOptions` neighbor). See
  `Vision05__get_codeblock.md`.

### 2026-09-04 — wish: no single-shot "dump numbered file" mode for short files
- **Severity:** wish
- **Cmd:** n/a (workflow observation across the session)
- **File:** general — hit repeatedly on files under ~130 lines (option tables, small validators, small React components)
- **Expected:** for a short file where I just want the full content with line numbers (equivalent to `cat -n`) without reasoning about block/ancestor levels, a direct flag would save a step.
- **Got:** had to either guess a `--line N --ancestor-level K` combo large enough to cover the whole file, or give up and use `Read`. In this session I ended up using `Read` for several files under 130 lines (electricalCapacityOptions.ts, ElectricalCapacityInspection.tsx, BaseCheckbox.tsx, SuiteElectricalServices.tsx) specifically because gcb's block-based model didn't offer a fast path to "just show me all of it".
- **Note:** Not asking to change the block-based default — it's genuinely better for large/deeply-nested files — just for a documented escape hatch for small ones, so agents don't have to fall back to a different tool mid-task.
- **Decided:** 2026-09-13 — same as the entry above: NOT a dedicated dump flag (rejected on
  purpose), the underlying "too little for a short/flat file" pain is what Vision05
  escalation targets instead. Files genuinely longer than `ESCALATE_CEILING` (40 lines) still
  won't get dumped whole — that's intentional, `Read` is still the tool for that case.

### 2026-09-04 — outline "showing 1..1" wording is opaque
- **Severity:** ux
- **Cmd:** `python get_codeblock.py --file .../ElectricalCapacityVerification.tsx --outline --level 9`
- **File:** ElectricalCapacityVerification.tsx (93 lines)
- **Expected:** self-explanatory header line.
- **Got:** `//outline — depth 1, L1=1, showing 1..1` — had to cross-reference the `--help` text to be confident this meant "the requested target(s) map to source line range 1..1", not e.g. "showing block 1 of 1". Not wrong, just terse enough to cost a re-read.
- **Note:** low priority; a slightly more verbose header (e.g. spelling out "line range" instead of bare `1..1`) would remove the ambiguity without hurting agents already familiar with the format.
- **Fixed:** 2026-09-13 — labeled every axis in the header instead of leaving bare numbers:
  `depth N` → `max depth N`, `showing A..B` → `showing levels A..B` (`core.py`, the single
  header-emit line). 4 golden fixtures re-recorded (header line only) and verified clean.

---

**2026-09-12** — файлы из этого отчёта выгружены в `feedback/files/` и пошли в работу (12.09.2026).

**2026-09-13** — смерджено с `cursor_feedback__gcb.md`/`sonet_feedback__gcb.md` в единый рабочий лог этой папки (`__dev/Requests/`); `feedback/` остаётся сырым intake/фикстурами.
