"""Shared helpers for split_langs modules (no language knowledge here)."""

import re

WORD_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")


def dedup(items):
    seen = set()
    out = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out


def treesitter_syntax_ok(data, ext):
    """Generic syntax check through get_codeblock's backend for `ext`: True / False, or None when
    that backend has no error flag (Markdown, plain text, ...) or the file can't be parsed at all."""
    try:
        from get_codeblock.reader.registry import resolve
        backend, _spec = resolve(ext)
        node = getattr(backend.root(data), "_n", None)
        if node is None or not hasattr(node, "has_error"):
            return None
        return not node.has_error
    except Exception:
        return None
