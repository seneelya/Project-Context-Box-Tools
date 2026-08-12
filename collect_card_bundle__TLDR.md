# collect_card_bundle

Call-saver: a target card's **full text + only the Public API of its dependencies**, glued into
one block. Instead of N card reads, the agent makes one call and gets the context it needs.

**Target:** `collect_card_bundle.py <file> [--cards-dir P] [--depth N]` — `<file>` is root-relative
(e.g. `capture.py`, `_engine/embed.py`).

## Quick use
```
collect_card_bundle.py <file>              # target card + its deps' Public API
collect_card_bundle.py <file> --depth 2    # expand deps transitively
```

## Behaviour

* pulls the target's whole card, then from each dependency slices out **only `## Public API`**;
* dependencies come from the graph (`graph_from_cards.build_graph`, the "From file" column);
* **`--depth N`** expands transitively (default `1` = direct deps only).

Thin topology → `graph_from_cards`; this is the thick layer (API) pulled on demand.
