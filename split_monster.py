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
import ast
import hashlib
import io
import re
import sys
import tokenize
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

_MD_EXTS = frozenset({".md", ".markdown"})


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
    """How get_codeblock `level` picks the block for `--split LINE`.

    Code (JS/TS/…): absolute level 1 = top landmark in the file hierarchy — a function/
    class line from `--outline` resolves to that whole top-level block.

    Markdown: level 1 is the outermost H1 section (often the whole file). Use 0 =
    innermost heading section on that line (H1..H6) so `--split` on a `##`/`###` line
    from `--outline` cuts that section, not the document root.
    """
    if Path(source_file).suffix.lower() in _MD_EXTS:
        return 0
    return 1


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
        return
    print(f"ERROR: {msg}. Regenerate the script, or pass --force to cut it anyway.", file=sys.stderr)
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


def _dedup_preserve_order(items):
    seen = set()
    out = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out


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
    """True / False / None (= this format has no syntax check here)."""
    ext = ext.lower()
    try:
        if ext == ".py":
            ast.parse(data.decode("utf-8", "replace").lstrip("﻿"))
            return True
        from get_codeblock.reader.registry import resolve
        backend, _spec = resolve(ext)
        node = getattr(backend.root(data), "_n", None)
        if node is None or not hasattr(node, "has_error"):
            return None
        return not node.has_error
    except SyntaxError:
        return False
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

        if not _is_apply():
            print(f"[dry-run] would write {target_file}: "
                  f"{len(header)} import(s), {len(blocks)} block(s)")
            return
        self._snap(target_file)
        for imp in imports:
            self._added.update(_nonblank(imp.text.encode("utf-8")))
        target.parent.mkdir(parents=True, exist_ok=True)
        _write_raw(target, final.replace("\n", eol), bom)
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
        self._snap(source_file)
        raw, _eol, bom = _read_raw(source_file)
        segs = _segments(raw)
        for b in sorted(blocks, key=lambda b: b.start, reverse=True):
            del segs[b.start - 1 : b.end]
        _write_raw(source_file, "".join(segs), bom)
        print(f"cut {len(blocks)} block(s) from {source_file}")
        self.verify()

    def replace(self, source_file, blocks):
        """Swap each block's [start..end] in `source_file` for its `.replacement` text.

        Accepts `Replace` objects from `replace()`. Empty `.replacement` deletes the range
        (like `cut`). Only touches `source_file`. `write()` still uses `.text` — content
        moved to targets is unchanged.
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
        _write_raw(source_file, "".join(segs), bom)
        print(f"replaced {len(blocks)} block(s) in {source_file}")
        self.verify()

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
            print("VERIFY FAILED — rolled every touched file back:", file=sys.stderr)
            for pr in problems:
                print(f"  - {pr}", file=sys.stderr)
            sys.exit(1)
        print(f"verified: {sum(before.values())} non-blank line(s) conserved across "
              f"{len(self._before)} file(s), all parse")
        self._before, self._added, self._repl = {}, Counter(), Counter()  # run closed

    def consumers(self, file_path, symbols, project_root="."):
        """Print (not fix) who outside `file_path` imports each of `symbols` — must be called
        BEFORE any cut, since consumers_of parses live declarations out of `file_path`."""
        from make_interface_card import consumers_of

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

_MD_HEADING_RE = re.compile(r"^\s*(#{1,6})\s+(.*)$")

_TOP_LEVEL_NAME_RE = re.compile(
    r"^(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s+(\w+)"
    r"|^(?:export\s+)?const\s+(\w+)\s*="
    r"|^(?:export\s+)?class\s+(\w+)"
    r"|^(?:export\s+)?let\s+(\w+)\s*="
)
_WORD_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")

_JS_EXTS = frozenset({".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx"})
# node types that mean "this name is USED/declared here" (not a property key, not a comment,
# not string content) — what the identifier scan collects
_JS_IDENT_TYPES = frozenset({"identifier", "type_identifier", "shorthand_property_identifier",
                             "shorthand_property_identifier_pattern"})


def _lang_kind(ext):
    """'py' | 'md' | 'js' | 'other'. 'other' = cut/replace still work (get_codeblock addresses
    the blocks) but name hints and import propagation are NOT wired for it — generate says so."""
    ext = (ext or "").lower()
    if ext == ".py":
        return "py"
    if ext in _MD_EXTS:
        return "md"
    if ext in _JS_EXTS:
        return "js"
    return "other"


def _md_slug(title):
    """GitHub-style heading anchor: lowercase, drop punctuation, spaces -> '-'."""
    t = re.sub(r"[`*_~]", "", title.strip().lower())
    t = re.sub(r"[^\w\s-]", "", t, flags=re.UNICODE)
    return re.sub(r"\s", "-", t.strip())


def _py_parse(text):
    try:
        return ast.parse(text)
    except SyntaxError:
        return None


def _py_target_names(node):
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        return [n for e in node.elts for n in _py_target_names(e)]
    return []


def _py_declared(tree):
    names = []
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(n.name)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                names.extend(_py_target_names(t))
        elif isinstance(n, (ast.AnnAssign, ast.AugAssign)):
            names.extend(_py_target_names(n.target))
    return _dedup_preserve_order(names)


def _declaration_line(text, ext=""):
    """The block's own declaration line — NOT necessarily line 0 of `text`, since get_codeblock
    (correctly) includes a leading comment as part of the same block/range."""
    kind = _lang_kind(ext)
    for line in text.splitlines():
        stripped = line.strip()
        if _MD_HEADING_RE.match(stripped) and kind in ("md", "other", ""):
            return stripped
        if kind == "py":
            if re.match(r"(async\s+def|def|class)\s", stripped) or \
                    re.match(r"[A-Za-z_]\w*\s*(:[^=]*)?=[^=]", stripped):
                return stripped
        elif _TOP_LEVEL_NAME_RE.match(stripped):
            return stripped
    return text.splitlines()[0].strip() if text else ""


def _all_names_in_block(text, ext=""):
    """Every top-level declaration name inside `text`, in order — a banded range (2-3
    declarations merged by get_codeblock because nothing separates them) carries more than
    one; a single declaration just returns a one-item list. Markdown: the section's anchor."""
    kind = _lang_kind(ext)
    if kind == "py":
        tree = _py_parse(text)
        return _py_declared(tree) if tree else []
    if kind == "md":
        for line in text.splitlines():
            hm = _MD_HEADING_RE.match(line.strip())
            if hm:
                slug = _md_slug(hm.group(2))
                return [slug] if slug else []
        return []
    names = []
    for line in text.splitlines():
        if line[:1].isspace():
            continue
        m = _TOP_LEVEL_NAME_RE.match(line)
        if m:
            name = next(g for g in m.groups() if g)
            if name not in names:
                names.append(name)
    return names


def _all_top_level_names(all_lines, ext=""):
    """Names declared at file top level. Only unindented lines count for JS (an indented
    `const x` inside another function is not top level); Python goes through `ast`; Markdown
    = every heading's anchor."""
    kind = _lang_kind(ext)
    if kind == "py":
        tree = _py_parse("\n".join(all_lines))
        return {n: True for n in _py_declared(tree)} if tree else {}
    if kind == "md":
        out = {}
        for line in all_lines:
            hm = _MD_HEADING_RE.match(line.strip())
            if hm and _md_slug(hm.group(2)):
                out[_md_slug(hm.group(2))] = True
        return out
    names = {}
    for line in all_lines:
        if line[:1].isspace():
            continue
        m = _TOP_LEVEL_NAME_RE.match(line)
        if m:
            names[next(g for g in m.groups() if g)] = True
    return names


def _identifiers(text, ext=""):
    """Names a snippet actually USES — code identifiers only. Words inside comments and string
    literals do NOT count (the old `_WORD_RE` scan counted them: a rationale comment that
    mentioned `buildRailRows` produced a bogus add_import). Python: `ast` (tokenize if the
    snippet doesn't parse). JS/TS: tree-sitter identifier nodes. Markdown: link anchors.
    Anything else: plain words (best effort — `_lang_kind` is 'other' there anyway)."""
    kind = _lang_kind(ext)
    if kind == "md":
        return set(re.findall(r"\]\(#([^)\s]+)\)", text))
    if kind == "py":
        tree = _py_parse(text)
        if tree is not None:
            return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        try:
            return {t.string for t in tokenize.generate_tokens(io.StringIO(text).readline)
                    if t.type == tokenize.NAME}
        except (tokenize.TokenError, IndentationError, SyntaxError):
            return set(_WORD_RE.findall(text))
    if kind == "js":
        try:
            from get_codeblock.reader.registry import resolve
            backend, _spec = resolve(ext)
            found, stack = set(), [backend.root(text.encode("utf-8"))]
            while stack:
                n = stack.pop()
                if n.type in _JS_IDENT_TYPES:
                    found.add(n.text())
                stack.extend(n.children())
            return found
        except Exception:
            return set(_WORD_RE.findall(text))
    return set(_WORD_RE.findall(text))


def _ref_pattern(name, ext):
    """How another line mentions `name`: a word for code, `#anchor` for Markdown."""
    if _lang_kind(ext) == "md":
        return rf"\(#{re.escape(name)}\)"
    return rf"\b{re.escape(name)}\b"


def _hint_lines(block, all_lines, top_level_names, ext=""):
    """Cheap best-effort — NOT a real resolver (Vision06: verify by eye). "Referenced elsewhere"
    is still a grep over the other lines; "needs" now uses the identifier scan (no comment/string
    false positives)."""
    hints = []
    if _lang_kind(ext) == "other":
        return hints
    names = _all_names_in_block(block.text, ext)
    for name in names:
        pat = re.compile(_ref_pattern(name, ext))
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

    used = _identifiers(block.text, ext)
    needs = sorted(n for n in used if n in top_level_names and n not in names)
    if needs:
        hints.append(f"# best-effort (идентификаторы, не резолв): возможно нужны — {', '.join(needs)}")
    return hints


def _preview_line(block, ext=""):
    return f"# {_declaration_line(block.text, ext)}  [{block.start}-{block.end}]"


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


def _py_source_imports(source_text):
    """Same shape as the JS reader: {specifier: {"kind", "items"}} for TOP-LEVEL `import` /
    `from … import` statements. kinds: 'named' (from-import), 'module' (plain import).
    A relative import keeps its dots in the specifier. `from __future__` and `*` are skipped."""
    tree = _py_parse(source_text)
    imports = {}
    if tree is None:
        return imports
    for n in tree.body:
        if isinstance(n, ast.ImportFrom) and n.module != "__future__":
            spec = "." * n.level + (n.module or "")
            entry = imports.setdefault(spec, {"kind": "named", "items": []})
            for a_ in n.names:
                if a_.name == "*":
                    continue
                pair = (a_.name, a_.asname or a_.name)
                if pair not in entry["items"]:
                    entry["items"].append(pair)
        elif isinstance(n, ast.Import):
            for a_ in n.names:
                local = a_.asname or a_.name.split(".")[0]
                entry = imports.setdefault(a_.name, {"kind": "module", "items": []})
                if (a_.name, local) not in entry["items"]:
                    entry["items"].append((a_.name, local))
    return {k: v for k, v in imports.items() if v["items"]}


def _source_imports(source_lines, ext=".js"):
    """{specifier: {"kind": "named"|"default"|"namespace"|"module", "items": [(original, local), ...]}}
    for the leading imports of `source_lines`. JS/TS: leading ES imports (stops at the first
    line that is neither blank, a comment, nor an import), read via find_code_usage's own
    ts_handler regexes (Находка 1, Vision06) — not reinvented; multi-line `import {...}` collapsed
    first via ts_handler's own `_join_multiline_imports` (Plan04-CARRY п.4). Python: `ast`.
    Markdown / other languages: none."""
    kind = _lang_kind(ext)
    if kind == "py":
        return _py_source_imports("\n".join(source_lines))
    if kind != "js":
        return {}
    from find_code_usage.handlers.ts_handler import TypeScriptHandler

    handler = TypeScriptHandler()
    lines = handler._join_multiline_imports(list(source_lines))

    imports = {}

    def _add(specifier, kind, items):
        entry = imports.setdefault(specifier, {"kind": kind, "items": []})
        for pair in items:
            if pair not in entry["items"]:
                entry["items"].append(pair)

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith(("//", "*", "/*")):
            continue
        m = TypeScriptHandler.ES_NAMED_RE.match(line)
        if m:
            _add(m.group(2).strip(), "named", handler._parse_named_items(m.group(1)))
            continue
        m = TypeScriptHandler.ES_DEFAULT_RE.match(line)
        if m:
            _add(m.group(2).strip(), "default", [(m.group(1), m.group(1))])
            continue
        m = TypeScriptHandler.ES_NAMESPACE_RE.match(line)
        if m:
            _add(m.group(2).strip(), "namespace", [(m.group(1), m.group(1))])
            continue
        if not stripped.startswith("import"):
            break  # first real line of code — leading-import scan is over
    return imports


def _needed_imports_for_target(blocks, source_imports, ext=""):
    """{specifier: (kind, [(original, local), ...])} restricted to names these `blocks`
    actually USE (identifier scan, not words) — union across every block assigned to one target."""
    used = set()
    for b in blocks:
        used.update(_identifiers(b.text, ext))
    needed = {}
    for specifier, info in source_imports.items():
        matched = [(orig, local) for orig, local in info["items"] if local in used]
        if matched:
            needed[specifier] = (info["kind"], matched)
    return needed


def _render_import_line(specifier, kind, items, ext=""):
    """Reconstructs one import statement — NOT copied verbatim from the source (a target may
    need only a subset of one specifier's names)."""
    if _lang_kind(ext) == "py":
        if kind == "named":
            parts = [orig if orig == local else f"{orig} as {local}" for orig, local in items]
            return f"from {specifier} import {', '.join(parts)}"
        if kind == "module":
            return "\n".join(
                f"import {orig}" if local == orig.split(".")[0] else f"import {orig} as {local}"
                for orig, local in items)
    if kind == "named":
        parts = [orig if orig == local else f"{orig} as {local}" for orig, local in items]
        return f"import {{ {', '.join(parts)} }} from '{specifier}'"
    if kind == "default":
        return f"import {items[0][1]} from '{specifier}'"
    if kind == "namespace":
        return f"import * as {items[0][1]} from '{specifier}'"
    raise ValueError(f"unknown import kind {kind!r}")


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
    top_level_names = _all_top_level_names(all_lines, ext)
    source_imports = _source_imports(all_lines, ext)
    outline = _gcb_outline_rows(file_path)
    is_md = ext in _MD_EXTS
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
    if _lang_kind(ext) == "other":
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
            for h in _hint_lines(b, all_lines, top_level_names, ext):
                out.append(h)
            names = _all_names_in_block(b.text, ext)
            if len(names) > 1:
                out.append(f"# банд: {len(names)} объявлений в одном диапазоне — "
                            f"{', '.join(names)}")
            out.append(_preview_line(b, ext))
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

        needed = _needed_imports_for_target(blocks, source_imports, ext)
        imp_var_names = []
        for i, (specifier, (kind, items)) in enumerate(needed.items(), start=1):
            line_text = _render_import_line(specifier, kind, items, ext)
            impname = f"{_safe_ident(target)}_IMP{i:02d}"
            out.append(f"{impname} = add_import({line_text!r})")
            imp_var_names.append(impname)
        imports_list_name = f"{_safe_ident(target)}_IMPORTS"
        import_list_names[target] = imports_list_name
        out.append(f"{imports_list_name} = [{', '.join(imp_var_names)}]")
        out.append("")

    if all_symbols and _lang_kind(ext) in ("py", "js"):
        out.insert(
            header_len,
            f"monster.consumers({file_path!r}, {all_symbols!r}, project_root={project_root!r})",
        )
        out.insert(header_len + 1, "")

    for target, list_name in list_names.items():
        out.append(f"monster.write({target!r}, {list_name}, {import_list_names[target]})")
    all_blocks = " + ".join(list_names.values())
    if is_md:
        out.append(f"monster.replace({file_path!r}, {all_blocks})")
    else:
        out.append(f"monster.cut({file_path!r}, {all_blocks})")

    Path(out_path).write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"generated {out_path} ({tag} block(s), {len(list_names)} target file(s))")


# --------------------------------------------------------------------------- --rebase

_REBASE_CALL_RE = re.compile(
    r"^(?P<pre>\s*\w+ = (?:cut|replace)\((?P<file>'[^']*'|\"[^\"]*\"), )(?P<line>\d+)"
    r"(?P<mid>.*?expect=)['\"](?P<fp>[0-9a-f]+)['\"](?P<post>\).*)$"
)
_REBASE_BARE_CALL_RE = re.compile(r"^\s*\w+ = (?:cut|replace)\(")
_REBASE_PREVIEW_RE = re.compile(r"^# (?P<decl>.*?)  \[(?P<s>\d+)-(?P<e>\d+)\]\s*$")
_REBASE_HASH_RE = re.compile(r"^(?P<pre>monster\.expect_source\((?:'[^']*'|\"[^\"]*\"), )['\"][0-9a-f]+['\"]")


def _name_from_decl(decl, ext):
    """Declaration name out of a generated preview line (`def user():`, `function f() {`, `## Beta`)."""
    kind = _lang_kind(ext)
    if kind == "md":
        hm = _MD_HEADING_RE.match(decl)
        return _md_slug(hm.group(2)) if hm else None
    if kind == "py":
        m = re.match(r"(?:async\s+def|def|class)\s+(\w+)", decl)
        if m:
            return m.group(1)
        m = re.match(r"([A-Za-z_]\w*)\s*(?::[^=]*)?=", decl)
        return m.group(1) if m else None
    m = _TOP_LEVEL_NAME_RE.match(decl)
    return next(g for g in m.groups() if g) if m else None


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
            name = _name_from_decl(decl, ext) if decl else None
            named = [b for b in by_range.values() if name and name in _all_names_in_block(b.text, ext)]
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
             "флаг повторяемый — каждая пара LINE TARGET. Обязателен без --investigate.",
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
        print(
            "--investigate ещё не реализован — это v1 (граф блок<->блок с честным резолвом), "
            "задумано, но не построено. См. Vision06__monster-file-split.md, секция 'v1'. "
            "Сейчас доступна только группировка через --split (v0, дешёвая grep-подсказка).",
            file=sys.stderr,
        )
        sys.exit(2)

    if not args.split or not args.out_script:
        p.error("--split и --out-script обязательны (если не передан --investigate)")

    splits = []
    for line_token, target in args.split:
        for line_no in _parse_split_line_token(line_token):
            splits.append((line_no, target))
    generate(args.file, splits, args.out_script, project_root=args.project_root)


if __name__ == "__main__":
    _cli()
