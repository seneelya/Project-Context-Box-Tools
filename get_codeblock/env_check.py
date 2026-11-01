"""Dependency preflight for get_codeblock.

Python (.py) and Markdown (.md) need no third-party packages. The tree-sitter
languages (C/C++, C#, TypeScript) each need a grammar package. When one is used
but not installed, we don't want a raw ImportError traceback — we want a clear
"install this" message.

Mechanic: before dispatching to a language handler, try importing that
language's modules. If they import, all good. If not, read the sibling
``requirements.txt`` (the single source of truth) to build the exact install
command for THIS interpreter and raise EnvError carrying that message.

pip name -> import name follows the standard convention: dashes become
underscores (``tree-sitter-c-sharp`` -> ``tree_sitter_c_sharp``).
"""

import importlib.util
import importlib
import platform
import sysconfig
import sys
from pathlib import Path

REQUIREMENTS = Path(__file__).parent / "requirements.txt"

# Which importable modules each language needs. Python/Markdown need none.
LANGUAGE_MODULES = {
    # A dict entry = a language shipped as our own wheel (``wheels/`` of the tools repo):
    # ``artifacts`` maps sysconfig.get_platform() -> wheel path from the tools root.
    "glsl": {"modules": ["tree_sitter", "tree_sitter_glsl_spec"],
             "artifacts": {"win-amd64": "wheels/tree_sitter_glsl_spec-1.0.0+capsule1-cp310-abi3-win_amd64.whl"},
             "capsule_module": "tree_sitter_glsl_spec"},
    "cpp": ["tree_sitter", "tree_sitter_cpp"],
    "csharp": ["tree_sitter", "tree_sitter_c_sharp"],
    "typescript": ["tree_sitter", "tree_sitter_typescript"],
    "tsx": ["tree_sitter", "tree_sitter_typescript"],
    "css": ["tree_sitter", "tree_sitter_css"],
    "yaml": ["tree_sitter", "tree_sitter_yaml"],
    "shell": ["tree_sitter", "tree_sitter_bash"],
    "powershell": ["tree_sitter", "tree_sitter_powershell"],
    "python": [],
    "markdown": [],
    "text": [],
    "batch": [],
}


class EnvError(RuntimeError):
    """Missing dependencies — carries a ready-to-print install message."""


def _import_name(pip_name):
    """pip distribution name -> importable module name (dashes -> underscores)."""
    return pip_name.replace("-", "_")


def parse_requirements(path=REQUIREMENTS):
    """Parse requirements.txt into [{pip, module, note}, ...].

    Blank/comment lines are skipped; an inline ``# comment`` becomes ``note``.
    """
    deps = []
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return deps
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        note = ""
        if "#" in line:
            line, note = (part.strip() for part in line.split("#", 1))
        if not line:
            continue
        # strip any version spec to get the bare package name
        pip_name = line
        for sep in ("==", ">=", "<=", "~=", ">", "<", "!="):
            if sep in pip_name:
                pip_name = pip_name.split(sep, 1)[0].strip()
                break
        deps.append({"pip": pip_name, "module": _import_name(pip_name), "note": note})
    return deps


def _quote(s):
    return f'"{s}"' if " " in s else s


def install_command(deps, path=REQUIREMENTS):
    """Exact pip install command for THIS interpreter, for the given deps."""
    py = _quote(sys.executable or "python")
    pkgs = " ".join(d["pip"] for d in deps)
    return f"{py} -m pip install {pkgs}"


def missing_report(missing, path=REQUIREMENTS):
    """Crisp message telling the user exactly what to install ('' if none)."""
    if not missing:
        return ""
    py = _quote(sys.executable or "python")
    plural = "package" if len(missing) == 1 else "packages"
    lines = [f"get_codeblock: missing {len(missing)} {plural} (this interpreter: {sys.executable}):"]
    for d in missing:
        lines.append(f"  - {d['pip']}" + (f"   {d['note']}" if d["note"] else ""))
    lines += ["", "Install with:", f"  {install_command(missing, path)}",
              "", f"Or all at once:  {py} -m pip install -r {_quote(str(path))}"]
    return "\n".join(lines)


def ensure_language(language, path=REQUIREMENTS):
    """Try importing `language`'s modules; if any are missing, raise EnvError
    with a crisp install message scoped to just those packages."""
    needed = LANGUAGE_MODULES.get(language, [])
    if isinstance(needed, dict):
        _ensure_artifact(language, needed)
        return
    absent = [m for m in needed if importlib.util.find_spec(m) is None]
    if not absent:
        return
    reqs = {d["module"]: d for d in parse_requirements(path)}
    # Prefer requirements.txt entries; fall back to a bare module name if a
    # needed module somehow isn't listed there.
    missing = [reqs.get(m, {"pip": m.replace("_", "-"), "module": m, "note": ""}) for m in absent]
    raise EnvError(f"'{language}' files need packages that are not installed.\n"
                   + missing_report(missing, path))


def _ensure_artifact(language, entry):
    """Optional local distribution + capsule validation; never load legacy pointers."""
    tools = Path(__file__).resolve().parent.parent
    absent = [m for m in entry['modules'] if importlib.util.find_spec(m) is None]
    failure = None
    if absent:
        failure = f"'{language}' files need packages that are not installed: {', '.join(absent)}."
    elif entry.get('capsule_module'):
        try:
            value = importlib.import_module(entry['capsule_module']).language()
            if type(value).__name__ != 'PyCapsule':
                raise ValueError('language() must return a PyCapsule, not a legacy pointer')
            from tree_sitter import Language
            Language(value)  # validate capsule name and supported grammar ABI as well
        except (ImportError, OSError, TypeError, ValueError, OverflowError) as exc:
            failure = f"'{language}': incompatible installed build ({exc})."
    if failure is None:
        return
    rel = entry['artifacts'].get(sysconfig.get_platform())
    if rel is None or platform.python_implementation() != 'CPython':
        raise EnvError(f"{failure}\nNo prebuilt wheel for this platform; build instructions: "
                       f"wheels/README.md in the tools repo (Project-Context-Box-Tools).")
    python = _quote(sys.executable or 'python')
    artifact = tools / rel
    if not artifact.is_file():
        # a vendored copy (e.g. hermes-filetools/vendor) has no wheels/ next to it
        raise EnvError(f"{failure}\nInstall {Path(rel).name} from wheels/ of the tools repo "
                       f"(Project-Context-Box-Tools), see wheels/README.md there:\n"
                       f"  {python} -m pip install --force-reinstall --no-deps <path to that wheel>")
    raise EnvError(f"{failure}\nInstall the supplied build:\n"
                   f"  {python} -m pip install --force-reinstall --no-deps {_quote(str(artifact))}")
