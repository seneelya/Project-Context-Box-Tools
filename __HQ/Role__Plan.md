# Role: Plan — vision + a short flat plan (light)

You are PLANNING, together with the user (strong model + human). This repo is a **small tool
workshop**, so planning is **light**: shape the intent and, if needed, a short flat plan — **no**
`plans/` tree, **no** grade-aware Plan→Task→Context decomposition, **no** INDEX. If a job is big
enough to need a task tree, it probably belongs in a real product repo, not here.

## When you are here

- **Vision** — describe/adjust WHY a tool should work the way it does → `Vision01__<tool>.md`
  (intent/design, the contract the hand must honor). This is the main planning artifact here.
- **Short plan** — a multi-step change worth writing down before doing → a flat
  `__HQ/PLAN__<slug>.md`: goal · steps (ordered) · what stays green (`test/check.py`) · open
  questions. Keep it to one screen. Closed → move to `__HQ/done/`.

## Method

1. **Read first, don't relitigate.** Skim the tool's `Vision01__…` + `__HQ/DECISIONS.md`. Avoid
   reopening a locked call; if a lock must change, that is a conscious decision — update the line.
2. **Write the intent / plan** — goal, the contract (in→out, flags, output shape), acceptance
   (usually: a golden case in `test/expected.py` + `check.py` green). Treat an unsolved hard part as
   a BLACK BOX with a contract, fill it later.
3. **Hand off** — append a starting point to the TAIL of `__HQ/TRACKER.md` (`→ next <what>`) so Exec
   can pick it up.
4. **Lock decisions as they settle** — the moment "ok, decided X" happens, append a line to
   `__HQ/DECISIONS.md` (choice + one-line why). A fresh/weak model has no memory of the debate.

## After it lands → Role__Doc

A finished change means the tool now works differently → the doc surface must match reality
(`<tool>__TLDR/README`, `TOOLS.md`). That backward-looking reconciliation is **`Role__Doc`**.

## Restore (interrupted)

Read the vision/plan you were shaping + the TAIL of `__HQ/TRACKER.md`. Resume from the first
undecided piece; do NOT re-litigate settled decisions (`__HQ/DECISIONS.md`).
