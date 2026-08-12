#!/usr/bin/env python3
"""Регресс на card-stamp: CARD_FORMAT.is_empty + merge-режим make_interface_card.

Не оракульный (в отличие от check.py) — самопроверяющие ассерты. Гоняет реальный
штемпель на фикстуре test/pythonSRC/backends/chat.py. Запуск:

    py test/test_cardstamp.py            # точки + сводка
    py test/test_cardstamp.py --fails    # только провалы + сводка

Exit 0 = всё ок, 1 = есть провал.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
for p in (_TOOLS, _HERE):
    if p not in sys.path:
        sys.path.insert(0, p)
sys.stdout.reconfigure(encoding="utf-8")

import CARD_FORMAT as cf
import make_interface_card as mic

_PR = os.path.join(_HERE, "pythonSRC")
_FILE = "backends/chat.py"

_PASS = 0
_FAIL = 0
_FAILS_ONLY = "--fails" in sys.argv


def check(name, cond):
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        if not _FAILS_ONLY:
            sys.stdout.write(".")
    else:
        _FAIL += 1
        sys.stdout.write(f"\nFAIL: {name}\n")


def _fill(text):
    """Впечатать «человеческую» прозу в свежий штемпель (как это делает агент)."""
    text = text.replace(mic.DIRECTIVE_SUMMARY, "SUMMARY_MARK")
    text = text.replace(mic.DIRECTIVE_DESC, "DESC_MARK", 1)
    text = text.replace("<Agent: why?>", "WHY_MARK", 1)
    text = text.replace("<Agent: describe the mechanism after reading the source>", "HOWITWORKS_MARK")
    return text


# --- is_empty: терпимость к "(none) — reason", защита от ложных срабатываний ---

def test_is_empty():
    check("is_empty bare", cf.is_empty("(none)") is True)
    check("is_empty backticks", cf.is_empty("`(none)`") is True)
    check("is_empty + em-dash reason", cf.is_empty("(none) — no consumers") is True)
    check("is_empty + comma reason", cf.is_empty("(none), see below") is True)
    check("is_empty surrounding blanks", cf.is_empty("\n\n(none)\n\n") is True)
    check("is_empty NOT (nonexistent)", cf.is_empty("(nonexistent) thing") is False)
    check("is_empty NOT marker+H3", cf.is_empty("(none)\n\n### Functions\n#### foo()") is False)
    check("is_empty NOT plain content", cf.is_empty("### Functions\n#### foo()") is False)


# --- merge: проза сохраняется по ключу-имени, факты освежаются -----------------

def test_merge_preserves_prose():
    fresh = mic.build_card(_PR, _FILE)
    filled = _fill(fresh)
    op = mic._parse_old_prose(filled)
    report = {}
    merged = mic.build_card(_PR, _FILE, op, report)
    check("merge flag set", report["merged"] is True)
    check("summary kept", "SUMMARY_MARK" in merged)
    check("entry desc kept", "DESC_MARK" in merged)
    check("why cell kept", "WHY_MARK" in merged)
    check("how-it-works kept", "HOWITWORKS_MARK" in merged)
    check("_chat_once in preserved", "_chat_once" in report["preserved_entries"])


def test_merge_signature_refresh():
    """Имя то же, сигнатура в карточке битая -> merge возвращает верную, desc держит."""
    fresh = mic.build_card(_PR, _FILE)
    filled = _fill(fresh)
    import re
    broken = re.sub(r"#### `_chat_once\([^\n]*`", "#### `_chat_once(WRONG)`", filled, count=1)
    op = mic._parse_old_prose(broken)
    merged = mic.build_card(_PR, _FILE, op, {})
    check("signature regenerated", "_chat_once(backend" in merged)
    check("desc survived sig change", "DESC_MARK" in merged)
    check("broken sig gone", "WRONG" not in merged)


def test_merge_salvage():
    """Запись, которой в коде нет, уезжает в ## Salvage и переживает повторный merge."""
    fresh = mic.build_card(_PR, _FILE)
    filled = _fill(fresh)
    ghost = "#### `ghost_fn() -> None`\nconsumers 0\nGHOST_PROSE\n"
    injected = filled.replace("### Consumed internals\n", "### Consumed internals\n" + ghost, 1)
    op = mic._parse_old_prose(injected)
    report = {}
    merged = mic.build_card(_PR, _FILE, op, report)
    check("salvage section present", "## Salvage" in merged)
    check("salvage prose kept", "GHOST_PROSE" in merged)
    check("ghost reported salvaged", "ghost_fn" in report["salvaged"])
    # повторный merge — Salvage не должен исчезнуть
    op2 = mic._parse_old_prose(merged)
    merged2 = mic.build_card(_PR, _FILE, op2, {})
    check("salvage persists 2nd merge", "GHOST_PROSE" in merged2)


def test_fresh_has_no_salvage_and_placeholders():
    fresh = mic.build_card(_PR, _FILE)
    check("fresh has summary placeholder", mic.DIRECTIVE_SUMMARY in fresh)
    check("fresh has no salvage", "## Salvage" not in fresh)


def main():
    test_is_empty()
    test_merge_preserves_prose()
    test_merge_signature_refresh()
    test_merge_salvage()
    test_fresh_has_no_salvage_and_placeholders()
    sys.stdout.write(f"\n{'-' * 50}\n{_PASS} passed, {_FAIL} failed\n")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
