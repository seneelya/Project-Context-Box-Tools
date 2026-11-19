# Plan14 — module purpose for importers (`(auto)` Why lines)

## Цель

У модулей, роль которых одинакова для всех импортёров (базовые типы: `vec3.h`, `time.h`), назначение
пишется ОДИН раз — в карточке самого модуля. Штамп сам ставит его в строку Why у каждого импортёра с
меткой `(auto)`. Агенты больше не пишут по 60 одинаковых «`Vec3d` places».

## Background (settled, do not re-open)

- Measured on sim (767 cards, 2026-11-19): 2138 Why lines, 724 empty = 39 % of all empty slots. An
  importer-count threshold is NOT the rule: >=10 importers removes half the lines, but useful ones too
  (`session.h`, `elements.h`, where agents write the real link). The field is set by a person/agent
  per module; the count only suggests candidates. Script: `C:\RAM_Cache\Temp\req018\why_fanin.py`
  (sim cards: `Y:\AgentsWork\dVOrbitals\sim\__HQ\__map`).
- Already done (2026-11-19): `AUTO_MARK = "(auto)"` in `make_interface_card.py`. A Why line starting
  with it is stamp-owned: `_parse_why_section` drops it, the stamp writes it again. An agent who
  rewrites the line drops the mark -> prose, kept. `_why_lines(keys, key_dir, why, ready)` takes
  `ready {key: text}`; own header (`OWN_PAIR_WHY`, hook `stamp_langs.own_pair`) uses it.
  Test: `test/test_own_pair_why.py`.
- Owner decisions (2026-11-19):
  1. The field lives in the module's OWN card, not in a separate registry file (a registry drifts
     on rename/delete; the card moves with the file).
  2. Place: the line right under the one-line summary after H1:
     `Why for importers: 3D vector and quaternion types.`
  3. First pass: only `(auto)` lines follow the field. A warning for agent-written lines whose
     dependency's field changed — LATER (step 6, separate go from the owner).

## Read code with our tools (owner's rule)

Use `get_codeblock` for every read — `python get_codeblock.py --file F --outline`, then
`--name NAME` or `--line N --query` (TLDR: `get_codeblock__TLDR.md`). Do not read whole files.
grep only for "where is this name called". Places (lines as of 2026-11-19, re-check by outline):

- `make_interface_card.py`: `_parse_old_prose` [538-656] (summary at ~560), `build_card` [662-951]
  (summary emit ~743, In-Project Dependencies + `ready` ~820-855), `_why_lines` [209-230],
  `_stamp_to_file` [960-983], `_stamp_all` [1126-1208], `_card_path` [954-957].
- `CARD_FORMAT.py`: docstring [1-93] (format description), `VERSION = "1.5.0"` (~266).
- `validate_cards.py`, `check_cards_freshness.py` (`check` [225-268]).
- Guides (ProjectStarter repo): `__HQ/guides/Guide__MakeCard.md` (Step 3, `(auto)` note),
  `__HQ/guides/Guide__AuditCards.md`.

## Steps

1. **Format.** `CARD_FORMAT.py`: constant `FOR_IMPORTERS = "Why for importers:"`, describe it in the
   docstring (optional line right after the summary; one line; only for modules with one role for all
   importers). `VERSION` -> 1.6.0. Check every reader of "summary = first non-empty line after H1"
   (`validate_cards`, `graph_from_cards`, `collect_card_bundle`, `_parse_old_prose`) — the field is the
   SECOND line, it must not become the summary and must not break "summary present" checks.
2. **Keep it on re-stamp.** `_parse_old_prose`: read the line into `P["for_importers"]`; `build_card`
   writes it back right after the summary. The stamp never creates it (it is prose: a person/agent
   writes it). Test: field survives re-stamp byte-for-byte; a card without it is unchanged.
3. **Validate.** `validate_cards`: accept the line; flag an empty value or a second such line.
4. **Fill importers.** `build_card` gets `cards_dir=None` (passed from `_stamp_to_file`/`_stamp_all`,
   which already know it). For each resolved in-project dep: read the dep's card
   (`_card_path(cards_dir, r["file"])`), take its field, `ready[key] = f"{AUTO_MARK} {text}"`. Own
   header wins over the field. No card / no field -> the directive as now. Folding (`_why_lines`)
   never folds a ready line (already so). Note in the code: with `--all` the dep's field comes from
   its EXISTING card — a field written just now reaches importers on the next stamp of each importer.
5. **Freshness for `(auto)`.** `check_cards_freshness`: an importer card whose `(auto)` line differs
   from the dep's current field (or whose dep has a field but the line is still a directive) ->
   "stale: re-stamp" with the reason. Cheap: read the importer card + its deps' cards.
6. **LATER, separate go:** agent-written line under a changed field -> warning. Needs a stored
   fingerprint of the field the line was written against; design it then.

## Tests (new file `test/test_for_importers.py`, synthetic tree, no real project code)

- module card with the field -> importer gets `- \`vec3\` — (auto) <field>`;
- field changed -> after re-stamp the `(auto)` line follows; an agent line (no mark) stays;
- no field -> directive; own header + field -> own header line;
- field kept on re-stamp of the module card; validate accepts; freshness flags the stale `(auto)`.
- Regression before commit: `test_cardstamp`, `test_cpp`, `test_glsl_stamp`, `run_restamp_fixtures`,
  `test_own_pair_why`, `check.py --fails` (venv `T:/AgentsWork/venv/Scripts/python.exe`).

## Docs

`Guide__MakeCard.md` (when to write the field, `(auto)` lines), `Guide__AuditCards.md` (format 1.6.0,
the field), `make_interface_card__TLDR.md`, `validate_cards__TLDR.md`, `check_cards_freshness__TLDR.md`
if its output changes, `__dev/CONTEXT_RESTORE.md` (format version). Tracker entry per step.

## Done when

Steps 1-5 landed with tests green; on a COPY of sim cards: write the field into `vec3.h`/`time.h`
cards, re-stamp their importers, count the Why directives that disappeared (expect ~100+ of 724).
Rollout to projects — only on the owner's word.
