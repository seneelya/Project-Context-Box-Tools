#!/usr/bin/env python3
"""Ручной/CI полигон для merge-идентичности карточек (REQ-004+005) — см. restamp_fixtures/README.md.

Каждый язык в `restamp_fixtures/<lang>/` — пара «источник + карточка ДО» вручную собранная так,
чтобы ОДНИМ прогоном показать все пять исходов identity-resolution: не изменилось / поменялась
сигнатура / переименовали / удалили / появилось новое. Тест копирует карточку в `.actual/` (сама
`sample.*.md` рядом с источником НИКОГДА не перезаписывается) и штемпелит копию.

Запуск:
    py test/run_restamp_fixtures.py            # прогнать все языки, точки + сводка
    py test/run_restamp_fixtures.py --diff     # плюс unified diff «до/после» на каждый язык
    py test/run_restamp_fixtures.py python     # только один язык (имя папки в restamp_fixtures/)

Exit 0 = всё ок, 1 = есть провал. Результат штемпеля остаётся в `restamp_fixtures/<lang>/.actual/`
(гитигнорится) — можно открыть глазами после прогона, это и есть «место для тестирования».
"""

import difflib
import os
import shutil
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
for p in (_TOOLS, _HERE):
    if p not in sys.path:
        sys.path.insert(0, p)
sys.stdout.reconfigure(encoding="utf-8")

import make_interface_card as mic  # noqa: E402  (путь уже поставлен выше)

_FIXTURES = os.path.join(_HERE, "restamp_fixtures")
_SHOW_DIFF = "--diff" in sys.argv
_ONLY = [a for a in sys.argv[1:] if not a.startswith("-")]

_PASS = 0
_FAIL = 0


def check(lang, name, cond):
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        sys.stdout.write(".")
    else:
        _FAIL += 1
        sys.stdout.write(f"\nFAIL [{lang}]: {name}\n")


# Каждый язык — своя пара имён на пять исходов (сами файлы см. restamp_fixtures/<lang>/).
# ЯЗЫК: (source filename, unchanged, sig_changed, renamed_old, renamed_new, removed, brand_new)
_CASES = {
    "python": ("sample.py", "unchanged_fn", "became_async_fn", "checkValue", "check_value",
               "obsolete_helper", "brand_new_fn"),
    "typescript": ("sample.ts", "isOurTool", "loadIt", "OUR_TOOLS", "ALLOWED_TOOLS",
                   "obsoleteHelper", "BRAND_NEW_CONST"),
    "csharp": ("Sample.cs", "UnchangedThing", "BecameSealed", "NetworkTools", "AllowedNetworkTools",
               "ObsoleteThing", "BrandNewThing"),
}


def run_one(lang):
    src_name, unchanged, sig_changed, ren_old, ren_new, removed, brand_new = _CASES[lang]
    lang_dir = os.path.join(_FIXTURES, lang)
    before_card = os.path.join(lang_dir, src_name + ".md")
    actual_dir = os.path.join(lang_dir, ".actual")
    os.makedirs(actual_dir, exist_ok=True)
    actual_card = os.path.join(actual_dir, src_name + ".md")
    shutil.copyfile(before_card, actual_card)  # источник фикстуры не трогаем — штемпелим копию

    status, report = mic._stamp_to_file(lang_dir, src_name, actual_card, force=False)
    check(lang, "merge status", status == "merged")

    after = open(actual_card, encoding="utf-8").read()

    check(lang, f"'{unchanged}' preserved verbatim, no marker",
          unchanged in report["preserved_entries"] and "PROSE_UNCHANGED" in after
          and "⚠" not in after.split("PROSE_UNCHANGED")[0].rsplit("consumers", 1)[-1])
    check(lang, f"'{sig_changed}' preserved WITH sig-changed marker",
          sig_changed in report["preserved_entries"]
          and (mic._MARK_SIG_CHANGED + "PROSE_SIG_CHANGED") in after)
    check(lang, f"'{ren_old}' -> '{ren_new}' reported as renamed",
          f"{ren_old} -> {ren_new}" in report["renamed"])
    check(lang, f"'{ren_new}' carries the renamed-from marker + old prose",
          ren_old in "".join(l for l in after.splitlines() if "похоже на переименование" in l)
          and "PROSE_RENAMED" in after)
    check(lang, f"'{removed}' salvaged, not silently dropped",
          removed in report["salvaged"] and "## Salvage" in after and "PROSE_REMOVED" in after)
    check(lang, f"'{brand_new}' reported as a genuinely new entry",
          brand_new in report["new_entries"])

    if _SHOW_DIFF:
        before_text = open(before_card, encoding="utf-8").read()
        sys.stdout.write(f"\n\n--- diff [{lang}] before -> after (.actual/{src_name}.md) ---\n")
        sys.stdout.writelines(difflib.unified_diff(
            before_text.splitlines(keepends=True), after.splitlines(keepends=True),
            fromfile=f"{lang}/{src_name}.md (before)", tofile=f"{lang}/.actual/{src_name}.md (after)"))


def main():
    langs = _ONLY or sorted(_CASES)
    for lang in langs:
        if lang not in _CASES:
            sys.stdout.write(f"unknown fixture language: {lang} (have: {', '.join(sorted(_CASES))})\n")
            return 1
        run_one(lang)
    sys.stdout.write(f"\n{'-' * 50}\n{_PASS} passed, {_FAIL} failed\n")
    if not _SHOW_DIFF:
        sys.stdout.write("(pass --diff to see the before/after text; results also sit in "
                          "restamp_fixtures/<lang>/.actual/ for reading by hand)\n")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
