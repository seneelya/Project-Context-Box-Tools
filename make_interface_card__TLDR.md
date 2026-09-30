# make_interface_card

The card **STAMP**: ONE command → a ready `.md` card skeleton where the FACT sections are
filled deterministically and the prose is left as `<Agent: …>` directive lines for the LLM to
complete after reading the source. It analyzes nothing new — it ORCHESTRATES three facts.

**Target:** `make_interface_card.py <file> [--project-root R] [--out PATH | --cards-dir D] [--force [--discard-prose]]` — multilingual (py/ts/cs/C/C++/CUDA). `<file>` also as `--file`, same thing.

**`--project-root`** — card-tool rule. `--project-root` not given -> implicitly `CONFIG__TOOLS.PROJECT_ROOT` of this tool's own `__HQ` (must exist; missing config -> refuses, never a silent cwd; a RELATIVE value must still contain this tool). `@` -> same, explicit, unchecked. Literal path -> as given. Cards: `--cards-dir` > `CONFIG__TOOLS.MAP_DIR` (relative to `__HQ`) > `<root>/__map/`; an explicit `--project-root` always means `<root>/__map/` (Vision08). `--cards-dir D` with a single `<file>` and no `--out` writes `D/<file>.md`; with `--all` it is the target folder.

## Quick use  (copy, tweak, run)
```
make_interface_card.py <f>.py --cards-dir <HQ>/__map          # stamp → write <HQ>/__map/<f>.py.md (<f> root-relative)
make_interface_card.py <f>.py                                  # preview to stdout (no write)
make_interface_card.py <f>.py --out <card>                     # write to an exact path; re-stamp = MERGE — facts refreshed, prose KEPT
make_interface_card.py <f>.py --out <card> --force             # on an EMPTY stamp: reset, as before
make_interface_card.py <f>.py --out <card> --force --discard-prose  # on a FILLED card: required, see below
make_interface_card.py --all                                   # bulk: whole tree -> MAP_DIR, CONFIG LANGUAGE
make_interface_card.py --all --language py,ts                  # bulk: POLYGLOT tree (or 'all')
make_interface_card.py <f>.py --project-root <R> --cards-dir <D>  # a foreign project, cards wherever you say
make_interface_card.py --all --path ggml/include --path ggml/src/ggml-vulkan   # bulk over a ZONE only (C/C++ trees are huge)
make_interface_card.py --all --stale          # only cards whose OWN source changed (freshness verdict); no new cards
```

**`--all` is single-language unless you say otherwise.** Extensions come from
`CONFIG__TOOLS.LANGUAGE` (which may itself be a list), so in a `python` project a bulk pass
used to skip every `.js`/`.ts` file *silently* — a polyglot repo (a python backend and its own
JS front end in one tree) got a half-built map and nothing said so. `--language` overrides per
run: comma/space separated, `all` for every known language, short forms `py/ts/js/tsx/cs`
accepted. The pass now prints the languages and extensions it went by, even on success.

**Languages = registry `stamp_langs/`** (one module per language, shape frozen in
`stamp_langs/CONTRACT.md`). Today: python, typescript (ts/tsx/js/jsx), csharp, cpp (C/C++/CUDA). A file whose extension
no module claims is REFUSED (exit 2) — it is never stamped as Python.
Per-FILE analysis was always polyglot — only the bulk selection was not.

**`--path SUBDIR` (repeatable, `--all` only) = the ZONE** — cards are written only for files under
it (default `CONFIG__TOOLS.STAMP_DIRS`, empty = whole root). The zone limits WHERE cards go, never
what is SEEN: includes, includers and consumers are still resolved over the whole root, so a card
in the zone lists who uses it from anywhere in the tree.

## C/C++ (and CUDA) — what is different

Conditions are TAGGED, never resolved. Needs `pip install tree-sitter tree-sitter-cpp` (no regex
fallback). Config keys (target project's `CONFIG__TOOLS`): `CPP_INCLUDE_DIRS` (where `"x.h"` is
looked up after the file's own folder; without it a unique path-suffix match is tried),
`CPP_STRIP_MACROS` (export/attribute macros cut before parsing — `GGML_API`, `X_ATTRIBUTE_FORMAT(1,2)`),
`CPP_WRAPPER_MACROS` (`DEPRECATED(decl, "hint")` -> `decl`), `CPP_PAIRS` (header<->impl the
same-stem rule misses). CUDA qualifiers (`__device__` …) are cut always; macros the file DEFINES
itself (`#define LLAMA_API …`, `#define DEPRECATED(func, hint) func …`) are detected — the two
macro keys are only needed for macros defined in another file (`get_codeblock/cpp_source.py`,
shared with get_codeblock).
* **Deps Kind** = `conditional(GGML_USE_CUDA)` when the `#include` sits under `#if`; `|` is written `\|`.
  Unresolved includes go to External with a tag: `[not in tree; if GGML_USE_METAL]`.
* **Header = "API: in source"** (card-format 1.3.0): NO signatures in the card (the header has them,
  with the author's comments). Public API = `API: in source — get_codeblock --file H --outline (N
  declarations)` + a family table `Family | Decls | Lines | Used from (by folder)` (fact) +
  `### What each family is for` — one prose line per family, kept by name on re-stamp; a family
  that disappears goes to Salvage. Families: the author's section frames (`//` / `// Title` / `//`)
  -> name prefix (groups >30 split deeper, <4 go to "other <kind>") -> kind. Hook
  `api_families` (`stamp_langs/CONTRACT.md`, amendment 3).
* **Implementation** exports only external definitions NOT declared in any header it includes —
  the header's API is not duplicated; an entry under `#if` gets a `condition: X` fact line.
* **`## Build facts`** (pure fact, rebuilt every stamp — never write prose there): header<->impl
  `pair:`, "defines what these headers declare", `#if` zones (`in f, g · wraps h · top level`),
  `included by` over the WHOLE tree (+ transitive count), grep seam hints grouped by container
  (`vtable ×12 in ggml_backend_cuda_buffer_interface`; small groups keep the code:
  `register_backend(ggml_backend_cuda_reg());` in `ggml_backend_registry` [if GGML_USE_CUDA]), and
  `opaque` places tree-sitter could not read (`in f (~40 lines)`; usually a macro for
  `CPP_WRAPPER_MACROS`/`CPP_STRIP_MACROS`). **No line numbers anywhere** — anchors are names
  (`get_codeblock --name f`), so an edit that shifts lines does not rewrite the card (git noise).
* **Speed:** the include tree comes from the scan cache (`find_code_usage__TLDR.md` § C/C++);
  a zone of 36 llama.cpp files restamps in ~8 s.

## The three facts it fills

* **Declared surface + signatures** — Python → `show_pyfile_api.collect` (ast, exact param types);
  TS/JS/C# → `get_codeblock` declarations (structural block headers); C/C++ → tree-sitter-cpp.
* **Consumed surface** — `find_code_usage` downstream: who REALLY imports each symbol
  (`consumers N: file…`); exposes leaked-private and dead surface.
* **Dependencies** — `find_code_usage --incoming`, resolved to files.

## Flags & output

* **`--out PATH`** — write the card file (creates folders). On an EXISTING card it **MERGES**:
  facts are re-derived from source, prose is carried over by NAME (not by position/signature text —
  see below), and a stderr delta lists what was kept/renamed/still-needs-writing. It does NOT
  refuse and it does NOT need `--force`. Without `--out` it prints to stdout (redirect yourself).
* **Identity across a re-stamp** — a symbol's prose survives by its NAME, found by position in the
  signature (before `(`/`=`, else after known language keywords), never by guessing "first word" of
  the signature text (that broke on `function foo(x)`/`async def foo`/`public static void Foo` —
  see `DONE__REQ-004+005_merge-identity-design.md`). Same name, different signature (became `async`, new
  param) → prose kept with a `⚠ поменялась сигнатура -` marker prepended (stacks on repeat drift,
  no counter). No exact name, but a similar one → treated as a rename, prose kept with a
  `⚠ похоже на переименование, было …` marker. Neither → the entry goes to `## Salvage` as before.
* **`--force`** — write a FRESH stamp instead of merging: **every line of prose in that card is
  discarded**, replaced by `<|Agent:NN …|>` directives. Use it to deliberately reset a card you
  intend to rewrite, never as "overwrite" — the merge path is the one that overwrites safely.
  On a card that still has EMPTY prose (never filled in), `--force` works exactly as before. On a
  card with FILLED prose, `--force` alone is **REFUSED** (exit 2, nothing written) — pass
  `--discard-prose` too to confirm you really mean to throw it away. Same rule under `--all`
  (counted as `blocked`, listed by file, non-zero exit if any).
* Emits `## Package layout` + `### Re-exports` for package/index files automatically.
* Declared-surface backend = `CONFIG__TOOLS.DECL_BACKEND` (`auto|treesitter|regex`); on a
  missing tree-sitter grammar prints a one-time stderr WARNING and falls back to regex.

* **Runtime seams** (connections the import graph can't see — dynamic load, separate process,
  shared file, event bus): `--help-seams` prints the full contract (columns, Kind/Shape vocab,
  examples), no file needed. `<file> --info-seams` greps that one file for suspected
  dynamic-connection patterns and prints the lines — it does not write a card or decide
  Kind/Shape/Why, that's still the agent's call. The stamp itself never invents the section: an
  existing `## Runtime seams` is kept byte-for-byte (only its contract-note line refreshes); a
  missing one only ever gets a one-line hint, never an empty placeholder.

Contract of the format it writes = `CARD_FORMAT.py`. Authoring recipe = `__HQ/guides/Guide__MakeCard.md`.
