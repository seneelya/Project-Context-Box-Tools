# mask_replace

Batch find-and-replace across files matching a mask — the migration/maintenance hand.

**Target:** `mask_replace.py <folder> <mask> [-r FIND WITH | -m EXPR FIND WITH] [-R]`

## Rules

* **`-r FIND WITH`** — plain substring replace.
* **`-m EXPR FIND WITH`** — replace only on lines where the Python **`EXPR`** is true (env:
  `line`, `re`) — a guard against touching prose. Safe eval: string/number/type builtins only.
* Multiple `-r`/`-m` allowed; applied **in command-line order**.
* **`-R`** — recurse into subfolders.
* In `FIND`/`WITH`, escapes `\n \t \r \\` are decoded (the `-m` expression is left raw).

Line endings are preserved. Example — rename a token repo-wide:
```
mask_replace.py . "*.py" -R -r "tools_config" "CONFIG__TOOLS"
```
Example — replace only on a heading line (not in prose):
```
mask_replace.py __map "*.md" -R -m 'line.strip()=="## Публичный API"' "## Публичный API" "## Public API"
```
