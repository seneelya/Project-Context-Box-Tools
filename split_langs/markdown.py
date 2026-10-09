"""Markdown for split_monster: a block is a heading section; its "name" is the heading's anchor,
and a "use" is a link `](#anchor)` to another section. No imports, no graph."""

import re

NAME = "markdown"
EXTENSIONS = (".md", ".markdown")
CUT_LEVEL = 0      # innermost heading section on the line (level 1 would be the whole H1)
STUBS = True       # the source keeps a link/stub where the section was

_HEADING_RE = re.compile(r"^\s*(#{1,6})\s+(.*)$")


def _slug(title):
    """GitHub-style heading anchor: lowercase, drop punctuation, spaces -> '-'."""
    t = re.sub(r"[`*_~]", "", title.strip().lower())
    t = re.sub(r"[^\w\s-]", "", t, flags=re.UNICODE)
    return re.sub(r"\s", "-", t.strip())


def declared_names(text, ext=""):
    for line in text.splitlines():
        hm = _HEADING_RE.match(line.strip())
        if hm:
            slug = _slug(hm.group(2))
            return [slug] if slug else []
    return []


def top_level_names(lines, ext=""):
    out = set()
    for line in lines:
        hm = _HEADING_RE.match(line.strip())
        if hm and _slug(hm.group(2)):
            out.add(_slug(hm.group(2)))
    return out


def identifiers(text, ext=""):
    return set(re.findall(r"\]\(#([^)\s]+)\)", text))


def decl_line(text, ext=""):
    for line in text.splitlines():
        if _HEADING_RE.match(line.strip()):
            return line.strip()
    return text.splitlines()[0].strip() if text else ""


def name_from_decl(decl):
    hm = _HEADING_RE.match(decl)
    return _slug(hm.group(2)) if hm else None


def source_imports(lines, ext=""):
    return {}


def render_import(specifier, kind, items):
    raise ValueError("Markdown has no imports")


def ref_pattern(name):
    return rf"\(#{re.escape(name)}\)"
