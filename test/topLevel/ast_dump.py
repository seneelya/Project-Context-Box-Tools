#!/usr/bin/env python3
"""Эксперимент: голый вывод AST-движков на файле, чтобы увидеть, что они РЕАЛЬНО
отдают для top-level конструкций (константы, макросы, литералы), которые текущий
get_codeblock не показывает.

Два движка:
  1. stdlib `ast`          — родной парсер Python (только .py)
  2. tree-sitter           — тот, что get_codeblock уже использует для не-Python

Запуск:
  python ast_dump.py [FILE]        # по умолчанию toplevel.py, вывод в ast_dump__OUT.txt

Каждый движок печатается двумя видами:
  A) TOP-LEVEL — одна строка на стейтмент модуля (главный вид для нашего вопроса)
  B) FULL      — полный рекурсивный дамп с отступами по глубине
"""
import ast
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_FILE = os.path.join(HERE, "toplevel.py")


def _out_file(path):
    """Вывод рядом со скриптом, имя привязано к входному файлу — прогоны разных
    файлов не затирают друг друга."""
    base = os.path.basename(path)
    return os.path.join(HERE, f"ast_dump__{base}.txt")

TS_LANGS = {  # ext -> (module name, language-callable attribute)
    ".py":  ("tree_sitter_python", "language"),
    ".ts":  ("tree_sitter_typescript", "language_typescript"),
    ".js":  ("tree_sitter_typescript", "language_typescript"),
    ".cpp": ("tree_sitter_cpp", "language"),
    ".hpp": ("tree_sitter_cpp", "language"),
    ".cs":  ("tree_sitter_c_sharp", "language"),
}


# ---------------------------------------------------------------- stdlib ast --

def _ast_extra(node):
    """Короткая сводка ключевых полей узла — имя/цель/тип значения."""
    t = type(node).__name__
    if t in ("FunctionDef", "AsyncFunctionDef", "ClassDef"):
        return f"name={node.name!r}"
    if t == "Assign":
        targets = [_target_name(x) for x in node.targets]
        return f"targets={targets} value={type(node.value).__name__}"
    if t == "AnnAssign":
        return (f"target={_target_name(node.target)} "
                f"annotation={_unparse(node.annotation)} "
                f"value={type(node.value).__name__ if node.value else None}")
    if t == "Name":
        return f"id={node.id!r}"
    if t == "Constant":
        r = repr(node.value)
        return f"pytype={type(node.value).__name__} value={r[:40] + ('...' if len(r) > 40 else '')}"
    if t == "Expr":
        return f"value={type(node.value).__name__}"  # ловит голую строку-выражение
    if t in ("Import", "ImportFrom"):
        names = [a.name for a in node.names]
        mod = getattr(node, "module", None)
        return f"module={mod!r} names={names}"
    if t in ("If", "For", "While", "With"):
        return ""
    return ""


def _target_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _unparse(node)
    if isinstance(node, (ast.Tuple, ast.List)):
        return [_target_name(e) for e in node.elts]
    return type(node).__name__


def _unparse(node):
    try:
        return ast.unparse(node)
    except Exception:
        return type(node).__name__


def _rng(node):
    a = getattr(node, "lineno", None)
    b = getattr(node, "end_lineno", None)
    return f"[{a}-{b}]" if a else "[--]"


def dump_ast(src, out):
    tree = ast.parse(src)

    out.write("=" * 78 + "\n")
    out.write("ENGINE 1: stdlib `ast`\n")
    out.write("=" * 78 + "\n\n")

    out.write("--- A) TOP-LEVEL (module.body, одна строка на стейтмент) ---\n\n")
    for node in tree.body:
        out.write(f"{_rng(node):>12}  {type(node).__name__:<16} {_ast_extra(node)}\n")

    out.write("\n--- B) FULL (рекурсивно, отступ = глубина) ---\n\n")

    def walk(node, depth):
        pad = "  " * depth
        out.write(f"{_rng(node):>12} {pad}{type(node).__name__}  {_ast_extra(node)}\n")
        for child in ast.iter_child_nodes(node):
            walk(child, depth + 1)

    for node in tree.body:
        walk(node, 0)
    out.write("\n")


# ------------------------------------------------------------- tree-sitter --

def _load_ts_language(ext):
    spec = TS_LANGS.get(ext)
    if spec is None:
        return None, f"нет tree-sitter грамматики для {ext}"
    modname, attr = spec
    try:
        mod = __import__(modname)
        from tree_sitter import Language
        return Language(getattr(mod, attr)()), None
    except Exception as e:
        return None, f"{modname} недоступен: {e}"


def dump_treesitter(src_bytes, ext, out):
    out.write("=" * 78 + "\n")
    out.write(f"ENGINE 2: tree-sitter ({ext})\n")
    out.write("=" * 78 + "\n\n")

    lang, err = _load_ts_language(ext)
    if lang is None:
        out.write(f"[пропущено] {err}\n\n")
        return

    from tree_sitter import Parser
    parser = Parser(lang)
    tree = parser.parse(src_bytes)
    root = tree.root_node

    def node_text(n):
        raw = src_bytes[n.start_byte:n.end_byte].decode("utf-8", "replace")
        raw = " ".join(raw.split())
        return raw[:50] + ("..." if len(raw) > 50 else "")

    def rng(n):
        return f"[{n.start_point[0] + 1}-{n.end_point[0] + 1}]"

    out.write("--- A) TOP-LEVEL (именованные дети корня, одна строка) ---\n\n")
    for n in root.named_children:
        out.write(f"{rng(n):>12}  {n.type:<26} {node_text(n)}\n")

    out.write("\n--- B) FULL (рекурсивно; named-узлы; отступ = глубина) ---\n\n")

    def walk(n, depth):
        pad = "  " * depth
        leaf = "" if n.named_children else f"  «{node_text(n)}»"
        out.write(f"{rng(n):>12} {pad}{n.type}{leaf}\n")
        for c in n.named_children:
            walk(c, depth + 1)

    for n in root.named_children:
        walk(n, 0)
    out.write("\n")


# --------------------------------------------------------------------- main --

def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FILE
    ext = os.path.splitext(path)[1].lower()

    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    src_bytes = src.encode("utf-8")

    buf = io.StringIO()
    buf.write(f"FILE: {path}\n")
    buf.write(f"EXT:  {ext}\n\n")

    if ext == ".py":
        dump_ast(src, buf)
    else:
        buf.write("(stdlib ast — только для .py, пропущено)\n\n")

    dump_treesitter(src_bytes, ext, buf)

    text = buf.getvalue()
    out_file = _out_file(path)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"written: {out_file} ({len(text)} chars)")


if __name__ == "__main__":
    main()
