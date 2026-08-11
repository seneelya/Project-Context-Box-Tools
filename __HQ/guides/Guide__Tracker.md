# Guide: Tracker — how to fill and read the tracker

The tracker (`__HQ/TRACKER.md`) is a **tail log** of execution progress.

**Read:** only the **TAIL** (last few lines) — that is where we are. Never read the whole file.

**Write:** append ONE line per step to the BOTTOM, newest last:
- `◐ <what>` — in progress
- `✅ <what> done → next <what>` — a step finished + what to take next
- `⏸ <what> — <why>` — blocked / parked

`<what>` is a short human handle (this repo has no `plans/` tree, so no `PlanNN-TaskMM` addresses) —
e.g. `add --symbol filter to import_search`, `fix find_body_end multiline sig`. Keep it greppable.

**Rotation:** when the file grows too large, start `TRACKER2.md`, `TRACKER3.md`, … and read the TAIL
of the latest one.

An optional compact **phase map** may sit at the top (changes rarely); the moving state is the log.
