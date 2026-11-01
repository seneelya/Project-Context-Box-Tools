"""GLSL glsl-spec: grammar data shared by map and addressing."""
from functools import partial
from ...handlers._treesitter_blocks import LangSpec
from .base import TSProfile
from ...glsl_source import preprocess_bytes

# Scalar argument counts from the Vulkan extension type declarations. No generic ident<...>.
PARAMETERIZED_TYPES = {'coopmat': (5, 5), 'tensorLayoutNV': (1, 2), 'tensorViewNV': (3, 7)}


def _load_glsl():
    from ...env_check import ensure_language
    ensure_language('glsl')
    from tree_sitter import Language
    import tree_sitter_glsl_spec
    return Language(tree_sitter_glsl_spec.language())


GLSL = TSProfile(
    LangSpec('GLSL', _load_glsl,
             body_types={'compound_statement', 'field_declaration_list'},
             transparent_parents=set(),
             named_def={'function_definition', 'struct_specifier', 'interface_block'},
             container={'struct_specifier', 'interface_block'},
             control={'if_statement', 'else_clause', 'for_statement', 'while_statement',
                      'do_statement', 'switch_statement'},
             scope_body='compound_statement',
             preprocess=partial(preprocess_bytes, type_parameters=PARAMETERIZED_TYPES)),
    extra_frames={'preproc_if', 'preproc_ifdef', 'preproc_else', 'preproc_elif'},
    node_rules={
        'inline_comments': {'comment'},
        'body_span_from_parent': {'field_declaration_list'},
        'declarators': {'declarator', 'field_declarator'},
        'flatten': {'statement_list': None, 'declarator_list': None,
                    'field_declarator_list': None, 'type': None, 'type_specifier': None,
                    'declarator': 'name'},
        'aliases': {'declaration': (('field_declaration_list', 'interface_block'),)},
        'fields': {'declaration': {'declarator': (('declarator',),)},
                   'field_declaration': {'declarator': (('field_declarator',),)}},
        'exclusive_end': {'preproc_def', 'preproc_function_def'},
    })
