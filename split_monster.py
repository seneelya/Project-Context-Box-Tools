#!/usr/bin/env python3
"""split_monster — move top-level blocks between files without hand-retyping content.

Two ways to use it:
  1. As a CLI: `--generate` turns `--file X --split LINE TARGET ...` into a throwaway,
     hand-editable Python script that does the actual move when run.
  2. As a library: that generated script (or one written by hand) imports `cut`,
     `add_import`, `monster` from this module and calls them directly.

See __dev/vision/Vision06__monster-file-split.md and __dev/plans/Plan04__split_monster.md
for the full design/rationale — this docstring only orients, it does not re-argue decisions.

FILES TO COPY if you take only this tool out of the toolkit (keep the folder layout; run from
the folder that holds split_monster.py; Python >= 3.10, `pip install -r get_codeblock/requirements.txt`):
  REQUIRED   split_monster.py  split_langs/  get_codeblock/ (+ its requirements: tree-sitter and
             the grammars)  find_code_usage/ (JS/TS import parsing reuses its ts_handler regexes)
  OPTIONAL   `monster.consumers(...)` — the "who outside imports these names" report — needs
             make_interface_card.py + stamp_langs/ + CARD_FORMAT.py + graph_from_cards.py +
             seam_scanner/ + termstyle.py (without them it prints one line and skips).
             CONFIG__TOOLS.py — only for the usage log (LOG_ENABLED_TOOLS/LOG_DIR); missing = log off.
  NOT NEEDED test/, __dev/, *.md docs (split_monster__TLDR.md is the quick reference).
Generated move.py files import split_monster by absolute path (sys.path.insert) — regenerate
them after moving the tool.

v0 scope: I (the LLM) decide which block goes to which file — this tool does not propose
groupings. The "best-effort hints" it writes into generated scripts are a cheap grep, not a
real reference graph (that's a future v1) — verify them, don't trust them blindly.
"""

import argparse
import ast
import hashlib
import atexit
import json
import os
import re
import sys
import time
from collections import Counter
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
from get_codeblock.reader.classify import outline_rows as _gcb_outline_rows

import split_langs
from split_langs._common import dedup as _dedup_preserve_order

TOOL_NAME = "split_monster"


# --------------------------------------------------------------------------- call logging
# Same opt-in mechanism as get_codeblock / make_interface_card (CONFIG__TOOLS.LOG_ENABLED_TOOLS +
# LOG_DIR -> "<LOG_DIR>/split_monster.log.jsonl"), kept as its own copy — tools stay independent.
# Diagnostic only: argv, outcome, counts, duration — never block text. Never raises.

def _is_absolute_path(p):
    if Path(p).is_absolute():
        return True
    return bool(p and len(p) >= 2 and p[1] == ":")


def _load_logging_config():
    """(enabled, log_dir, base) — enabled is False whenever the config is missing/unreadable."""
    if os.environ.get("SPLIT_MONSTER_NO_LOG"):  # test suites set this — keep real logs clean
        return False, None, None
    try:
        import CONFIG__TOOLS as c
        schema = getattr(c, "CONFIG_SCHEMA_VERSION", 1) or 1
        base = _HERE.parent if schema >= 2 else c.PROJECT_ROOT
        return TOOL_NAME in (c.LOG_ENABLED_TOOLS or []), c.LOG_DIR, base
    except Exception:
        return False, None, None


def _log_call(record):
    try:
        enabled, log_dir, root = _load_logging_config()
        if not enabled:
            return
        log_dir = log_dir or "."
        base = Path(root) if root and not _is_absolute_path(log_dir) else None
        log_path = (base / log_dir if base else Path(log_dir)) / f"{TOOL_NAME}.log.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        record.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%S"))
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


_CLI_STATS = {}  # details the CLI modes (generate / rebase) add to their log record


def _parse_split_line_token(token):
    """One `--split` LINE arg: a single line or comma-separated list (get_codeblock-style)."""
    parts = [p.strip() for p in str(token).split(",") if p.strip()]
    if not parts:
        raise ValueError(f"empty --split line list: {token!r}")
    try:
        return [int(p) for p in parts]
    except ValueError as e:
        raise ValueError(f"invalid --split line number in {token!r}") from e


def _default_cut_level(source_file):
    """How get_codeblock `level` picks the block for `--split LINE` — the language decides
    (`split_langs`): code = 1, the top landmark; Markdown = 0, the innermost heading section."""
    return split_langs.for_file(source_file).CUT_LEVEL


# --------------------------------------------------------------------------- primitives

class Block:
    """A byte-exact top-level code range pulled from one source file."""

    __slots__ = ("source_file", "start", "end", "text", "level")

    def __init__(self, source_file, start, end, text, level=1):
        self.source_file = source_file
        self.start = start
        self.end = end
        self.text = text
        self.level = level

    def __repr__(self):
        return f"Block({self.source_file!r}, {self.start}, {self.end})"


class Replace(Block):
    """Same resolved range as `cut`, plus text to leave in the source on `monster.replace`."""

    __slots__ = ("replacement",)

    def __init__(self, source_file, start, end, text, level, replacement):
        super().__init__(source_file, start, end, text, level)
        self.replacement = replacement

    def __repr__(self):
        return f"Replace({self.source_file!r}, {self.start}, {self.end})"


class Import:
    """A marker around an import-line string — never parsed, just carried and deduped."""

    __slots__ = ("text",)

    def __init__(self, text):
        self.text = text

    def __repr__(self):
        return f"Import({self.text!r})"


def _fingerprint(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _check_expected(block, expect, line):
    """`expect` = fingerprint of the block text recorded when the script was generated. A moved/
    edited block is refused unless `--force` is on the command line (then: warning, proceed)."""
    if not expect or _fingerprint(block.text) == expect:
        return
    msg = (f"block at {block.source_file}:{line} [{block.start}-{block.end}] is not the text the "
           f"plan was made for (the file changed and this line now resolves to something else)")
    if "--force" in sys.argv:
        print(f"WARNING (--force): {msg}", file=sys.stderr)
        monster._note(forced_mismatch=monster._run_get("forced_mismatch", 0) + 1)
        return
    print(f"ERROR: {msg}. Regenerate the script, or pass --force to cut it anyway.", file=sys.stderr)
    monster._note(outcome="refused_block_mismatch")
    sys.exit(2)


def cut(source_file, line, level=None, expect=None):
    """Resolve the block to move for `line` in `source_file`.

    Resolves immediately (not lazily) via get_codeblock addressing — no escalation, no
    guessing the end line myself. Default `level` is file-kind specific (see
    `_default_cut_level`): top-level landmarks for code, innermost heading section for
    Markdown. Pass `level` explicitly to override.
    """
    if level is None:
        level = _default_cut_level(source_file)
    res = _gcb_get_codeblock(source_file, line_num=line, level=level, query=True)
    block = Block(source_file, res["start"], res["end"], res["text"], res["level"])
    _check_expected(block, expect, line)
    return block


def replace(source_file, line, replacement, level=None, expect=None):
    """Like `cut`, but also carries `replacement` for `monster.replace` on the source file.

    `replacement` is substituted for the whole [start..end] range (may be several lines if
    the string contains newlines). Empty string removes the range — same effect as
    `monster.cut` for that block. Use with `monster.write` like a normal block (`.text`
    is still the section content moved to the target).
    """
    b = cut(source_file, line, level=level, expect=expect)
    return Replace(b.source_file, b.start, b.end, b.text, b.level, replacement)


def add_import(text):
    """Wrap an import-line string so it can be collected/deduped/dropped by short name."""
    return Import(text)


def _is_apply():
    return "--apply" in sys.argv


_BOM = b"\xef\xbb\xbf"
_IMPORT_LINE_RE = re.compile(r"^(import\b|from\s+\S+\s+import\b|const\s+\S+\s*=\s*require\()")


def _read_raw(path):
    """(raw_text, eol, bom): `raw_text` is the file UNTOUCHED (CRLF kept); `eol` is the dominant
    line ending, `bom` whether a UTF-8 BOM led the file. All writes go through `_write_raw`, so
    a move never changes a file's line endings or BOM (Windows text mode used to turn LF to CRLF)."""
    data = Path(path).read_bytes()
    bom = data.startswith(_BOM)
    if bom:
        data = data[3:]
    raw = data.decode("utf-8")
    return raw, ("\r\n" if "\r\n" in raw else "\n"), bom


def _write_raw(path, raw, bom):
    Path(path).write_bytes((_BOM if bom else b"") + raw.encode("utf-8"))


def _segments(raw):
    """Lines as `get_codeblock` numbers them (split on `\n` only), each keeping its own ending."""
    return re.findall(r"[^\n]*\n|[^\n]+", raw)


def _nonblank(data):
    text = data.decode("utf-8", "replace").lstrip("﻿")
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


_HEADER_LINE_RE = re.compile(r"^\s*(import\b|from\s+\S+\s+import\b|const\s+\S+\s*=\s*require\()")


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


def _syntax_ok(data, ext):
    """True / False / None (= this format has no syntax check) — the language's own hook."""
    try:
        return split_langs.for_ext(ext).syntax_ok(data, ext)
    except Exception:
        return None


class _Monster:
    """The mutating half of the library — everything here only touches disk under `--apply`.

    Every touched file is journaled first; after the closing `cut`/`replace` on the source
    `verify()` checks nothing was lost or invented and that nothing stopped parsing — on a
    failure it rolls every touched file back to its pre-run bytes."""

    def __init__(self):
        self._before = {}        # path -> original bytes, or None if the file did not exist
        self._added = Counter()  # lines this run is allowed to add: import lines
        self._repl = Counter()   # ... and replacement/stub lines
        self._run = None         # usage record of this move.py run (logged once, at exit)
        self._plan = []          # (target, blocks, imports, lines) — shown by the dry-run summary

    def _note(self, **kv):
        """Accumulate the run's usage record; the first call arms the at-exit log write."""
        if self._run is None:
            self._run = {"tool": TOOL_NAME, "kind": "run", "argv": sys.argv[1:],
                         "script": Path(sys.argv[0]).name, "apply": _is_apply(),
                         "force": "--force" in sys.argv, "blocks": 0, "targets": 0,
                         "imports": 0, "_t0": time.time()}
            atexit.register(self._flush_run)
        self._run.update(kv)

    def _run_get(self, key, default=None):
        return (self._run or {}).get(key, default)

    def _flush_run(self):
        r = self._run
        if not r:
            return
        r.setdefault("outcome", ("incomplete" if r["apply"] else "dry-run"))
        r["duration_ms"] = round((time.time() - r.pop("_t0")) * 1000, 2)
        _log_call(r)

    def _snap(self, path):
        key = str(Path(path))
        if key not in self._before:
            p = Path(path)
            self._before[key] = p.read_bytes() if p.exists() else None

    def expect_source(self, source_file, sha):
        """Warn when `source_file` changed since this script was generated. Not a refusal by
        itself: a changed file is fine as long as every block still resolves to the same text —
        each `cut(..., expect=...)` checks that individually (and refuses unless `--force`)."""
        now = hashlib.sha256(Path(source_file).read_bytes()).hexdigest()[:16]
        self._note(source=str(source_file), stale_warning=(now != sha))
        if now != sha:
            print(f"WARNING: {source_file} changed since this script was generated "
                  f"(hash {sha} -> {now}). Each block is re-checked against its recorded text; "
                  f"a mismatch stops the run unless --force.", file=sys.stderr)

    def write(self, target_file, blocks, imports=None):
        """Write `blocks`/`imports` into `target_file` (dedup imports; new blocks go BEFORE
        whatever body is already there). Only ever touches `target_file` — never `source_file`."""
        imports = imports or []
        header = _dedup_preserve_order([imp.text for imp in imports])
        new_body = _reconstruct_body(blocks)

        target = Path(target_file)
        if target.exists():
            old_raw, eol, bom = _read_raw(target)
            old_header, old_body = _split_header_body(old_raw.replace("\r\n", "\n"))
            header = _dedup_preserve_order(old_header + header)
            body = new_body + old_body  # this batch goes BEFORE whatever was already there
        else:
            eol, bom = ("\n", False)
            if blocks and Path(blocks[0].source_file).exists():
                _, eol, bom = _read_raw(blocks[0].source_file)  # new file inherits source's EOL/BOM
            body = new_body

        lines = list(header)
        if header and body:
            lines.append("")
        lines.extend(body)
        final = "\n".join(lines) + ("\n" if lines else "")

        self._note(targets=self._run_get("targets", 0) + 1,
                   blocks=self._run_get("blocks", 0) + len(blocks),
                   imports=self._run_get("imports", 0) + len(imports))
        if not _is_apply():
            print(f"[dry-run] would write {target_file}: "
                  f"{len(header)} import(s), {len(blocks)} block(s)")
            self._plan.append((str(target_file), len(blocks), len(header),
                               sum(b.end - b.start + 1 for b in blocks)))
            return
        self._snap(target_file)
        for imp in imports:
            self._added.update(_nonblank(imp.text.encode("utf-8")))
        target.parent.mkdir(parents=True, exist_ok=True)
        _write_raw(target, final.replace("\n", eol), bom)
        print(f"wrote {target_file}: {len(header)} import(s), {len(blocks)} block(s)")

    def cut(self, source_file, blocks, imports=None):
        """Remove `blocks`' exact ranges from `source_file` — every block must belong to this
        same `source_file` (raises otherwise); only ever touches `source_file`, never a target.
        `imports` (optional add_import list) are added to the source's header AFTER the cut — what
        the remaining code now needs from the files the blocks moved to."""
        for b in blocks:
            if b.source_file != source_file:
                raise ValueError(
                    f"block from {b.source_file!r} passed to monster.cut({source_file!r})"
                )
        if not _is_apply():
            print(f"[dry-run] would cut {len(blocks)} block(s) from {source_file}")
            self._dry_summary(source_file, blocks, imports)
            return
        self._snap(source_file)
        raw, _eol, bom = _read_raw(source_file)
        segs = _segments(raw)
        for b in sorted(blocks, key=lambda b: b.start, reverse=True):
            del segs[b.start - 1 : b.end]
        added = _insert_imports(segs, imports or [], _eol, split_langs.for_file(source_file), Path(source_file).suffix.lower())
        for text in added:
            self._added.update(_nonblank(text.encode("utf-8")))
        _write_raw(source_file, "".join(segs), bom)
        print(f"cut {len(blocks)} block(s) from {source_file}"
              + (f", +{len(added)} import(s) into it" if added else ""))
        self.verify()

    def replace(self, source_file, blocks, imports=None):
        """Swap each block's [start..end] in `source_file` for its `.replacement` text.

        Accepts `Replace` objects from `replace()`. Empty `.replacement` deletes the range
        (like `cut`). Only touches `source_file`. `write()` still uses `.text` — content
        moved to targets is unchanged. `imports`: as in `cut`.
        """
        for b in blocks:
            if b.source_file != source_file:
                raise ValueError(
                    f"block from {b.source_file!r} passed to monster.replace({source_file!r})"
                )
            if not isinstance(b, Replace):
                raise TypeError(
                    f"monster.replace expects Replace from replace(), got {type(b).__name__}"
                )
        if not _is_apply():
            print(f"[dry-run] would replace {len(blocks)} block(s) in {source_file}")
            self._dry_summary(source_file, blocks, imports)
            return
        self._snap(source_file)
        raw, eol, bom = _read_raw(source_file)
        segs = _segments(raw)
        for b in sorted(blocks, key=lambda b: b.start, reverse=True):
            repl = b.replacement.replace("\r\n", "\n")
            if repl and not repl.endswith("\n"):
                repl = repl + "\n"
            self._repl.update(_nonblank(repl.encode("utf-8")))
            segs[b.start - 1 : b.end] = _segments(repl.replace("\n", eol)) if repl else []
        added = _insert_imports(segs, imports or [], eol, split_langs.for_file(source_file), Path(source_file).suffix.lower())
        for text in added:
            self._added.update(_nonblank(text.encode("utf-8")))
        _write_raw(source_file, "".join(segs), bom)
        print(f"replaced {len(blocks)} block(s) in {source_file}"
              + (f", +{len(added)} import(s) into it" if added else ""))
        self.verify()

    def _dry_summary(self, source_file, blocks, imports):
        """The dry-run table: where the lines go, and what the source ends up with."""
        try:
            total = len(_segments(_read_raw(source_file)[0]))
        except OSError:
            return
        moved = sum(b.end - b.start + 1 for b in blocks)
        print("[dry-run] plan:")
        print(f"  {'file':<44} {'blocks':>6} {'imports':>7} {'lines':>6}")
        for target, nb, ni, nl in self._plan:
            print(f"  {target[-44:]:<44} {nb:>6} {ni:>7} {nl:>6}")
        print(f"  {str(source_file)[-44:]:<44} {'':>6} {len(imports or []):>7} "
              f"{total:>6} -> ~{total - moved + len(imports or [])} after")
        self._plan = []

    def verify(self):
        """After-the-fact safety net for the whole run (journaled files only).

        1. Nothing lost: every non-blank line that existed before still exists somewhere
           (a deduplicated import line is the one tolerated exception).
        2. Nothing invented: lines that appeared are only imports / replacement stubs.
        3. Nothing stopped parsing (only where it parsed before).
        On a failure every touched file is restored byte-for-byte and the run exits 1."""
        if not self._before:
            return
        before, after, problems = Counter(), Counter(), []
        for path, old in self._before.items():
            if old is not None:
                before.update(_nonblank(old))
            now = Path(path).read_bytes() if Path(path).exists() else None
            if now is not None:
                after.update(_nonblank(now))
            ext = Path(path).suffix
            if now is not None and _syntax_ok(now, ext) is False and \
                    (old is None or _syntax_ok(old, ext) is not False):
                problems.append(f"{path}: no longer parses after the move")
        present = set(after)
        lost = {ln: n for ln, n in (before - after).items()
                if not (_IMPORT_LINE_RE.match(ln) and ln in present)}
        if lost:
            sample = "; ".join(f"{n}x {ln[:60]!r}" for ln, n in list(lost.items())[:5])
            problems.append(f"{sum(lost.values())} line(s) LOST: {sample}")
        extra = after - before - self._added - self._repl
        if extra:
            sample = "; ".join(f"{n}x {ln[:60]!r}" for ln, n in list(extra.items())[:5])
            problems.append(f"{sum(extra.values())} line(s) INVENTED: {sample}")
        if problems:
            for path, old in self._before.items():
                if old is None:
                    Path(path).unlink(missing_ok=True)
                else:
                    Path(path).write_bytes(old)
            self._before, self._added, self._repl = {}, Counter(), Counter()
            self._note(outcome="verify_failed", problems=len(problems))
            print("VERIFY FAILED — rolled every touched file back:", file=sys.stderr)
            for pr in problems:
                print(f"  - {pr}", file=sys.stderr)
            sys.exit(1)
        print(f"verified: {sum(before.values())} non-blank line(s) conserved across "
              f"{len(self._before)} file(s), all parse")
        self._before, self._added, self._repl = {}, Counter(), Counter()  # run closed
        self._note(outcome="applied_verified")

    def consumers(self, file_path, symbols, project_root="."):
        """Print (not fix) who outside `file_path` imports each of `symbols` — must be called
        BEFORE any cut, since consumers_of parses live declarations out of `file_path`."""
        try:
            from make_interface_card import consumers_of
        except ImportError as e:  # optional tier not copied along (see the module docstring)
            print(f"# {file_path}: потребителей не искал — make_interface_card недоступен ({e})")
            return
        try:
            data = consumers_of(project_root, file_path)
        except ValueError as e:  # no stamp language for this extension (e.g. .md, .mjs)
            print(f"# {file_path}: потребителей не искал — {e}")
            return
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

def _hint_lines(block, all_lines, top_level_names, lang, ext=""):
    """Cheap best-effort — NOT a real resolver (Vision06: verify by eye). "Referenced elsewhere"
    is a grep over the other lines; "needs" uses the language's identifier scan (no comment/string
    false positives). Languages without name support get no hints."""
    hints = []
    if not lang.HAS_NAMES:
        return hints
    names = lang.declared_names(block.text, ext)
    for name in names:
        pat = re.compile(lang.ref_pattern(name))
        referenced_at = [
            i for i, line in enumerate(all_lines, start=1)
            if not (block.start <= i <= block.end) and pat.search(line)
        ]
        if referenced_at:
            shown = ", ".join(str(n) for n in referenced_at[:5])
            more = ", ..." if len(referenced_at) > 5 else ""
            hints.append(
                f"# best-effort (grep, не резолв): '{name}' встречается ещё на строках "
                f"{shown}{more}"
            )

    used = lang.identifiers(block.text, ext)
    needs = sorted(n for n in used if n in top_level_names and n not in names)
    if needs:
        hints.append(f"# best-effort (идентификаторы, не резолв): возможно нужны — {', '.join(needs)}")
    return hints


def _preview_line(block, lang, ext=""):
    return f"# {lang.decl_line(block.text, ext)}  [{block.start}-{block.end}]"


def _safe_ident(target_file):
    stem = Path(target_file).stem
    ident = re.sub(r"\W+", "_", stem).strip("_").upper()
    return ident or "TARGET"


def _generated_script_api_header(source_kind):
    """One palette for every generated move.py — language of --file does not shrink the API."""
    mode = (
        "replace() + STUB_XX + monster.replace() — типично для .md"
        if source_kind == "md"
        else "cut() + monster.cut() — типично для кода"
    )
    return [
        "# --- split_monster API (полная палитра — одинакова для любого --file) ---",
        "# monster.write(target, blocks, imports) — дописывает .text блоков в target (imports опционально).",
        "# В source после write нужно освободить диапазон блока — два способа:",
        "#   • cut(source, line) → Block → monster.cut(source, blocks) — диапазон удаляется;",
        "#   • replace(source, line, replacement) → Replace (там же .text для write и",
        "#     .replacement для source) → monster.replace(source, blocks) — только Replace[],",
        "#     не Block из cut(); replacement попадает в source на [start..end] (заглушка, md-ссылка, …).",
        "# replacement / STUB_XX — обычные Python-строки, допускают переносы (\\n).",
        "# Пустой replacement = удалить диапазон, как cut.",
        "# add_import(...) — строка import для target; monster.consumers(...) — подсказка, кто ещё",
        "# использует символы (до cut/replace). Всё mutating — только при python move.py --apply.",
        f"# Этот скрипт сгенерирован как: {mode}. Другой способ — вручную до --apply, без",
        "# перезапуска split_monster (см. _MANUAL_APPEND_NOTE ниже).",
        "# --- докстринги примитивов (не дублируют палитру выше, но не противоречат ей) ---",
    ]


def _help_lines(source_kind="code"):
    """Cheat-sheet for the imported names, pulled from their OWN docstrings — not hand-copied,
    so it can't drift out of sync with them. A future session reading a generated script has
    no reason to already know what `cut`/`add_import`/`monster.*` do; this is instead of making
    it go re-read split_monster.py's source to find out."""
    import inspect

    entries = [("cut", cut), ("replace", replace), ("add_import", add_import),
               ("monster.write", _Monster.write), ("monster.cut", _Monster.cut),
               ("monster.replace", _Monster.replace),
               ("monster.consumers", _Monster.consumers)]
    lines = list(_generated_script_api_header(source_kind))
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
    lines.append("# --- конец API / докстрингов ---")
    return lines


def _needed_imports_for_target(blocks, source_imports, lang, ext=""):
    """{specifier: (kind, [(original, local), ...])} restricted to names these `blocks`
    actually USE (the language's identifier scan, not words) — union across every block
    assigned to one target file."""
    used = set()
    for b in blocks:
        used.update(lang.identifiers(b.text, ext))
    needed = {}
    for specifier, info in source_imports.items():
        matched = (list(info["items"]) if info.get("always")
                   else [(orig, local) for orig, local in info["items"] if local in used])
        if matched:
            needed[specifier] = (info["kind"], matched)
    return needed


def _orphan_candidates(same_level_rows, block_start, block_end):
    """Anonymous same-level outline rows STRICTLY outside [block_start, block_end], bounded
    on each side by the nearest NAMED (non-filler) same-level row — offered as fold-in
    candidates for Находка 2, not auto-included. `same_level_rows` must already be filtered
    to one `level` (a comment before a level-2 method is not this level-1 block's neighbor —
    "разорванный диапазон" would result from mixing levels).

    Import-kind rows are excluded — they have their own dedicated propagation (add_import,
    Находка 1) and must never be silently cut out of the source (other code may still need
    them)."""
    before = [r for r in same_level_rows if r["end"] < block_start]
    after = [r for r in same_level_rows if r["start"] > block_end]

    candidates = []
    for r in reversed(before):
        if not r["filler"]:
            break
        if not r["text"].startswith("imports: "):
            candidates.append((r, "до"))
    for r in after:
        if not r["filler"]:
            break
        if not r["text"].startswith("imports: "):
            candidates.append((r, "после"))
    return candidates


# --------------------------------------------------------------------------- split-set graph

def _find_cycles(edges, limit=5):
    """Simple cycles in {node: set(nodes)}, each reported once (rotated to its smallest node)."""
    found, seen = [], set()

    def dfs(start, node, path):
        for nxt in sorted(edges.get(node, ())):
            if nxt == start:
                cyc = path[:]
                k = cyc.index(min(cyc))
                key = tuple(cyc[k:] + cyc[:k])
                if key not in seen:
                    seen.add(key)
                    found.append(list(key) + [key[0]])
            elif nxt not in path and nxt > start and len(path) < 6:
                dfs(start, nxt, path + [nxt])

    for n in sorted(edges):
        dfs(n, n, [n])
        if len(found) >= limit:
            break
    return found[:limit]


def _split_graph(file_path, lang, ext, by_target, all_lines):
    """Dependencies BETWEEN the files of this split — exact, because every moved name is known.

    Not a general resolver: only names declared by the moved blocks (and the names that stay in
    the source) are tracked, found by the identifier scan. Returns None for languages without
    name support, else {"cross": {target: {specifier: ("named", [(n, n)])}},
    "source": {specifier: ("named", [...])}, "notes": [comment lines]}.
    cross[target] = what that target must import from the OTHER targets and from the source;
    source = what the source must import back from the targets once the blocks left."""
    if not lang.GRAPH:
        return None
    moved, owner_block = {}, {}
    for t, blocks in by_target.items():
        for b in blocks:
            for n in lang.declared_names(b.text, ext):
                moved.setdefault(n, t)
                owner_block.setdefault(n, b)
    moved_idx = set()
    for blocks in by_target.values():
        for b in blocks:
            moved_idx.update(range(b.start - 1, b.end))
    remaining = [ln for i, ln in enumerate(all_lines) if i not in moved_idx]
    remaining_names = {n for n in lang.top_level_names(remaining, ext) if n not in moved}

    cross = {t: {} for t in by_target}   # target -> {specifier: [names]}
    src_back = {}                         # specifier -> [names]
    edges = {}                            # file -> {files it imports from}
    used_across = {}                      # name -> who needs it (for export warnings)

    def need(importer, importer_path, name, provider_path):
        spec = _file_spec(importer_path, provider_path, ext)
        return spec

    for t, blocks in by_target.items():
        used = set()
        for b in blocks:
            used |= lang.identifiers(b.text, ext)
        for name in sorted(used & set(moved)):
            other = moved[name]
            if other != t:
                spec = lang.file_spec(t, other)
                cross[t].setdefault(spec, []).append(name)
                edges.setdefault(Path(t).name, set()).add(Path(other).name)
                used_across.setdefault(name, set()).add(Path(t).name)
        for name in sorted(used & remaining_names):
            spec = lang.file_spec(t, file_path)
            cross[t].setdefault(spec, []).append(name)
            edges.setdefault(Path(t).name, set()).add(Path(file_path).name)
            used_across.setdefault(name, set()).add(Path(t).name)
    src_used = lang.identifiers("\n".join(remaining), ext) if remaining else set()
    for name in sorted(src_used & set(moved)):
        spec = lang.file_spec(file_path, moved[name])
        src_back.setdefault(spec, []).append(name)
        edges.setdefault(Path(file_path).name, set()).add(Path(moved[name]).name)
        used_across.setdefault(name, set()).add(Path(file_path).name)

    notes = []
    original_text = "\n".join(all_lines)
    exported = lang.exported_names(original_text)          # None = no visibility notion
    if exported is not None and lang.ENFORCES_PRIVACY:
        for name, users in sorted(used_across.items()):
            if name not in exported:
                where = Path(moved[name]).name if name in moved else Path(file_path).name
                notes.append(f"# WARNING export: `{name}` ({where}) is not exported but is used by "
                             f"{', '.join(sorted(users))} — fix by hand (changes block text, "
                             f"so the tool does not do it)")
    if exported is not None:
        for t, blocks in by_target.items():
            public = sorted({n for b in blocks for n in lang.declared_names(b.text, ext)} & exported)
            if public:
                line = lang.reexport_line(public, lang.file_spec(file_path, t))
                notes.append(f"# NOTE public API: {', '.join(public)} {'is' if len(public) == 1 else 'are'} exported "
                             f"from {Path(file_path).name} and move{'s' if len(public) == 1 else ''} to {Path(t).name} — "
                             f"importers of the source break unless it re-exports"
                             + (f" (e.g. `{line}`)" if line else ""))
        moved_names = sorted(moved)
        for name in lang.dangling_exports(remaining, moved_names):
            notes.append(f"# WARNING dangling export: the source still lists `{name}` in its export list, "
                         f"but `{name}` moves out — remove it from that list (or re-export it)")
    for cyc in _find_cycles(edges):
        notes.append("# WARNING cycle: " + " -> ".join(cyc) + " — circular import between the new files")
    pack = lambda d: {sp: ("named", [(n, n) for n in names]) for sp, names in d.items()}
    return {"cross": {t: pack(d) for t, d in cross.items()}, "source": pack(src_back), "notes": notes}


def _insert_imports(segs, imports, eol, lang, ext=""):
    """Add import lines to the source's header (skipping ones already present). `segs` mutated."""
    present = {s.strip() for s in segs}
    lines = [imp.text for imp in imports if imp.text.strip() not in present]
    if not lines:
        return []
    at = lang.import_insert_index(segs, ext)
    segs[at:at] = [ln + eol for text in lines for ln in text.split("\n")]
    return lines


_MANUAL_APPEND_NOTE = [
    "# --- как дополнить перенос вручную (без перезапуска этого генератора) ---",
    "# 'кандидат' ниже (если есть) — не единственный способ забрать что-то ещё в перенос.",
    "# Тул работает без графа ссылок и мог не увидеть/не предложить нужное, если оно лежит",
    "# не рядом с целью (например константу из другого конца файла). В этом случае можно",
    "# найти нужный диапазон самому (get_codeblock --outline) и дописать снизу —",
    "# cut(FILE, LINE) или replace(FILE, LINE, STUB) + STUB='…\\n', присвоить cXX/rXX,",
    "# добавить в _BLOCKS и в monster.cut или monster.replace. Перегенерировать не нужно.",
    "# --- конец ---",
]


def generate(file_path, splits, out_path, project_root="."):
    """Expand `[(line, target_file), ...]` into a full three-layer script at `out_path`.

    Grouping (which line goes to which target) is decided by the caller — this only expands
    it into the runnable/editable shape (Vision06 Пример Б) with best-effort hint comments.
    """
    ext = Path(file_path).suffix.lower()
    all_lines = Path(file_path).read_text(encoding="utf-8").splitlines()
    lang = split_langs.for_ext(ext)
    top_level_names = lang.top_level_names(all_lines, ext)
    source_imports = lang.source_imports(all_lines, ext)
    outline = _gcb_outline_rows(file_path)
    is_md = lang.STUBS
    src_hash = hashlib.sha256(Path(file_path).read_bytes()).hexdigest()[:16]

    by_target = {}
    seen_ranges = {}  # (start, end) -> target already claimed for this exact resolved range
    for line_no, target in splits:
        block = cut(file_path, line_no)
        key = (block.start, block.end)
        prev_target = seen_ranges.get(key)
        if prev_target is not None:
            if prev_target != target:
                raise ValueError(
                    f"--split {line_no} resolves to the SAME block [{block.start}-{block.end}] "
                    f"as an earlier --split (get_codeblock bands adjacent simple top-level "
                    f"statements into one block) but points at a DIFFERENT target "
                    f"({target!r} vs already-claimed {prev_target!r}) — this one range can only "
                    f"go to one file; pick a single target for the whole band."
                )
            print(f"# note: --split {line_no} is the same banded block as an earlier --split "
                  f"([{block.start}-{block.end}]) — deduped, not written twice")
            continue
        seen_ranges[key] = target
        by_target.setdefault(target, []).append(block)

    graph = _split_graph(file_path, lang, ext, by_target, all_lines)

    out = [
        f"# сгенерировано: split_monster --file {file_path} --split ...",
        "import sys",
        f'sys.path.insert(0, r"{_HERE}")',
        "from split_monster import cut, replace, add_import, monster",
        f"monster.expect_source({file_path!r}, {src_hash!r})  # warns if the file changed since; blocks re-checked",
        "",
        *_help_lines("md" if is_md else "code"),
        "",
        *_MANUAL_APPEND_NOTE,
        "",
    ]
    lang_notes = lang.notes(all_lines, ext)
    if lang_notes:
        out.append("# --- notes about this source file ---")
        out.extend(lang_notes)
        out.append("")
    if graph and graph["notes"]:
        out.append("# --- split-set checks (computed from the names of the moved blocks) ---")
        out.extend(graph["notes"])
        out.append("")
    if not lang.HAS_NAMES:
        out.append(f"# note: name hints / import propagation are NOT available for {ext or 'this file type'} — "
                   f"cut/replace work (get_codeblock addresses the blocks); write imports by hand.")
        out.append("")
    header_len = len(out)

    tag = 0
    list_names = {}
    import_list_names = {}
    all_symbols = []
    # a block already being cut (to ANY target in this batch) is not free to grab, must never
    # be offered as a candidate for another one — checked by CONTAINMENT, not exact-tuple
    # match: outline_rows' own Classifier can report a FINER split (e.g. a comment as its own
    # row, [53-53]) than what cut()'s band-merge actually resolved for the same span ([53-59],
    # comment glued into the following multi-line const) — an exact-tuple check would miss
    # that the narrower row is already fully inside an already-claimed wider one, and offer it
    # as a "free" candidate; if a future session naively cut() it too, the overlapping range
    # would be deleted TWICE (real corruption risk, not just cosmetic noise — found live on
    # prompt-mirror.js, 2026-09-16).
    printed_candidates = set()

    def _already_claimed(cand):
        return any(s <= cand["start"] and cand["end"] <= e for s, e in seen_ranges)

    for target, blocks in by_target.items():
        var_names = []
        for b in blocks:
            tag += 1
            same_level_rows = [r for r in outline if r["level"] == b.level]
            for cand, position in _orphan_candidates(same_level_rows, b.start, b.end):
                key = (cand["start"], cand["end"])
                if key in printed_candidates or _already_claimed(cand):
                    continue
                printed_candidates.add(key)
                out.append(
                    f"# кандидат (не включён): строки [{cand['start']}-{cand['end']}], "
                    f"уровень {b.level}, {position} блока [{b.start}-{b.end}] — забрать: "
                    f"cut({file_path!r}, {cand['start']}), присвоить своему cXX"
                )
            for h in _hint_lines(b, all_lines, top_level_names, lang, ext):
                out.append(h)
            names = lang.declared_names(b.text, ext)
            if len(names) > 1:
                out.append(f"# банд: {len(names)} объявлений в одном диапазоне — "
                            f"{', '.join(names)}")
            out.append(_preview_line(b, lang, ext))
            varname = f"c{tag:02d}"
            if is_md:
                stubname = f"STUB_{tag:02d}"
                out.append(
                    f"# md [{b.start}-{b.end}] → {target!r}: текст-указатель на месте секции "
                    f"(пусто = удалить, как cut)"
                )
                out.append(f'{stubname} = ""')
                out.append(
                    f"{varname} = replace({file_path!r}, {b.start}, {stubname}, "
                    f"expect={_fingerprint(b.text)!r})  #{tag}"
                )
            else:
                out.append(f"{varname} = cut({file_path!r}, {b.start}, "
                           f"expect={_fingerprint(b.text)!r})  #{tag}")
            var_names.append(varname)
            all_symbols.extend(names)
        out.append("")
        list_name = f"{_safe_ident(target)}_BLOCKS"
        list_names[target] = list_name
        out.append(f"{list_name} = [{', '.join(var_names)}]")

        needed = _needed_imports_for_target(blocks, source_imports, lang, ext)
        cross_specs = set()
        if graph:
            for spec, (kind, items) in graph["cross"].get(target, {}).items():
                cross_specs.add(spec)
                if spec in needed:
                    needed[spec] = (needed[spec][0], needed[spec][1] + [i for i in items if i not in needed[spec][1]])
                else:
                    needed[spec] = (kind, items)
        imp_var_names = []
        for i, (specifier, (kind, items)) in enumerate(needed.items(), start=1):
            line_text = lang.render_import(specifier, kind, items)
            impname = f"{_safe_ident(target)}_IMP{i:02d}"
            if specifier in cross_specs:
                out.append("# between the files of this split (names the moved blocks use from each other / the source):")
            out.append(f"{impname} = add_import({line_text!r})")
            imp_var_names.append(impname)
        imports_list_name = f"{_safe_ident(target)}_IMPORTS"
        import_list_names[target] = imports_list_name
        out.append(f"{imports_list_name} = [{', '.join(imp_var_names)}]")
        out.append("")

    if all_symbols and lang.CONSUMERS:
        out.insert(
            header_len,
            f"monster.consumers({file_path!r}, {all_symbols!r}, project_root={project_root!r})",
        )
        out.insert(header_len + 1, "")

    src_imp_arg = ""
    if graph and graph["source"]:
        out.append("# the source still uses names that are moving out — it needs these imports back:")
        names = []
        for i, (spec, (kind, items)) in enumerate(graph["source"].items(), start=1):
            out.append(f"SOURCE_IMP{i:02d} = add_import({lang.render_import(spec, kind, items)!r})")
            names.append(f"SOURCE_IMP{i:02d}")
        out.append(f"SOURCE_IMPORTS = [{', '.join(names)}]")
        out.append("")
        src_imp_arg = ", imports=SOURCE_IMPORTS"

    for target, list_name in list_names.items():
        out.append(f"monster.write({target!r}, {list_name}, {import_list_names[target]})")
    all_blocks = " + ".join(list_names.values())
    if is_md:
        out.append(f"monster.replace({file_path!r}, {all_blocks}{src_imp_arg})")
    else:
        out.append(f"monster.cut({file_path!r}, {all_blocks}{src_imp_arg})")

    Path(out_path).write_text("\n".join(out) + "\n", encoding="utf-8")
    _CLI_STATS.update(lang=lang.NAME, blocks=tag, targets=len(list_names),
                      imports=sum(1 for ln in out if "= add_import(" in ln))
    print(f"generated {out_path} ({tag} block(s), {len(list_names)} target file(s))")


# --------------------------------------------------------------------------- --rebase

_REBASE_CALL_RE = re.compile(
    r"^(?P<pre>\s*\w+ = (?:cut|replace)\((?P<file>'[^']*'|\"[^\"]*\"), )(?P<line>\d+)"
    r"(?P<mid>.*?expect=)['\"](?P<fp>[0-9a-f]+)['\"](?P<post>\).*)$"
)
_REBASE_BARE_CALL_RE = re.compile(r"^\s*\w+ = (?:cut|replace)\(")
_REBASE_PREVIEW_RE = re.compile(r"^# (?P<decl>.*?)  \[(?P<s>\d+)-(?P<e>\d+)\]\s*$")
_REBASE_HASH_RE = re.compile(r"^(?P<pre>monster\.expect_source\((?:'[^']*'|\"[^\"]*\"), )['\"][0-9a-f]+['\"]")


def rebase(script_path, write=False, accept_changed=False):
    """Re-anchor an existing generated script to the CURRENT source — without regenerating it.

    Only the line number of each generated `cut(...)`/`replace(...)` call (plus the preview
    comment's range and the source hash) is rewritten. Hand edits — appended overrides, fixed
    imports, filled STUBs — are never touched. Per block: same text found elsewhere -> moved;
    same NAME but different text -> reported, re-anchored only with `accept_changed`; neither ->
    left as is (the script will refuse that block at run time). Returns the number of blocks
    that could not be re-anchored. Writes only if `write`."""
    raw = Path(script_path).read_bytes()
    bom = raw.startswith(_BOM)
    text = raw[3:].decode("utf-8") if bom else raw.decode("utf-8")
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.replace("\r\n", "\n").split("\n")

    calls = []
    for i, ln in enumerate(lines):
        m = _REBASE_CALL_RE.match(ln)
        if m:
            calls.append((i, m))
    if not calls:
        print(f"{script_path}: no generated cut/replace calls with expect=... found — nothing to rebase")
        return 0
    src_file = ast.literal_eval(calls[0][1].group("file"))
    ext = Path(src_file).suffix.lower()
    lang = split_langs.for_ext(ext)

    # every block the source offers NOW, resolved the same way the script resolves them
    by_fp, by_range, seen_starts = {}, {}, set()
    for row in _gcb_outline_rows(src_file):
        if row["text"].startswith("imports: ") or row["start"] in seen_starts:
            continue
        seen_starts.add(row["start"])
        try:
            b = cut(src_file, row["start"])
        except Exception:
            continue
        by_range.setdefault((b.start, b.end), b)
    for b in by_range.values():
        by_fp.setdefault(_fingerprint(b.text), []).append(b)

    report, unresolved = [], 0
    for i, m in calls:
        old_line, fp = int(m.group("line")), m.group("fp")
        decl, old_range = None, None
        for j in range(i - 1, max(i - 6, -1), -1):
            pm = _REBASE_PREVIEW_RE.match(lines[j])
            if pm:
                decl, old_range = pm.group("decl"), (j, int(pm.group("s")), int(pm.group("e")))
                break
        new_block, how = None, None
        hits = by_fp.get(fp, [])
        if hits:
            new_block = min(hits, key=lambda b: abs(b.start - old_line))
            how = "same" if new_block.start == old_line else "moved"
        else:
            name = lang.name_from_decl(decl) if decl else None
            named = [b for b in by_range.values() if name and name in lang.declared_names(b.text, ext)]
            if len(named) == 1:
                new_block, how = named[0], "changed"
        label = decl or "?"
        if new_block is None:
            unresolved += 1
            report.append(f"  NOT FOUND   line {old_line}: {label} — left as is (run will refuse it)")
            continue
        if how == "same":
            report.append(f"  unchanged   line {old_line}: {label}")
            continue
        if how == "changed" and not accept_changed:
            unresolved += 1
            report.append(f"  CHANGED     {label}: same name now at [{new_block.start}-{new_block.end}] but its "
                          f"TEXT differs — review it, then re-run with --accept-changed")
            continue
        new_fp = fp if how == "moved" else _fingerprint(new_block.text)
        lines[i] = f"{m.group('pre')}{new_block.start}{m.group('mid')}'{new_fp}'{m.group('post')}"
        if old_range:
            j = old_range[0]
            lines[j] = lines[j].replace(f"[{old_range[1]}-{old_range[2]}]", f"[{new_block.start}-{new_block.end}]")
        tag = "moved      " if how == "moved" else "ACCEPTED   "
        report.append(f"  {tag} {label}: line {old_line} -> {new_block.start}"
                      + ("  (text changed, fingerprint updated)" if how == "changed" else ""))

    bare = [i + 1 for i, ln in enumerate(lines)
            if _REBASE_BARE_CALL_RE.match(ln) and not _REBASE_CALL_RE.match(ln)
            and not ln.lstrip().startswith("#")]
    new_hash = hashlib.sha256(Path(src_file).read_bytes()).hexdigest()[:16]
    for i, ln in enumerate(lines):
        hm = _REBASE_HASH_RE.match(ln)
        if hm:
            lines[i] = f"{hm.group('pre')}'{new_hash}'" + ln[hm.end():]
    _CLI_STATS.update(
        lang=lang.NAME, write=bool(write), accept_changed=bool(accept_changed),
        blocks=len(calls), unresolved=unresolved,
        moved=sum(1 for r_ in report if r_.lstrip().startswith("moved")),
        accepted=sum(1 for r_ in report if r_.lstrip().startswith("ACCEPTED")),
        same=sum(1 for r_ in report if r_.lstrip().startswith("unchanged")),
        hand_written=len(bare))
    print(f"rebase {script_path} against {src_file}:")
    print("\n".join(report))
    if bare:
        print(f"  no fingerprint (hand-written, NOT re-anchored — check yourself): script line(s) "
              f"{', '.join(map(str, bare))}")
    if write:
        Path(script_path).write_bytes((_BOM if bom else b"") + nl.join(lines).encode("utf-8"))
        print(f"wrote {script_path}" + (f" — {unresolved} block(s) still need attention" if unresolved else ""))
    else:
        print("(dry — nothing written; add --write to apply)")
    return unresolved


# --------------------------------------------------------------------------- --investigate

def _investigate_blocks(file_path, lang, ext, all_lines):
    """Top-level blocks of the file with what they declare/use: [{start,end,lines,names,uses,used_by}]."""
    rows = [r for r in _gcb_outline_rows(file_path)
            if r["level"] == 1 and not r["text"].startswith("imports: ")]
    blocks, no_names = [], 0
    for r in rows:
        text = "\n".join(all_lines[r["start"] - 1: r["end"]])
        names = lang.declared_names(text, ext)
        if not names:
            no_names += 1
            continue
        blocks.append({"start": r["start"], "end": r["end"], "lines": r["end"] - r["start"] + 1,
                       "names": names, "ids": lang.identifiers(text, ext), "uses": [], "used_by": []})
    owner = {}
    for i, b in enumerate(blocks):
        for n in b["names"]:
            owner.setdefault(n, []).append(i)
    for i, b in enumerate(blocks):
        deps = {j for n in b["ids"] if n in owner for j in owner[n] if j != i}
        b["uses"] = sorted(deps)
    for i, b in enumerate(blocks):
        for j in b["uses"]:
            blocks[j]["used_by"].append(i)
    return blocks, no_names


_ORCH_MIN = 5   # a block that uses >= this many other blocks of the file is an "orchestrator"


def _clusters(blocks, excluded):
    """Connected components over `uses` edges among the blocks NOT in `excluded` (hubs and
    orchestrators would otherwise glue every family into one lump)."""
    parent = list(range(len(blocks)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, b in enumerate(blocks):
        for j in b["uses"]:
            if j in excluded or i in excluded:
                continue
            parent[find(i)] = find(j)
    groups = {}
    for i in range(len(blocks)):
        if i not in excluded:
            groups.setdefault(find(i), []).append(i)
    return sorted(groups.values(), key=lambda g: blocks[g[0]]["start"])


def investigate(file_path, project_root="."):
    """The picture of a monster file for the one who decides the split: every top-level block with
    its size, what it declares, which other blocks of the SAME file it uses and who uses it;
    shared "hub" blocks; clusters of blocks that belong together; a starting `--split` command.
    Facts + a proposal — the grouping stays the caller's call. Uses the language's identifier scan
    (no comment/string noise), not a full resolver."""
    ext = Path(file_path).suffix.lower()
    lang = split_langs.for_ext(ext)
    if not lang.HAS_NAMES or lang.STUBS:
        print(f"investigate: no name graph for {ext or 'this file type'} — use "
              f"`get_codeblock --file {file_path} --outline` and pick the lines yourself")
        return 0
    all_lines = Path(file_path).read_text(encoding="utf-8").splitlines()
    blocks, no_names = _investigate_blocks(file_path, lang, ext, all_lines)
    n = len(blocks)
    hub_min = max(3, -(-n * 3 // 10))          # used by >= max(3, 30% of blocks) -> shared hub
    hubs = {i for i, b in enumerate(blocks) if len(b["used_by"]) >= hub_min}
    _CLI_STATS.update(lang=lang.NAME, blocks=n, hubs=len(hubs))

    def label(i):
        return ",".join(blocks[i]["names"][:2]) + ("+" if len(blocks[i]["names"]) > 2 else "")

    total = sum(b["lines"] for b in blocks)
    print(f"investigate {file_path} — {n} named top-level block(s), {total} line(s) "
          f"of {len(all_lines)}" + (f"; {no_names} unnamed band(s) not listed (comments/glue)" if no_names else ""))
    print(f"{'#':>3} {'lines':>11} {'size':>5}  {'declares':<28} {'uses (same file)':<30} used by")
    for i, b in enumerate(blocks):
        uses = [label(j) for j in b["uses"]]
        used_by = [label(j) for j in b["used_by"]]
        cut_ = lambda xs: ", ".join(xs[:5]) + (f" +{len(xs) - 5}" if len(xs) > 5 else "") if xs else "-"
        mark = " *" if i in hubs else ""
        print(f"{i + 1:>3} {str(b['start']) + '-' + str(b['end']):>11} {b['lines']:>5}  "
              f"{label(i):<28.28} {cut_(uses):<30.30} {cut_(used_by)}{mark}")
    if hubs:
        print(f"\nhubs (*) — used by >= {hub_min} blocks, kept out of the clusters; usually a shared file "
              f"or they stay in the source: " + ", ".join(label(i) for i in sorted(hubs)))
    orch = {i for i, b in enumerate(blocks) if len(b["uses"]) >= _ORCH_MIN and i not in hubs}
    groups = _clusters(blocks, hubs | orch)
    families = [g for g in groups if len(g) >= 2]
    singles = [g[0] for g in groups if len(g) == 1]
    letter = {}
    print(f"\nfamilies (>= 2 blocks linked by 'uses'; hubs and orchestrators left out) — {len(families)}:")
    stem, suffix = Path(file_path).stem, Path(file_path).suffix
    split_args, taken = [], set()
    for k, g in enumerate(families):
        tag = chr(ord("A") + k) if k < 26 else f"F{k}"
        for i in g:
            letter[i] = tag
        lines = sum(blocks[i]["lines"] for i in g)
        pool = [n for i in g for n in blocks[i]["names"]]
        first = next((n for n in pool if not n.isupper()), pool[0])      # a function/class, not a CONSTANT
        print(f"  {tag} [{lines:>4} lines] " + ", ".join(label(i) for i in g))
        tname = re.sub(r"\W+", "_", first).strip("_") or "part"
        while tname in taken:
            tname += "_"
        taken.add(tname)
        split_args.append((",".join(str(blocks[i]["start"]) for i in g), f"{stem}_{tname}{suffix}"))
    if singles:
        print("lone blocks (no link to another non-orchestrator block): " + ", ".join(label(i) for i in singles))
    if orch:
        print(f"orchestrators (use >= {_ORCH_MIN} blocks) and the families they lean on:")
        for i in sorted(orch):
            lean = sorted({letter[j] for j in blocks[i]["uses"] if j in letter})
            print(f"  {label(i)} [{blocks[i]['lines']} lines] -> " + (", ".join(lean) if lean else "no family"))
    if hubs:
        split_args.append((",".join(str(blocks[i]["start"]) for i in sorted(hubs)), f"{stem}_shared{suffix}"))
    print("\nstarting point (a proposal: peel the families off, the core stays — group/rename as you see fit, "
          "then review the generated script):")
    if split_args:
        print(f"  split_monster.py --file {file_path} " +
              " ".join(f'--split {ln} "{t}"' for ln, t in split_args) + " --out-script move.py")
    else:
        print("  (no family to peel off — the blocks are one tangle or independent; decide by the table above)")
    return 0


# --------------------------------------------------------------------------- CLI

_CLI_EPILOG = """
Форматы (--file), резка блоков:
  Границы блоков — get_codeblock (см. get_codeblock__TLDR.md): в т.ч. .js .mjs .ts .tsx .jsx,
  .py, .md/.markdown. Строки для --split берите из `get_codeblock --file F --outline`
  (.md: добавьте --level 4+, строка заголовка).

  Smoke на копиях фикстур: test/topLevel (js, ts, tsx, py), test/mdSRC/*.md,
  test/tsSRC/dyn (*.mjs). Регресс: test/test_split_monster.py.

Автоподстановка import в сгенерированный скрипт (add_import):
  Только ведущие ESM-строки `import … from '…'` в --file (парсер find_code_usage/ts_handler).
  В целевой файл попадает подмножество имён, которые переносимые блоки упоминают (grep по
  тексту, не резолвер). Подходит для JS/TS/TSX/MJS с таким синтаксисом.
  CommonJS require() не сканируется; Python import и Markdown — нет (add_import вручную).

Подсказки в скрипте: best-effort grep (имена объявлений в стиле JS); превью .md — строка заголовка.

Markdown: generate() emits STUB_XX + replace() + monster.replace (stub on месте вырезки); код — cut +
monster.cut.
""".strip()


def _cli(argv=None):
    """Thin logging wrapper around `_cli_impl` — observes argv in, exit code/duration out."""
    t0 = time.time()
    argv_list = list(sys.argv[1:] if argv is None else argv)
    record = {"tool": TOOL_NAME, "kind": ("rebase" if "--rebase" in argv_list else
                                          "investigate" if "--investigate" in argv_list else "generate"),
              "argv": argv_list}
    code = 0
    try:
        _cli_impl(argv)
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        raise
    except BaseException as e:
        code = 1
        record["error"] = f"{type(e).__name__}: {e}"
        raise
    finally:
        record.update(_CLI_STATS)
        record["exit_code"] = code
        record["duration_ms"] = round((time.time() - t0) * 1000, 2)
        _log_call(record)


def _cli_impl(argv=None):
    p = argparse.ArgumentParser(
        prog="split_monster",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Разворачивает line->target_file пары в исполняемый скрипт-перенос (v0). "
            "Сначала get_codeblock --outline, потом --split; python OUT.py [--apply]."
        ),
        epilog=_CLI_EPILOG,
    )
    p.add_argument(
        "--file",
        help="файл-монстр (js/mjs/ts/tsx/py/md/… — см. epilog); блоки режет get_codeblock",
    )
    p.add_argument(
        "--split", nargs=2, action="append", metavar=("LINE", "TARGET"),
        help="номер строки (или список через запятую: 12,34,45) + целевой файл; "
             "флаг повторяемый — каждая пара LINE TARGET. Обязателен без --investigate/--rebase.",
    )
    p.add_argument(
        "--out-script",
        help="куда записать сгенерированный скрипт. Обязателен, если не передан --investigate/--rebase.",
    )
    p.add_argument(
        "--investigate", action="store_true",
        help=(
            "картина файла-монстра для решения о разрезе: все top-level блоки (размер, что объявляют, "
            "какие другие блоки ЭТОГО файла используют и кто использует их), хабы, кластеры и "
            "стартовая команда --split. Только факты + предложение; группировку решаете вы. "
            "Ничего не пишет."
        ),
    )
    p.add_argument("--project-root", default=".", help="для monster.consumers(...)")
    p.add_argument(
        "--rebase", metavar="SCRIPT",
        help="лёгкая перегенерация: переставить номера строк в УЖЕ существующем move.py под "
             "изменившийся источник (по отпечаткам блоков), не трогая ручные правки. Без --write — "
             "только отчёт.",
    )
    p.add_argument("--write", action="store_true", help="с --rebase: записать изменения в SCRIPT")
    p.add_argument("--accept-changed", action="store_true",
                   help="с --rebase: принять и блоки с тем же именем, но изменённым текстом")
    args = p.parse_args(argv)

    if args.rebase:
        sys.exit(1 if rebase(args.rebase, write=args.write, accept_changed=args.accept_changed) else 0)
    if not args.file:
        p.error("--file обязателен (кроме --rebase)")

    if args.investigate:
        sys.exit(investigate(args.file, project_root=args.project_root))

    if not args.split or not args.out_script:
        p.error("--split и --out-script обязательны (кроме --investigate/--rebase)")

    splits = []
    for line_token, target in args.split:
        for line_no in _parse_split_line_token(line_token):
            splits.append((line_no, target))
    generate(args.file, splits, args.out_script, project_root=args.project_root)


if __name__ == "__main__":
    _cli()
