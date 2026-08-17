"""CSS / SCSS / Sass handler for get_codeblock.

Navigation (outline / get_blocks / line_level) comes from the shared tree-sitter
block engine. A "block" is a rule set's brace body `selector { … }`; nested rules
(SCSS `&::before { … }`, `@media`/`@include` blocks) nest naturally, and the label
is the selector list.

Grammar note: we use `tree-sitter-css`. The dedicated `tree-sitter-scss` package
(1.0.0) ships an old-ABI `language()` that overflows on 64-bit Windows with
tree-sitter >= 0.26, so it is unusable here. The css grammar flags SCSS-only
syntax (`@mixin`, `@include`, `@if`, `&` interpolation) as ERROR nodes, but the
surrounding rule/selector/nesting structure still parses — which is exactly what
navigation needs. Good enough to work across a real SCSS codebase.

Requires: pip install tree-sitter tree-sitter-css
"""

from ._treesitter_blocks import LangSpec, TreeSitterBlockHandler


def _load_css_language():
    import tree_sitter_css
    from tree_sitter import Language
    return Language(tree_sitter_css.language())


CSS_SPEC = LangSpec(
    "CSS/SCSS",
    _load_css_language,
    body_types={'block'},
    transparent_parents=set(),
    named_def={'rule_set', 'keyframes_statement', 'at_rule',
               'media_statement', 'supports_statement'},
    container=set(),
    control=set(),
    scope_body='block',
)


class CssHandler(TreeSitterBlockHandler):
    SPEC = CSS_SPEC
