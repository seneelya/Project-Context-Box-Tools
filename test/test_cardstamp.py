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
    text = text.replace(mic.DIRECTIVE_WHY, "WHY_MARK", 1)
    text = text.replace(mic.DIRECTIVE_HOWITWORKS, "HOWITWORKS_MARK")
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


def test_agent_directive_marker():
    """Единый маркер `<|Agent: … |>`: конструктор + детекторы (терпят легаси `<Agent:…>`)."""
    d = cf.agent("why?")
    check("agent() builds the uniform marker", d == "<|Agent: why? |>")
    check("is_agent_directive: new form", cf.is_agent_directive(d))
    check("is_agent_directive: legacy form", cf.is_agent_directive("<Agent: why?>"))
    check("is_agent_directive: strips backticks", cf.is_agent_directive("`<|Agent: x |>`"))
    check("is_agent_directive: real prose is not a directive", not cf.is_agent_directive("does the thing"))
    check("has_agent_directive: finds inline new", cf.has_agent_directive("consumers 2: a, b  <|Agent: note |>"))
    check("has_agent_directive: finds inline legacy", cf.has_agent_directive("foo <Agent: note> bar"))
    check("has_agent_directive: none when filled", not cf.has_agent_directive("consumers 2: a, b"))
    # marker must not collide with code punctuation the stamp emits around it
    check("marker uses collision-proof <| |>", cf.AGENT_OPEN == "<|Agent:" and cf.AGENT_CLOSE == "|>")


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
    issues, pending, awaiting = vc.validate_card(card, cards, ["config.py", "ghost.py"], root)
    check("pending has source-without-card", "config.py" in pending)
    check("pending excludes broken ref", "ghost.py" not in pending)
    check("broken ref is an issue", any("ghost.py" in i for i in issues))
    check("source-without-card is NOT an issue", not any("config.py" in i for i in issues))
    check("filled card is not awaiting", awaiting == [])

    # карточка с оставшимися директивами `<|Agent:…|>` -> статус awaiting (new + legacy формы)
    (root / "bar.py").write_text("x=1\n", encoding="utf-8")
    tmpl = _CARD_TMPL.replace("# foo.py", "# bar.py")
    tmpl = tmpl.replace("summary.", cf.agent("one-line summary"))     # summary = директива (new)
    tmpl = tmpl.replace("\nx\n", "\n<Agent: how it works>\n")          # How it works = директива (legacy)
    wcard = cards / "bar.py.md"
    wcard.write_text(tmpl, encoding="utf-8")
    _i, _p, aw = vc.validate_card(wcard, cards, [], root)
    check("awaiting flags summary directive", "(summary)" in aw)
    check("awaiting flags section (legacy form too)", "How it works" in aw)
    check("awaiting is not an issue", not any("Agent" in i for i in _i))


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


def test_stamp_all_recursive():
    """--all: карточки для всего дерева под root, рекурсивно; повторный проход — merge."""
    root = Path(tempfile.mkdtemp(prefix="all_"))
    (root / "pkg" / "sub").mkdir(parents=True)
    (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (root / "pkg" / "a.py").write_text('"""A."""\ndef f():\n    return 1\n', encoding="utf-8")
    (root / "pkg" / "b.py").write_text("from . import a\n", encoding="utf-8")
    (root / "pkg" / "sub" / "deep.py").write_text("x = 1\n", encoding="utf-8")

    check("stamp_all exit 0", mic._stamp_all(str(root), force=False) == 0)
    made = sorted(str(p.relative_to(root / "__map")).replace("\\", "/")
                  for p in (root / "__map").rglob("*.md"))
    check("stamp_all mirrors the tree",
          made == ["pkg/__init__.py.md", "pkg/a.py.md", "pkg/b.py.md", "pkg/sub/deep.py.md"])
    # проза сохраняется, а __map сам себя не штемпелит (EXCLUDED_DIRS)
    card = root / "__map" / "pkg" / "a.py.md"
    card.write_text(card.read_text(encoding="utf-8").replace(mic.DIRECTIVE_SUMMARY, "KEPT"), encoding="utf-8")
    check("stamp_all rerun exit 0", mic._stamp_all(str(root), force=False) == 0)
    check("stamp_all rerun keeps prose", "KEPT" in card.read_text(encoding="utf-8"))
    check("stamp_all does not card the __map dir",
          not (root / "__map" / "__map").exists())


def test_graph_file_zone_and_cycles():
    """graph_from_cards: цикл A→B→C→A детектится; зона = downstream + upstream вокруг узла."""
    from graph_from_cards import build_graph, find_cycles, file_zone

    root = Path(tempfile.mkdtemp(prefix="graph_"))
    cards = root / "__map"
    cards.mkdir()

    def card(name, deps):
        if deps:
            rows = "\n".join(f"| `{d[:-3]}` | `{d}` |  | why | normal |" for d in deps)
            tbl = "| Import | File Path | Symbols | Why | Kind |\n|---|---|---|---|---|\n" + rows
        else:
            tbl = "(none)"
        (cards / (name + ".md")).write_text(
            f"# {name}\n\nsummary.\n\n## Dependencies Internal\n\n{tbl}\n", encoding="utf-8")

    card("a.py", ["b.py"])
    card("b.py", ["c.py"])
    card("c.py", ["a.py"])   # cycle a -> b -> c -> a
    card("d.py", ["a.py"])   # d depends on a (upstream of a)
    g = build_graph(cards)

    cycles = find_cycles(g["nodes"])
    check("one elementary cycle", len(cycles) == 1)
    check("cycle members a/b/c closed",
          cycles and set(cycles[0][:-1]) == {"a.py", "b.py", "c.py"} and cycles[0][0] == cycles[0][-1])

    z = file_zone(g, "a.py", 1)
    check("file_zone downstream = {b}", z["down"] == {"b.py"})
    check("file_zone upstream = {c,d}", z["up"] == {"c.py", "d.py"})


def test_graph_views():
    """packages группирует по пакетам с rel-путями; layers даёт слой 0=листья; --edges out/in/inout."""
    from graph_from_cards import build_graph, format_packages, format_layers

    root = Path(tempfile.mkdtemp(prefix="gview_"))
    cards = root / "__map"
    (cards / "pkg").mkdir(parents=True)

    def card(path, deps):
        if deps:
            rows = "\n".join(f"| `x` | `{d}` |  | why | normal |" for d in deps)
            tbl = "| Import | File Path | Symbols | Why | Kind |\n|---|---|---|---|---|\n" + rows
        else:
            tbl = "(none)"
        f = cards / (path + ".md")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(f"# {path.split('/')[-1]}\n\ns.\n\n## Dependencies Internal\n\n{tbl}\n", encoding="utf-8")

    card("pkg/a.py", ["pkg/b.py"])
    card("pkg/b.py", [])
    card("root.py", ["pkg/a.py"])
    g = build_graph(cards)

    # шапка-ориентир (строки '>') сама содержит '→'/'← ×N' как ключ — ассерты по ТЕЛУ (без '>')
    def body(text):
        return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith(">"))

    pk = format_packages(g, "__map", "inout")
    check("packages groups by pkg", "## pkg/ (2)" in pk)
    check("packages has (root)", "## (root) (1)" in pk)
    check("packages uses rel path in-pkg", "→ b.py" in body(pk))     # pkg/a.py -> pkg/b.py shown as b.py
    body_out = body(format_packages(g, "__map", "out"))
    check("edges=out hides used-by", "← ×" not in body_out)
    check("edges=out keeps uses", "→ b.py" in body_out)
    body_in = body(format_packages(g, "__map", "in"))
    check("edges=in shows used-by", "← ×" in body_in)
    check("edges=in hides uses", "→ b.py" not in body_in)

    ly = format_layers(g, "__map", "inout")
    check("layers has layer 0", "## layer 0" in ly)


def test_discrepancies():
    """Свод «карта vs реальность»: orphan / pending / unresolved + переорганизация группировки."""
    from graph_from_cards import (build_graph, collect_discrepancies,
                                   format_discrepancies, group_by)

    root = Path(tempfile.mkdtemp(prefix="discr_"))
    cards = root / "__map"
    (cards / "pkg").mkdir(parents=True)

    def src(rel):                       # реальный исходник в дереве проекта
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x = 1\n", encoding="utf-8")

    def card(path, deps):
        if deps:
            rows = "\n".join(f"| `x` | `{d}` |  | why | normal |" for d in deps)
            tbl = "| Import | File Path | Symbols | Why | Kind |\n|---|---|---|---|---|\n" + rows
        else:
            tbl = "(none)"
        f = cards / (path + ".md")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(f"# {path.split('/')[-1]}\n\ns.\n\n## Dependencies Internal\n\n{tbl}\n", encoding="utf-8")

    src("a.py"); src("b.py"); src("c.py")   # c.py БЕЗ карточки (цель pending); ghost/zzz нет вовсе
    card("a.py", [])                          # исходник есть -> НЕ orphan (контроль)
    card("b.py", ["c.py", "zzz.py"])          # c.py -> pending, zzz.py -> unresolved
    card("pkg/ghost.py", [])                  # pkg/ghost.py исходника нет -> orphan

    g = build_graph(cards)
    items = collect_discrepancies(g, root)
    kinds = sorted(d.kind for d in items)
    check("collect finds exactly orphan+pending+unresolved", kinds == ["orphan", "pending", "unresolved"])
    o = next(d for d in items if d.kind == "orphan")
    check("orphan is the sourceless card", o.card == "pkg/ghost.py")
    p = next(d for d in items if d.kind == "pending")
    check("pending points at uncarded source", p.card == "b.py" and p.ref == "c.py")
    u = next(d for d in items if d.kind == "unresolved")
    check("unresolved points at nothing", u.card == "b.py" and u.ref == "zzz.py")

    by_kind = format_discrepancies(items, group="kind")
    check("digest counts line", "1 orphan · 1 pending · 1 unresolved" in by_kind)
    check("digest kind order orphan<unresolved",
          by_kind.index("## orphan") < by_kind.index("## unresolved"))
    check("kind grouping omits redundant tag", "[orphan]" not in by_kind)

    by_pkg = format_discrepancies(items, group="package")
    check("package grouping splits (root) vs pkg/", "## (root) (2)" in by_pkg and "## pkg/ (1)" in by_pkg)
    check("non-kind grouping keeps [kind] tag", "[orphan]" in by_pkg)

    # переорганизация группировки = другая key-функция, без правки формата
    grouped = group_by(items, lambda d: d.card)
    check("group_by is a reusable primitive", set(grouped) == {"b.py", "pkg/ghost.py"})

    check("empty digest says clean",
          format_discrepancies([]) == "# discrepancies — none (map matches reality)")


def main():
    test_is_empty()
    test_agent_directive_marker()
    test_validate_pending_vs_broken()
    test_resolver_submodule_and_docstring()
    test_stamp_all_recursive()
    test_graph_file_zone_and_cycles()
    test_graph_views()
    test_discrepancies()
    test_merge_preserves_prose()
    test_merge_signature_refresh()
    test_merge_salvage()
    test_fresh_has_no_salvage_and_placeholders()
    sys.stdout.write(f"\n{'-' * 50}\n{_PASS} passed, {_FAIL} failed\n")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
