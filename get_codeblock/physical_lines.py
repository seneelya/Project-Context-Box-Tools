"""One definition of a line, for every reader of a file (code review R03, R08).

A line ends after `\\n` and keeps its ending (`\\r\\n` stays `\\r\\n`): the same rows tree-sitter
counts, so the text, the map and the addressing agree. `str.splitlines` also breaks on `\\f`,
`\\x85`, `U+2028`, ... and text-mode `open` turns `\\r\\n` into `\\n` — both are wrong here.
A lone `\\r` is not a line break (tree-sitter does not count it either)."""


import re


def split_lines(text):
    """`text` -> its physical lines, endings kept; `"".join(result) == text`."""
    lines = text.split("\n")
    out = [ln + "\n" for ln in lines[:-1]]
    if lines[-1]:
        out.append(lines[-1])
    return out


_CYRILLIC_RUN = re.compile(rb"[\xc0-\xff]{3}")


def _fallback_encodings(data):
    """Single-byte code pages to try after UTF-8. Russian words in cp1251 are runs of bytes
    0xC0-0xFF; Western text (cp1252) has them one by one between ASCII letters -> pick by that.
    Then the system code page, then latin-1, which never fails and keeps every line break."""
    import locale
    first = ["cp1251", "cp1252"] if _CYRILLIC_RUN.search(data) else ["cp1252", "cp1251"]
    try:
        sys_enc = locale.getencoding()          # 3.11+: ignores UTF-8 mode
    except AttributeError:
        sys_enc = locale.getpreferredencoding(False)
    if sys_enc and sys_enc.lower().replace("-", "") not in ("utf8", "ascii", "cp1251", "cp1252"):
        first.append(sys_enc)
    return first + ["latin-1"]


def decode_source(data):
    """bytes -> (text, encoding or None). None = UTF-8. Reading only: a non-UTF-8 file is shown,
    never written back, so a wrong guess costs a few wrong letters, never a line or a block."""
    try:
        return data.decode("utf-8"), None
    except UnicodeDecodeError:
        pass
    for enc in _fallback_encodings(data):
        try:
            return data.decode(enc), enc
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("latin-1"), "latin-1"


def read_source(path):
    """The file's bytes as UTF-8 (re-encoded when it was not): tree-sitter byte offsets, the text
    lines and the labels all agree. Line breaks are ASCII in every encoding tried -> rows stay."""
    with open(path, "rb") as f:
        data = f.read()
    text, enc = decode_source(data)
    return data if enc is None else text.encode("utf-8")


def source_encoding(path):
    """None for a UTF-8 file, else the encoding it was read as."""
    with open(path, "rb") as f:
        return decode_source(f.read())[1]


def read_lines(path, errors="strict"):
    """The file's physical lines, endings exactly as on disk. UTF-8, else `decode_source`'s fallback
    (`errors` is kept for old callers; decoding no longer fails)."""
    with open(path, "rb") as f:
        return split_lines(decode_source(f.read())[0])

