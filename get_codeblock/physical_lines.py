"""One definition of a line, for every reader of a file (code review R03, R08).

A line ends after `\\n` and keeps its ending (`\\r\\n` stays `\\r\\n`): the same rows tree-sitter
counts, so the text, the map and the addressing agree. `str.splitlines` also breaks on `\\f`,
`\\x85`, `U+2028`, ... and text-mode `open` turns `\\r\\n` into `\\n` — both are wrong here.
A lone `\\r` is not a line break (tree-sitter does not count it either)."""


def split_lines(text):
    """`text` -> its physical lines, endings kept; `"".join(result) == text`."""
    lines = text.split("\n")
    out = [ln + "\n" for ln in lines[:-1]]
    if lines[-1]:
        out.append(lines[-1])
    return out


def read_lines(path, errors="strict"):
    """The file's physical lines, decoded as UTF-8, endings exactly as on disk."""
    with open(path, "rb") as f:
        return split_lines(f.read().decode("utf-8", errors))

