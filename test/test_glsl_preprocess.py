"""Synthetic regressions for Vulkan masks, protected text and false comparisons."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from get_codeblock.glsl_source import preprocess_bytes
from get_codeblock.reader.profiles.glsl import GLSL


def check_masks():
    mask = GLSL.langspec.preprocess
    cases = [
        b'if (a < b && c > d) return;',
        b'int value = a < b ? c : d > e;',
        b'coopmat < a && c > d;',
        b'tensorLayoutNV < a && c > d;',
        b'OtherType<a,b,c,d,e> value;',
        b'obj.coopmat<float, Scope, 8, 8, Use>(0.0);',
        b'coopmat<float, Scope, 8, 8, Use> + other;',
        b'coopmat<float, Scope, 8; x > y;',
        b'coopmat<float, Scope, (evil { body; }), 8, Use> value;',
        b'[[unroll] for (int i=0;i<4;i++) {}',
        b'[[bad { body; }]] for (;;) {}',
        b'// [[unroll]] coopmat<float, Scope, 8, 8, Use> a;\n',
        b'/* [[unroll]] tensorLayoutNV<2> value; */',
        b'/* unterminated [[unroll]]',
        b'"unterminated [[unroll]]\\',
        b"'unterminated tensorLayoutNV<2>\\",
        b'"escaped \\\" [[unroll]] coopmat<float, S, 8, 8, U>"',
        b'#include "[[unroll]]-tensorLayoutNV<2>.glsl"\n',
        b'// continued \\\r\n[[unroll]]\r\n',
    ]
    for source in cases:
        assert mask(source) == source, source
    source = ('// Юникод\r\n[[unroll]] for (;;) {}\r\n'
              'coopmat<float, Scope, (8 >> 1), (4 < 5 ? 8 : 4), Use> tile;\r\n'
              'tensorLayoutNV<2> layout;\r\n'
              'tensorLayoutNV<2, Mode> clamped;\r\n'
              'tensorViewNV<2, false, 1, 0> view;\r\n').encode('utf-8')
    output = mask(source)
    assert len(output) == len(source)
    assert [i for i,c in enumerate(source) if c in (10,13)] == [i for i,c in enumerate(output) if c in (10,13)]
    assert b'[[unroll]]' not in output and b'coopmat<' not in output
    assert b'tensorLayoutNV<' not in output and b'tensorViewNV<' not in output
    assert b'for (;;) {}' in output and b' tile;' in output and b' view;' in output
    assert output.startswith('// Юникод\r\n'.encode('utf-8'))
    assert mask(output) == output  # idempotent
    protected = b'[[dependency_length(/* keep */ (4))]] for (;;) {}'
    assert b'/* keep */' in mask(protected)
    assert preprocess_bytes(b'[[hint(array[index[0]])]] for (;;) {}').endswith(b'for (;;) {}')
    assert b'[[' not in preprocess_bytes(b'[[hint(array[index[0]])]] for (;;) {}')
    fixture = Path(__file__).parent / 'glslSRC/vulkan-extensions.comp'
    tree = GLSL.langspec.parser().parse(mask(fixture.read_bytes()))
    assert not tree.root_node.has_error, tree.root_node
    print(f'PASS GLSL masks: {len(cases)} unchanged adversarial cases + CRLF/UTF8/offsets/types/attributes')


if __name__ == '__main__':
    check_masks()
