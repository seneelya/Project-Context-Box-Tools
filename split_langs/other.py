"""Fallback language: any extension no module claims. Cut/replace work; nothing else is wired."""

import re

from ._common import WORD_RE

NAME = "other"
EXTENSIONS = ()
HAS_NAMES = False


def declared_names(text):
    return []


def top_level_names(lines):
    return set()


def identifiers(text, ext=""):
    return set(WORD_RE.findall(text))


def decl_line(text):
    return text.splitlines()[0].strip() if text else ""


def name_from_decl(decl):
    return None


def source_imports(lines):
    return {}


def render_import(specifier, kind, items):
    raise ValueError("no import syntax known for this file type")
