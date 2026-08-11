"""Markdown handler for get_codeblock — sections by heading hierarchy.

Unlike code handlers, a Markdown "block" is a heading section: `## X` owns everything
until the next heading of the same or higher level. Level = heading depth (no +1: the
heading and its body are one section at that level). Root/preamble text = level 1.
Fenced code blocks (``` / ~~~) are skipped so a `#` inside them isn't read as a heading.
"""

import re

_ATX = re.compile(r'^(#{1,6})\s+(.*?)\s*#*\s*$')
_FENCE = re.compile(r'^(```+|~~~+)')


def _headings(lines):
    """Return [(idx, level, text)] for ATX headings, ignoring fenced code blocks."""
    out = []
    fence = None
    for i, line in enumerate(lines):
        s = line.strip()
        if fence is not None:
            if s.startswith(fence):
                fence = None
            continue
        f = _FENCE.match(s)
        if f:
            fence = f.group(1)[:3]  # closing fence must be at least as long; match on marker
            continue
        m = _ATX.match(line)
        if m:
            out.append((i, len(m.group(1)), m.group(2).strip()))
    return out


def _section_end(hs, k, nlines):
    """1-based inclusive end line of the section headed by hs[k]."""
    level = hs[k][1]
    for j in range(k + 1, len(hs)):
        if hs[j][1] <= level:
            return hs[j][0]  # line just before the next same/higher heading
    return nlines


class MarkdownHandler:

    def line_level(self, lines, idx):
        """Heading depth of the section containing line idx (0-based). Root = 1."""
        if idx < 0 or idx >= len(lines):
            return 1
        active = 1
        for hidx, level, _t in _headings(lines):
            if hidx <= idx:
                active = level
            else:
                break
        return active

    def get_blocks(self, file_path, target_line):
        """Enclosing heading sections for a line, outermost → innermost."""
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        if not lines:
            return []
        idx = target_line - 1
        if idx < 0 or idx >= len(lines):
            return []

        hs = _headings(lines)
        n = len(lines)
        if not hs:
            return [{'level': 1, 'start': 1, 'end': n}]

        # active heading = last one at/above idx
        k = -1
        for j, (hidx, _lvl, _t) in enumerate(hs):
            if hidx <= idx:
                k = j
            else:
                break
        if k == -1:
            return [{'level': 1, 'start': 1, 'end': hs[0][0]}]  # preamble before first heading

        # enclosing chain: walk back collecting strictly-decreasing heading levels
        chain = []
        cur = 10 ** 9
        j = k
        while j >= 0:
            lvl = hs[j][1]
            if lvl < cur:
                chain.append(j)
                cur = lvl
            j -= 1
        chain.reverse()  # outermost first

        return [
            {'level': hs[j][1], 'start': hs[j][0] + 1, 'end': _section_end(hs, j, n)}
            for j in chain
        ]

    def outline(self, lines, max_level=None):
        """Table of contents: [{level, text, start, end}] for every heading."""
        hs = _headings(lines)
        n = len(lines)
        out = []
        for k, (hidx, level, text) in enumerate(hs):
            if max_level and level > max_level:
                continue
            out.append({'level': level, 'text': text, 'start': hidx + 1, 'end': _section_end(hs, k, n)})
        return out
