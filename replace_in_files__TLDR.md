# replace_in_files

Batch find-and-replace across files matching a glob mask — the migration/maintenance hand.
`<mask>` = which files (e.g. `*.py`); the replace is the action.

## Quick use  (copy, tweak, run — no need to read further)
```
# preview first — count replacements, write NOTHING:
replace_in_files.py <folder> "*.md" -R -n -r "OLD" "NEW"
# then apply (drop -n):
replace_in_files.py <folder> "*.md" -R -r "OLD" "NEW"
# several file types = one run per mask:
replace_in_files.py . "*.py" -R -r "OLD" "NEW"
# guarded — replace only on lines where a Python expr is true (spare the prose):
replace_in_files.py __map "*.md" -R -m 'line.strip()=="## X"' "X" "Y"
```

**Target:** `replace_in_files.py <folder> <mask> [-r FIND WITH | -m EXPR FIND WITH] [-R] [-n]`

## Rules

* **`-n` / `--dry-run`** — report replacement count per file + a total; write nothing. Preview before applying.
* **`-r FIND WITH`** — plain substring replace.
* **`-m EXPR FIND WITH`** — replace only on lines where the Python **`EXPR`** is true (env: `line`,
  `re`) — a guard against touching prose. Safe eval: string/number/type builtins only.
* Multiple `-r`/`-m` allowed; applied **in command-line order**.
* **`-R`** — recurse into subfolders.
* In `FIND`/`WITH`, escapes `\n \t \r \\` are decoded (the `-m` expression is left raw). Line endings preserved.
