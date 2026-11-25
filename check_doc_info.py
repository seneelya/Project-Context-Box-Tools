"""check_doc_info: find markdown files whose sections lack their summary callouts.

The rule (Guide__Doc, Guide__Outline): a section opens with a typed callout `> [!info] ...` that
`get_codeblock --outline` shows after the title. Not every section needs one, so the check is by
share: inside every heading block (and the file itself), at least MIN_SHARE of its direct child
sections must carry a callout in their own body (anywhere before the next heading, as
get_codeblock finds it). A file that breaks the rule anywhere is reported:
"Looks like this file has problems with its summaries".

Usage:
    python check_doc_info.py <file.md | dir> [...]     # dirs: every *.md below them
    python check_doc_info.py docs --all                 # also list the files that pass

Exit code: 0 all files pass, 1 a file has problems, 2 bad arguments.
"""
import argparse
import re
import sys
from pathlib import Path

# The hardcoded rule (no config yet).
MIN_SHARE = 0.5            # at least this share of a block's children carry a callout
FILE_GLOB = '*.md'         # what a directory argument expands to (recursively)

HEADING = re.compile(r'^(#{1,6})\s+(.*?)\s*#*\s*$')
FENCE = re.compile(r'^\s*(```|~~~)')
CALLOUT = re.compile(r'^\s*>\s*\[![A-Za-z][\w-]*\]')


class Node:
    def __init__(self, level, title, line):
        self.level, self.title, self.line = level, title, line
        self.info = False
        self.kids = []


def parse(text):
    """The heading tree of a markdown text; a node's `info` is a callout in its own body."""
    root = Node(0, '(file)', 0)
    stack = [root]
    fence = None
    for n, line in enumerate(text.splitlines(), 1):
        m = FENCE.match(line)
        if m:
            fence = None if fence == m.group(1) else (fence or m.group(1))
            continue
        if fence:
            continue
        h = HEADING.match(line)
        if h:
            node = Node(len(h.group(1)), h.group(2), n)
            while stack[-1].level >= node.level:
                stack.pop()
            stack[-1].kids.append(node)
            stack.append(node)
        elif CALLOUT.match(line):
            stack[-1].info = True
    return root


def problems(root):
    """(line, title, with_info, kids) of every block whose children fall below MIN_SHARE."""
    out = []

    def walk(node):
        if node.kids:
            have = sum(k.info for k in node.kids)
            if have < MIN_SHARE * len(node.kids):
                out.append((node.line, node.title, have, len(node.kids)))
        for k in node.kids:
            walk(k)

    walk(root)
    return out


def files_of(args):
    for a in args:
        p = Path(a)
        if p.is_dir():
            yield from sorted(p.rglob(FILE_GLOB))
        elif p.is_file():
            yield p
        else:
            print(f'not found: {a}', file=sys.stderr)
            sys.exit(2)


def main():
    ap = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='Find markdown files whose sections lack their summary callouts (> [!info] ...).',
        epilog='''the rule (MIN_SHARE 0.5 in the header):
  inside every heading block, and the file's top level, at least half of the direct child
  sections carry a typed callout:   > [!info] <the main fact of the section>
  any type counts (info, note, summary ...), anywhere in the section's own body before the
  next heading; a plain "> quote" does not; code blocks are skipped.
  Not every section needs one, so the check is by share, not per section.

why: get_codeblock --outline shows the callout after the title, so the outline reads as an
  annotated table of contents (Guide__Doc, Guide__Outline).

exit: 0 all files pass, 1 a file has problems, 2 a path not found.
more: check_doc_info__TLDR.md''')
    ap.add_argument('paths', nargs='+', help='markdown files or directories')
    ap.add_argument('--all', action='store_true', help='also list the files that pass')
    a = ap.parse_args()
    bad = 0
    for f in files_of(a.paths):
        found = problems(parse(f.read_text(encoding='utf-8', errors='replace')))
        if not found:
            if a.all:
                print(f'OK   {f}')
            continue
        bad += 1
        print(f'BAD  {f}: looks like this file has problems with its summaries')
        for line, title, have, kids in found:
            where = f'L{line} {title}' if line else '(the file top level)'
            print(f'       {where}: {have} of {kids} child sections have a callout')
    if bad:
        print(f'{bad} file(s): add `> [!info] <the main fact>` under the headings (Guide__Doc, Guide__Outline).')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
