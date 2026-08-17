"""ЭТАЛОН (оракул) для test/check.py — значения проверяются РУКАМИ; правь ЗДЕСЬ.
Формат выровнен по колонкам для сверки глазами. Секции:
  LEVELS  (line, level, src)           глубина строки; 1+объемлющие тела; корень=1; MD=глубина заголовка
  OUTLINE (level, start, end, label)   оглавление: именованные блоки / заголовки
  LADDER  (level, start, end)          все объемлющие блоки строки, внутренний→внешний
  QUERY   (level, start, end)          какой блок вернёт --query --level
  IMPORTS {файл: [символы]}            downstream=потребитель берёт у цели / incoming=цель берёт у источника
  SYMBOL  {файл: [символы]}            тот же граф, отфильтрованный по символу
  INCOMING_DETAIL  resolved/external/dangling(импортнут-не-использован)/usages(источник,символ,строки,levels в цели)
  CONSUMERS        [файлы]  кто импортит цель — только набор файлов (для крупных фикстур)
  INCOMING_SOURCES [файлы]  импорты цели, резолвнутые в файлы (лочит ESM .js -> .ts)
  DECLARATIONS     (name, kind, exported, n_members)  объявленная поверхность, REGEX-бэкенд (детерминизм)
"""

LEVELS = {
    'pythonSRC/backends/__init__.py': [
        # line  lvl  source
        ( 51, 1, 'BackendError,'),
        ( 94, 1, 'def chat('),
        (131, 2, 'chain = resolve_chain(cfg, role)'),
        (132, 2, 'if not chain:'),
        (133, 3, 'logger.info("backends.chat: role %r resolved to an empty c'),
        (140, 4, 'logger.warning('),
    ],
    'mdSRC/capture.py.md': [
        # line  lvl  source
        ( 1, 1, '# capture.py'),
        ( 4, 2, '## Public API'),
        ( 6, 3, '### Классы'),
        (12, 4, '#### compute_signals(text: str, \\*, side: str = "user") ->'),
        (28, 2, '## Dependencies Internal'),
    ],
    'tsSRC/src/analyzer.ts': [
        # line  lvl  source
        (40, 1, 'function handleExportDeclaration(node: SourceFileReferenci'),
        (41, 2, 'return (node as ExportDeclaration).getNamedExports().map(('),
        (45, 2, 'return ['),
        (58, 2, 'const clause = node.getImportClause();'),
    ],
    'csharpSRC/Core/GlobalStopWatchInstance.cs': [
        # line  lvl  source
        ( 1, 1, '\ufeffusing AndreasReitberger.Core.Interfaces;'),
        # namespaces are transparent -> types/members one level shallower than
        # the old brace engine (which counted the braced namespace as a level).
        ( 8, 1, 'public class GlobalStopWatchInstance : IGlobalStopWatch'),
        (12, 3, 'Stopwatch sw = Stopwatch.StartNew();'),
        (19, 2, 'public async Task<long> StopWatchActionAsync(Func<Task> fu'),
        (22, 3, 'await function();'),
    ],
    # Syntax-edge fixture: doc/line/block comments, wrapped signatures, nested types.
    'csEdge/Edge.cs': [
        # line  lvl  source
        ( 3, 1, '/// class doc \u2014 transparent namespace, so class header = level 1'),
        ( 9, 2, '/// ctor doc \u2014 preamble sits at the ctor header level (member)'),
        (13, 2, 'wrapped ctor param \u2014 NOT a new scope, stays at header level'),
        (16, 3, '_count = count;  (ctor body)'),
        (22, 3, 'if (_count > 0)  \u2014 control header at method-body level'),
        (24, 4, '_count++;  (if body)'),
        (44, 2, '/// nested-type doc'),
        (49, 4, 'for (...) header inside Deep'),
        (51, 5, 'Console.WriteLine(i);  (for body, deepest)'),
    ],
}

OUTLINE = {
    'pythonSRC/backends/__init__.py': [
        # (level, start, end, label)
        (1,  94, 175, 'def chat('),
        (1, 176, 240, 'def embed('),
        (1, 241, 306, 'def rerank('),
    ],
    'pythonSRC/backends/resolve.py': [
        # (level, start, end, label)
        (1,  26,  42, 'def _backends_map(cfg: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:'),
        (1,  43,  47, 'def _roles_section(cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:'),
        (1,  48,  67, 'def _normalize_backend(name: str, definition: Dict[str, Any]) -> Dict[str, Any]:'),
        (1,  68,  80, 'def _fallback_names(backend: Dict[str, Any]) -> List[str]:'),
        (1,  81, 106, 'def is_local_backend(backend: Dict[str, Any]) -> bool:'),
        (1, 107, 170, 'def resolve_chain(cfg: Optional[Dict[str, Any]], role: str) -> List[Dict[str, Any]]:'),
        (1, 171, 184, 'def _embedder_chain_key(backend: Dict[str, Any]) -> str:'),
        (1, 185, 216, 'def validate_embedder_chain(chain: List[Dict[str, Any]]) -> List[Dict[str, Any]]:'),
    ],
    'mdSRC/capture.py.md': [
        # (level, start, end, label)
        (1,   1,  56, 'capture.py'),
        (2,   4,  27, 'Public API'),
        (3,   6,   9, 'Классы'),
        (3,  10,  27, 'Функции'),
        (4,  12,  15, 'compute_signals(text: str, \\*, side: str = "user") -> Dict\\[str, Any]'),
        (4,  16,  19, 'extract_and_store(conn, text: str, \\*, side: str = "user", session_id: str = "", cfg: Optional\\[Dict\\[str, Any]] = None) -> Optional\\[Dict\\[str, Any]]'),
        (4,  20,  23, 'process_turn(conn, user_content: str, assistant_content: str, \\*, session_id: str = "", cfg: Optional\\[Dict\\[str, Any]] = None) -> Dict\\[str, Optional\\[Dict\\[str, Any]]]'),
        (4,  24,  27, 'manual_capture(conn, content: str, \\*, kind: str = "fact", notability: str = "high", pinned: bool = False, session_id: str = "", cfg: Optional\\[Dict\\[str, Any]] = None) -> Dict\\[str, Any]'),
        (2,  28,  39, 'Dependencies Internal'),
        (2,  40,  43, 'How it works'),
        (2,  44,  51, 'Dependencies External'),
        (2,  52,  56, '⚠️ Расхождения docstring ↔ код'),
    ],
    'csEdge/Edge.cs': [
        # (level, start, end, label) — preamble comments glued onto each block's start
        (1,  1, 56, 'namespace Edge.Cases'),
        (1,  3, 55, 'public class Widget'),              # /// doc on line 3 glued
        (2,  8, 17, 'public Widget( int count, string name)'),  # multi-line sig + /// glued
        (2, 19, 28, 'public int Increment()'),           # // comment glued
        (2, 30, 36, 'public void Reset()'),              # /* block */ glued
        (2, 38, 42, 'public void Trailing()'),           # no preamble
        (2, 44, 54, 'public class Inner'),               # nested type, /// glued
        (3, 47, 53, 'public void Deep()'),
    ],
    'mdSRC/cli.py.md': [
        # (level, start, end, label)
        (1,   1,  55, 'cli.py'),
        (2,   4,  33, 'Public API'),
        (3,   6,  19, 'Функции'),
        (4,   8,  11, 'register_cli(subparser) -> None'),
        (4,  12,  15, 'memohood_command(args) -> None'),
        (4,  16,  19, 'register(ctx) -> None'),
        (3,  20,  33, 'Функции (внутренние, не описаны)'),
        (4,  22,  25, '\\_print_status(hermes_home: str) -> None'),
        (4,  26,  29, '\\_setup = register_cli'),
        (4,  30,  33, '\\_handle = memohood_command'),
        (2,  34,  44, 'Dependencies Internal'),
        (2,  45,  48, 'How it works'),
        (2,  49,  52, 'Dependencies External'),
        (2,  53,  55, '⚠️ Расхождения docstring ↔ код'),
    ],
}

LADDER = [
    {"file": 'pythonSRC/backends/__init__.py', "line": 140, "expect": [(3, 139, 145), (2, 137, 161), (1, 94, 172)]},
    {"file": 'mdSRC/capture.py.md', "line": 12, "expect": [(4, 12, 15), (3, 10, 27), (2, 4, 27), (1, 1, 56)]},
    # namespace is transparent -> not a ladder entry; enclosing blocks one level shallower.
    {"file": 'csharpSRC/Core/GlobalStopWatchInstance.cs', "line": 12, "expect": [(2, 10, 17), (1, 8, 26)]},
    # Preamble comment (line 9 = ctor's /// doc) belongs to the ctor, not the class.
    {"file": 'csEdge/Edge.cs', "line": 9, "expect": [(2, 8, 17), (1, 4, 55)]},
    # Deep nesting: for-body -> Deep -> Inner -> Widget (namespace transparent).
    {"file": 'csEdge/Edge.cs', "line": 51, "expect": [(4, 49, 52), (3, 47, 53), (2, 45, 54), (1, 4, 55)]},
]

QUERY = [
    {"file": 'pythonSRC/backends/__init__.py', "line": 140, "level": 0, "expect": (3, 139, 145)},
    {"file": 'pythonSRC/backends/__init__.py', "line": 140, "level": 1, "expect": (1, 94, 172)},
    {"file": 'mdSRC/capture.py.md', "line": 4, "level": 0, "expect": (2, 4, 27)},
    # --- preamble-comment regression: landing on a comment returns the block it documents ---
    {"file": 'csEdge/Edge.cs', "line":  9, "level": 0, "expect": (2,  8, 17)},  # /// doc  -> ctor
    {"file": 'csEdge/Edge.cs', "line": 19, "level": 0, "expect": (2, 19, 28)},  # //       -> Increment
    {"file": 'csEdge/Edge.cs', "line": 31, "level": 0, "expect": (2, 30, 36)},  # /* ... */ -> Reset
    {"file": 'csEdge/Edge.cs', "line":  9, "level": 1, "expect": (1,  4, 55)},  # zoom out -> class
    # trailing comment INSIDE a body documents nothing below: stays in its own method.
    {"file": 'csEdge/Edge.cs', "line": 41, "level": 0, "expect": (2, 38, 42)},
]

IMPORTS = {
    'py downstream _http': {
        "mode": 'downstream', "root": 'pythonSRC', "file": 'backends/_http.py',
        "expect": {
            'backends/__init__.py':      ['BackendError', 'DEFAULT_TIMEOUT_S', 'MAX_RETRIES', '_DEFAULT_CONNECT_TIMEOUT_S', '_DEFAULT_READ_TIMEOUT_S', '_RERANK_PROVIDERS', '_RETRYABLE_STATUS', '_ROLE_KIND', '_api_key_for', '_apply_score_transform', '_backends_map', '_build_headers', '_chat_once', '_embed_once', '_embedder_chain_key', '_fallback_names', '_normalize_backend', '_post_with_retries', '_rank_candidates', '_rerank_once', '_roles_section', '_timeouts_for', 'is_local_backend', 'resolve_chain', 'validate_embedder_chain'],
            'backends/chat.py':          ['BackendError', '_build_headers', '_post_with_retries', '_timeouts_for'],
            'backends/embed_driver.py':  ['BackendError', '_api_key_for'],
            'backends/rerank_driver.py': ['BackendError', '_build_headers', '_post_with_retries', '_timeouts_for', 'logger'],
        },
    },
    'py incoming __init__': {
        "mode": 'incoming', "root": 'pythonSRC', "file": 'backends/__init__.py',
        "expect": {
            'backends/__init__.py':      ['embed'],
            'backends/_http.py':         ['BackendError', 'DEFAULT_TIMEOUT_S', 'MAX_RETRIES', '_DEFAULT_CONNECT_TIMEOUT_S', '_DEFAULT_READ_TIMEOUT_S', '_RETRYABLE_STATUS', '_api_key_for', '_build_headers', '_post_with_retries', '_timeouts_for'],
            'backends/chat.py':          ['_chat_once'],
            'backends/embed_driver.py':  ['_embed_once'],
            'backends/rerank_driver.py': ['_RERANK_PROVIDERS', '_apply_score_transform', '_rank_candidates', '_rerank_once'],
            'backends/resolve.py':       ['_ROLE_KIND', '_backends_map', '_embedder_chain_key', '_fallback_names', '_normalize_backend', '_roles_section', 'is_local_backend', 'resolve_chain', 'validate_embedder_chain'],
        },
    },
    'ts downstream analyzer': {
        "mode": 'downstream', "root": 'tsSRC', "file": 'src/analyzer.ts',
        "expect": {
            'src/runner.ts': ['analyze'],
        },
    },
    'ts incoming analyzer': {
        "mode": 'incoming', "root": 'tsSRC', "file": 'src/analyzer.ts',
        "expect": {
            'src/configurator.ts':                ['IConfigInterface'],
            'src/constants.ts':                   ['ignoreComment'],
            'src/util/getModuleSourceFile.ts':    ['getModuleSourceFile'],
            'src/util/getNodesOfKind.ts':         ['getNodesOfKind'],
            'src/util/isDefinitelyUsedImport.ts': ['isDefinitelyUsedImport'],
            'src/utils/common.ts':                ['countBy', 'last'],
        },
    },
    'cs downstream interface': {
        "mode": 'downstream', "root": 'csharpSRC', "file": 'Core/IGlobalStopWatch.cs',
        "expect": {
            'Core/GlobalStopWatchInstance.cs': ['IGlobalStopWatch'],
        },
    },
    'cs incoming impl': {
        "mode": 'incoming', "root": 'csharpSRC', "file": 'Core/GlobalStopWatchInstance.cs',
        "expect": {
            'Core/IGlobalStopWatch.cs': ['IGlobalStopWatch'],
        },
    },
    # C# same-namespace: consumers use the type with NO `using` (own namespace) — locks that fix.
    'cs downstream same-namespace Extension': {
        "mode": 'downstream', "root": 'csharpSRC2', "file": 'Core/Extension.cs',
        "expect": {
            'Core/ExtensionsManager.cs': ['Extension'],
            'Core/Program.cs':           ['Extension'],
            'Core/WebServer.cs':         ['Extension'],
        },
    },
}

SYMBOL = {
    'py _http BackendError': {
        "root": 'pythonSRC', "file": 'backends/_http.py', "symbol": ['BackendError'],
        "expect": {
            'backends/__init__.py':      ['BackendError'],
            'backends/chat.py':          ['BackendError'],
            'backends/embed_driver.py':  ['BackendError'],
            'backends/rerank_driver.py': ['BackendError'],
        },
    },
}

INCOMING_DETAIL = {
    'py __init__': {
        "root": 'pythonSRC', "file": 'backends/__init__.py',
        "resolved": {
            'backends/__init__.py':      ['embed'],
            'backends/_http.py':         ['BackendError', 'DEFAULT_TIMEOUT_S', 'MAX_RETRIES', '_DEFAULT_CONNECT_TIMEOUT_S', '_DEFAULT_READ_TIMEOUT_S', '_RETRYABLE_STATUS', '_api_key_for', '_build_headers', '_post_with_retries', '_timeouts_for'],
            'backends/chat.py':          ['_chat_once'],
            'backends/embed_driver.py':  ['_embed_once'],
            'backends/rerank_driver.py': ['_RERANK_PROVIDERS', '_apply_score_transform', '_rank_candidates', '_rerank_once'],
            'backends/resolve.py':       ['_ROLE_KIND', '_backends_map', '_embedder_chain_key', '_fallback_names', '_normalize_backend', '_roles_section', 'is_local_backend', 'resolve_chain', 'validate_embedder_chain'],
        },
        "external": ['from __future__ import annotations', 'from typing import Any, Dict, List, Optional, Tuple', 'import logging', 'import time'],
        "dangling": [],
        # (source_file, symbol, [lines in target], [levels])
        "usages": [
            ('backends/__init__.py',      'embed',                      [176, 202, 211, 224, 230],               [1, 3, 4, 5, 2]),
            ('backends/_http.py',         'BackendError',               [51, 136, 154, 207, 221, 222, 276, 293], [1, 2, 3, 2, 3, 5, 2, 3]),
            ('backends/_http.py',         'DEFAULT_TIMEOUT_S',          [52],                                    [1]),
            ('backends/_http.py',         'MAX_RETRIES',                [53, 101, 248],                          [1, 1, 1]),
            ('backends/_http.py',         '_DEFAULT_CONNECT_TIMEOUT_S', [54],                                    [1]),
            ('backends/_http.py',         '_DEFAULT_READ_TIMEOUT_S',    [55],                                    [1]),
            ('backends/_http.py',         '_RETRYABLE_STATUS',          [56],                                    [1]),
            ('backends/_http.py',         '_api_key_for',               [57],                                    [1]),
            ('backends/_http.py',         '_build_headers',             [58],                                    [1]),
            ('backends/_http.py',         '_post_with_retries',         [59],                                    [1]),
            ('backends/_http.py',         '_timeouts_for',              [60],                                    [1]),
            ('backends/chat.py',          '_chat_once',                 [150],                                   [4]),
            ('backends/embed_driver.py',  '_embed_once',                [216],                                   [4]),
            ('backends/rerank_driver.py', '_RERANK_PROVIDERS',          [80, 285],                               [1, 3]),
            ('backends/rerank_driver.py', '_apply_score_transform',     [81],                                    [1]),
            ('backends/rerank_driver.py', '_rank_candidates',           [82, 300],                               [1, 3]),
            ('backends/rerank_driver.py', '_rerank_once',               [83, 292],                               [1, 4]),
            ('backends/resolve.py',       '_ROLE_KIND',                 [65],                                    [1]),
            ('backends/resolve.py',       '_backends_map',              [66],                                    [1]),
            ('backends/resolve.py',       '_embedder_chain_key',        [67],                                    [1]),
            ('backends/resolve.py',       '_fallback_names',            [68],                                    [1]),
            ('backends/resolve.py',       '_normalize_backend',         [69],                                    [1]),
            ('backends/resolve.py',       '_roles_section',             [70],                                    [1]),
            ('backends/resolve.py',       'is_local_backend',           [71],                                    [1]),
            ('backends/resolve.py',       'resolve_chain',              [72, 131, 200, 270],                     [1, 2, 2, 2]),
            ('backends/resolve.py',       'validate_embedder_chain',    [73],                                    [1]),
        ],
    },
    'ts analyzer': {
        "root": 'tsSRC', "file": 'src/analyzer.ts',
        "resolved": {
            'src/configurator.ts':                ['IConfigInterface'],
            'src/constants.ts':                   ['ignoreComment'],
            'src/util/getModuleSourceFile.ts':    ['getModuleSourceFile'],
            'src/util/getNodesOfKind.ts':         ['getNodesOfKind'],
            'src/util/isDefinitelyUsedImport.ts': ['isDefinitelyUsedImport'],
            'src/utils/common.ts':                ['countBy', 'last'],
        },
        "external": ['import { realpathSync } from "fs";', 'import {(10 symbols) from "ts-morph"};'],
        "dangling": ['IConfigInterface'],
        # (source_file, symbol, [lines in target], [levels])
        "usages": [
            ('src/constants.ts',                   'ignoreComment',          [151],      [2]),
            ('src/util/getModuleSourceFile.ts',    'getModuleSourceFile',    [178, 193], [2, 2]),
            ('src/util/getNodesOfKind.ts',         'getNodesOfKind',         [64],       [2]),
            ('src/util/isDefinitelyUsedImport.ts', 'isDefinitelyUsedImport', [179],      [2]),
            ('src/utils/common.ts',                'countBy',                [221],      [2]),
            ('src/utils/common.ts',                'last',                   [151],      [2]),
        ],
    },
    'cs impl': {
        "root": 'csharpSRC', "file": 'Core/GlobalStopWatchInstance.cs',
        "resolved": {
            'Core/IGlobalStopWatch.cs': ['IGlobalStopWatch'],
        },
        "external": ['using System.Diagnostics;', 'using System.Threading.Tasks;', 'using System;'],
        "dangling": [],
        # (source_file, symbol, [lines in target], [levels])
        "usages": [
            ('Core/IGlobalStopWatch.cs', 'IGlobalStopWatch', [8], [1]),
        ],
    },
}

# --- multilingual fixtures: cross-file resolution / visibility / declared surface ---------

# CONSUMERS: who imports the target — FILE SET only (symbol lists omitted for big fixtures).
CONSUMERS = {
    # TS ESM/NodeNext: consumers write `from "./util.js"` — resolves to util.ts (the .js fix).
    'ts .js->.ts consumers (zod util)': {
        "root": 'tsSRC2', "file": 'core/util.ts',
        "expect": ['core/api.ts', 'core/checks.ts', 'core/errors.ts', 'core/json-schema-processors.ts',
                   'core/parse.ts', 'core/regexes.ts', 'core/schemas.ts', 'core/to-json-schema.ts'],
    },
    # C# descendant namespace: 3 adapters in .Adapters see the parent-namespace interface w/o `using`.
    'cs descendant-namespace (unity IAnalyticsAdapter)': {
        "root": 'unitySRC', "file": 'Services/Analytics/IAnalyticsAdapter.cs',
        "expect": ['Services/Analytics/Adapters/CompositeAnalyticsAdapter.cs',
                   'Services/Analytics/Adapters/FirebaseAnalyticsAdapter.cs',
                   'Services/Analytics/Adapters/NullAnalyticsAdapter.cs',
                   'Services/Analytics/AnalyticsService.cs'],
    },
}

# INCOMING_SOURCES: the target's own imports resolved to sibling files (locks ESM .js -> .ts).
INCOMING_SOURCES = {
    'ts .js->.ts incoming (zod schemas)': {
        "root": 'tsSRC2', "file": 'core/schemas.ts',
        "expect": ['core/api.ts', 'core/checks.ts', 'core/core.ts', 'core/doc.ts', 'core/errors.ts',
                   'core/json-schema.ts', 'core/parse.ts', 'core/regexes.ts', 'core/standard-schema.ts',
                   'core/to-json-schema.ts', 'core/util.ts', 'core/versions.ts'],
    },
}

# DECLARATIONS: declared surface via the REGEX backend (deterministic, tree-sitter-independent).
# (name, kind, exported, n_members)
DECLARATIONS = {
    'cs class (Extension)': {
        "root": 'csharpSRC2', "file": 'Core/Extension.cs',
        "expect": [('Extension', 'class', True, 20)],
    },
    # interface members carry no `public` modifier → the regex reports 0 members (tree-sitter finds them).
    'cs interface (IAnalyticsAdapter)': {
        "root": 'unitySRC', "file": 'Services/Analytics/IAnalyticsAdapter.cs',
        "expect": [('IAnalyticsAdapter', 'interface', True, 0)],
    },
    'ts const (zod versions)': {
        "root": 'tsSRC2', "file": 'core/versions.ts',
        "expect": [('version', 'const', True, 0)],
    },
}
