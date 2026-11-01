"""Guard against unsafe tree-sitter Point attribute access (runtime 0.26.0)."""
from pathlib import Path
import re


def violations(root):
    pattern = re.compile(r'\b(?:[A-Za-z_]\w*point|point)\s*\.\s*(?:row|column)\b')
    found = []
    for path in Path(root).rglob('*.py'):
        if any(p in {'__dev', '.git', '__pycache__', '.venv', 'venv'} for p in path.relative_to(root).parts):
            continue
        for line, text in enumerate(path.read_text(encoding='utf-8', errors='replace').split('\n'), 1):
            if pattern.search(text):
                found.append(f'{path.relative_to(root).as_posix()}:{line}')
    return found
