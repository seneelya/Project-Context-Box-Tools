# sample.ts

Sample module for merge-identity manual tests (REQ-004+005).

## Public API

### Functions
#### `function isOurTool(name: string)`
consumers 0
PROSE_UNCHANGED — must survive a re-stamp byte-for-byte, no markers.
#### `function loadIt(x)`
consumers 0
PROSE_SIG_CHANGED — source gained `async`; same identity, different shape.
#### `function obsoleteHelper(x)`
consumers 0
PROSE_REMOVED — source no longer has this function at all; must land in `## Salvage`.

### Constants
#### `const OUR_TOOLS = ['read_file', 'write_file']`
consumers 0
PROSE_RENAMED — source renamed this to `ALLOWED_TOOLS`; close enough to match by similarity.

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
