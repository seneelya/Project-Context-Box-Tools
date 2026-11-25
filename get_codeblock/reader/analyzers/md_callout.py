"""Markdown section summary for the outline (REQ-024) — an Analyzer (CONTRACT.md, Recipe C).

A section's note is a typed callout (`> [!info] ...`, any case) anywhere in the section's own
body (up to its first child heading; fenced code skipped). Several -> by type: summary, info,
note, any other, warning last; the first of the best type wins. A plain quote `> text` is not a
note, and nothing is guessed from prose. The whole callout counts: consecutive `>` lines plus lazy
continuations, up to a blank line or a new block. Markers are dropped, lines joined with a
space, spaces squeezed, the text cut to SUMMARY_CAP with `…`. Result: `[info] text`.
Structure (role/range/children) is never touched — only `block.description`.
"""

import re

from ...physical_lines import split_lines

SUMMARY_CAP = 200

_CALLOUT = re.compile(r'^ {0,3}>[ \t]?\[!([A-Za-z][\w-]*)\][+-]?[ \t]*(.*)$')
_QUOTE = re.compile(r'^ {0,3}>[ \t]?(.*)$')
# a new block ends a lazy continuation: heading, code fence, thematic break
_BREAK = re.compile(r'^ {0,3}(#{1,6}([ \t]|$)|```|~~~|([-*_])([ \t]*\3){2,}[ \t]*$)')
_FENCE = re.compile(r'^ {0,3}(```|~~~)')
_HEADING = re.compile(r'^ {0,3}#{1,6}([ \t]|$)')
# which callout is the section's note: summary, info, note, any other type, warning last
_RANK = {'summary': 0, 'info': 1, 'note': 2, 'warning': 4}
_OTHER = 3


class CalloutAnalyzer:
    """`describe(block, source)` -> `[type] text` for a heading block, else None."""

    def __init__(self):
        self._src = None
        self._lines = []

    def describe(self, block, source):
        if block.kind != 'heading':
            return None
        if source is not self._src:                 # one split per file, not per block
            self._src, self._lines = source, split_lines(source)
        lines = self._lines
        end = min(block.end, len(lines))
        best = None                                 # (rank, kind, text)
        fence = False
        i = block.start                             # 1-based heading -> 0-based next line
        while i < end:
            ln = lines[i].rstrip('\r\n')
            if _FENCE.match(ln):
                fence = not fence
            elif not fence and _HEADING.match(ln):
                break                               # own body only: a child section has its own note
            elif not fence and (m := _CALLOUT.match(ln)):
                kind = m.group(1).lower()
                rank = _RANK.get(kind, _OTHER)
                i, text = _collect(lines, i, end, m.group(2))
                if best is None or rank < best[0]:
                    best = (rank, kind, text)
                    if rank == 0:
                        break
                continue
            i += 1
        if best is None:
            return None
        _r, kind, text = best
        if len(text) > SUMMARY_CAP:
            text = text[:SUMMARY_CAP].rstrip() + '…'
        return f"[{kind}] {text}".rstrip()


def _collect(lines, i, end, first):
    """The callout starting at line i: (next line index, its text joined into one line)."""
    parts = [first]
    i += 1
    while i < end:
        ln = lines[i].rstrip('\r\n')
        if not ln.strip() or _BREAK.match(ln) or _CALLOUT.match(ln):
            break
        q = _QUOTE.match(ln)
        parts.append(q.group(1) if q else ln)        # lazy continuation: the line as is
        i += 1
    return i, ' '.join(' '.join(parts).split())
