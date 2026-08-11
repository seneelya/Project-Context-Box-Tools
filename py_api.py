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


def collect(path: Path) -> dict:
    """Структурный разбор одного .py через ast — ЕДИНЫЙ источник для текстового
    вывода (`analyze`) и для штемпеля карточки (`card_api`).

    Возвращает dict:
      ok, error, docstring_first,
      functions        [{name, signature}]           — публичные top-level функции,
      classes          [{name, methods:[{name,signature}]}] — публичные классы + публ. методы,
      all_defs         {name: signature}             — ВСЕ top-level def/class (вкл. `_`), для
                                                        поиска сигнатуры потреблённого приватного,
      import_froms     [{module, level, names}]      — from-импорты (для резолва ре-экспортов),
      internal_imports [str], external_imports [str] — как в текстовом выводе.
    """
    src = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return {"ok": False, "error": str(exc), "docstring_first": None,
                "functions": [], "classes": [], "all_defs": {},
                "import_froms": [], "internal_imports": [], "external_imports": []}

    doc = ast.get_docstring(tree)
    docstring_first = doc.strip().splitlines()[0].strip() if doc else None

    functions: list[dict] = []
    classes: list[dict] = []
    all_defs: dict[str, str] = {}
    module_globals: list[str] = []           # top-level assigned names (logger, CONSTS, …)

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            sig = _fmt_signature(node)
            all_defs[node.name] = sig
            if _is_public(node.name):
                functions.append({"name": node.name, "signature": sig})
        elif isinstance(node, ast.ClassDef):
            all_defs[node.name] = node.name
            if not _is_public(node.name):
                continue
            methods = [{"name": it.name, "signature": _fmt_signature(it)}
                       for it in node.body
                       if isinstance(it, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_public(it.name)]
            classes.append({"name": node.name, "methods": methods})
        elif isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    module_globals.append(tgt.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            module_globals.append(node.target.id)

    # Re-exports live in TOP-LEVEL relative imports only — a `from .. import x` nested
    # inside a function is a lazy dependency, NOT a re-export, so scan tree.body (not walk).
    import_froms: list[dict] = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            import_froms.append({"module": node.module or "", "level": node.level or 0,
                                 "names": [a.name for a in node.names]})

    internal_imports: list[str] = []
    external_imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                external_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            level = node.level or 0
            label = f"from {'.' * level}{mod} import {', '.join(a.name for a in node.names)}"
            (internal_imports if _looks_internal(mod, level) else external_imports).append(label)

    return {"ok": True, "error": None, "docstring_first": docstring_first,
            "functions": functions, "classes": classes, "all_defs": all_defs,
            "module_globals": module_globals, "import_froms": import_froms,
            "internal_imports": internal_imports, "external_imports": external_imports}


def analyze(path: Path) -> str:
    data = collect(path)
    if not data["ok"]:
        return f"[py_api] не удалось распарсить {path.name}: {data['error']}"

    out: list[str] = []
    out.append(f"# Подсказка py_api для: {path.name}")
    out.append("# (опциональная сводка из ast; сверяйся с кодом, это не спека)")
    out.append("")

    if data["docstring_first"]:
        out.append(f"Модульный docstring (1-я строка): {data['docstring_first']}")
        out.append("")

    out.append("## Публичные функции")
    if data["functions"]:
        for f in data["functions"]:
            out.append(f"  - {f['signature']}")
    else:
        out.append("  (нет)")
    out.append("")

    out.append("## Публичные классы")
    if data["classes"]:
        for c in data["classes"]:
            out.append(f"  - {c['name']}")
            if c["methods"]:
                for m in c["methods"]:
                    out.append(f"      . {m['signature']}")
            else:
                out.append("      (нет публичных методов)")
    else:
        out.append("  (нет)")
    out.append("")

    out.append("## Импорты — похоже на внутренние (относительные)")
    if data["internal_imports"]:
        for imp in data["internal_imports"]:
            out.append(f"  - {imp}")
    else:
        out.append("  (нет)")
    out.append("")

    out.append("## Импорты — внешние / stdlib")
    if data["external_imports"]:
        for imp in sorted(set(data["external_imports"])):
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
