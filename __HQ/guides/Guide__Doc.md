# Guide: Doc — the tool doc surface (how a tool works NOW)

A tool's docs describe **how it actually works right now** — the lasting consequence of landed work.
Written/reconciled by `Role__Doc`. Distinct from its neighbour:

- **Vision** (`Vision01__<tool>.md`) = WHY / how it *should* work (intent, the contract).
- **Doc surface** = how it *does* work (reality): `<tool>__TLDR.md` + `<tool>__README.md` + the
  `TOOLS.md` row.

## What goes in

Practical, current facts a newcomer (human or agent) needs to USE the tool:
- what it does in one line (`TLDR`) and its full flag/output contract (`README`);
- concrete example invocations and the real output shape;
- what replaced what, when behavior changed.

Facts, not intent. If a statement stops being true, fix it (git keeps the history).

## Shape

- `<tool>__TLDR.md` — one screen: purpose + the few flags that matter + one example.
- `<tool>__README.md` — full `--help`-level: every mode/flag, output format, edge cases.
- `TOOLS.md` — one row per tool under its layer (source-analysis · card-map · maintenance).

Keep them short and current: a small change is a couple of edited lines; a new tool is a new
`TLDR` + `README` + a `TOOLS.md` row.
