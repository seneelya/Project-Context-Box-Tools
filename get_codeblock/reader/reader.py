"""Reader — единая точка входа приложения (Vision03).

Проверенные режимы (outline / get_blocks / line_level / declarations) ДЕЛЕГИРУЮТСЯ
существующему языковому хендлеру — поведение и паритет (оракул 88/88) сохраняются
бесплатно. Новый режим `.0` (IR-классификация) идёт через reader-backend.

Смысл: `core.py` ходит СЮДА, а не в `get_handler` напрямую. Это фронт-дверь, за
которой позже консолидируются registry/лестница/анализаторы — без правки CLI.
Интерфейс намеренно совпадает с хендлером, поэтому Reader — drop-in замена.
"""

from pathlib import Path

# Один маппинг ext -> language (позже вытеснит 3 копии lang_map в core.py).
_LANG_MAP = {
    '.py': 'python',
    '.ts': 'typescript', '.js': 'typescript',
    '.tsx': 'tsx', '.jsx': 'tsx',
    '.cs': 'csharp',
    '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp', '.c++': 'cpp',
    '.hpp': 'cpp', '.hh': 'cpp', '.hxx': 'cpp', '.h': 'cpp', '.c': 'cpp',
    '.scss': 'css', '.sass': 'css', '.css': 'css',
    '.md': 'markdown', '.markdown': 'markdown',
}


def language_for_ext(ext):
    return _LANG_MAP.get(ext.lower(), 'python')


class Reader:
    def __init__(self, path, lines, language, handler):
        self.path = path
        self.lines = lines
        self.language = language
        self.handler = handler

    @classmethod
    def open(cls, path, lines, language=None):
        if language is None:
            language = language_for_ext(Path(path).suffix)
        from ..handlers import get_handler
        return cls(path, lines, language, get_handler(language))

    # -- проверенные режимы: делегация хендлеру (drop-in-сигнатуры) --------

    def outline(self, lines, max_level=None):
        return self.handler.outline(lines, max_level=max_level)

    def get_blocks(self, file_path, line):
        return self.handler.get_blocks(file_path, line)

    def line_level(self, lines, idx):
        return self.handler.line_level(lines, idx)

    def declarations(self, lines):
        return self.handler.declarations(lines)

    # -- новый режим: .0 (IR через reader-backend) ------------------------

    def classify(self, depth=0):
        from .classify import classify_file
        return classify_file(self.path, depth=depth)
