"""Золотой слепок СТАРЫХ хендлеров: get_blocks/line_level/outline/declarations по всем
фикстурам. Эталон для parity нового IR-конвейера. Печатает детерминированно.

⚠ Это ЕДИНСТВЕННЫЙ оставшийся вызыватель старой ветки хендлеров
(_treesitter_blocks.outline/get_blocks/line_level, python/md/ts .outline). Оракул (check.py)
уже ходит через Reader. Значит судьба этих старых методов = судьба этого файла: решить,
нужен ли ещё parity-слепок. Пока НЕ режем ни то, ни другое (см. ⚠ SUSPECT-DEAD пометки в handlers/)."""
import os
import sys

TOOLS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # test/parity → tools
sys.path.insert(0, TOOLS)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from get_codeblock.handlers import get_handler  # noqa: E402

LANG = {".py": "python", ".ts": "typescript", ".js": "typescript", ".tsx": "tsx",
        ".jsx": "tsx", ".cs": "csharp", ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp",
        ".hpp": "cpp", ".hh": "cpp", ".h": "cpp", ".c": "cpp",
        ".scss": "css", ".sass": "css", ".css": "css", ".md": "markdown"}

TESTDIR = os.path.join(TOOLS, "test")


SKIP_DIRS = {"secret", "__pycache__", "test__replace_in_files"}


def fixtures():
    out = []
    for root, dirs, files in os.walk(TESTDIR):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in LANG:
                out.append(os.path.join(root, f))
    return sorted(out)


def cap(path):
    lang = LANG[os.path.splitext(path)[1].lower()]
    h = get_handler(lang)
    lines = open(path, encoding="utf-8", errors="replace").readlines()
    rel = os.path.relpath(path, TESTDIR).replace("\\", "/")
    print(f"\n########## {rel}  ({lang}, {len(lines)} lines)")

    # outline
    try:
        rows = h.outline(lines, max_level=None) if hasattr(h, "outline") else []
        print("--- OUTLINE")
        for r in rows:
            print(f"  L{r['level']} [{r['start']}-{r['end']}] {r['text']}")
    except Exception as e:
        print(f"--- OUTLINE ERROR {e!r}")

    # line_level for every line
    try:
        print("--- LINELEVEL")
        vals = [str(h.line_level(lines, i)) for i in range(len(lines))]
        print("  " + ",".join(vals))
    except Exception as e:
        print(f"--- LINELEVEL ERROR {e!r}")

    # get_blocks ladder for every line
    try:
        print("--- LADDER")
        for ln in range(1, len(lines) + 1):
            blocks = h.get_blocks(path, ln)
            lad = [(b["level"], b["start"], b["end"]) for b in blocks]
            print(f"  :{ln} {lad}")
    except Exception as e:
        print(f"--- LADDER ERROR {e!r}")

    # declarations
    try:
        if hasattr(h, "declarations"):
            print("--- DECLARATIONS")
            for d in h.declarations(lines):
                print(f"  {d.get('name')} {d.get('kind')} exp={d.get('exported')} "
                      f"m={len(d.get('methods', []))}")
    except Exception as e:
        print(f"--- DECLARATIONS ERROR {e!r}")


if __name__ == "__main__":
    for p in fixtures():
        cap(p)
