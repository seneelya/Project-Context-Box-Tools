# graph_from_cards

The project's topology from `__map/` cards — the "second compilation". Load it ONCE and
then reason in your head (impact / chain / depth); no need to re-read cards.

**Target:** `graph_from_cards.py [--project-root P] [--view tree|depth] [--edges out|in|inout]`
— default cards = `<project>/__map/`.

## Quick use
```
graph_from_cards.py                           # tree view (default), both edge directions
graph_from_cards.py --view depth              # 0=leaves → up toward entry points
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
counts or take "none (map matches reality)" away from a healthy polyglot project. There is
no import edge between such parts and there should not be — their link is a runtime contract
(an event type, a REST path). Document that seam and point both cards' `Doc links` at the
doc, instead of expecting the graph to invent an edge it cannot verify.

## Emits (lean text)

* **`--view tree`** (default): modules grouped by top directory, each with summary + edges, ⟲ on cycle nodes;
* **`--view depth`**: same modules ordered by dependency depth (0 = leaves);
* **`--edges`** out | in | inout — which edge directions to print (`→ uses` / `← used-by` / both);
* tail slices in both views: **hotspots** (most depended-on + leaves), **cycles**, **unresolved refs**.

**hotspots** splits by topology when there is more than one independent part: `independent
parts: N — …`, then `leaves in <part>` per part instead of one merged list (leaves are a
suggested READING ORDER, and a merged list offers a foreign part's files as the way into
yours). Files with no import edge in either direction are listed separately as `isolated
files` — a lone script or a package index is not an architecture, and counting it as a
"part" turned two real parts into a noisy four.

Edges come from the `File Path` / "From file" column of each card's Internal-dependencies table
(English or Russian heading — works on old cards too).

* **`--json`** — the graph as JSON. DRAFT feed for an external structure visualizer for the
  operator; for an LLM, use the text output.
