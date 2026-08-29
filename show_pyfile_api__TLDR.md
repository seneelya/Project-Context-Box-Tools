# show_pyfile_api

Python-only AST hint for a card writer — an OPTIONAL aid, **not a gate** and not a substitute
for reading the code. Parses one `.py` file via stdlib `ast` and prints a compact summary.

**Target:** `show_pyfile_api.py <file.py>` (or `--file <file.py>`, same thing) — reads only, never
writes, never crashes on valid Python.

## Quick use
```
show_pyfile_api.py <path>/<file>.py         # public funcs/classes/methods + imports + docstring line
show_pyfile_api.py --file <path>/<file>.py  # same, flag form (unifies with find_code_usage/get_codeblock)
```

## Prints

* public **functions** with signatures;
* public **classes** and their public **methods**;
* **imports**, heuristically split into "looks internal" vs "external/stdlib";
* the module docstring's first line.

Note: `make_interface_card` calls `show_pyfile_api.collect()` internally for the declared Python surface — running
`show_pyfile_api` by hand is just a quick look when you want the AST view without stamping a full card.
