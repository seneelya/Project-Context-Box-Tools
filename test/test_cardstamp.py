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

import tempfile
from pathlib import Path

import CARD_FORMAT as cf
import make_interface_card as mic
import validate_cards as vc

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


# --- validate_cards: File Path на исходник-без-карточки = pending, не ошибка ------

_CARD_TMPL = """# foo.py

summary.

## Public API

(none)

## Dependencies Internal

| Import | File Path | Symbols | Why | Kind |
|---|---|---|---|---|
| `config` | `config.py` | `y` | pending | normal |
| `ghost` | `ghost.py` | `z` | broken | normal |

## Dependencies External

(none)

## How it works

x

## Doc links

(none)

## Discrepancies

(none)
"""


def test_validate_pending_vs_broken():
    """config.py — исходник есть, карточки нет -> pending; ghost.py — нет исходника -> ошибка."""
    root = Path(tempfile.mkdtemp(prefix="vc_"))
    (root / "foo.py").write_text("x=1\n", encoding="utf-8")
    (root / "config.py").write_text("y=2\n", encoding="utf-8")  # исходник есть, карточки нет
    cards = root / "__map"
    cards.mkdir()
    card = cards / "foo.py.md"
    card.write_text(_CARD_TMPL, encoding="utf-8")
    # unresolved_raw передаём напрямую (в бою его даёт build_graph)
    issues, pending = vc.validate_card(card, cards, ["config.py", "ghost.py"], root)
    check("pending has source-without-card", "config.py" in pending)
    check("pending excludes broken ref", "ghost.py" not in pending)
    check("broken ref is an issue", any("ghost.py" in i for i in issues))
    check("source-without-card is NOT an issue", not any("config.py" in i for i in issues))


# --- resolver (find_code_usage): AST-based imports + submodule resolution --------

def test_resolver_submodule_and_docstring():
    """#3: `from . import sub` -> submodule FILE (symbols []); #2: docstring text is not an import."""
    from find_code_usage.resolvers import get_resolver
    from find_code_usage.core import scan_incoming
    from find_code_usage.handlers import get_handler

    root = Path(tempfile.mkdtemp(prefix="res_"))
    pkg = root / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "sub.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (pkg / "helper.py").write_text("X = 1\n", encoding="utf-8")
    (pkg / "main.py").write_text(
        '"""Title.\n\n'
        'Note: import fakeimport for it. and from bogus import stuff.\n'
        '"""\n'
        'from . import sub\n'        # bare submodule -> pkg/sub.py, no symbols
        'from .helper import X\n'    # real symbol from a module
        'import os\n',
        encoding="utf-8")

    resolver = get_resolver("python")
    handler = get_handler("python")
    resolved, externals, _u, _s = scan_incoming(
        resolver, str(pkg / "main.py"), str(root), handler=handler, verbose=False)
    rmap = {r["file"]: r["symbols"] for r in resolved}

    sub_key = next((f for f in rmap if f.endswith("sub.py")), None)
    check("submodule resolves to file", sub_key is not None)
    check("submodule has empty symbols", rmap.get(sub_key) == [])
    h_key = next((f for f in rmap if f.endswith("helper.py")), None)
    check("symbol import keeps its symbol", h_key is not None and "X" in rmap.get(h_key, []))
    joined = " ".join(externals)
    check("docstring text not leaked as import", "fakeimport" not in joined and "bogus" not in joined)


def main():
    test_is_empty()
    test_validate_pending_vs_broken()
    test_resolver_submodule_and_docstring()
    test_merge_preserves_prose()
    test_merge_signature_refresh()
    test_merge_salvage()
    test_fresh_has_no_salvage_and_placeholders()
    sys.stdout.write(f"\n{'-' * 50}\n{_PASS} passed, {_FAIL} failed\n")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
