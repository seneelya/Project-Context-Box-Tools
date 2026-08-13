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


# Палитра (только цвет, БЕЗ bold — в новых терминалах жирный шрифт тяжёлый и хуже читается).
# Яркие коды 9x дают «светлый» оттенок вместо bold.
_C_HEAD = "96"     # заголовки # / ## — светлый циан
_C_NAME = "93"     # **имя-модуля** — ярко-жёлтый (как в get_codeblock/core.py; маркеры ** снимаем)
_C_SUMM = "90"     # сводка после « — » — серый (bright-black; работает и в cmd, в отличие от faint '2')
_C_USES = "32"     # → uses (исходящие) — зелёный
_C_USEDBY = "35"   # ← used-by (входящие) — магента (другой смысл -> другой цвет)
_C_COUNT = "33"    # ×N (сколько зависит) — жёлтый
_C_CYCLE = "91"    # ⟲ участник цикла — ярко-красный (это предупреждение)

_NAME_RE = re.compile(r"\*\*(.+?)\*\*")
_SUMM_RE = re.compile(r"(—[^—]*)$")      # от длинного тире до конца строки (второе тире маловероятно)
_COUNT_RE = re.compile(r"(×\d+)")


def _paint_line(ln):
    s = ln.lstrip()
    if s.startswith("#"):                                    # заголовок целиком
        return f"\x1b[{_C_HEAD}m{ln}\x1b[0m"
    ln = _NAME_RE.sub(lambda m: f"\x1b[{_C_NAME}m{m.group(1)}\x1b[0m", ln)   # **имя** -> цвет, без **
    ln = _SUMM_RE.sub(lambda m: f"\x1b[{_C_SUMM}m{m.group(1)}\x1b[0m", ln)   # « — сводка» -> приглушённо
    ln = _COUNT_RE.sub(lambda m: f"\x1b[{_C_COUNT}m{m.group(1)}\x1b[0m", ln)  # ×N -> жёлтый
    ln = ln.replace("→", f"\x1b[{_C_USES}m→\x1b[0m").replace("←", f"\x1b[{_C_USEDBY}m←\x1b[0m")
    ln = ln.replace("⟲", f"\x1b[{_C_CYCLE}m⟲\x1b[0m")
    return ln


def md(text):
    """Подсветить markdown-вывод для терминала. Вне TTY возвращает text как есть.

    Красит структуру: заголовки, имена модулей, сводку после « — », рёбра →/←,
    счётчики ×N, метку цикла ⟲. Построчно — чтобы « — » в заголовке не спуталось со сводкой.
    """
    if not enabled():
        return text
    return "\n".join(_paint_line(ln) for ln in text.split("\n"))
