# Sample.cs

Sample module for merge-identity manual tests (REQ-004+005).

## Public API

### Classes
#### `public static class UnchangedThing`
consumers 0
PROSE_UNCHANGED — must survive a re-stamp byte-for-byte, no markers.
#### `public class BecameSealed`
consumers 0
PROSE_SIG_CHANGED — source became `sealed`; same identity, different shape.
#### `public class NetworkTools`
consumers 0
PROSE_RENAMED — source renamed this to `AllowedNetworkTools`; close enough to match by similarity.
#### `public class ObsoleteThing`
consumers 0
PROSE_REMOVED — source no longer has this class at all; must land in `## Salvage`.

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
