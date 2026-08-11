"""Golden expected values (the ORACLE). Verify by hand; edit numbers if wrong.
Grouped by fixture/case. LEVELS: (line, expected_level, source-snippet).
level = 1 + enclosing block BODIES; file root = 1; 0 is never a real depth."""

LEVELS = {
    'pythonSRC/backends/__init__.py': [
        (51, 1, 'BackendError,'),
        (94, 1, 'def chat('),
        (131, 2, 'chain = resolve_chain(cfg, role)'),
        (132, 2, 'if not chain:'),
        (133, 3, 'logger.info("backends.chat: role %r resolved to an empty c'),
        (140, 4, 'logger.warning('),
    ],
    'mdSRC/capture.py.md': [
        (1, 1, '# capture.py'),
        (4, 2, '## Public API'),
        (6, 3, '### Классы'),
        (12, 4, '#### compute_signals(text: str, /*, side: str = "user") ->'),
        (28, 2, '## Dependencies Internal'),
    ],
    'tsSRC/src/analyzer.ts': [
        (40, 1, 'function handleExportDeclaration(node: SourceFileReferenci'),
        (41, 2, 'return (node as ExportDeclaration).getNamedExports().map(('),
        (45, 2, 'return ['),
        (58, 2, 'const clause = node.getImportClause();'),
    ],
    'csharpSRC/GlobalStopWatchInstance.cs': [
        (1, 1, '\ufeffusing AndreasReitberger.Core.Interfaces;'),
        (8, 2, 'public class GlobalStopWatchInstance : IGlobalStopWatch'),
        (12, 4, 'Stopwatch sw = Stopwatch.StartNew();'),
        (19, 3, 'public async Task<long> StopWatchActionAsync(Func<Task> fu'),
        (22, 4, 'await function();'),
    ],
}

IMPORTS = {
    'py downstream _http': {
        "mode": 'downstream', "root": 'pythonSRC', "file": 'backends/_http.py',
        "expect": {
            'backends/chat.py': ['BackendError', '_build_headers', '_post_with_retries', '_timeouts_for'],
            'backends/embed_driver.py': ['BackendError', '_api_key_for'],
            'backends/rerank_driver.py': ['BackendError', '_build_headers', '_post_with_retries', '_timeouts_for', 'logger'],
        },
    },
    'py incoming __init__': {
        "mode": 'incoming', "root": 'pythonSRC', "file": 'backends/__init__.py',
        "expect": {
            'backends/chat.py': ['_chat_once'],
            'backends/embed_driver.py': ['_embed_once'],
            'backends/rerank_driver.py': ['_RERANK_PROVIDERS', '_apply_score_transform', '_rank_candidates', '_rerank_once'],
        },
    },
    'ts downstream analyzer': {
        "mode": 'downstream', "root": 'tsSRC', "file": 'src/analyzer.ts',
        "expect": {
            'src/runner.ts': ['analyze'],
        },
    },
    'cs incoming impl': {
        "mode": 'incoming', "root": 'csharpSRC', "file": 'GlobalStopWatchInstance.cs',
        "expect": {
            'IGlobalStopWatch.cs': ['IGlobalStopWatch'],
        },
    },
}
