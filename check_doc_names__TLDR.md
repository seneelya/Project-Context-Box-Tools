# check_doc_names — TLDR

> **A ROUGH CHECK, NOT A PROOF.** It finds code names and file paths a markdown doc quotes that no
> longer exist. A name that still sits in a comment passes; a math symbol written like a name alarms;
> the truth of the doc's sentences is not checked at all. Rough is still better than none.

```
python __HQ/tools/check_doc_names.py __HQ/docs                 # sources: CONFIG__TOOLS.PROJECT_ROOT
python __HQ/tools/check_doc_names.py __HQ/docs --root <src>    # another source root
python __HQ/tools/check_doc_names.py some.md --hq <HQ>         # the HQ whose files a doc may name
```

**What is checked.** Every `backticked` token of the doc (code blocks skipped):
- **a file token** (a known extension at its end, or a folder ending with `/`) must exist under the
  sources, the HQ (`notes/`, `plans/`, `reports/` ...) or the doc's own folder; a bare name may lie
  anywhere; `src/batch*.cpp`, `src/x.*` are globs, `a.h/.cpp` is two files;
- **a name token** split into identifiers; one shaped like code (CamelCase inside, snake_case,
  `kConstant`, `ALL_CAPS`, at least 3 characters) must be a whole word of some code file (`CODE_EXT` in
  the header; `BLACKLIST_DIRS` of the config and `__HQ` skipped) or a file's stem (`get_codeblock`,
  `Doc__10`); `name*` is a prefix.
- **Placeholders** of a series read as wildcards: `TASKn.md`, `bench_roundN.cpp`, `contact_testsN`.

**False alarms** (math symbols `r_apo`, system macros `FLT_MAX`, files outside the project): silence
them per doc with an HTML comment anywhere in it (invisible when rendered):
`<!-- check_doc_names: ignore r_apo FLT_MAX ctime.exe -->`.

Output: `CHECK <doc>: N names, not found: k names, m paths`, then `L<line> <name>` / `L<line> path <p>`.
Exit 0 nothing reported, 1 something not found, 2 bad arguments.

Use: after reconciling docs (Role__Doc) and in the session-end ritual, next to `check_doc_info`. A
finding is a question, not a verdict: renamed in the code -> fix the doc; a math symbol -> ignore it.
