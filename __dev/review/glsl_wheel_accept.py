"""Plan10 acceptance: isolated native workers, strict environment and baseline checks."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import importlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import sysconfig
import time
import traceback

HERE = Path(__file__).resolve().parent
BUILD = Path('T:/AgentsWork/glsl-wheel-plan10' if os.name == 'nt' else '/mnt/t/AgentsWork/glsl-wheel-plan10')
SHADERS = Path('Y:/AgentsWork/PlanetWeather/viewer_layered/export/shaders' if os.name == 'nt'
               else '/mnt/y/AgentsWork/PlanetWeather/viewer_layered/export/shaders')
RUNTIME = Path(sysconfig.get_path('platlib'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf8')


def within(path, root):
    return Path(path).resolve().is_relative_to(Path(root).resolve())


def walk(root):
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(reversed(node.children))


def environment(cfg, cpp=False):
    assert not os.environ.get('GLSL_PROBE_RUNTIME'), 'diagnostic runtime override'
    assert not os.environ.get('PYTHONHOME'), 'PYTHONHOME override'
    assert Path(sys.executable).resolve() == Path(cfg['python']).resolve(), 'wrong Python'
    assert platform.architecture()[0] == '64bit', 'wrong architecture'
    assert sys.version_info[:2] == (3, 12), 'wrong Python version'
    for key in ('TEMP', 'TMP'):
        assert within(os.environ[key], BUILD), f'{key} outside build root'
    ts = importlib.import_module('tree_sitter')
    tb = importlib.import_module('tree_sitter._binding')
    module_name = 'tree_sitter_cpp' if cpp else cfg['grammar_module']
    package_name = 'tree-sitter-cpp' if cpp else cfg['grammar_package']
    g = importlib.import_module(module_name)
    gb = importlib.import_module(module_name + '._binding')
    assert metadata.version('tree-sitter') == cfg['runtime_version'], 'wrong runtime version'
    for path in (ts.__file__, tb.__file__):
        assert within(path, cfg['runtime_root']), 'wrong runtime path'
    expected_root = RUNTIME if cpp else Path(cfg['grammar_root'])
    for path in (g.__file__, gb.__file__):
        assert within(path, expected_root), 'wrong grammar path'
    version = metadata.version(package_name)
    if not cpp:
        assert version == cfg['grammar_version'], 'wrong grammar version'
        assert sha(gb.__file__) == cfg['grammar_sha256'], 'wrong grammar binary'
    value = g.language()
    if cfg['runtime_version'] == '0.26.0' or cpp:
        assert type(value).__name__ == 'PyCapsule', 'language() must return PyCapsule'
    lang = ts.Language(value)  # Deliberately no ctypes/fallback.
    info = dict(python=sys.executable, python_version=sys.version, architecture=platform.machine(),
                runtime_version=metadata.version('tree-sitter'), runtime=ts.__file__,
                runtime_binary=tb.__file__, runtime_sha256=sha(tb.__file__),
                grammar_version=version, grammar=g.__file__, grammar_binary=gb.__file__,
                grammar_sha256=sha(gb.__file__), language_type=type(value).__name__,
                abi=lang.abi_version, temp=os.environ['TEMP'], tmp=os.environ['TMP'],
                pythonpath=os.environ.get('PYTHONPATH'))
    return ts, lang, info


def coord(point, index, safe=False):
    return point[index] if safe else (point.row if index == 0 else point.column)


def snapshot(root, src, path, safe=False):
    nodes = list(walk(root))
    counts = Counter(n.type for n in nodes if n.is_named)
    errors = []
    functions = []
    for n in nodes:
        if n.type == 'ERROR' or n.is_missing:
            errors.append(dict(type=n.type, missing=n.is_missing,
                               start=[coord(n.start_point, 0, safe) + 1, coord(n.start_point, 1, safe)],
                               end=[coord(n.end_point, 0, safe) + 1, coord(n.end_point, 1, safe)],
                               bytes=[n.start_byte, n.end_byte]))
        if n.type == 'function_definition':
            functions.append(dict(start=coord(n.start_point, 0, safe) + 1, end=coord(n.end_point, 0, safe) + 1,
                                  text=src[n.start_byte:n.end_byte].decode('utf8', 'replace')[:220]))
    return dict(file=Path(path).name, sha256=hashlib.sha256(src).hexdigest(),
                counts=dict(counts), errors=errors, functions=functions,
                has_error=root.has_error, total_nodes=len(nodes))


def worker(job_path):
    job = json.loads(Path(job_path).read_text(encoding='utf8'))
    env_file = Path(job['out']).with_suffix('.env.json')
    try:
        ts, lang, info = environment(job, job['mode'] == 'cpp')
        # Persist before touching a tree: survives access violations in native code.
        write(env_file, info)
        src = Path(job['file']).read_bytes()
        parser = ts.Parser(lang)
        tree = parser.parse(src)
        if job['mode'] in ('minimal', 'cpp'):
            nodes = list(walk(tree.root_node))
            counts = Counter(n.type for n in nodes if n.is_named)
            errors = [(n.type, coord(n.start_point, 0, job.get('index_points', False)))
                      for n in nodes if n.type == 'ERROR' or n.is_missing]
            result = dict(total_nodes=len(nodes), counts=dict(counts), errors=errors,
                          sha256=hashlib.sha256(src).hexdigest())
        else:
            result = snapshot(tree.root_node, src, job['file'], job.get('index_points', False))
        write(job['out'], dict(environment=info, data=result))
        return 0
    except Exception:
        write(job['out'], dict(error=traceback.format_exc()))
        return 1


def cleaned_env(runtime_root, grammar_root):
    env = os.environ.copy()
    for key in ('GLSL_PROBE_RUNTIME', 'PYTHONPATH', 'PYTHONHOME', 'PYTHONPYCACHEPREFIX'):
        env.pop(key, None)
    paths = [str(p) for p in (grammar_root, runtime_root) if Path(p).resolve() != RUNTIME.resolve()]
    if paths:
        env['PYTHONPATH'] = os.pathsep.join(paths)
    env.update(TEMP=str(BUILD / 'tmp'), TMP=str(BUILD / 'tmp'),
               PYTHONDONTWRITEBYTECODE='1', PIP_CACHE_DIR=str(BUILD / 'pip-cache'))
    return env


def run_job(job, env, timeout):
    cfg_path = Path(job['out']).with_suffix('.job.json')
    write(cfg_path, job)
    started = time.monotonic()
    try:
        proc = subprocess.run([sys.executable, '-X', 'faulthandler', '-B', __file__,
                               '--worker', str(cfg_path)], env=env, capture_output=True,
                              text=True, encoding='utf8', errors='replace', timeout=timeout)
        record = dict(file=Path(job['file']).name, mode=job['mode'], repeat=job['repeat'],
                      exit_code=proc.returncode, timeout=False, stdout=proc.stdout, stderr=proc.stderr)
    except subprocess.TimeoutExpired as exc:
        record = dict(file=Path(job['file']).name, mode=job['mode'], repeat=job['repeat'],
                      exit_code=None, timeout=True, stderr=str(exc))
    record['seconds'] = round(time.monotonic() - started, 4)
    out = Path(job['out'])
    if out.exists():
        record.update(json.loads(out.read_text(encoding='utf8')))
    env_file = out.with_suffix('.env.json')
    if 'environment' not in record and env_file.exists():
        record['environment'] = json.loads(env_file.read_text(encoding='utf8'))
    record['passed'] = record['exit_code'] == 0 and not record['timeout'] and 'data' in record
    return record


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--worker')
    ap.add_argument('--grammar-root', type=Path, default=BUILD / 'glsl-test')
    ap.add_argument('--grammar-version', default='1.0.0+capsule1')
    ap.add_argument('--grammar-module', default='tree_sitter_glsl_spec')
    ap.add_argument('--grammar-package', default='tree-sitter-glsl-spec')
    ap.add_argument('--runtime-root', type=Path, default=RUNTIME)
    ap.add_argument('--runtime-version', default='0.26.0')
    ap.add_argument('--baseline', type=Path)
    ap.add_argument('--make-baseline', action='store_true')
    ap.add_argument('--out', type=Path, default=BUILD / 'glsl_probe_results_runtime26.json')
    ap.add_argument('--work-dir', type=Path, required='--worker' not in sys.argv)
    ap.add_argument('--repeats', type=int, default=20)
    ap.add_argument('--timeout', type=int, default=45)
    ap.add_argument('--jobs', type=int, default=4)
    ap.add_argument('--cpp', type=Path)
    ap.add_argument('--index-points', action='store_true',
                    help='Separate diagnostic variant using Point[0/1]; NOT the original acceptance')
    args = ap.parse_args()
    if args.worker:
        return worker(args.worker)
    assert within(args.work_dir, BUILD), 'work directory must be on T: under build root'
    args.work_dir.mkdir(parents=True, exist_ok=False)
    assert args.repeats > 0 and args.jobs > 0
    assert args.make_baseline or args.baseline, 'baseline required for acceptance'
    assert not args.out.exists(), 'refusing to overwrite existing report'
    files = sorted(p for p in SHADERS.iterdir() if p.suffix in ('.fs', '.vs'))
    assert len(files) == 22, 'expected exactly 22 shaders'
    binaries = [p for p in (args.grammar_root / args.grammar_module).glob('_binding*')
                if p.suffix in ('.pyd', '.so')]
    assert len(binaries) == 1
    cfg = dict(python=sys.executable, runtime_root=str(args.runtime_root.resolve()),
               runtime_version=args.runtime_version, grammar_root=str(args.grammar_root.resolve()),
               grammar_version=args.grammar_version, grammar_sha256=sha(binaries[0]),
               index_points=args.index_points, grammar_module=args.grammar_module,
               grammar_package=args.grammar_package)
    jobs = []
    repeats = 1 if args.make_baseline else args.repeats
    for path in files:
        for repeat in range(repeats):
            jobs.append(dict(cfg, file=str(path), mode='full', repeat=repeat + 1))
    if not args.make_baseline:
        for repeat in range(repeats):
            jobs.append(dict(cfg, file=str(SHADERS / 'cloud-layer.fs'), mode='minimal', repeat=repeat + 1))
            if args.cpp:
                jobs.append(dict(cfg, file=str(args.cpp.resolve()), mode='cpp', repeat=repeat + 1))
    env = cleaned_env(args.runtime_root, args.grammar_root)
    for i, job in enumerate(jobs):
        job['out'] = str(args.work_dir / f'{i:04}.json')
    baseline = None
    if args.baseline:
        baseline = json.loads(args.baseline.read_text(encoding='utf8'))['baseline']
    records = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(run_job, job, env, args.timeout) for job in jobs]
        for future in as_completed(futures):
            record = future.result()
            if record['passed'] and baseline is not None and record['mode'] == 'full':
                expected = baseline.get(record['file'])
                if record['data'] != expected:
                    record['passed'] = False
                    record['differences'] = [key for key in set(record['data']) | set(expected or {})
                                             if record['data'].get(key) != (expected or {}).get(key)]
            records.append(record)
            if len(records) % 40 == 0 or len(records) == len(jobs):
                print(f'{len(records)}/{len(jobs)} completed; failures={sum(not r["passed"] for r in records)}', flush=True)
    records.sort(key=lambda r: (r['mode'], r['file'], r['repeat']))
    report = dict(configuration=cfg, repeats=repeats, input_hashes={p.name: sha(p) for p in files},
                  total=len(jobs), passed=sum(r['passed'] for r in records), records=records)
    if args.make_baseline and report['passed'] == len(jobs):
        report['baseline'] = {r['file']: r['data'] for r in records}
    write(args.out, report)
    print(f'Report: {args.out}; PASS={report["passed"]}/{len(jobs)}', flush=True)
    return 0 if report['passed'] == len(jobs) else 1


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf8')
    sys.exit(main())
