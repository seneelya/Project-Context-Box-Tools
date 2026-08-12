# py_api

Python-only AST hint for a card writer — an OPTIONAL aid, **not a gate** and not a substitute
for reading the code. Parses one `.py` file via stdlib `ast` and prints a compact summary.

**Target:** `py_api.py <file.py>` — reads only, never writes, never crashes on valid Python.

## Quick use
```
py_api.py <path>/<file>.py     # public funcs/classes/methods + imports + docstring line
```

## Prints

* public **functions** with signatures;
* public **classes** and their public **methods**;
* **imports**, heuristically split into "looks internal" vs "external/stdlib";
* the module docstring's first line.

Note: `make_interface_card` calls `py_api.collect()` internally for the declared Python surface — running
`py_api` by hand is just a quick look when you want the AST view without stamping a full card.
