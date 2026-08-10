# Tools

Each tool has a corresponding  `<name>__TLDR.md` with usage guidance and exposes its complete CLI interface through --help.

- codebase_import_search.py — finds where `symbols` from a target module are used across the project.
- get_codeblock.py — gets `code block` containing a line N in a file, with optional query for exact parent blocks.






## Configuration notes
When `tools_config.py` exists, `PROJECT_ROOT`, `LANGUAGE`, and `TEST_DIRS` are used as defaults.  (overridden by CLI `--project-root` , .. )

Language is auto-detected from file extension: `.py`, `.ts`, `.js`, `.cs`.

Supported languages: Python (indentation-based), TypeScript/JavaScript (brace matching with string/template literal awareness), C# (brace matching with verbatim strings)

