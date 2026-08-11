# START — entry point: name your role → read its file

> You just entered **`tools/`** — the dev workshop for the "hands" (CLI tools) of the ProjectStarter
> scheme. It runs a **lightweight** ProjectStarter skeleton: **no card layer (`__map/`)** and **no
> long-plan ritual** (no `plans/` tree, no Plan→Task→Context decomposition) — this is a small,
> hand-held tool repo, not a card-mapped product. Your **ROLE is set by the USER**. Find it below,
> open its file, act by it.
>
> ⚠️ **Don't know your task/role? — ASK the user**, then come back here.

## How to use

1. From the user's words, pick the role from the table (look at "when you take it").
2. None fits / unclear → **ask the user**, return to step 1.
3. Open the role file (`__HQ/Role__*.md`) and follow it strictly — it holds the method + how to
   restore context for that role.

## Roles

| Role file (in `__HQ/`) | When you take it — the user says… |
| --- | --- |
| **`__HQ/Role__Plan.md`** | "let's plan", "write/adjust the vision", "how should this tool work" (light: vision + short flat plan, no task tree) |
| **`__HQ/Role__Exec.md`** | "do the task", "continue", "fix …", "implement …", "add a flag" |
| **`__HQ/Role__EnvSetup.md`** | "how do I run / test this", "set up the environment" |
| **`__HQ/Role__Doc.md`** | "update the docs", "reconcile the docs with what we built" |

**Restoring** ("we stopped at …", "continue") → first open **`CONTEXT_RESTORE.md`**.

## Universal rules

- **The tools ARE the map here** (no `__map/` cards). To understand a tool cheaply, read its
  doc surface — `Vision01__<tool>.md` (intent) · `<tool>__TLDR.md` · `<tool>__README.md` · `TOOLS.md`
  — before blind-reading source. For arbitrary source, use the tools themselves (`get_codeblock
  --outline`, `codebase_import_search`).
- **Edit a tool's source → in the SAME pass keep its surface true:** if public behavior/flags changed,
  update its `TLDR`/`README`/`Vision` + the `TOOLS.md` row; at semantic-change moments update the
  golden oracle (`test/expected.py`) and keep **`py test/check.py` green**.
- Record progress by **appending to the TAIL** of `__HQ/TRACKER.md` (`✅ done … → next …`); when
  reading, look only at the **TAIL**.

## Naming system

A file name encodes **address + human-readable name**: `<Tag><N>[-<Tag><N> …]__<name>.md`
(parse: `split("__")[0].split("-")`). Tags used **here** (light subset):
**`Vision`** (intent/design) · **`Doc`** (how it works NOW) · **`HowTo`** (recurring project action:
run/test) · **`Guide`** (authoring recipe) · **`Role`** · **`PLAN`** (a short, flat plan — no task tree).

## Where things live (don't load extra)

- **Tool catalog** → `TOOLS.md` — every tool, grouped by 3 layers (source-analysis · card-map ·
  maintenance). Start here to see what hands exist.
- **Per-tool docs** → `Vision01__<tool>.md` (why/design) · `<tool>__TLDR.md` (one-screen) ·
  `<tool>__README.md` (full `--help`-level). Read these instead of the source.
- **Settled decisions** → `__HQ/DECISIONS.md` — locked calls + one-line why; **read before
  (re)designing, don't relitigate**.
- **Context restore** → `CONTEXT_RESTORE.md` + the TAIL of `__HQ/TRACKER.md`.
- **Vision / light plans** → `__HQ/Vision01__*.md` (intent) · `__HQ/PLAN__*.md` (short flat plans);
  closed → `__HQ/done/`.
- **How to run / test** → `__HQ/HowTo__*.md`.
- **Tests (golden)** → `test/` — `check.py` (runner) · `expected.py` (human-verified oracle) ·
  `README.md`. Card-tool fixtures live under `test/cards/`.
- **How the scheme works** (roles, flow, naming — big picture) → `__HQ/WORKFLOW.md`.
- **Authoring recipes** → `__HQ/guides/` — how to shape a Doc / tracker entry / split a large file.
