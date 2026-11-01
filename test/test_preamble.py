"""REQ-017: blank rows inside a glued preamble have the map's owner."""
from pathlib import Path
import sys
import tempfile

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))
from get_codeblock.physical_lines import read_lines
from get_codeblock.reader.registry import resolve
from get_codeblock.reader.classify import outline_rows
from get_codeblock.reader.reader import Reader
from get_codeblock.core import get_codeblock


def blank_preamble_ranges(path, lines):
    """Map/focus's canonical glued range for blank rows BEFORE a named header.

    Body gaps and blanks before the first comment are deliberately excluded.
    Pairs actual full-map ranges with raw named headers; no duplicate glue algorithm.
    """
    backend, spec = resolve(Path(path).suffix)
    root = backend.root(''.join(lines).encode('utf-8'))
    mapped = [r for r in outline_rows(path,deep=True) if not r['frame'] and not r['filler']]
    expected = {}

    def walk(scope):
        children = scope.children()
        for child in children:
            frame = spec.unwrap_frame(child)
            definition = None if frame is not None else spec.unwrap_def(child)
            if frame is None and definition is None:
                continue
            if definition is not None:
                # Use the FULL map: the focus selector alone may mistake a trailing
                # comment on the previous statement for this definition's preamble.
                name = spec.name(child)
                if name is None:
                    continue
                row = next((r for r in mapped if r['end']==child.end_row+1
                            and r['start']<=child.start_row+1
                            and (r['text']==name or r['text'].startswith(name+'  '))),None)
                if row is not None:
                    start = row['start']
                    for line in range(start, child.start_row + 1):
                        if not lines[line - 1].strip():
                            expected.setdefault(line, []).append((start, child.end_row + 1))
            body = spec.body(frame if frame is not None else child)
            if body is not None:
                walk(body)
            elif frame is not None:
                walk(frame)

    walk(root)
    return expected


def findings(blocks, line, expected):
    return [f"map preamble [{start}-{end}] absent from ladder at blank line {line}"
            for start, end in expected.get(line, ())
            if not any((b['start'], b['end']) == (start, end) for b in blocks)]


def check_preambles(verbose=True):
    passed = 0
    for ext in ('cpp', 'ts', 'cs', 'glsl', 'py'):
        path = str(TOOLS / 'test/Edge' / ('preamble_gap.' + ext))
        lines = read_lines(path)
        reader = Reader.open(path, lines)
        rows = outline_rows(path)
        for line, bounds in ((3, (2, 8)), (5, (2, 8)), (11, (10, 14))):
            result = get_codeblock(path, line, query=True)
            assert (result['start'], result['end']) == bounds, (ext, line, result)
            assert result['text'] == ''.join(lines[bounds[0]-1:bounds[1]])
            assert any((r['start'], r['end']) == bounds for r in rows), (ext, line, rows)
            focused = outline_rows(path, focus_line=line)
            assert focused and (focused[0]['start'], focused[0]['end']) == bounds, (ext, line, focused)
            passed += 1
        expected = blank_preamble_ranges(path, lines)
        assert set(expected) == {3, 5, 11}, (ext, expected)
        for line in (1, 9, 15):
            blocks = reader.get_blocks(path, line)
            assert all((b['start'], b['end']) not in ((2, 8), (10, 14)) for b in blocks), (ext, line, blocks)
            passed += 1
        assert findings([{'start':1, 'end':15}], 3, expected), 'guard must catch old file fallback'
        assert not findings(reader.get_blocks(path,3), 3, expected)
    if verbose:
        print(f'PASS preamble: {passed} map/focus/query/boundary cases in C++/TS/C#/GLSL/Python')
    with tempfile.TemporaryDirectory(prefix='preamble-') as tmp:
        p = Path(tmp) / 'decorated.py'
        p.write_bytes(b'\n# Header\r\n \t\r\n# Details\r\n\r\n@decorate(\r\n    1,\r\n)\r\ndef f():\r\n    return 1\r\n\r\ndef tail():\r\n    pass\r\n')
        lines = read_lines(str(p))
        for line in (3,5):
            result = get_codeblock(str(p),line,query=True)
            assert (result['start'],result['end']) == (2,10), result
            assert result['text'] == ''.join(lines[1:10])
        for ext in ('cpp','ts','cs','glsl'):
            nested = Path(tmp) / ('nested.' + ext)
            header = 'f() {' if ext == 'ts' else 'void f() {'
            closing = '};' if ext == 'cpp' else '}'
            nested.write_text('class Outer {\n// First\n\n// Second\n' + header + '\n    return;\n}\n' + closing + '\n',encoding='utf-8')
            # GLSL has structs, not classes/methods; use a nested braced function scope instead.
            if ext == 'glsl':
                nested.write_text('void outer() {\n// First\n\n// Second\nif (true) {\n    return;\n}\n}\n',encoding='utf-8')
            blocks = Reader.open(str(nested),read_lines(str(nested))).get_blocks(str(nested),3)
            bounds = (2,4) if ext == 'glsl' else (2,7)
            assert any((b['start'],b['end']) == bounds for b in blocks), (ext,blocks)
        literal = Path(tmp) / 'literal.py'
        literal.write_text('def f():\n    text = """payload\n\n# not a preamble\n\n"""\n    return text\n\ndef tail():\n    pass\n',encoding='utf-8')
        result = get_codeblock(str(literal),3,query=True)
        assert result['start'] <= 3 <= result['end'] and result['end'] <= 7, result
        leaf = Path(tmp) / 'leaf.cpp'
        leaf.write_text('struct Outer {\nint previous; // previous field\n// Field docs\n\nenum Kind value;\n};\nvoid tail() {}\n',encoding='utf-8')
        result = get_codeblock(str(leaf),4,query=True)
        assert (result['start'],result['end']) == (3,5), result
        focused = outline_rows(str(leaf),focus_line=4)
        assert (focused[0]['start'],focused[0]['end']) == (3,5), focused
        namespaced = Path(tmp) / 'namespace.cs'
        namespaced.write_text('namespace Demo; // Enum docs\n\npublic enum Color { Red }\npublic class Tail {}\n',encoding='utf-8')
        result = get_codeblock(str(namespaced),2)
        assert (result['start'],result['end']) == (1,3), result
        for ext,header in [('cpp','void f() {}'),('ts','function f() {}'),
                           ('cs','public class Data {}'),('glsl','void f() {}')]:
            p=Path(tmp)/('trailing.'+ext)
            p.write_text('int previous = 1; // previous statement\n\n// Real preamble\n'+header+'\n'+header.replace('f()', 'tail()').replace('Data','Tail')+'\n',encoding='utf-8')
            # TypeScript uses let; all fixtures are independently authored syntax.
            if ext=='ts':p.write_text(p.read_text().replace('int previous','let previous'),encoding='utf-8')
            r=get_codeblock(str(p),2)
            assert (r['start'],r['end'])==(1,5),(ext,r)
            assert not outline_rows(str(p),focus_line=2),(ext,'false focus preamble')
    if verbose:
        print('PASS nested/leaf owners, decorated Python, whitespace/CRLF, literals and namespace preamble')
    return True


if __name__ == '__main__':
    check_preambles()
    import sweep_invariants as sweep
    with tempfile.TemporaryDirectory(prefix='preamble-sweep-') as tmp:
        p=Path(tmp)/'physical.py'
        p.write_bytes(('def payload():\r\n    text = """a\u2028b\fc\rd"""\r\n    return text\r\n\r\n# Header\r\n\r\n# Details\r\ndef tail():\r\n    pass\r\n').encode('utf-8'))
        checked, violations=sweep.sweep_file(str(p),1,0,check_query=True)
        assert not [v for v in violations if sweep.SEVERITY[v[1]]=='HIGH'], violations
        assert checked==8, checked
    print('PASS sweep physical boundaries (CRLF/lone CR/U+2028/formfeed) and blank preamble')
