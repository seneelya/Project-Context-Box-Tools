"""Reproducible GLSL grammar experiment; does not register production profiles."""
import ctypes
import importlib
import importlib.metadata
import json
import subprocess
import sys
import os
import re
import tempfile
from collections import Counter
from pathlib import Path

if '--runtime25' in sys.argv:
    os.environ['GLSL_PROBE_RUNTIME'] = str(Path(tempfile.gettempdir()) / 'projectstarter-glsl-runtime25')
if os.environ.get('GLSL_PROBE_RUNTIME'):
    sys.path.insert(0, os.environ['GLSL_PROBE_RUNTIME'])
from tree_sitter import Language, Parser

TARGET = Path('Y:/AgentsWork/PlanetWeather/viewer_layered/export/shaders')
OUT = Path(__file__).with_name('glsl_probe_results.json')


def language(module):
    value = module.language()
    if isinstance(value, int):
        # Diagnostic adapter only: wheel 1.0.0 returns a legacy raw pointer.
        capsule_new = ctypes.pythonapi.PyCapsule_New
        capsule_new.restype = ctypes.py_object
        capsule_new.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p]
        value = capsule_new(value, b'tree_sitter.Language', None)
    return Language(value)


def walk(root):
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(reversed(node.children))


def record(node, src):
    return dict(type=node.type, start=node.start_point.row + 1,
                end=node.end_point.row + 1,
                text=src[node.start_byte:node.end_byte].decode('utf8', 'replace')[:220])


def lexical_functions(src):
    """Independent brace oracle for these fixtures, not a general GLSL parser."""
    clean = re.sub(rb'/\*.*?\*/|//[^\n]*',
                   lambda m: bytes(10 if b == 10 else 32 for b in m[0]), src, flags=re.S)
    found = []
    for m in re.finditer(rb'(?<!\w)\s*(?:void|float|int|bool|[biud]?vec[234]|mat[234])\s+(\w+)\s*\([^;{}]*\)\s*\{', clean, re.M):
        opening = m.end() - 1
        depth = 1
        end = opening + 1
        while end < len(clean) and depth:
            depth += (clean[end] == 123) - (clean[end] == 125)
            end += 1
        # Start after the regex's leading whitespace, which can include blank rows.
        start = m.start() + len(m[0]) - len(m[0].lstrip())
        found.append(dict(name=m[1].decode(), start=clean[:start].count(b'\n') + 1,
                          end=clean[:end].count(b'\n') + 1))
    return found


def probe(package, module_name, only=None):
    module = importlib.import_module(module_name)
    try:
        Language(module.language())
        direct = 'ok'
    except Exception as exc:
        direct = f'{type(exc).__name__}: {exc}'
    lang = language(module)
    parser = Parser(lang)
    result = dict(version=importlib.metadata.version(package), runtime=importlib.metadata.version('tree-sitter'), direct_load=direct,
                  abi=lang.abi_version, files=[])
    for path in sorted(TARGET.iterdir()):
        if path.suffix not in ('.fs', '.vs'):
            continue
        if only is not None and path.name != only:
            continue
        src = path.read_bytes()
        tree = parser.parse(src)
        root = tree.root_node
        nodes = list(walk(root))
        counts = Counter(n.type for n in nodes if n.is_named)
        errors = [record(n, src) for n in nodes if n.type == 'ERROR' or n.is_missing]
        funcs = [n for n in nodes if n.type == 'function_definition']
        functions = []
        for n in funcs:
            info = record(n, src)
            info['fields'] = {key: child.type for key in ('name', 'declarator', 'body', 'type')
                              if (child := n.child_by_field_name(key)) is not None}
            body = n.child_by_field_name('body')
            info['body'] = record(body, src) if body else None
            functions.append(info)
        item = dict(file=path.name, lines=src.count(b'\n') + bool(src and not src.endswith(b'\n')),
                    has_error=root.has_error, errors=errors, counts=dict(counts), functions=functions)
        oracle = lexical_functions(src)
        item['lexical_oracle'] = oracle
        ranges = {(n.start_point.row + 1, n.end_point.row + 1) for n in funcs}
        item['function_range_mismatches'] = [f for f in oracle if (f['start'], f['end']) not in ranges]
        if path.name in ('cover-map.fs', 'sim-step.fs', 'cover-map.vs'):
            item['top_level'] = [record(n, src) for n in root.named_children]
            item['samples'] = {}
            for typ in ('function_definition', 'declaration', 'preproc_ifdef', 'preproc_if',
                        'preproc_def', 'preproc_function_def', 'for_statement', 'if_statement',
                        'layout_specification', 'layout_qualifier'):
                sample = next((n for n in nodes if n.type == typ), None)
                if sample:
                    item['samples'][typ] = str(sample)[:4000]
        result['files'].append(item)
        print(f'{package}: {path.name}: functions={len(funcs)}, errors={len(errors)}, has_error={root.has_error}')
    return result


if __name__ == '__main__':
    if len(sys.argv) == 5 and sys.argv[1] == '--worker':
        result = probe(sys.argv[2], sys.argv[2].replace('-', '_'), sys.argv[3])
        Path(sys.argv[4]).write_text(json.dumps(result, indent=2), encoding='utf8')
        sys.exit(0)
    results = {}
    for package in ('tree-sitter-glsl-spec', 'tree-sitter-glsl'):
        result = dict(files=[], crashes=[])
        for path in sorted(TARGET.iterdir()):
            if path.suffix not in ('.fs', '.vs'):
                continue
            tmp = OUT.with_suffix('.worker.json')
            worker = subprocess.run([sys.executable, '-u', __file__, '--worker', package, path.name, str(tmp)], capture_output=True, text=True)
            print(worker.stdout, end='')
            if worker.returncode:
                result['crashes'].append(dict(file=path.name, code=worker.returncode, stderr=worker.stderr))
                print('CRASH', package, path.name, worker.returncode, worker.stderr)
            else:
                data = json.loads(tmp.read_text(encoding='utf8'))
                result.update({k: v for k, v in data.items() if k != 'files'})
                result['files'].extend(data['files'])
                tmp.unlink()
        results[package] = result
    if os.environ.get('GLSL_PROBE_RUNTIME'):
        OUT = OUT.with_name('glsl_probe_results_runtime25.json')
    else:
        OUT = OUT.with_name('glsl_probe_results_runtime26_diagnostic.json')
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf8')
    for package, result in results.items():
        print(package, 'direct:', result['direct_load'], 'ABI:', result['abi'])
        for item in result['files']:
            if item['errors']:
                print(item['file'], json.dumps(item['errors'][:8], ensure_ascii=False))
        sample = next((f for f in result['files'] if f['file']=='cover-map.fs'), None)
        if sample:
            print('cover-map function fields:', sample['functions'][0]['fields'])
    print('Report:', OUT)
