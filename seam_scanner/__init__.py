"""seam_scanner — standalone detector for suspected Runtime-seam patterns (Plan03 pt.3 /
Vision07). Pure grep over known dynamic-call signatures per language; does NOT decide
Kind/Shape/Why for a hit — that's the agent's job after reading `<file> --info-seams` output.

NOT a CLI tool — no `__main__`, no TLDR, no entry-point wrapper at `__HQ/tools/` top level. It's
an internal helper imported by `make_interface_card.py` (`--info-seams`/hint-on-stamp), the same
role `termstyle.py` plays for output formatting elsewhere in this package.

Deliberately NOT exhaustive — a config-shaped list, not hard logic (same spirit as
CONFIG__TOOLS.BLACKLIST_DIRS/ESCALATE_*): extend PATTERNS as real misses turn up on live
projects. `file`-kind (bare `open()`/reads/writes) is deliberately excluded — it fires on nearly
every ordinary config read, too many false positives to be a useful hint (see Vision07).
"""

import os
import re

_EXT_LANG = {
    ".py": "python",
    ".ts": "typescript", ".tsx": "typescript", ".js": "typescript", ".jsx": "typescript",
    ".cs": "csharp",
}

# lang -> [(label, compiled regex)]. Label is shown as-is in `--info-seams` output — pick names
# that hint at the Kind an agent would assign, not just the API name.
PATTERNS = {
    "python": [
        ("by-path: spec_from_file_location", re.compile(r"spec_from_file_location\s*\(")),
        ("by-path: importlib.import_module", re.compile(r"importlib\.import_module\s*\(")),
        ("process: subprocess", re.compile(r"subprocess\.(run|Popen|call|check_output)\s*\(")),
        ("process: os.system", re.compile(r"os\.system\s*\(")),
        ("http: requests", re.compile(r"requests\.(get|post|put|delete|patch)\s*\(")),
        ("event: pub/sub", re.compile(r"\.(subscribe|publish)\s*\(")),
    ],
    "typescript": [
        ("by-path: dynamic import", re.compile(r"\bimport\s*\(")),
        ("by-path: require", re.compile(r"\brequire\s*\(")),
        ("process: child_process", re.compile(r"child_process\.(spawn|exec|execFile|fork)\s*\(")),
        ("http: fetch", re.compile(r"\bfetch\s*\(")),
        ("http: axios", re.compile(r"\baxios\.(get|post|put|delete|patch)\s*\(")),
        ("event: on/emit", re.compile(r"\.(on|emit)\s*\(")),
        ("event: pub/sub", re.compile(r"\.(subscribe|publish)\s*\(")),
    ],
    "csharp": [
        ("by-path: Assembly.Load", re.compile(r"Assembly\.Load\s*\(")),
        ("process: Process.Start", re.compile(r"Process\.Start\s*\(")),
        ("http: HttpClient", re.compile(r"\.(GetAsync|PostAsync|PutAsync|DeleteAsync)\s*\(")),
    ],
}


def scan(file_path, lang=None):
    """-> [(line_no, label, snippet), ...], 1-indexed. Empty list on unknown language, unreadable
    file, or no hits — never raises."""
    lang = lang or _EXT_LANG.get(os.path.splitext(file_path)[1].lower())
    patterns = PATTERNS.get(lang, [])
    if not patterns:
        return []
    try:
        text = open(file_path, encoding="utf-8", errors="replace").read()
    except OSError:
        return []
    hits = []
    for i, line in enumerate(text.splitlines(), start=1):
        for label, rx in patterns:
            if rx.search(line):
                hits.append((i, label, line.strip()))
    return hits
