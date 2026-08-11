# CONTEXT_RESTORE — you are resuming

You (or a previous you) were interrupted. This file gets you back on track. It is a **REDIRECT** —
the real restore method lives per-role.

## Steps

1. Read the **TAIL** of `__HQ/TRACKER.md` (last lines) → what was being done and what is next.
   If `TRACKER2.md` / `TRACKER3.md` … exist, read the tail of the **highest-numbered** one.
2. Which role were you in? (`Plan` / `Exec` / `EnvSetup` / `Doc`.) Unclear → check `START.md`, or ask.
3. Open that role file (`__HQ/Role__*.md`) and follow its **Restore** section.
4. Check `git status` → what is half-done. Decide: continue if it is clear, else roll back the
   uncommitted changes and restart that unit. Unsure → **ask the user**.
5. Sanity anchor after code changes: `py test/check.py` should be green (or FAIL points at the
   exact file/line/case you were changing).

Do NOT re-litigate settled decisions (`__HQ/DECISIONS.md`). Do NOT blind-read the whole repo —
restore from the tail up.
