"""Централизованная подкраска вывода для тулов — ТОЛЬКО в терминал.

Правило: красим, если `stdout` — это TTY и не задан `NO_COLOR` (стандарт no-color.org).
При редиректе/пайпе/записи в файл ANSI НЕ применяется — выходит чистый текст (важно,
т.к. вывод парсят/кладут в карту). На Windows best-effort включаем VT-режим консоли.

Использование в туле:
    import termstyle
    print(termstyle.md(text))     # text — обычный markdown-вывод; краска накинется поверх

`md()` подсвечивает markdown-структуру (заголовки, **имена**, стрелки →/←, метку цикла ⟲),
чтобы человек видел форму, а не «стену текста». Машиночитаемый вывод (`--json`) НЕ пропускай
через md() — краска в JSON не нужна.
"""

import os
import re
import sys

_ENABLED = None


def _enable_windows_vt():
    if os.name != "nt":
        return
    try:  # ENABLE_VIRTUAL_TERMINAL_PROCESSING (0x4) на stdout-хэндле (-11)
        import ctypes
        k = ctypes.windll.kernel32
        h = k.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if k.GetConsoleMode(h, ctypes.byref(mode)):
            k.SetConsoleMode(h, mode.value | 0x4)
    except Exception:
        pass


def enabled():
    """True, если красить можно: stdout — TTY и не запрещено NO_COLOR. Кэшируется."""
    global _ENABLED
    if _ENABLED is None:
        _ENABLED = (os.environ.get("NO_COLOR") is None
                    and hasattr(sys.stdout, "isatty") and sys.stdout.isatty())
        if _ENABLED:
            _enable_windows_vt()
    return _ENABLED


# ANSI-обёртки (пустые, если краска выключена) --------------------------------
def _sgr(code, s):
    return f"\x1b[{code}m{s}\x1b[0m" if enabled() else s


def bold(s):    return _sgr("1", s)
def dim(s):     return _sgr("2", s)
def red(s):     return _sgr("31", s)
def green(s):   return _sgr("32", s)
def yellow(s):  return _sgr("33", s)
def blue(s):    return _sgr("34", s)
def magenta(s): return _sgr("35", s)
def cyan(s):    return _sgr("36", s)


def md(text):
    """Подсветить markdown-вывод для терминала. Вне TTY возвращает text как есть."""
    if not enabled():
        return text
    # заголовки '# … / ## …' -> жирный циан (вся строка)
    text = re.sub(r"^(#{1,6} .+)$", lambda m: f"\x1b[1;36m{m.group(1)}\x1b[0m", text, flags=re.M)
    # **имя** -> жирным (маркеры оставляем — это всё ещё markdown)
    text = re.sub(r"\*\*(.+?)\*\*", lambda m: f"\x1b[1m{m.group(0)}\x1b[0m", text)
    # рёбра и метка цикла — акцентными цветами (в т.ч. в строке-легенде -> она же ключ цветов)
    text = text.replace("→", "\x1b[32m→\x1b[0m").replace("←", "\x1b[35m←\x1b[0m")
    text = text.replace("⟲", "\x1b[33m⟲\x1b[0m")
    return text
