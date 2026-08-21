"""ЭТАЛОН (оракул) для test/check.py — значения проверяются РУКАМИ; правь ЗДЕСЬ.
Формат выровнен по колонкам для сверки глазами. Секции:
  LEVELS  (line, level, src)           глубина строки; 1+объемлющие тела; корень=1; MD=глубина заголовка
  OUTLINE (level, start, end, label)   НОВЫЙ путь: .0-рендер Reader.outline (регресс-эталон,
                                       снят с проверенного вывода; регенерация — см. ниже у OUTLINE=)
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
    'Edge/Edge.cs': [
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

OUTLINE = {  # НОВЫЙ путь: .0-рендер Reader.outline (регресс-эталон, снят с проверенного вывода)
    'pythonSRC/backends/__init__.py': [
        (1, 1, 41, '~docstring'),
        (1, 43, 46, 'imports: annotations, logging, time'),
        (1, 46, 46, '# re-exported so tests can monkeypatch ``backends.time.sleep…'),
        (1, 47, 47, 'imports: typing'),
        (1, 49, 49, '# --- transport floor --------------------------------------…'),
        (1, 50, 61, 'imports: ._http'),
        (1, 63, 63, '# --- config → chains (offline) ----------------------------…'),
        (1, 64, 74, 'imports: .resolve'),
        (1, 76, 76, '# --- per-service network seams ----------------------------…'),
        (1, 77, 77, 'imports: .chat'),
        (1, 77, 77, '# noqa: F401 - seam (monkeypatched by tests)'),
        (1, 78, 78, 'imports: .embed_driver'),
        (1, 78, 78, '# noqa: F401 - seam'),
        (1, 79, 84, 'imports: .rerank_driver'),
        (1, 86, 86, 'assign: logger'),
        (1, 89, 166, 'def chat( cfg: Optional[Dict[str, Any]], role: str, system_prompt: str, user_content: str, *, timeout: Optional[float] = None, max_retries: int = MAX_RETRIES, params: Optional[Dict[str, Any]] = None, messages: Optional[List[Dict[str, Any]]] = None, ) -> Optional[str]  # chat — openai-chat protocol, walk the chain …'),
        (1, 169, 171, '# embed — walk the embedder chain (same-model/dims fallback) …'),
        (1, 173, 173, 'assign: _EMBED_PROVIDERS'),
        (1, 176, 233, 'def embed( cfg: Optional[Dict[str, Any]], role: str, texts: List[str], *, is_query: bool = False, ) -> Optional[List[List[float]]]'),
        (1, 236, 306, 'def rerank( cfg: Optional[Dict[str, Any]], role: str, query: str, candidates: List[Dict[str, Any]], *, timeout: Optional[float] = None, max_retries: int = MAX_RETRIES, ) -> Tuple[List[Dict[str, Any]], str]  # rerank — cross-encoder reranking, walk the reranker chain …'),
    ],
    'pythonSRC/backends/resolve.py': [
        (1, 1, 8, '~docstring'),
        (1, 10, 14, 'imports: annotations, logging, typing, urllib.parse'),
        (1, 16, 16, 'assign: logger'),
        (1, 18, 19, '# Backends whose base_url points at a private/local host: no…'),
        (1, 20, 20, 'assign: _LOCAL_HOST_SUFFIXES'),
        (1, 22, 22, '# A role may only START on a backend of its own service ``ki…'),
        (1, 23, 23, 'assign: _ROLE_KIND'),
        (1, 26, 40, 'def _backends_map(cfg: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]'),
        (1, 43, 45, 'def _roles_section(cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]'),
        (1, 48, 65, 'def _normalize_backend(name: str, definition: Dict[str, Any]) -> Dict[str, Any]'),
        (1, 68, 78, 'def _fallback_names(backend: Dict[str, Any]) -> List[str]'),
        (1, 81, 104, 'def is_local_backend(backend: Dict[str, Any]) -> bool'),
        (1, 107, 168, 'def resolve_chain(cfg: Optional[Dict[str, Any]], role: str) -> List[Dict[str, Any]]'),
        (1, 171, 182, 'def _embedder_chain_key(backend: Dict[str, Any]) -> str'),
        (1, 185, 216, 'def validate_embedder_chain(chain: List[Dict[str, Any]]) -> List[Dict[str, Any]]'),
    ],
    'mdSRC/capture.py.md': [
        (1, 1, 56, 'capture.py'),
        (2, 4, 27, 'Public API'),
        (3, 6, 9, 'Классы'),
        (3, 10, 27, 'Функции'),
        (4, 12, 15, 'compute_signals(text: str, \\*, side: str = "user") -> Dict\\[str, Any]'),
        (4, 16, 19, 'extract_and_store(conn, text: str, \\*, side: str = "user", session_id: str = "", cfg: Optional\\[Dict\\[str, Any]] = None) -> Optional\\[Dict\\[str, Any]]'),
        (4, 20, 23, 'process_turn(conn, user_content: str, assistant_content: str, \\*, session_id: str = "", cfg: Optional\\[Dict\\[str, Any]] = None) -> Dict\\[str, Optional\\[Dict\\[str, Any]]]'),
        (4, 24, 27, 'manual_capture(conn, content: str, \\*, kind: str = "fact", notability: str = "high", pinned: bool = False, session_id: str = "", cfg: Optional\\[Dict\\[str, Any]] = None) -> Dict\\[str, Any]'),
        (2, 28, 39, 'Dependencies Internal'),
        (2, 40, 43, 'How it works'),
        (2, 44, 51, 'Dependencies External'),
        (2, 52, 56, '⚠️ Расхождения docstring ↔ код'),
    ],
    'Edge/Edge.cs': [
        (1, 1, 56, 'namespace Edge.Cases'),
        (1, 3, 55, 'public class Widget  /// <summary>Documents the whole class.</summary>'),
        (2, 8, 17, 'public Widget( int count, string name)  /// <summary> …'),
        (2, 19, 28, 'public int Increment()  // ordinary line comment, not XML-doc — still a preamble of…'),
        (2, 30, 36, 'public void Reset()  /* block comment …'),
        (2, 38, 42, 'public void Trailing()'),
        (2, 44, 54, 'public class Inner  /// <summary>A nested type inside Widget.</summary>'),
        (3, 47, 53, 'public void Deep()'),
    ],
    'Edge/Component.tsx': [
        (1, 1, 1, 'imports: react'),
        (1, 3, 17, 'export const Counter = (props: { start: number }) =>  /** A tiny React component — a block-bodied const-arrow boun…'),
        (2, 7, 10, 'const increment = () =>  // nested block-bodied arrow bound to `increment` -> named,…'),
        (1, 19, 22, 'function label(n: number): string  // plain named function still works alongside'),
    ],
    'Edge/Edge.scss': [
        (1, 1, 12, '.card  /* Card component — nested SCSS rules (comment preamble abov…'),
        (2, 5, 7, '&:hover'),
        (2, 9, 11, '.title'),
        (1, 14, 18, '@media (max-width: 600px)'),
        (2, 15, 17, '.card'),
    ],
    'mdSRC/cli.py.md': [
        (1, 1, 55, 'cli.py'),
        (2, 4, 33, 'Public API'),
        (3, 6, 19, 'Функции'),
        (4, 8, 11, 'register_cli(subparser) -> None'),
        (4, 12, 15, 'memohood_command(args) -> None'),
        (4, 16, 19, 'register(ctx) -> None'),
        (3, 20, 33, 'Функции (внутренние, не описаны)'),
        (4, 22, 25, '\\_print_status(hermes_home: str) -> None'),
        (4, 26, 29, '\\_setup = register_cli'),
        (4, 30, 33, '\\_handle = memohood_command'),
        (2, 34, 44, 'Dependencies Internal'),
        (2, 45, 48, 'How it works'),
        (2, 49, 52, 'Dependencies External'),
        (2, 53, 55, '⚠️ Расхождения docstring ↔ код'),
    ],
}

LADDER = [
    # (1,*) glued to 89: the '# chat ...' banner above `def chat` (94) is its preamble
    # — every ladder rung now reports the same glued range as a direct query (tool-verified).
    {"file": 'pythonSRC/backends/__init__.py', "line": 140, "expect": [(3, 139, 145), (2, 137, 160), (1, 89, 166)]},
    {"file": 'mdSRC/capture.py.md', "line": 12, "expect": [(4, 12, 15), (3, 10, 27), (2, 4, 27), (1, 1, 56)]},
    # namespace is transparent -> not a ladder entry; enclosing blocks one level shallower.
    {"file": 'csharpSRC/Core/GlobalStopWatchInstance.cs', "line": 12, "expect": [(2, 10, 17), (1, 8, 26)]},
    # Preamble comment (line 9 = ctor's /// doc) belongs to the ctor, not the class.
    # Every rung glued: class reports 3-55 (its /// on line 3), same as outline.
    {"file": 'Edge/Edge.cs', "line": 9, "expect": [(2, 8, 17), (1, 3, 55)]},
    # Deep nesting: for-body -> Deep -> Inner -> Widget (namespace transparent).
    # Inner glues its line-44 ///; Widget its line-3 /// — outer rungs glued too.
    {"file": 'Edge/Edge.cs', "line": 51, "expect": [(4, 49, 52), (3, 47, 53), (2, 44, 54), (1, 3, 55)]},
    # Python Bug A: landing on `async def ws_reader` gives that def + its parent.
    # Outer def starts at 16: its `@asynccontextmanager` decorator is part of the block
    # (addressing now glues decorators, matching the map — same [start-end] both engines).
    {"file": 'Edge/Edge.py', "line": 37, "expect": [(2, 35, 51), (1, 16, 67)]},
    # try/except siblings: line 45 (in the inner `except`) must NOT report the sibling
    # `try` (41) as a deeper container — clean monotonic chain, no phantom rung.
    {"file": 'Edge/Edge.py', "line": 45, "expect": [(6, 44, 46), (5, 41, 49), (4, 40, 49), (3, 39, 49), (2, 35, 51), (1, 16, 67)]},
    # CSS nested at-rules: a rule inside @media inside @supports — 3 real rungs.
    {"file": 'cssSRC/ChatViewer.css', "line": 214, "expect": [(3, 213, 219), (2, 212, 220), (1, 210, 221)]},
    # TS one-truth: line 71 (inside an arrow that is a property value in an object
    # literal) -> arrow-body [70-73] · object literal [69-74] · function [17-77]. The
    # brace-less `if (...) return true;` on 71 is NOT a block; the object literal IS.
    {"file": 'Edge/Edge.ts', "line": 71, "expect": [(3, 70, 73), (2, 69, 74), (1, 17, 77)]},
    # INVARIANT regression: a line inside a top-level bracket construct must return a block
    # that CONTAINS it — the indentation heuristic doesn't model list/dict literals, so this
    # used to fall through to the nearest def (a block NOT spanning the line). Now the list
    # literal itself is the container.
    {"file": 'topLevel/toplevel.py', "line": 44, "expect": [(1, 42, 49)]},
    # Nested dict inside a top-level dict: full bracket nesting, both rungs contain the line.
    {"file": 'topLevel/toplevel.py', "line": 174, "expect": [(2, 173, 176), (1, 168, 177)]},
    # Hanging-indent signature: the closing `) -> str:` sits at the continuation column, not
    # the header indent. `beta` must NOT balloon over sibling `alpha` (find_colon_line RANGE
    # bug, sweep-caught). Line 14 = beta's 2nd signature line.
    {"file": 'pythonSRC/hanging_sig.py', "line": 14, "expect": [(2, 13, 15), (1, 6, 15)]},
    # Inline body (`...`) after a hanging-indent signature stays inside its own def.
    {"file": 'pythonSRC/hanging_sig.py', "line": 11, "expect": [(2, 10, 11), (1, 6, 15)]},
]

QUERY = [
    {"file": 'pythonSRC/backends/__init__.py', "line": 140, "level": 0, "expect": (3, 139, 145)},
    {"file": 'pythonSRC/backends/__init__.py', "line": 140, "level": 1, "expect": (1, 89, 166)},  # ends at last content (return None)
    {"file": 'mdSRC/capture.py.md', "line": 4, "level": 0, "expect": (2, 4, 27)},
    # --- preamble-comment regression: landing on a comment returns the block it documents ---
    {"file": 'Edge/Edge.cs', "line":  9, "level": 0, "expect": (2,  8, 17)},  # /// doc  -> ctor
    {"file": 'Edge/Edge.cs', "line": 19, "level": 0, "expect": (2, 19, 28)},  # //       -> Increment
    {"file": 'Edge/Edge.cs', "line": 31, "level": 0, "expect": (2, 30, 36)},  # /* ... */ -> Reset
    {"file": 'Edge/Edge.cs', "line":  9, "level": 1, "expect": (1,  3, 55)},  # zoom out -> class (glued)
    # trailing comment INSIDE a body documents nothing below: stays in its own method.
    {"file": 'Edge/Edge.cs', "line": 41, "level": 0, "expect": (2, 38, 42)},
    # --- relative addressing (what --ancestor-level N exposes = --level -N) ---
    # From deep line 51: ancestor 0 = for-body, 1 = Deep, 2 = Inner (walking up).
    {"file": 'Edge/Edge.cs', "line": 51, "level":  0, "expect": (4, 49, 52)},  # ancestor-level 0
    {"file": 'Edge/Edge.cs', "line": 51, "level": -1, "expect": (3, 47, 53)},  # ancestor-level 1
    {"file": 'Edge/Edge.cs', "line": 51, "level": -2, "expect": (2, 44, 54)},  # ancestor-level 2

    # --- C++ preamble gluing (shared engine): both comment kinds glue to the func ---
    {"file": 'Edge/Edge.cpp', "line":  82, "level": 0, "expect": (1,  82,  87)},  # /// doc -> version
    {"file": 'Edge/Edge.cpp', "line": 131, "level": 0, "expect": (1, 131, 153)},  # /* block */ -> main

    # --- Python handler fixes ---
    # Bug B: the FIRST line of a multi-line comment preamble still reaches the def below.
    {"file": 'Edge/Edge.py', "line": 35, "level": 0, "expect": (2, 35, 51)},  # 1st comment -> ws_reader
    {"file": 'Edge/Edge.py', "line": 36, "level": 0, "expect": (2, 35, 51)},  # 2nd comment -> ws_reader
    # Bug A: a def-header line belongs to the block it opens, not the parent.
    {"file": 'Edge/Edge.py', "line": 37, "level": 0, "expect": (2, 35, 51)},  # `async def ws_reader`
    {"file": 'Edge/Edge.py', "line": 53, "level": 0, "expect": (2, 53, 62)},  # `async def ws_writer`
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
            ('backends/__init__.py',      'embed',                      [176, 202, 211, 224, 230],               [1, 3, 4, 4, 2]),
            # line 222 is inside `except` (a sibling of `try`, same depth) -> 4, not 5:
            # the fix stops `try` from being counted as containing its except's lines.
            ('backends/_http.py',         'BackendError',               [51, 136, 154, 207, 221, 222, 276, 293], [1, 2, 3, 2, 3, 4, 2, 3]),
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
            # 178/193 sit inside multi-line object literals (`({...})` returned from an
            # arrow) — those count as foldable blocks, so depth 2. get_blocks returns the
            # object literal itself, not a bogus nearby function.
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
