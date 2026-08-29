# replace_in_files

Batch find-and-replace across files matching a glob mask — the migration/maintenance hand.
`<mask>` = which files (e.g. `*.py`); the replace is the action. Universal utility — no notion
of "the project", works on any folder you point it at.

**Target:** `replace_in_files.py PATH MASK --find "F" --with "W" [--match EXPR] (--dry-run or --apply)`
— `PATH`/`MASK` also as `--path`/`--mask` flags, same thing (don't mix the two forms for the same run).

## Quick use  (copy, tweak, run — no need to read further)
```
# preview first — default is dry-run, writes NOTHING:
replace_in_files.py <folder> "*.md" --find "OLD" --with "NEW"
# then apply:
replace_in_files.py <folder> "*.md" --find "OLD" --with "NEW" --apply
# recurse into subfolders:
replace_in_files.py . "*.py" --recurse --find "OLD" --with "NEW" --apply
# guarded — replace only on lines where a Python expr is true (spare the prose):
replace_in_files.py __map "*.md" --find "old heading" --with "new heading" --match 'line.startswith("## ")' --apply
# --path/--mask flag form (identical to the positional form above):
replace_in_files.py --path . --mask "*.py" --find "OLD" --with "NEW" --apply
# @ = CONFIG__TOOLS.PROJECT_ROOT, only when written explicitly (never implicit):
replace_in_files.py --path @ --mask "*.md" --find "OLD" --with "NEW" --dry-run
```

## Rules

* **Default is DRY-RUN** — nothing is written unless you pass `--apply` explicitly.
* **`--find X --with Y`** — exactly one replacement rule per invocation (not a list of pairs).
* **`--match EXPR`** — guarded replace: only on lines where the Python expression `EXPR` is true
  (`line`, `re` module, basic builtins available) — a guard against touching prose, not just headings.
* **`--recurse`** — recurse into subfolders (bare run is top-level only).
* **`--verbose`** — shows the changed lines with their line numbers, not just a count.
* Masks `*`/`*.*` are refused for `--apply` (too broad) — forced to dry-run regardless.
* Dangerous system paths (`/etc/`, `C:\Windows`, …) and binary extensions are refused outright.
* Escapes `\n \t \r \\` in `--find`/`--with` are decoded (insert real newlines/tabs); `--match` is
  left as raw Python, not escape-decoded.

Full flag contract (exact list, edge cases) — `replace_in_files.py --help`.
