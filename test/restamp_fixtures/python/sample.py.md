# sample.py

Sample module for merge-identity manual tests (REQ-004+005).

## Public API

### Functions
#### `unchanged_fn(x)`
consumers 0
PROSE_UNCHANGED — must survive a re-stamp byte-for-byte, no markers.
#### `became_async_fn(x)`
consumers 0
PROSE_SIG_CHANGED — source gained `async` + a new parameter; same identity, different shape.
#### `checkValue(x)`
consumers 0
PROSE_RENAMED — source renamed this to `check_value`; close enough to match by similarity.
#### `obsolete_helper(x)`
consumers 0
PROSE_REMOVED — source no longer has this function at all; must land in `## Salvage`.

## Dependencies Internal

(none)

## Dependencies External

(none)

## How it works

Manual fixture for REQ-004+005 identity-resolution — see test/restamp_fixtures/README.md.

## Doc links

(none)

## Discrepancies

(none)
