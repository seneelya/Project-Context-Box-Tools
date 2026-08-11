#!/usr/bin/env python3
"""py_api.py — опциональная подсказка для агента-документатора (Pass 1/Pass 2).

Это ВСПОМОГАТЕЛЬНАЯ подсказка, а НЕ гейт и не замена анализу кода. Скрипт парсит
один .py файл через stdlib-модуль `ast` и печатает в stdout компактную сводку:
публичные функции с сигнатурами, публичные классы и их публичные методы, импорты
(эвристически разделённые на «похоже на внутренние» и «внешние/stdlib») и первую
строку модульного docstring. Ничего не пишет в файлы и не падает на синтаксически
валидном Python.

Использование:
    python py_api.py <путь/к/файлу.py>
"""

import ast
import sys
from pathlib import Path


def _fmt_arg(arg: ast.arg) -> str:
    if arg.annotation is not None:
        try:
            return f"{arg.arg}: {ast.unparse(arg.annotation)}"
        except Exception:
            return arg.arg
    return arg.arg


def _fmt_signature(node) -> str:
    """Собирает читаемую сигнатуру функции/метода без тела."""
    a = node.args
    parts: list[str] = []

    pos = list(a.posonlyargs) + list(a.args)
    defaults = list(a.defaults)
    n_no_default = len(pos) - len(defaults)
    for i, arg in enumerate(pos):
        s = _fmt_arg(arg)
        if i >= n_no_default:
            try:
                s += f"={ast.unparse(defaults[i - n_no_default])}"
            except Exception:
                s += "=..."
        parts.append(s)
        if a.posonlyargs and arg is a.posonlyargs[-1]:
            parts.append("/")

    if a.vararg is not None:
        parts.append("*" + _fmt_arg(a.vararg))
    elif a.kwonlyargs:
        parts.append("*")

    for arg, default in zip(a.kwonlyargs, a.kw_defaults):
        s = _fmt_arg(arg)
        if default is not None:
            try:
                s += f"={ast.unparse(default)}"
            except Exception:
                s += "=..."
        parts.append(s)

    if a.kwarg is not None:
        parts.append("**" + _fmt_arg(a.kwarg))

    returns = ""
    if node.returns is not None:
        try:
            returns = f" -> {ast.unparse(node.returns)}"
        except Exception:
            returns = ""

    prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
    return f"{prefix}{node.name}({', '.join(parts)}){returns}"


def _is_public(name: str) -> bool:
    return not name.startswith("_")


def _looks_internal(module: str | None, level: int) -> bool:
    """Эвристика: относительные импорты (from . / from .._engine) — внутренние."""
    if level and level > 0:
        return True
    return False


def analyze(path: Path) -> str:
    src = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return f"[py_api] не удалось распарсить {path.name}: {exc}"

    out: list[str] = []
    out.append(f"# Подсказка py_api для: {path.name}")
    out.append("# (опциональная сводка из ast; сверяйся с кодом, это не спека)")
    out.append("")

    doc = ast.get_docstring(tree)
    if doc:
        first = doc.strip().splitlines()[0].strip()
        out.append(f"Модульный docstring (1-я строка): {first}")
        out.append("")

    functions: list[str] = []
    classes: list[tuple[str, list[str]]] = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _is_public(node.name):
                functions.append(_fmt_signature(node))
        elif isinstance(node, ast.ClassDef):
            if not _is_public(node.name):
                continue
            methods: list[str] = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if _is_public(item.name):
                        methods.append(_fmt_signature(item))
            classes.append((node.name, methods))

    internal_imports: list[str] = []
    external_imports: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                external_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            names = ", ".join(a.name for a in node.names)
            dots = "." * (node.level or 0)
            label = f"from {dots}{mod} import {names}"
            if _looks_internal(node.module, node.level or 0):
                internal_imports.append(label)
            else:
                external_imports.append(label)

    out.append("## Публичные функции")
    if functions:
        for f in functions:
            out.append(f"  - {f}")
    else:
        out.append("  (нет)")
    out.append("")

    out.append("## Публичные классы")
    if classes:
        for name, methods in classes:
            out.append(f"  - {name}")
            if methods:
                for m in methods:
                    out.append(f"      . {m}")
            else:
                out.append("      (нет публичных методов)")
    else:
        out.append("  (нет)")
    out.append("")

    out.append("## Импорты — похоже на внутренние (относительные)")
    if internal_imports:
        for imp in internal_imports:
            out.append(f"  - {imp}")
    else:
        out.append("  (нет)")
    out.append("")

    out.append("## Импорты — внешние / stdlib")
    if external_imports:
        for imp in sorted(set(external_imports)):
            out.append(f"  - {imp}")
    else:
        out.append("  (нет)")

    return "\n".join(out)


def main() -> int:
    if len(sys.argv) != 2:
        print("Использование: python py_api.py <путь/к/файлу.py>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"[py_api] файл не найден: {path}", file=sys.stderr)
        return 2
    print(analyze(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
