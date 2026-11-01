"""Plan11 acceptance: fixtures by default; --shaders DIR --out JSON for real inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))
from get_codeblock.physical_lines import read_lines
from get_codeblock.reader.reader import Reader
from get_codeblock.reader import classify
from get_codeblock.core import get_codeblock
from get_codeblock.name_resolver import resolve_name


def cli(path, *args):
    result = subprocess.run([sys.executable, '-B', str(TOOLS / 'get_codeblock.py'),
                             '--file', str(path), *args], capture_output=True,
                            encoding='utf-8', errors='replace', timeout=45)
    assert result.returncode == 0, (path, args, result.stderr, result.stdout)
    assert 'Traceback' not in result.stderr
    # --name differs from --line only by the informational name header.
    return '\n'.join(l for l in result.stdout.split('\n') if not l.startswith('//name:'))


def raw_functions(data):
    from tree_sitter import Language, Parser
    import tree_sitter_glsl_spec
    root = Parser(Language(tree_sitter_glsl_spec.language())).parse(data).root_node
    functions, stack = [], [root]
    while stack:
        n = stack.pop()
        if n.type == 'function_definition':
            functions.append({'start': n.start_point[0] + 1, 'end': n.end_point[0] + 1,
                              'text': data[n.start_byte:n.end_byte].decode('utf-8')})
        stack.extend(reversed(n.named_children))
    return functions


def check_file(path, baseline=None):
    data = path.read_bytes()
    lines = read_lines(str(path))
    funcs = raw_functions(data)
    if baseline:
        assert hashlib.sha256(data).hexdigest() == baseline['sha256'], path
        # Plan10 stores the first 220 characters, not the entire function text.
        assert [{**f, 'text': f['text'][:220]} for f in funcs] == baseline['functions'], path
    reader = Reader.open(str(path), lines)
    rows = classify.outline_rows(str(path), deep=True)
    landmarks = [r for r in rows if not r['filler'] and not r['frame']]
    error_rows = set()
    for error in (baseline or {}).get('errors', []):
        error_rows.update(range(error['start'][0] + 1, min(len(lines), error['end'][0] + 1) + 1))
    error_results = []
    for line in range(1, len(lines) + 1):
        blocks = reader.get_blocks(str(path), line)
        assert blocks and all(b['start'] <= line <= b['end'] for b in blocks), (path, line, blocks)
        result = get_codeblock(str(path), line, query=True)
        assert result['start'] <= line <= result['end'], (path, line, result)
        assert result['text'] == ''.join(lines[result['start'] - 1:result['end']])
        # Every map landmark covering this physical line must be addressable with
        # its public preamble range. Frames and collapsed control bands are not landmarks.
        for row in landmarks:
            if row['start'] <= line <= row['end']:
                assert any((b['start'], b['end']) == (row['start'], row['end']) for b in blocks), (path, line, row, blocks)
        if line in error_rows:
            error_results.append({'line': line, 'start': result['start'], 'end': result['end']})
    for fn in funcs:
        name = re.search(r'\b(\w+)\s*\(', fn['text']).group(1)
        match = resolve_name(str(path), name)
        assert match.exact and any(h.line == fn['start'] for h in match.hits), (path, name, match)
        # No special overload behavior: ambiguous names retain the existing CLI contract.
        assert len(match.hits) == 1, (path, name, 'overload requires candidate-based acceptance')
        assert cli(path, '--name', name, '--force') == cli(path, '--line', str(fn['start']), '--query', '--force'), (path, name)
        public = get_codeblock(str(path), fn['start'], query=True)
        assert any(r['start'] == public['start'] and r['end'] == public['end'] for r in rows), (path, name, public)
    return {'file': path.name, 'lines': len(lines), 'functions': len(funcs),
            'errors': len((baseline or {}).get('errors', [])), 'error_results': error_results,
            'sha256': hashlib.sha256(data).hexdigest()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--shaders', type=Path)
    ap.add_argument('--out', type=Path)
    ap.add_argument('--baseline', type=Path,
                    help='runtime 0.25.2 baseline JSON for --shaders (kept outside the repo: private shaders)')
    args = ap.parse_args()
    baseline = {}
    root = args.shaders or TOOLS / 'test/glslSRC'
    if args.shaders:
        if not args.baseline:
            ap.error('--shaders needs --baseline')
        baseline = json.loads(args.baseline.read_text(encoding='utf-8'))['baseline']
    # Existing sweep memoization avoids reparsing identical bytes for every line;
    # it does not alter production algorithms or normalize the output.
    import sweep_invariants
    results = []
    for path in sorted(root.iterdir()):
        if path.suffix not in ('.fs', '.vs', '.glsl'):
            continue
        result = check_file(path, baseline.get(path.name))
        results.append(result)
        print(f"PASS {path.name}: {result['lines']} lines, {result['functions']} functions", flush=True)
    if args.shaders:
        assert len(results) == 22 and sum(r['functions'] for r in results) == 348
    # Keep normal query escalation, including its visible expansion note.
    path = TOOLS / 'test/glslSRC/noise-field.fs'
    normal = cli(path, '--name', 'dirOfAngles')
    forced = cli(path, '--name', 'dirOfAngles', '--force')
    assert normal != forced and ('escalat' in normal.lower() or 'expand' in normal.lower()), normal
    report = {'files': results, 'lines': sum(r['lines'] for r in results),
              'functions': sum(r['functions'] for r in results)}
    if args.out:
        args.out.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f"PASS {len(results)} files / {report['lines']} lines / {report['functions']} functions")


if __name__ == '__main__':
    main()
