# graph_from_cards

The project's topology from `__map/` cards — the "second compilation". Load it ONCE and
then reason in your head (impact / chain / layers); no need to re-read cards.

**Target:** `graph_from_cards.py [--project-root P] [--view packages|layers] [--edges out|in|inout]`
— default cards = `<project>/__map/`.

## Quick use
```
graph_from_cards.py                           # packages view (default), both edge directions
graph_from_cards.py --view layers             # 0=leaves → up toward entry points
graph_from_cards.py --edges out               # only "→ uses" (quieter; reading order)
graph_from_cards.py --edges in                # only "← used-by" (blast radius of a change)
graph_from_cards.py --zone _engine/embed.py   # focus slice around one module
graph_from_cards.py --cycles                  # circular deps as A → B → C → A
graph_from_cards.py --json                    # JSON draft for a visualizer
```

## Emits (lean text)

* **`--view packages`** (default): modules grouped by top dir, each with summary + edges, ⟲ on cycle nodes;
* **`--view layers`**: same modules ordered by dependency depth (0 = leaves);
* **`--edges`** out | in | inout — which edge directions to print (`→ uses` / `← used-by` / both);
* tail slices in both views: **hotspots** (most depended-on + leaves), **cycles**, **unresolved refs**.

Edges come from the `File Path` / "From file" column of each card's Internal-dependencies table
(English or Russian heading — works on old cards too).

* **`--json`** — the graph as JSON. DRAFT feed for an external structure visualizer for the
  operator; for an LLM, use the text output.
