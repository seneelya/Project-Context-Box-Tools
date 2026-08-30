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
- **Fixed:** 2026-08-30 — `address.py::_bound_ancestor_label` walks up from the arrow/function's
  binder ancestor and reuses `spec.name()`, the same mechanism outline's const-promotion uses.
  Ladder and outline now render an identical label for the same block. New golden section
  `LADDER_LABEL` (LADDER never checked label text before, only ranges).

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
- **Already fixed:** an unrelated later commit (2026-08-24, one day after this note) added an
  inline legend at the point of every ladder/query call reminding about `--ancestor-level` —
  verified 2026-08-30 that it still fires. No new change needed.

### 2026-08-23 — C# primary-constructor L1 labels extremely long
- **Severity:** ux
- **Cmd:** `… --file AcceptInvitationHandler.cs` (outline / ladder)
- **File:** Warehub `AcceptInvitationHandler.cs` (primary ctor + many DI params)
- **Expected:** Compact class label (`AcceptInvitationHandler`) in outline/ladder
- **Got:** Full parameter list in the L1 label (hundreds of chars) — noisy in agent context
- **Note:** Truncate signature in outline/ladder labels; keep full text only in `--query`.
- **Fixed:** 2026-08-30 — `TreeSitterSpec.name()` (single shared point for every brace-language
  landmark/frame header, outline AND ladder) caps at 350 chars + `…`. `--query` on the same
  range still returns the untruncated source — display-only. Cap picked above the longest real
  multi-kwarg signature already in the golden fixtures (267 chars).

### 2026-08-23 — SCSS outline reports `~ERROR` bands (globals.scss)
- **Severity:** bug
- **Cmd:** `… --file globals.scss`
- **File:** Warehub.Frontend `src/globals.scss`
- **Expected:** Usable rule/mixin outline or clean fallback
- **Got:** Rows like `~ERROR`, `~ERROR x16` mixed with selectors; weak map  `t:\AgentsWork\ProjectStarter\__HQ\tools>py get_codeblock.py --file t:\AgentsWork\ProjectStarter\__dev\tools\Requests\globals.scss`
- **Note:** `custom.scss` (larger) outlined more usefully (mixins, selectors at L1). Investigate globals parse failures; don’t fail silently under `~ERROR` without saying why.
- **Fixed:** 2026-08-30 — root cause: a top-level (brace-depth 0) `$var: value;` isn't valid
  CSS, and unlike `@mixin`/`@include` the parser's recovery from it cascaded into losing the
  parse of the REST OF THE FILE (`root.type` itself came back `'ERROR'`). Nested `$var:` inside
  a rule block stays contained (verified) — left alone. Added `LangSpec.preprocess` (generic,
  opt-in, `None` for every other language — no shared-engine special-casing per the
  self-containment rule) and `css_handler._mask_scss_top_level_vars`, which rewrites each
  top-level `$var:` into a same-length real CSS comment before parsing. New fixture
  `test/cssSRC/vars.scss`.
  **Residual, separate finding (not fixed, not this bug):** a SCSS variable used AS A VALUE
  inside a real rule (`property: $var;`) is ALSO unparseable and can ALSO cascade to sibling
  rules — found while testing this fix on a synthetic `.footer { height: $footerHeight; }`
  case. Distinct from the reported globals.scss case (a vars-only file, no usage) and not
  addressed here; would need masking every bare `$name` value reference too, a bigger and
  riskier change. Left for a future request if it turns out to matter in practice.

### 2026-08-23 — First evaluation: tool fits agent workflow (positive)
- **Severity:** note (keep for changelog)
- **Context:** Warehub FE+BE — outline / ladder / query / MD section extract
- **Got:** Strong win on C# handlers and multi-function TSX; MD TOC+section pull works; token cost of outline often ~2–20% of full file
- **Note:** Recommended agent path: outline → line → `--ancestor-level 1 --query`. Session should call `--help` for evolving flags.
