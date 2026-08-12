# Guide: MakeCard — write a code card (STAMP-FIRST)

You are given **ONE source file**. Produce its **card** — a cheap map another agent reads
INSTEAD of the source. Two parts:
- **Part 1 (primary):** the stamp utility fills the FACTS; you fill only the prose.
- **Part 2 (fallback):** used ONLY if the utility does not work — and you MUST tell your caller first.

Card path (where the result goes):
```
<PROJECT_ROOT>/__map/<same/relative/path>/<name><ext>.md
```
Example: source `_engine/db.py` → card `<PROJECT_ROOT>/__map/_engine/db.py.md`.

`<TOOLS>` below = the folder holding the tools (`card_api.py`, `validate_cards.py`).

---

## Part 1 — STAMP-FIRST  (use this)

### Step 1 — generate the skeleton (write it to the card file)
```
py <TOOLS>/card_api.py <source-file> --project-root <PROJECT_ROOT> --out <card-path>
```
`--out` writes the card file directly (creating folders). Without `--out` it PRINTS to
stdout instead — then YOU must redirect it yourself (`… > <card-path>`). Prefer `--out`.

The card is a ready `.md` where the **FACT** sections are already filled:
- `## Public API` — real signatures grouped by kind (`### Functions/Classes/…`), and under each
  entry a fact line `consumers N: file1, file2` (who really imports it; `consumers 0` = nobody).
- `## Dependencies Internal/External`, `## Package layout` (for a package/index file).
- Prose slots are **directives**: `<Agent: …>` lines — that is YOUR job in Step 3.

### Step 1b — if the card ALREADY exists
`card_api --out` refuses to overwrite (exit 2, `card already exists`). Decide:
- the existing card is only an **unfilled stamp** (still full of `<Agent: …>` lines, no real
  descriptions) → re-run with **`--force`** to replace it;
- the existing card has **real prose** → do NOT `--force` (you would delete the descriptions).
  Instead run WITHOUT `--out` (to stdout) to get the fresh FACTS, and update only the changed
  fact sections (Public API signatures, `consumers N`, dependencies) into the existing card by
  hand, keeping the prose. (Use `check_freshness.py` to see which cards are stale.)

### Step 2 — check the stderr note
If stderr shows `WARNING: … REGEX FALLBACK … pip install tree-sitter …`:
- the high-fidelity parser is not installed; the card is **still usable** (signatures are
  slightly lower-fidelity). This is NOT a failure — continue.
- You MAY tell the caller: "for sharper signatures, install `tree-sitter tree-sitter-<lang>`."

### Step 3 — fill the prose (read the source ONCE)
Replace every `<Agent: …>` line, using FACTS FROM THE CODE ONLY:
- summary line under the H1 → one line: what the module does;
- each `#### <symbol>` → one concise line (what it does + its role), OR **delete the directive
  line** if the symbol is trivial;
- `## Dependencies Internal` "why" cells; `## How it works` (the mechanism); `## Discrepancies`
  (docstring vs code contradictions; else `(none)`); `## Package layout` (one line per submodule).
- **Keep the fact lines** (`consumers N: …`) — they are verified; do not invent or "improve" them.
- No "key / main / important / core". Do not invent dependencies or symbols not in the output.

### Step 4 — validate
```
py <TOOLS>/validate_cards.py --cards-dir <PROJECT_ROOT>/__map --project-root <PROJECT_ROOT>
```
Fix what it flags (missing section, empty summary, unresolved `File Path`). **Green = done.**

---

## Part 2 — FALLBACK  (the utility is NOT working)

Enter this part ONLY if Step 1 fails: `card_api.py` errors, will not run, or prints nothing.

### Step 0 — REPORT TO YOUR CALLER FIRST (do not switch silently)
Say plainly to whoever invoked you:
> "`card_api.py` is not working (`<paste the exact error>`). Switching to MANUAL card authoring
> (fallback). Facts (consumers/signatures) will be hand-derived and may be less complete."

Then, and only then, author the card by hand.

### Manual recipe (facts from the code only)
The exact format contract is **`<TOOLS>/card_format.py`** (its docstring is the card skeleton).
Follow it: H1 = the file name only; the next non-empty line = a one-line summary; then all H2
sections in order (empty → `(none)`).

- **Public API** — group by kind under `###`; list EVERY public symbol (functions, classes and
  their public methods one per line, constants, types). Include a `_`-private name only if OTHER
  files import it (that is the effective interface) → put such names under `### Consumed internals`.
- **Consumed surface, not just "public"** — describe what other files actually use. If unsure who
  uses a symbol, mark it "possible export" rather than guessing.
- **Dependencies Internal** — table `| Import | File Path | Symbols | Why | Kind |`; each `File Path`
  is the root-relative path to the imported file. **Dependencies External** — third-party/stdlib
  the reader may not know.
- **How it works** — the mechanism in a few lines. **Discrepancies** — real docstring↔code contradictions.
- Keep it short: several× smaller than the source, one sentence per object. Facts only.

### After the fallback
Re-run `py <TOOLS>/validate_cards.py …` if it runs (it is independent of `card_api.py`). If the
whole toolchain is down, tell the caller that too.
