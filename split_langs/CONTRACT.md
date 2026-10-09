# CONTRACT — a split_monster language module

`split_monster.py` talks only to `split_langs` (registry), never `if language == …`. A module is
`split_langs/<name>.py` + its name in `_MODULES` (`__init__.py`). Missing required items fail
LOUDLY at load (`ValueError`), not as silently empty hints. Unclaimed extensions get `other.py`
(cut/replace work, no hints/imports/graph — the generated script says so).

## Required

| item | meaning |
|---|---|
| `NAME`, `EXTENSIONS` | canonical name; extensions with the dot, lower case, owned by ONE language |
| `declared_names(text, ext) -> [str]` | top-level names a block declares, in order (a banded range has several) |
| `top_level_names(lines, ext) -> set` | top-level names of a whole file / remaining text |
| `identifiers(text, ext) -> set` | names the text USES — never words in comments/strings |
| `decl_line(text, ext) -> str` | the block's declaration line for the preview comment |
| `name_from_decl(decl) -> str\|None` | name out of that preview line (used by `--rebase`) |
| `source_imports(lines, ext) -> {spec: {"kind", "items": [(orig, local)]}}` | the file's leading imports |
| `render_import(spec, kind, items) -> str` | one import statement for a SUBSET of a specifier's names |

## Optional (defaults in `_Defaults`)

`HAS_NAMES=True` · `CUT_LEVEL=1` (md: 0) · `STUBS=False` (md: True — source keeps a stub) ·
`CONSUMERS=False` (make_interface_card understands the language) · `GRAPH=False` (True needs
`file_spec(from, to)` and `import_insert_index(segs, ext)`) · `ref_pattern(name)` · `export_problem(name,
block_text)` · `notes(lines, ext)` (warnings for the generated script) · `syntax_ok(data, ext)` (default: get_codeblock's tree-sitter `has_error`).

`treesitter.py` is the generic module: every tree-sitter language of get_codeblock listed in its
`EXTENSIONS` gets names / identifiers / import band from get_codeblock's `Spec` — no per-language code.

## Donors (don't reinvent — import)

get_codeblock `Spec`/`backend.root` (names, identifiers, `imports:` outline band), find_code_usage
handlers/resolvers (imports, specifiers, TS aliases, C++ includes), stamp_langs `declared()`
(`all_defs` − `exports` = private names). Python stays on stdlib `ast`.
