# rebuild_graph

The project's flat topology from `__map/` cards — the "second compilation". Load it ONCE and
then reason in your head (impact / chain / layers); no need to re-read cards.

**Target:** `rebuild_graph.py [--cards-dir P] [--json]` — default cards = `<project>/__map/`.

## Emits (lean text)

* every module: id (root-relative source path) + one-line summary + `depends_on`;
* derived slices: **entry points** (most depended-on), **leaves**;
* **unresolved refs** at the end — links that matched no card (a signal to normalize).

Edges come from the `File Path` / "From file" column of each card's Internal-dependencies table
(English or Russian heading — works on old cards too).

* **`--json`** — the graph as JSON. DRAFT feed for an external structure visualizer for the
  operator; for an LLM, use the text output.
