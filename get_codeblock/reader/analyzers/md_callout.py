"""Markdown section summary for the outline (REQ-024) — an Analyzer (CONTRACT.md, Recipe C).

A section's summary is a typed callout (`> [!info] ...`, any type, any case) as the first
non-blank line under its heading. A plain quote `> text` is not a summary, and nothing is
guessed from the body. The whole callout counts: consecutive `>` lines plus lazy
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
        i, end = block.start, min(block.end, len(lines))   # 1-based heading -> 0-based next line
        while i < end and not lines[i].strip():
            i += 1
        m = _CALLOUT.match(lines[i].rstrip('\r\n')) if i < end else None
        if not m:
            return None
        parts = [m.group(2)]
        for ln in lines[i + 1:end]:
            ln = ln.rstrip('\r\n')
            if not ln.strip() or _BREAK.match(ln):
                break
            q = _QUOTE.match(ln)
            parts.append(q.group(1) if q else ln)    # lazy continuation: the line as is
        text = ' '.join(' '.join(parts).split())
        if len(text) > SUMMARY_CAP:
            text = text[:SUMMARY_CAP].rstrip() + '…'
        return f"[{m.group(1).lower()}] {text}".rstrip()
