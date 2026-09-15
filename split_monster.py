#!/usr/bin/env python3
"""split_monster — move top-level blocks between files without hand-retyping content.

Two ways to use it:
  1. As a CLI: `--generate` turns `--file X --split LINE TARGET ...` into a throwaway,
     hand-editable Python script that does the actual move when run.
  2. As a library: that generated script (or one written by hand) imports `cut`,
     `add_import`, `monster` from this module and calls them directly.

See __dev/vision/Vision06__monster-file-split.md and __dev/plans/Plan04__split_monster.md
for the full design/rationale — this docstring only orients, it does not re-argue decisions.

v0 scope: I (the LLM) decide which block goes to which file — this tool does not propose
groupings. The "best-effort hints" it writes into generated scripts are a cheap grep, not a
real reference graph (that's a future v1) — verify them, don't trust them blindly.
"""

import argparse
import re
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from get_codeblock.core import get_codeblock as _gcb_get_codeblock


# --------------------------------------------------------------------------- primitives

class Block:
    """A byte-exact top-level code range pulled from one source file."""

    __slots__ = ("source_file", "start", "end", "text")

    def __init__(self, source_file, start, end, text):
        self.source_file = source_file
        self.start = start
        self.end = end
        self.text = text

    def __repr__(self):
        return f"Block({self.source_file!r}, {self.start}, {self.end})"


class Import:
    """A marker around an import-line string — never parsed, just carried and deduped."""

    __slots__ = ("text",)

    def __init__(self, text):
        self.text = text

    def __repr__(self):
        return f"Import({self.text!r})"


def cut(source_file, line):
    """Resolve the top-level block starting at/containing `line` in `source_file`.

    Resolves immediately (not lazily) via get_codeblock's own `level=1` addressing — no
    escalation, no guessing the end line myself.
    """
    res = _gcb_get_codeblock(source_file, line_num=line, level=1, query=True)
    return Block(source_file, res["start"], res["end"], res["text"])


def add_import(text):
    """Wrap an import-line string so it can be collected/deduped/dropped by short name."""
    return Import(text)


def _is_apply():
    return "--apply" in sys.argv


def _read_lines(path):
    return Path(path).read_text(encoding="utf-8").splitlines(keepends=True)


def _dedup_preserve_order(items):
    seen = set()
    out = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out


_HEADER_LINE_RE = re.compile(r"^\s*(import\b|const\s+\S+\s*=\s*require\()")


def _split_header_body(text):
    """Existing target_file's leading import-ish lines vs. everything after the first blank
    line that follows them — used only to merge a second batch into an already-written file."""
    lines = text.splitlines()
    header = []
    i = 0
    while i < len(lines) and _HEADER_LINE_RE.match(lines[i]):
        header.append(lines[i])
        i += 1
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    body = lines[i:]
    return header, body


def _reconstruct_body(blocks):
    """Sort by start DESCENDING, prepend each into the body list — restores ascending source
    order regardless of the order `blocks` was passed in (Vision06: bottom-up + prepend)."""
    ordered = sorted(blocks, key=lambda b: b.start, reverse=True)
    body_texts = []
    for b in ordered:
        body_texts.insert(0, b.text)
    lines = []
    for text in body_texts:
        lines.extend(text.splitlines())
    return lines


class _Monster:
    """The mutating half of the library — everything here only touches disk under `--apply`."""

    def write(self, target_file, blocks, imports=None):
        """Write `blocks`/`imports` into `target_file` (dedup imports; new blocks go BEFORE
        whatever body is already there). Only ever touches `target_file` — never `source_file`."""
        imports = imports or []
        header = _dedup_preserve_order([imp.text for imp in imports])
        new_body = _reconstruct_body(blocks)

        target = Path(target_file)
        if target.exists():
            old_header, old_body = _split_header_body(target.read_text(encoding="utf-8"))
            header = _dedup_preserve_order(old_header + header)
            body = new_body + old_body  # this batch goes BEFORE whatever was already there
        else:
            body = new_body

        lines = list(header)
        if header and body:
            lines.append("")
        lines.extend(body)
        final = "\n".join(lines) + ("\n" if lines else "")

        if not _is_apply():
            print(f"[dry-run] would write {target_file}: "
                  f"{len(header)} import(s), {len(blocks)} block(s)")
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(final, encoding="utf-8")
        print(f"wrote {target_file}: {len(header)} import(s), {len(blocks)} block(s)")

    def cut(self, source_file, blocks):
        """Remove `blocks`' exact ranges from `source_file` — every block must belong to this
        same `source_file` (raises otherwise); only ever touches `source_file`, never a target."""
        for b in blocks:
            if b.source_file != source_file:
                raise ValueError(
                    f"block from {b.source_file!r} passed to monster.cut({source_file!r})"
                )
        if not _is_apply():
            print(f"[dry-run] would cut {len(blocks)} block(s) from {source_file}")
            return
        lines = _read_lines(source_file)
        for b in sorted(blocks, key=lambda b: b.start, reverse=True):
            del lines[b.start - 1 : b.end]
        Path(source_file).write_text("".join(lines), encoding="utf-8")
        print(f"cut {len(blocks)} block(s) from {source_file}")

    def consumers(self, file_path, symbols, project_root="."):
        """Print (not fix) who outside `file_path` imports each of `symbols` — must be called
        BEFORE any cut, since consumers_of parses live declarations out of `file_path`."""
        from make_interface_card import consumers_of

        data = consumers_of(project_root, file_path)
        any_hits = False
        for sym in symbols:
            hits = data.get(sym, [])
            if not hits:
                continue
            any_hits = True
            print(f"# {sym} — потребители вне {file_path} (правь руками):")
            for consumer, _kind, lines in hits:
                for ln in lines:
                    print(f"#   {consumer}:{ln}")
        if not any_hits:
            print(f"# {file_path}: внешних потребителей среди {symbols} не найдено")


monster = _Monster()


# --------------------------------------------------------------------------- --generate

_TOP_LEVEL_NAME_RE = re.compile(
    r"^(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s+(\w+)"
    r"|^(?:export\s+)?const\s+(\w+)\s*="
    r"|^(?:export\s+)?class\s+(\w+)"
    r"|^(?:export\s+)?let\s+(\w+)\s*="
)
_WORD_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")


def _declaration_line(text):
    """The block's own declaration line — NOT necessarily line 0 of `text`, since get_codeblock
    (correctly) includes a leading comment as part of the same block/range."""
    for line in text.splitlines():
        if _TOP_LEVEL_NAME_RE.match(line.strip()):
            return line.strip()
    return text.splitlines()[0].strip() if text else ""


def _block_name(text):
    m = _TOP_LEVEL_NAME_RE.match(_declaration_line(text))
    if not m:
        return None
    return next(g for g in m.groups() if g)


def _all_top_level_names(all_lines):
    """Only lines with NO leading whitespace — an indented `const x = ...` inside some other
    function is not a top-level name just because it matches the same regex when stripped."""
    names = {}
    for line in all_lines:
        if line[:1].isspace():
            continue
        m = _TOP_LEVEL_NAME_RE.match(line)
        if m:
            names[next(g for g in m.groups() if g)] = True
    return names


def _hint_lines(block, all_lines, top_level_names):
    """Cheap best-effort grep — NOT a real resolver (Vision06: затычка v0, verify by eye)."""
    hints = []
    name = _block_name(block.text)
    if name:
        referenced_at = [
            i for i, line in enumerate(all_lines, start=1)
            if not (block.start <= i <= block.end) and re.search(rf"\b{re.escape(name)}\b", line)
        ]
        if referenced_at:
            shown = ", ".join(str(n) for n in referenced_at[:5])
            more = ", ..." if len(referenced_at) > 5 else ""
            hints.append(
                f"# best-effort (grep, не резолв): '{name}' встречается ещё на строках "
                f"{shown}{more}"
            )

    used = set(_WORD_RE.findall(block.text))
    needs = sorted(n for n in used if n in top_level_names and n != name)
    if needs:
        hints.append(f"# best-effort (grep, не резолв): возможно нужны — {', '.join(needs)}")
    return hints


def _preview_line(block):
    return f"# {_declaration_line(block.text)}  [{block.start}-{block.end}]"


def _safe_ident(target_file):
    stem = Path(target_file).stem
    ident = re.sub(r"\W+", "_", stem).strip("_").upper()
    return ident or "TARGET"


def _help_lines():
    """Cheat-sheet for the imported names, pulled from their OWN docstrings — not hand-copied,
    so it can't drift out of sync with them. A future session reading a generated script has
    no reason to already know what `cut`/`add_import`/`monster.*` do; this is instead of making
    it go re-read split_monster.py's source to find out."""
    import inspect

    entries = [("cut", cut), ("add_import", add_import),
               ("monster.write", _Monster.write), ("monster.cut", _Monster.cut),
               ("monster.consumers", _Monster.consumers)]
    lines = ["# --- шпаргалка по импортированному (из докстрингов split_monster.py) ---"]
    for name, fn in entries:
        params = [p for p in inspect.signature(fn).parameters if p != "self"]
        doc = inspect.getdoc(fn) or ""
        first_para = []
        for docline in doc.splitlines():
            if not docline.strip():
                break
            first_para.append(docline.strip())
        summary = " ".join(first_para)
        lines.append(f"# {name}({', '.join(params)}) — {summary}")
    lines.append("# --- конец шпаргалки ---")
    return lines


def generate(file_path, splits, out_path, project_root="."):
    """Expand `[(line, target_file), ...]` into a full three-layer script at `out_path`.

    Grouping (which line goes to which target) is decided by the caller — this only expands
    it into the runnable/editable shape (Vision06 Пример Б) with best-effort hint comments.
    """
    all_lines = Path(file_path).read_text(encoding="utf-8").splitlines()
    top_level_names = _all_top_level_names(all_lines)

    by_target = {}
    for line_no, target in splits:
        by_target.setdefault(target, []).append(cut(file_path, line_no))

    out = [
        f"# сгенерировано: split_monster --file {file_path} --split ...",
        "import sys",
        f'sys.path.insert(0, r"{_HERE}")',
        "from split_monster import cut, add_import, monster",
        "",
        *_help_lines(),
        "",
    ]
    header_len = len(out)

    tag = 0
    list_names = {}
    all_symbols = []
    for target, blocks in by_target.items():
        var_names = []
        for b in blocks:
            tag += 1
            for h in _hint_lines(b, all_lines, top_level_names):
                out.append(h)
            out.append(_preview_line(b))
            varname = f"c{tag:02d}"
            out.append(f"{varname} = cut({file_path!r}, {b.start})  #{tag}")
            var_names.append(varname)
            name = _block_name(b.text)
            if name:
                all_symbols.append(name)
        out.append("")
        list_name = f"{_safe_ident(target)}_BLOCKS"
        list_names[target] = list_name
        out.append(f"{list_name} = [{', '.join(var_names)}]")
        out.append("")

    if all_symbols:
        out.insert(
            header_len,
            f"monster.consumers({file_path!r}, {all_symbols!r}, project_root={project_root!r})",
        )
        out.insert(header_len + 1, "")

    for target, list_name in list_names.items():
        out.append(f"monster.write({target!r}, {list_name}, [])")
    out.append(f"monster.cut({file_path!r}, {' + '.join(list_names.values())})")

    Path(out_path).write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"generated {out_path} ({tag} block(s), {len(list_names)} target file(s))")


# --------------------------------------------------------------------------- CLI

def _cli(argv=None):
    p = argparse.ArgumentParser(
        prog="split_monster",
        description=(
            "Разворачивает line->target_file пары в исполняемый скрипт-перенос (v0, реализовано). "
            "--investigate — граф блок<->блок с честным резолвом вместо grep-подсказки (v1, "
            "ЗАДУМАНО, ЕЩЁ НЕ РЕАЛИЗОВАНО, см. Vision06__monster-file-split.md)."
        ),
    )
    p.add_argument("--file", required=True, help="файл-монстр, источник блоков")
    p.add_argument(
        "--split", nargs=2, action="append", metavar=("LINE", "TARGET"),
        help="номер строки начала блока + целевой файл; повторяемый флаг, не список. "
             "Обязателен, если не передан --investigate.",
    )
    p.add_argument(
        "--out-script",
        help="куда записать сгенерированный скрипт. Обязателен, если не передан --investigate.",
    )
    p.add_argument(
        "--investigate", action="store_true",
        help=(
            "[ЗАДУМАНО, НЕ РЕАЛИЗОВАНО — v1] Граф ссылок блок<->блок ВНУТРИ --file с честным "
            "резолвом (тем же классом инструментов, что find_code_usage/graph_from_cards), "
            "вместо дешёвой grep-подсказки из --split. Плюс кэш дампа графа по хэшу файла. "
            "См. Vision06__monster-file-split.md, секция 'v1'. Сейчас просто печатает это "
            "сообщение и завершается с ошибкой — используйте --split."
        ),
    )
    p.add_argument("--project-root", default=".", help="для monster.consumers(...)")
    args = p.parse_args(argv)

    if args.investigate:
        print(
            "--investigate ещё не реализован — это v1 (граф блок<->блок с честным резолвом), "
            "задумано, но не построено. См. Vision06__monster-file-split.md, секция 'v1'. "
            "Сейчас доступна только группировка через --split (v0, дешёвая grep-подсказка).",
            file=sys.stderr,
        )
        sys.exit(2)

    if not args.split or not args.out_script:
        p.error("--split и --out-script обязательны (если не передан --investigate)")

    splits = [(int(line), target) for line, target in args.split]
    generate(args.file, splits, args.out_script, project_root=args.project_root)


if __name__ == "__main__":
    _cli()
