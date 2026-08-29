# get_codeblock — Cursor agent feedback log

Log of findings while using the tool as an agent context reader.
Entries are fixed over time; append new ones at the top (below this header).

---

### 2026-08-23 — Ladder labels lose names that outline has (TS/TSX)
- **Severity:** ux
- **Cmd:** `… --file VideoDropzone.tsx --line 150` vs bare `--file` outline
- **File:** Warehub.Frontend `src/shared/VideoDropzone/VideoDropzone.tsx` (tsx)
- **Expected:** Ladder rungs named like outline (`const addNewVideo = async …`, component name)
- **Got:** Outline correct; ladder showed `() => {…}` / anonymous tags for the same ranges
- **Note:** Agents should trust outline for names, ladder for nesting. Prefer named labels in ladder output when the block is a name-bound const/function.

### 2026-08-23 — Flat mega-component: no carve of JSX / route islands
- **Severity:** wish
- **Cmd:** `… --file App.tsx` and `… --line <ProtectedRoute line>`
- **File:** Warehub.Frontend `src/App.tsx` (~600 lines, one `const App = () =>` + huge `return`)
- **Expected:** Useful mid-level units (e.g. route groups) or at least more than one structural landmark inside the return
- **Got:** Outline depth 1 only (`const App`); ladder at a route line → `~return_statement` spanning almost the whole component. `--outline --level 2` still depth 1 (structurally correct, agent-weak)
- **Note:** For route tables / large JSX returns, outline maps the file but cannot replace Grep+offset Read. Optional: treat significant JSX subtrees or repeated patterns as outline landmarks.

### 2026-08-23 — Default innermost `--query` often too small for agent use
- **Severity:** ux / wish
- **Cmd:** `… --line 150 --query` (no ancestor)
- **File:** same VideoDropzone.tsx; also C# `AcceptInvitationHandler.cs` line 120
- **Expected:** Function/method body as the common “useful unit”
- **Got:** Innermost `try` / `if` (3–4 lines). Useful extract needed `--ancestor-level 1` or `2`
- **Note:** Docs already say this; agents forget. Possible defaults/hints: suggest parent in ladder output, or a `--query-useful` that prefers named function/method over control blocks.

### 2026-08-23 — C# primary-constructor L1 labels extremely long
- **Severity:** ux
- **Cmd:** `… --file AcceptInvitationHandler.cs` (outline / ladder)
- **File:** Warehub `AcceptInvitationHandler.cs` (primary ctor + many DI params)
- **Expected:** Compact class label (`AcceptInvitationHandler`) in outline/ladder
- **Got:** Full parameter list in the L1 label (hundreds of chars) — noisy in agent context
- **Note:** Truncate signature in outline/ladder labels; keep full text only in `--query`.

### 2026-08-23 — SCSS outline reports `~ERROR` bands (globals.scss)
- **Severity:** bug
- **Cmd:** `… --file globals.scss`
- **File:** Warehub.Frontend `src/globals.scss`
- **Expected:** Usable rule/mixin outline or clean fallback
- **Got:** Rows like `~ERROR`, `~ERROR x16` mixed with selectors; weak map  `t:\AgentsWork\ProjectStarter\__HQ\tools>py get_codeblock.py --file t:\AgentsWork\ProjectStarter\__dev\tools\Requests\globals.scss`
- **Note:** `custom.scss` (larger) outlined more usefully (mixins, selectors at L1). Investigate globals parse failures; don’t fail silently under `~ERROR` without saying why.

### 2026-08-23 — First evaluation: tool fits agent workflow (positive)
- **Severity:** note (keep for changelog)
- **Context:** Warehub FE+BE — outline / ladder / query / MD section extract
- **Got:** Strong win on C# handlers and multi-function TSX; MD TOC+section pull works; token cost of outline often ~2–20% of full file
- **Note:** Recommended agent path: outline → line → `--ancestor-level 1 --query`. Session should call `--help` for evolving flags.
