# graph_from_cards

The project's topology from `__map/` cards — the "second compilation". Load it ONCE and
then reason in your head (impact / chain / depth); no need to re-read cards.

**Target:** `graph_from_cards.py [--project-root P] [--view tree|depth|seams-mermaid] [--edges out|in|inout]`
— default cards = `<project>/__map/`. `--project-root` not given -> implicitly
`CONFIG__TOOLS.PROJECT_ROOT`, sanity-checked (must contain this tool's own folder — a stale/foreign
config refuses instead of silently mapping the wrong tree). `@` -> same, explicit, unchecked.
Literal path -> as given, unchecked.

## Quick use
```
graph_from_cards.py                           # tree view (default), both edge directions
graph_from_cards.py --view depth              # 0=leaves → up toward entry points
graph_from_cards.py --view seams-mermaid      # every Runtime seam as one mermaid diagram
graph_from_cards.py --edges out               # only "→ uses" (quieter; reading order)
graph_from_cards.py --edges in                # only "← used-by" (blast radius of a change)
graph_from_cards.py --verbose 0               # modules + edges only (hide summary lines)
graph_from_cards.py --file _engine/embed.py   # focus slice around one file
graph_from_cards.py --cycles                  # circular deps as A → B → C → A
graph_from_cards.py --discrepancies           # "map vs reality" digest (orphan/pending/unresolved)
graph_from_cards.py --discrepancies --group-by package   # same findings, regrouped by package
graph_from_cards.py --json                    # JSON draft for a visualizer
```

**`--discrepancies`** = coverage audit of the card layer against the source tree:
*orphan* (card without source), *pending* (dep on a source that has no card yet),
*unresolved* (dep ref matching neither). `--group-by kind|package|card` slices the same
findings differently — the collection is one flat typed list, grouping is just a key.

A map split into **several independent parts** (a second plugin, a JS front end to this
backend) adds a `> note:` line here — deliberately NOT a typed finding and NOT in `--json`:
more than one part is legitimate architecture, not a defect, so it must not inflate the
counts or take "none (map matches reality)" away from a healthy polyglot project. Parts are
counted by IMPORT edges only (see Runtime seams below for why) — there is no import edge
between such parts and there should not be.

## Emits (lean text)

* **`--view tree`** (default): modules grouped by top directory, each with summary + edges, ⟲ on cycle nodes;
* **`--view depth`**: same modules ordered by dependency depth (0 = leaves);
* **`--view seams-mermaid`**: every Runtime seam in the project, one mermaid diagram (see below);
* **`--edges`** out | in | inout — which edge directions to print (`→ uses` / `← used-by` / both);
* tail slices in both views: **hotspots** (most depended-on + leaves), **runtime seams bridging
  parts**, **cycles**, **runtime seams** (full list), **unresolved refs**.

**hotspots** splits by topology when there is more than one independent part: `independent
parts: N — …`, then `leaves in <part>` per part instead of one merged list (leaves are a
suggested READING ORDER, and a merged list offers a foreign part's files as the way into
yours). Files with no import edge in either direction are listed separately as `isolated
files` — a lone script or a package index is not an architecture, and counting it as a
"part" turned two real parts into a noisy four.

Edges come from the `File Path` column of each card's `In-Project Dependencies` table (old
`Dependencies Internal` heading, or its Russian alias, still resolve via `CARD_FORMAT.canon()`).

## Runtime seams (connections the import graph can't see)

A card's `## Runtime seams` table (dynamic load by path, a separate process, a shared file,
an event bus — see `make_interface_card.py --help-seams`) is a DIFFERENT kind of edge from an
import, and stays visually and structurally separate on purpose:

* Marker **`【SEAM⇢】`** (I declared this seam on the target) / **`【SEAM⇠】`** (someone declared
  a seam on ME — computed automatically, never hand-duplicated on the target's own card) — on
  its OWN line next to a module, for EVERY seam, not only the ones that happen to cross a part
  boundary (a file that dynamically loads its own sibling is just as real a fact). CJK tag
  brackets around a dashed arrow (not the plain `→`/`←` used for imports) so a text search for
  either never matches the other.
* **Does NOT merge independent parts** (reviewed 2026-09-14 — it used to, and that erased the
  exact fact "independent parts" exists to surface: these are architecturally different apps).
  Instead, a separate `> note:` line reports **"N Runtime seam(s) bridge otherwise-disconnected
  parts"**, naming which parts and by which Kind.
* **`## runtime seams (N)`** — a dedicated tail section listing every seam in the project
  (resolved AND free-text targets), independent of the parts/bridging note above.
* **`--view seams-mermaid`** — the same list assembled into one mermaid diagram (generated on
  the fly, never stored — see `Vision07__runtime-seams.md`); free-text targets appear here too,
  as their own node (the only view where they show up at all).

* **`--json`** — the graph as JSON. DRAFT feed for an external structure visualizer for the
  operator; for an LLM, use the text output.
