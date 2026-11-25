# check_doc_info — TLDR

Finds markdown files whose sections lack the summary callout `> [!info] ...` (Guide__Doc,
Guide__Outline) that `get_codeblock --outline` shows after a heading. Zero dependencies.

```
python __HQ/tools/check_doc_info.py __HQ/docs          # every *.md below; only the files with problems
python __HQ/tools/check_doc_info.py __HQ/docs --all    # also the files that pass (OK lines)
python __HQ/tools/check_doc_info.py some.md other.md
```

**The rule (hardcoded in the tool's header, `MIN_SHARE` 0.5):** inside every heading block, and the
file's top level, at least half of the direct child sections carry a typed callout (`> [!type]`, any
type, anywhere in the section's own body before the next heading). Not every section needs one, so
the check is by share, not per section. Code fences are skipped; a plain `> quote` does not count.

Output: `BAD <file>: looks like this file has problems with its summaries`, then one line per block
below the share (`L<line> <title>: k of n child sections have a callout`). Exit 0 all pass, 1 a
file has problems, 2 a path not found.

Use: after writing or reconciling docs (Role__Doc), before the commit; then fix the reported blocks
by adding a one-line callout with the main fact under the child headings.
