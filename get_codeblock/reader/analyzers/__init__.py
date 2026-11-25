"""Analyzers — the optional meaning pass over the IR (CONTRACT.md, Recipe C).

`analyzers_for(ext)` lists the analyzers of a format; most formats have none.
"""


def analyzers_for(ext):
    ext = ext.lower()
    if ext in ('.md', '.markdown'):
        from .md_callout import CalloutAnalyzer
        return [CalloutAnalyzer()]
    return []
