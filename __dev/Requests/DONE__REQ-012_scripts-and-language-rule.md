добавить поддержку бат и ps1  sh файлов

добавить общие правила  Language.md  к самому проекту. Кратко на каком языке писать что.
## Done (2026-10-06)

- Scripts in get_codeblock: `.sh .bash` = brace profile `reader/profiles/bash.py` (functions + loops;
  bash `if`/`case` have no body node -> bands); `.ps1 .psm1` = own Spec over tree-sitter-powershell
  (`reader/backends/powershell.py`, wrappers spliced, generic addressing); `.bat .cmd` = zero-dep
  `reader/backends/batch.py` (labels = sections). `--name` exact on all three. Sweep clean on real
  scripts (llama.cpp ci, ai-memory-hermes-plugin, beellama sycl). Fixtures `test/scriptSRC/`.
- One ext -> language map: core.py's 3 copies and test/check.py's copy now use
  `reader.reader.language_for_ext`; the full wiring list is in `reader/CONTRACT.md` (Recipe A).
- Language rule: template `__HQ/guides/Guide__Language.md` (instructions English, the rest in the
  owner's language), linked from START and the guides.
