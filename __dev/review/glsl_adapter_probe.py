"""Try the existing Classifier with a temporary GLSL profile, without registration."""
import sys
from pathlib import Path
import tempfile
sys.stdout.reconfigure(encoding='utf8')

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(tempfile.gettempdir()) / 'projectstarter-glsl-runtime25'))
sys.path.insert(0, str(HERE.parent.parent))
from glsl_probe import language, TARGET
import tree_sitter_glsl_spec as glsl
from get_codeblock.handlers._treesitter_blocks import LangSpec
from get_codeblock.reader.profiles.base import TSProfile
from get_codeblock.reader.backends.treesitter import TSNode, TreeSitterSpec
from get_codeblock.reader.classify import Classifier, render


class FlatNode(TSNode):
    def children(self):
        result = []
        for child in self._n.named_children:
            if child.type == 'statement_list':
                result.extend(FlatNode(child, self._src).children())
            else:
                result.append(FlatNode(child, self._src))
        return result


ls = LangSpec('GLSL probe', lambda: language(glsl),
              body_types={'compound_statement'},
              transparent_parents={'preproc_if', 'preproc_ifdef', 'preproc_else', 'preproc_elif'},
              named_def={'function_definition', 'struct_specifier'},
              container=set(), control={'if_statement', 'for_statement', 'while_statement',
                                        'do_statement', 'switch_statement', 'else_clause'},
              scope_body='compound_statement')
spec = TreeSitterSpec(TSProfile(ls))
src = (TARGET / 'cover-map.fs').read_bytes()
tree = ls.parser().parse(src)
output = []
for cls in (TSNode, FlatNode):
    root = cls(tree.root_node, src)
    blocks = Classifier(spec).classify(root, 1, 2)
    first_fn = next(b for b in blocks if b.kind == 'function_definition')
    output.append(f'{cls.__name__}: first_fn children = {[(c.kind, c.start, c.end) for c in first_fn.children]}')
    if cls is FlatNode:
        output.append(render(blocks))
text = '\n'.join(output)
HERE.joinpath('glsl_adapter_outline.txt').write_text(text, encoding='utf8')
print('\n'.join(output[:2]))
print('Outline saved:', HERE / 'glsl_adapter_outline.txt')
