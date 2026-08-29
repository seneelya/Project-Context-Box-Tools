#!/usr/bin/env python3
"""Регресс на card-stamp: CARD_FORMAT.is_empty + merge-режим make_interface_card.

Не оракульный (в отличие от check.py) — самопроверяющие ассерты. Гоняет реальный
штемпель на фикстуре test/pythonSRC/backends/chat.py. Запуск:

    py test/test_cardstamp.py            # точки + сводка
    py test/test_cardstamp.py --fails    # только провалы + сводка

Exit 0 = всё ок, 1 = есть провал.
"""

import os
import re
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


def _directive_re(directive):
    """build_card прогоняет вывод через cf.number_directives — «<|Agent: xxx |>» становится
    «<|Agent:07 xxx |>». Точное совпадение с сырой DIRECTIVE_* строкой поэтому никогда не находится
    (само число между ':' и текстом — единственная разница), матчим с учётом опционального номера."""
    prefix, _, rest = directive.partition(":")
    return re.compile(re.escape(prefix + ":") + r"\d*\s*" + re.escape(rest.lstrip()))


def _fill(text):
    """Впечатать «человеческую» прозу в свежий штемпель (как это делает агент)."""
    text = _directive_re(mic.DIRECTIVE_SUMMARY).sub("SUMMARY_MARK", text)
    text = _directive_re(mic.DIRECTIVE_DESC).sub("DESC_MARK", text, count=1)
    text = _directive_re(mic.DIRECTIVE_WHY).sub("WHY_MARK", text, count=1)
    text = _directive_re(mic.DIRECTIVE_HOWITWORKS).sub("HOWITWORKS_MARK", text)
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
    check("fresh has summary placeholder", _directive_re(mic.DIRECTIVE_SUMMARY).search(fresh) is not None)
    check("fresh has no salvage", "## Salvage" not in fresh)


# --- REQ-004+005: устойчивая идентичность записи (не угадывание по первому слову) ------
# Найденный баг: имя записи вычислялось разрезанием ТЕКСТА сигнатуры («первое слово»).
# Работает только для голого Python (`foo(x)`) — у JS/TS/C#/async-Python сигнатура НАЧИНАЕТСЯ
# со служебного слова языка («function», «async», «public static void», …), и «первое слово» —
# это обёртка, не имя. Хуже: у ВСЕХ функций файла обёртка одинаковая («function»), поэтому при
# разборе старой карточки все записи схлопывались в ОДИН ключ — выживала проза только последней.

def test_entry_key_survives_language_decorators():
    """Имя ищем по ПОЗИЦИИ (перед `(`/`=`, иначе после известных слов языка), не угадыванием."""
    check("js function", mic._entry_key("#### `function isOurTool(name)`", "typescript") == "isOurTool")
    check("js async function", mic._entry_key("#### `async function loadIt(x)`", "typescript") == "loadIt")
    check("js const", mic._entry_key("#### `const OUR_TOOLS = ['a', 'b']`", "typescript") == "OUR_TOOLS")
    check("js class", mic._entry_key("#### `class Widget`", "typescript") == "Widget")
    check("python async def", mic._entry_key("#### `async load_it(x)`", "python") == "load_it")
    check("csharp modifiers+type", mic._entry_key("#### `public static void Foo(x)`", "csharp") == "Foo")
    check("csharp async modifiers", mic._entry_key("#### `public async Task Bar(x)`", "csharp") == "Bar")


_TS_PR = os.path.join(_HERE, "tsSRC")
_TS_FILE = "src/analyzer.ts"
_CS_PR = os.path.join(_HERE, "unitySRC")
_CS_FILE = "Services/Analytics/AnalyticsEvents.cs"


def _fill_all_descs(text):
    """Как _fill, но заполняет КАЖДОЕ описание записи уникальным текстом (не только первое) —
    нужно, чтобы после merge проверить, что переживает каждая запись, а не только одна."""
    counter = [0]

    def repl(_m):
        counter[0] += 1
        return f"DESC_{counter[0]}."

    return _directive_re(mic.DIRECTIVE_DESC).sub(repl, text)


def test_merge_ts_multi_const_no_collision():
    """analyzer.ts: несколько `export const foo = (...) => …` — сигнатура каждой НАЧИНАЕТСЯ
    с одного и того же слова 'const'. До фикса все такие записи схлопывались в ключ 'const'
    при разборе старой карточки, и merge на реальном re-stamp терял прозу у всех, кроме одной."""
    fresh = mic.build_card(_TS_PR, _TS_FILE)
    filled = _fill_all_descs(fresh)
    op = mic._parse_old_prose(filled, "typescript")
    const_like = [n for n, e in op["entries"].items() if e["group"] == "Constants" and e["desc"]]
    check("multiple const-like keys parsed distinctly (no collision)", len(const_like) >= 3)
    report = {}
    mic.build_card(_TS_PR, _TS_FILE, op, report)
    check("no new entries on unchanged re-stamp", report["new_entries"] == [])
    check("every const-like entry survived merge", all(n in report["preserved_entries"] for n in const_like))


def test_merge_csharp_multi_class_no_collision():
    """AnalyticsEvents.cs: два top-level класса, ОБА начинаются с 'public static class' —
    тот же класс бага, что и у JS 'function', только на C#-модификаторах."""
    fresh = mic.build_card(_CS_PR, _CS_FILE)
    filled = _fill_all_descs(fresh)
    op = mic._parse_old_prose(filled, "csharp")
    check("AnalyticsEvents key correct", "AnalyticsEvents" in op["entries"])
    check("AnalyticsParams key correct (not collapsed with sibling)", "AnalyticsParams" in op["entries"])
    report = {}
    mic.build_card(_CS_PR, _CS_FILE, op, report)
    check("both csharp classes survived merge",
          "AnalyticsEvents" in report["preserved_entries"]
          and "AnalyticsParams" in report["preserved_entries"])


def test_merge_marker_on_signature_change_and_rename():
    """Имя то же, сигнатура другая -> проза с маркером-предупреждением (не потеряна, но
    отмечена «не проверено»). Имени вообще нет, но есть похожее -> перенос с др. маркером."""
    card = (
        "# plugin.js\n\nSummary.\n\n## Public API\n\n### Functions\n"
        "#### `function isOurTool(name)`\nconsumers 0\nA.\n"
        "\n### Constants\n#### `const OUR_TOOLS = ['a']`\nconsumers 0\nB.\n"
        "\n## Dependencies Internal\n\n(none)\n\n## Dependencies External\n\n(none)\n\n"
        "## How it works\n\nH.\n\n## Doc links\n\n(none)\n\n## Discrepancies\n\n(none)\n"
    )
    op = mic._parse_old_prose(card, "typescript")

    new_syms_sig_changed = [("isOurTool", "Functions", "async function isOurTool(name)")]
    report = {"new_entries": [], "preserved_entries": [], "salvaged": [], "renamed": []}
    resolved, renamed_from = mic._resolve_entry_identities(new_syms_sig_changed, op, report)
    check("sig-changed keeps prose", resolved["isOurTool"][0].endswith("A."))
    check("sig-changed gets warn marker", resolved["isOurTool"][0].startswith(mic._MARK_SIG_CHANGED))

    new_syms_renamed = [("ALLOWED_TOOLS", "Constants", "const ALLOWED_TOOLS = ['a']")]
    report2 = {"new_entries": [], "preserved_entries": [], "salvaged": [], "renamed": []}
    resolved2, renamed_from2 = mic._resolve_entry_identities(new_syms_renamed, op, report2)
    check("renamed keeps prose", resolved2["ALLOWED_TOOLS"][0].endswith("B."))
    check("renamed gets a different marker than sig-change",
          resolved2["ALLOWED_TOOLS"][0].startswith("⚠ похоже на переименование")
          and "OUR_TOOLS" in resolved2["ALLOWED_TOOLS"][0])
    check("renamed old name reported", "OUR_TOOLS -> ALLOWED_TOOLS" in report2["renamed"])
    check("renamed old entry excluded from Salvage", "OUR_TOOLS" in renamed_from2)

    # стопка маркеров: снова не совпадает -> ещё одна копия спереди, без счётчика
    op_marked = {"entries": {"isOurTool": {
        "desc": resolved["isOurTool"], "sig": "async function isOurTool(name)", "group": "Functions"}}}
    new_syms_sig_changed_again = [("isOurTool", "Functions", "async function isOurTool(name, strict)")]
    resolved3, _ = mic._resolve_entry_identities(
        new_syms_sig_changed_again, op_marked, {"new_entries": [], "preserved_entries": [], "salvaged": [], "renamed": []})
    check("marker stacks on repeated drift, no counter needed",
          resolved3["isOurTool"][0].count(mic._MARK_SIG_CHANGED) == 2)
    check("stable case does not re-add marker",
          mic._resolve_entry_identities(
              [("isOurTool", "Functions", "async function isOurTool(name)")], op_marked,
              {"new_entries": [], "preserved_entries": [], "salvaged": [], "renamed": []}
          )[0]["isOurTool"][0].count(mic._MARK_SIG_CHANGED) == 1)


def test_force_guard_refuses_on_prose_then_discard_prose_works():
    """REQ-004: --force на карточке с прозой отказывает (exit-статус 'blocked'), не пишет
    ничего; --force + --discard-prose работает как раньше (фича, не регресс)."""
    root = Path(tempfile.mkdtemp(prefix="forceguard_"))
    (root / "m.py").write_text('"""Mod."""\ndef foo(x):\n    return x\n', encoding="utf-8")
    out = root / "__map" / "m.py.md"
    status, _ = mic._stamp_to_file(str(root), "m.py", str(out), force=False)
    check("first stamp is new", status == "new")
    filled = _directive_re(mic.DIRECTIVE_DESC).sub("REAL PROSE.", out.read_text(encoding="utf-8"), count=1)
    out.write_text(filled, encoding="utf-8")

    before = out.read_text(encoding="utf-8")
    status, report = mic._stamp_to_file(str(root), "m.py", str(out), force=True)
    check("force without discard-prose is blocked", status == "blocked")
    check("blocked reports prose block count", report.get("prose_blocks", 0) >= 1)
    check("blocked write does not touch the file", out.read_text(encoding="utf-8") == before)

    status, _ = mic._stamp_to_file(str(root), "m.py", str(out), force=True, discard_prose=True)
    check("force + discard-prose proceeds", status == "forced")
    check("prose actually discarded", "REAL PROSE." not in out.read_text(encoding="utf-8"))


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
    card.write_text(_directive_re(mic.DIRECTIVE_SUMMARY).sub("KEPT", card.read_text(encoding="utf-8"), count=1),
                     encoding="utf-8")
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
    """tree группирует по каталогам; depth даёт слой 0=листья; --edges out/in/inout; правило ×N."""
    from graph_from_cards import build_graph, format_tree, format_depth

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
    card("root.py", ["pkg/a.py", "pkg/b.py"])   # b.py импортят двое (a.py, root.py) -> '← ×2 (…)'
    g = build_graph(cards)

    # шапка-ориентир (строки '>') сама содержит глифы как ключ — ассерты по ТЕЛУ (без '>')
    def body(text):
        return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith(">"))

    pk = format_tree(g, "__map", "inout")
    check("tree groups by dir", "## pkg/ (2)" in pk)
    check("tree has (root)", "## (root) (1)" in pk)
    check("single dep: no ×, no brackets", "→ b.py" in body(pk))     # a.py -> b.py, один -> без ×/()
    # ассерты по ЛИСТИНГУ модулей (до '## hotspots' — тот легально содержит '← ×N')
    mods_out = body(format_tree(g, "__map", "out")).split("## hotspots")[0]
    check("edges=out hides used-by", "←" not in mods_out)
    check("edges=out keeps uses", "→ b.py" in mods_out)
    mods_in = body(format_tree(g, "__map", "in")).split("## hotspots")[0]
    check("edges=in shows used-by", "←" in mods_in)
    check("edges=in multi -> ×N + brackets", "← ×2 (" in mods_in)    # b.py used-by a.py+root.py
    check("edges=in hides uses", "→ b.py" not in mods_in)

    dp = format_depth(g, "__map", "inout")
    check("depth view has depth 0", "## depth 0" in dp)

    # --verbose 0 прячет описания (строку « — summary»), но модули/связи остаются
    v1 = body(format_tree(g, "__map", "inout", 1))
    v0 = body(format_tree(g, "__map", "inout", 0))
    check("verbose 1 keeps summary", "— s." in v1)
    check("verbose 0 hides summary", "— s." not in v0)
    check("verbose 0 keeps module+edges", "**b.py**" in v0 and "→ b.py" in v0)


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
    test_entry_key_survives_language_decorators()
    test_merge_ts_multi_const_no_collision()
    test_merge_csharp_multi_class_no_collision()
    test_merge_marker_on_signature_change_and_rename()
    test_force_guard_refuses_on_prose_then_discard_prose_works()
    sys.stdout.write(f"\n{'-' * 50}\n{_PASS} passed, {_FAIL} failed\n")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
