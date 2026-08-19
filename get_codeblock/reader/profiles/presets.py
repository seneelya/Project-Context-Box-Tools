"""Общие наборы для профилей — чтобы C-подобные языки не копипастили правила (Vision03).

Тут живут по одному разу разделяемые таблицы лейблера band'ов: тип-узла → слово,
множества «это импорт» / «это привязка имени». Профиль языка может их дополнить, но
общее не дублируется. Движок — `reader/label.py`, читает эти наборы.
"""

# тип узла backend'а → человекочитаемое слово в заголовке полосы
HUMAN_KIND = {
    # tree-sitter python
    'import_statement': 'imports', 'import_from_statement': 'imports',
    'future_import_statement': 'imports', 'expression_statement': 'assign',
    # stdlib ast (фолбек)
    'Import': 'imports', 'ImportFrom': 'imports', 'Assign': 'assign', 'AnnAssign': 'assign',
    # C-подобные / общие
    'lexical_declaration': 'const', 'variable_declaration': 'const',
    'using_directive': 'imports', 'import_declaration': 'imports',
    'preproc_include': 'includes', 'export_statement': 'export',
}

# узлы, чей заголовок = список имён импортируемых модулей
IMPORT_KINDS = {
    'import_statement', 'import_from_statement', 'future_import_statement',
    'using_directive', 'import_declaration', 'preproc_include',
    'Import', 'ImportFrom',
}

# узлы-обёртки, внутри которых сидит привязка имени (NAME = value / const NAME = … /
# export const NAME = …). def/class/arrow сюда НЕ попадают — они landmark'и (unwrap_def).
ASSIGN_WRAPPERS = {
    'expression_statement', 'lexical_declaration', 'variable_declaration',
    'export_statement', 'Assign', 'AnnAssign',
}

# узлы-привязки и их поле-цель (имя слева от `=`)
BINDER_TYPES = ('assignment', 'augmented_assignment', 'variable_declarator')

# узлы, которые сами ЯВЛЯЮТСЯ именем (для fallback-поиска)
NAME_TYPES = ('identifier', 'dotted_name', 'scoped_identifier', 'type_identifier',
              'property_identifier', 'field_identifier')

CAP = 8   # максимум имён в заголовке; дальше — «…» (полное через --query)
