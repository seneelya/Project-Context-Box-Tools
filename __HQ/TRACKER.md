# TRACKER — tail log

Execution progress. **Read only the TAIL** (last lines). How to fill/read → `guides/Guide__Tracker.md`.

---
<!-- progress log — append below, newest last -->
✅ consolidate step1 (pull 7 ProjectStarter tools + fix self-locate to CWD/__map, golden green) → next: base pull (adapted scaffold: START/roles/tracker, no cards, no long plans)
✅ consolidate step2 (base pulled + adapted: AGENTS/START/CONTEXT_RESTORE + __HQ WORKFLOW/TRACKER/DECISIONS + Role__Exec/Plan/EnvSetup/Doc + guides Tracker/SplitLargeFiles/Doc; cards+long-plan ritual dropped; unified TOOLS.md by 3 layers; golden 49/0) → next: wire LLM playbook into roles/guides (plan step 5), then optional py_api⟷--outline dedup (step 3)
✅ card stamp engine: py_api.collect() structured AST + card_api.py (one cmd → fact-filled card skeleton: declared API+signatures × consumed surface × deps); contract tweaks: blank-line-after-heading wording, new `Consumed internals` H3 (private OK). golden 49/0 → next: rewrite MakeCard skill stamp-first (old mechanism = fallback)
✅ card stamp format pass: fact label `consumers N`/`consumers 0`; external imports one-per-line + drop `__future__`; richer <Agent: …> directive; re-export source on H4 heading (`← .mod`), consumers line pure. card_format: renamed H2_SECTIONS/H2_SECTIONS_PACKAGE/H3_API_SUBSECTIONS + docstring = nested card skeleton with var mapping (updated validate_cards refs). → next: rewrite MakeCard skill stamp-first; decide multi-language stamp
✅ TS reverse-index fix: handle ESM/NodeNext `.js` specifiers (import "./util.js" → util.ts) in ts_resolver._resolve_module + ts_handler.matches_target; +tsSRC2 fixture (zod v4/core, 19 files). util.ts now 8 consumers (was 0). golden 49/0 → next: TS/C# outline + index.* as package + card_api declared-source via outline (multilingual card)
