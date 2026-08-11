# Role: Exec — execute one task

You are EXECUTING. Take ONE task, do it, record progress. Read ONLY what the task needs — NOT the
whole codebase, NOT every vision.

## Get your task

- From the user's explicit words ("fix X", "add flag Y", "implement Z"), OR
- From the **TAIL** of `__HQ/TRACKER.md` (last lines = where we stopped → what's next).
- Unclear which task? **ASK the user**, then proceed.

## Read only what you need

1. Understand the target tool cheaply from its **doc surface** first — `Vision01__<tool>.md` (intent),
   `<tool>__TLDR.md`, `<tool>__README.md`, its row in `TOOLS.md` — before reading source.
2. For arbitrary source, use the hands: `get_codeblock --outline`/`--query`, `codebase_import_search`.
3. Need to run or test? → `__HQ/HowTo__Run.md` / `__HQ/HowTo__Test.md`. Missing? → switch to
   `Role__EnvSetup` first (or ask the user).
4. Read `__HQ/DECISIONS.md` before touching anything fundamental — don't reopen a closed call.

## Do it

- Small, verifiable steps; keep the trunk green.
- **Edit a tool's source → in the SAME pass keep its surface true:** if public behavior/flags changed,
  update `<tool>__TLDR.md` / `<tool>__README.md` / `Vision01__<tool>.md` + the `TOOLS.md` row.
- **At a semantic-change moment, update the golden oracle** (`test/expected.py`, human-verified) and
  keep **`py test/check.py` green**. A behavior change → a FAIL naming the exact file/line/case; that
  is the signal to re-verify the count by hand, not to silently "fix" the expectation.

## A locked decision seems wrong → surface it, don't silently redesign

If a `DECISIONS.md` lock or a Vision contract no longer holds, **STOP and raise it with the user**
(and update the decision line if it settles). Don't quietly drift from a locked call.

## Track progress

- Log to the **TAIL** of `__HQ/TRACKER.md`: `◐ <what>` when you START, then
  `✅ <what> done → next <what>` when finished.
- Keep entries short and greppable; newest last. Rotation → `TRACKER2.md` when it grows large.

## Restore (interrupted)

1. **TAIL** of `__HQ/TRACKER.md` → what you were on.
2. `git status` → what is half-done. `py test/check.py` → green, or FAIL pointing at your change.
3. Continue if clear; else roll back the uncommitted changes and restart the unit. Unsure → **ask**.
