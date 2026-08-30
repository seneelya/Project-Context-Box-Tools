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
        # Trailing same-line comments (`import time  # note`, `from .chat import x  # noqa`)
        # glue into the run they annotate — they no longer spawn their own `~comment` row
        # or poison the run's label with a spurious `+multiType` (real bug: a trailing
        # `# resolved once, cached` in docker.py split one assign line into two rows).
        (1, 43, 47, 'imports: annotations, logging, time, typing'),
        (1, 49, 49, '# --- transport floor --------------------------------------…'),
        (1, 50, 61, 'imports: ._http'),
        (1, 63, 63, '# --- config → chains (offline) ----------------------------…'),
        (1, 64, 74, 'imports: .resolve'),
        (1, 76, 76, '# --- per-service network seams ----------------------------…'),
        (1, 77, 84, 'imports: .chat, .embed_driver, .rerank_driver'),
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
    # cursor_feedback__gcb.md #5 — top-level SCSS `$var: value;` used to blow up the WHOLE
    # file's parse (root itself came back typed 'ERROR', everything downstream fragmented
    # into single-token noise: `~ERROR x16`). Masked into real comments before parsing
    # (css_handler._mask_scss_top_level_vars) so the surrounding real content — the `//`
    # comment, the `.footer` rule — parses cleanly again; the masked comments glue onto
    # `.footer` as its preamble (same rule as any real comment directly above a landmark),
    # extending its range up to 9 rather than its own line 12 — expected, not a bug.
    'cssSRC/vars.scss': [
        (1, 1, 2, '~import x2'),
        (1, 4, 6, '/*$footerHeight: 18*/ …'),
        (1, 8, 8, '~js_comment'),
        (1, 9, 15, '.footer  /*$red: $accentMainCo*/ …'),
    ],
    # Plain-text experiment: no markup at all, structure purely from blank-line runs.
    # SECTION (2+ blank lines apart) contains PARAGRAPH (single-blank-line apart);
    # trailing `---` is its own top-level `~rule` filler, not swallowed. Names are each
    # node's own first ~60 chars (no headings exist to read a name from). A paragraph
    # with 2+ marker lines (`1.`/`-`) splits one level deeper into ITEMs — a lead-in
    # line before the first marker becomes its own unmarked item.
    'nonCode/text1_smal.txt': [
        (1, 1, 8, 'The user is testing me on this. They want me to think…'),
        (2, 1, 1, 'The user is testing me on this. They want me to think…'),
        (2, 3, 3, 'Let me actually do some substantial thinking here — pick an…'),
        (2, 5, 6, 'Wait — important nuance. If the reasoning budget is set and…'),
        (2, 8, 8, 'Actually, let me think carefully: the user said "давай…'),
        (1, 11, 26, 'Let me think deeply about the topic. Topic choice:…'),
        (2, 11, 14, 'Let me think deeply about the topic. Topic choice:…'),
        (3, 11, 11, 'Let me think deeply about the topic. Topic choice:…'),
        (3, 12, 12, '- What to store (facts vs procedures vs episodic)'),
        (3, 13, 13, '- Conflict resolution between memories'),
        (3, 14, 14, '- Token budget for memory injection'),
        (2, 16, 16, 'This is perfect — it directly relates to our conversation…'),
        (2, 18, 18, '1. **Storage model**: KV pairs vs graph vs append-only log.…'),
        (2, 20, 20, '2. **Write policy**: The hardest part. Write too much →…'),
        (2, 22, 26, 'Let me write the response in Russian: 1. One line: picked a…'),
        (3, 22, 22, 'Let me write the response in Russian:'),
        (3, 23, 23, '1. One line: picked a topic (agent memory system — meta,…'),
        (3, 24, 24, '2. **Concluded:** 3–5 items with real substance'),
        (3, 25, 25, '3. **Still needed:** open questions + exact next steps…'),
        (3, 26, 26, '4. Short synthesis/answer'),
        (1, 30, 39, '**Concluded:**'),
        (2, 30, 30, '**Concluded:**'),
        (2, 32, 33, '1. **Хранение**: оптимальна гибридная схема — append-only…'),
        (3, 32, 32, '1. **Хранение**: оптимальна гибридная схема — append-only…'),
        (3, 33, 33, '4. **Ключевое открытие** (самый ценный вывод): чекпоинты из…'),
        (2, 35, 35, '**Still needed:**'),
        (2, 37, 39, '1. Как эмпирически измерить *ценность* записи памяти (для…'),
        (3, 37, 37, '1. Как эмпирически измерить *ценность* записи памяти (для…'),
        (3, 38, 38, '2. Частота компакции: по таймеру, по объёму журнала, или по…'),
        (3, 39, 39, '3. Разрешение конфликтов: новая запись противоречит старой…'),
        (1, 41, 41, '~rule'),
    ],
    # Own fixture #1: a "clean" realistic case — mixed marker styles (`1.` and `1)`),
    # a paragraph whose SECOND half is a list (lead-in item + numbered items), a rule
    # in the middle as a section break, and a final paragraph with no list at all.
    'nonCode/notes_meeting.txt': [
        (1, 1, 8, 'Weekly sync notes, planning track. Attendees: Dana, Marcus,…'),
        (2, 1, 1, 'Weekly sync notes, planning track. Attendees: Dana, Marcus,…'),
        (2, 3, 3, 'Dana opened with a status update on the migration. The old…'),
        (2, 5, 8, 'Decisions made today: 1. Cut over the primary queue…'),
        (3, 5, 5, 'Decisions made today:'),
        (3, 6, 6, '1. Cut over the primary queue consumer on Thursday, not…'),
        (3, 7, 7, '2. Keep the old consumer running read-only for one more…'),
        (3, 8, 8, "3. Marcus owns the rollback runbook, due before Thursday's…"),
        (1, 11, 14, 'Open questions for next week, in priority order: - Who owns…'),
        (2, 11, 14, 'Open questions for next week, in priority order: - Who owns…'),
        (3, 11, 11, 'Open questions for next week, in priority order:'),
        (3, 12, 12, '- Who owns the alerting thresholds after cutover?'),
        (3, 13, 13, '- Does the shadow-mode data need to be archived or can it…'),
        (3, 14, 14, '- Should the on-call rotation change once the new consumer…'),
        (1, 16, 16, '~rule'),
        (1, 18, 23, 'Action items, assigned: 1) Marcus: write the rollback…'),
        (2, 18, 21, 'Action items, assigned: 1) Marcus: write the rollback…'),
        (3, 18, 18, 'Action items, assigned:'),
        (3, 19, 19, '1) Marcus: write the rollback runbook.'),
        (3, 20, 20, '2) Dana: draft the alerting threshold proposal.'),
        (3, 21, 21, '3) On-call: monitor error rates through Thursday.'),
        (2, 23, 23, 'Closing note from Dana: this is the last blocker before the…'),
    ],
    # Own fixture #2: edge cases — file OPENS with a rule (`===`), a paragraph that is
    # ENTIRELY a list with no lead-in, a mixed-marker list (`-`/`*`), a 2-item list
    # separated from its neighbor by only ONE blank line (stays in the SAME section),
    # and a final double-blank + rule (`***`) at EOF.
    'nonCode/edge_cases.txt': [
        (1, 1, 1, '~rule'),
        (1, 3, 12, 'A file that opens with a rule line above, immediately…'),
        (2, 3, 3, 'A file that opens with a rule line above, immediately…'),
        (2, 5, 5, 'No.'),
        (2, 7, 9, '- Only a bullet list here, no lead-in line before the first…'),
        (3, 7, 7, '- Only a bullet list here, no lead-in line before the first…'),
        (3, 8, 8, '- Second bullet.'),
        (3, 9, 9, '* Third bullet, different marker character, still counts.'),
        (2, 11, 12, '1. First numbered item right after a blank-only gap. 2.…'),
        (3, 11, 11, '1. First numbered item right after a blank-only gap.'),
        (3, 12, 12, '2. Second numbered item, single blank line apart from the…'),
        (1, 15, 15, '~rule'),
    ],
    # YAML (real grammar, tree-sitter-yaml): key:value pair / list item are landmarks;
    # a comment directly above `database:` glues on as its trailing label (existing
    # generic preamble mechanic, no YAML-specific code needed for that).
    'yamlSRC/config.yaml': [
        (1, 1, 1, 'name: myapp'),
        (1, 2, 2, 'version: 1.2.3'),
        (1, 4, 10, 'database:  # database connection settings'),
        (2, 6, 6, 'host: localhost'),
        (2, 7, 7, 'port: 5432'),
        (2, 8, 10, 'credentials:'),
        (3, 9, 9, 'user: admin'),
        (3, 10, 10, 'password: secret'),
        (1, 12, 16, 'servers:'),
        (2, 13, 14, '- name: web1'),
        (3, 13, 13, 'name: web1'),
        (3, 14, 14, 'ip: 10.0.0.1'),
        (2, 15, 16, '- name: web2'),
        (3, 15, 15, 'name: web2'),
        (3, 16, 16, 'ip: 10.0.0.2'),
        (1, 18, 21, 'flags:'),
        (2, 19, 19, '- debug'),
        (2, 20, 20, '- verbose'),
    ],
}

LADDER = [
    # (1,*) glued to 89: the '# chat ...' banner above `def chat` (94) is its preamble
    # — every ladder rung now reports the same glued range as a direct query (tool-verified).
    {"file": 'pythonSRC/backends/__init__.py', "line": 140, "expect": [(3, 139, 145), (2, 137, 160), (1, 89, 166)]},
    {"file": 'mdSRC/capture.py.md', "line": 12, "expect": [(4, 12, 15), (3, 10, 27), (2, 4, 27), (1, 1, 56)]},
    # namespace is transparent -> not a ladder entry; enclosing blocks one level shallower.
    # Invariant #9 (extended): even inside an addressable rung (the method), a plain
    # statement that opens no block of its own is a narrower filler one level deeper —
    # `Stopwatch sw = …;` doesn't merge with its neighbors (each is a DIFFERENT node kind:
    # local_declaration_statement / expression_statement / return_statement), so it stays
    # its own single-line rung, matching what `--dot` already shows for this line.
    {"file": 'csharpSRC/Core/GlobalStopWatchInstance.cs', "line": 12,
     "expect": [(3, 12, 12), (2, 10, 17), (1, 8, 26)]},
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
    # CSS nested at-rules: a rule inside @media inside @supports — 3 real rungs. Invariant #9
    # (extended): the rule's own declaration list [214-218] is a narrower filler one level
    # deeper than the rule itself (same-kind `declaration` nodes merge into one run).
    {"file": 'cssSRC/ChatViewer.css', "line": 214,
     "expect": [(4, 214, 218), (3, 213, 219), (2, 212, 220), (1, 210, 221)]},
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
    # bug, sweep-caught). Line 15 = beta's 2nd signature line. `class Api` starts at its own
    # line 10, NOT glued to the module docstring above (lines 1-7): a Python docstring is a
    # real statement, not a comment — it stays its own filler in the map (`~docstring`), and
    # addressing must agree (collect_preamble bug: was gluing the docstring's bare closing
    # `"""` into the class as if it were a fresh one-line comment).
    {"file": 'pythonSRC/hanging_sig.py', "line": 15, "expect": [(2, 14, 16), (1, 10, 16)]},
    # Inline body (`...`) after a hanging-indent signature stays inside its own def. Invariant
    # #9 (extended): `...` (Ellipsis) is itself a narrower filler (`~expression_statement`)
    # one level deeper than `alpha`'s own signature rung.
    {"file": 'pythonSRC/hanging_sig.py', "line": 12, "expect": [(3, 12, 12), (2, 11, 12), (1, 10, 16)]},
    # Comprehension `for`/`if` inside `{…}` are NOT loop/statement headers — line 21 sits in
    # the set comprehension; only the enclosing def contains it, no fabricated inner block.
    # Invariant #9 (extended): the dict-comprehension assignment (`names = {…}`, lines 20-24)
    # and the next assignment (`match = …`, line 25) are the SAME node kind (`assignment`) —
    # they merge into ONE filler run [20-25], same rule as top-level imports/assigns merging.
    {"file": 'pythonSRC/hanging_sig.py', "line": 21, "expect": [(2, 20, 25), (1, 19, 28)]},
    # Soft keyword as identifier: `match = _re.search(...)` is an assignment, not a block.
    # Same merged assign-run as line 21 (both are inside it).
    {"file": 'pythonSRC/hanging_sig.py', "line": 25, "expect": [(2, 20, 25), (1, 19, 28)]},
    # But a real `if` statement IS still a block (soft/comprehension fixes didn't over-reach).
    {"file": 'pythonSRC/hanging_sig.py', "line": 27, "expect": [(2, 26, 27), (1, 19, 28)]},
    # Bracket inside a string literal (`if ch == ")":`) must not corrupt the colon scan and
    # balloon the block — string/comment-aware find_colon_line. Clean 3-rung nest.
    {"file": 'pythonSRC/hanging_sig.py', "line": 34, "expect": [(3, 34, 35), (2, 33, 35), (1, 31, 36)]},
    # A function's OWN docstring must not be stolen by its first inner block: `if not env:`
    # starts at its own line 44, NOT glued to the closing `"""` of the docstring on line 43
    # (collect_preamble bug — walked onto a docstring's bare closing quote and mistook it
    # for a fresh one-line comment preamble). Real bug found via docker.py in the wild.
    {"file": 'pythonSRC/hanging_sig.py', "line": 44, "expect": [(2, 44, 45), (1, 39, 46)]},
    # `} else {` on ONE physical line: `if (p)` must end at 102 (its own body), NOT balloon to
    # 105 (the end of the sibling `else`) — tree-sitter folds else_clause inside if_statement,
    # own-body-end (`_own_end_row`) cuts it. Both siblings are honestly listed at the same
    # level 6, sharing the boundary line (invariant #8 — see `SIBLING` in the fuzz sweep).
    {"file": 'tsSRC/src/analyzer.ts', "line": 102,
     "expect": [(6, 102, 105), (6, 99, 102), (5, 97, 106), (4, 95, 108), (3, 93, 109), (2, 69, 120), (1, 52, 123)]},
    # Line 104 is INSIDE `else` only (not on the shared brace line) — `if (p)` must NOT appear;
    # own-body-end also fixes the containment filter, not just the reported range.
    {"file": 'tsSRC/src/analyzer.ts', "line": 104,
     "expect": [(6, 102, 105), (5, 97, 106), (4, 95, 108), (3, 93, 109), (2, 69, 120), (1, 52, 123)]},
    # Invariant #9: a top-level line with NO addressable block (module docstring — no def/
    # class contains it) must return the FILLER band `--outline` already shows for it
    # (`~docstring [1-7]`), not the whole-file fallback `[1, N]`. Real bug: docker.py line 9
    # (a top-level `import`) used to return `[1-2050] <module>` — the entire file — instead
    # of the tight `imports: …` band.
    {"file": 'pythonSRC/hanging_sig.py', "line": 3, "expect": [(1, 1, 7)]},
    # Same invariant, brace engine: a leading `import` line (no enclosing def/class) returns
    # the `imports: …` filler band, not `[1, N]`.
    {"file": 'Edge/Edge.ts', "line": 1, "expect": [(1, 1, 3)]},
    # Plain-text: section -> paragraph -> list item, 3 real rungs (line 33 is a marker
    # line inside a 2-item list paragraph with no lead-in — see LADDER_LABEL for names).
    {"file": 'nonCode/text1_smal.txt', "line": 33,
     "expect": [(3, 33, 33), (2, 32, 33), (1, 30, 39)]},
    {"file": 'nonCode/notes_meeting.txt', "line": 7,
     "expect": [(3, 7, 7), (2, 5, 8), (1, 1, 8)]},
    {"file": 'nonCode/edge_cases.txt', "line": 8,
     "expect": [(3, 8, 8), (2, 7, 9), (1, 3, 12)]},
    # YAML: mapping -> nested mapping -> pair, 3 real rungs.
    {"file": 'yamlSRC/config.yaml', "line": 9,
     "expect": [(3, 9, 9), (2, 8, 10), (1, 4, 10)]},
]

# cursor_feedback__gcb.md #1 — labels only (LADDER above checks ranges, not text). A
# standalone arrow/function body bound to a name must show that name (outline-identical),
# NOT the generic anonymous tag; one bound to nothing keeps the honest generic tag.
LADDER_LABEL = [
    {"file": 'tsSRC/src/analyzer.ts', "line": 60,
     "expect": ["const: clause, namespaceImport, source, uses, symbols",
                "export const trackWildcardUses = (node: ImportDeclaration) =>"]},
    {"file": 'tsSRC/src/analyzer.ts', "line": 234,
     "expect": ["() => {…}",
                "export const getPotentiallyUnused = ( file: SourceFile, skipper?: RegExp ): "
                "IAnalysedResult =>"]},
    {"file": 'nonCode/text1_smal.txt', "line": 33,
     "expect": ["4. **Ключевое открытие** (самый ценный вывод): чекпоинты из…",
                "1. **Хранение**: оптимальна гибридная схема — append-only…",
                "**Concluded:**"]},
    {"file": 'yamlSRC/config.yaml', "line": 9,
     "expect": ["user: admin", "credentials:", "database:"]},
]

FOCUS_OUTLINE = [
    # `--dot --line N` focus mode never had oracle coverage at all before invariant #9 (it
    # was newly able to terminate on a bare filler leaf). Two real bugs found via manual
    # --dot testing on namespaced C# files, both in `_containing_chain`'s level bookkeeping:
    #
    # (a) CRASH: when the ENTIRE focus display is a single filler row (no landmark sibling
    #     at all), core.py's adaptive-depth tally excludes filler from `per_level`, so
    #     `base_level` defaulted to 1 while the row's real level was deeper — the row got
    #     filtered out by its own `shown` cap, `labels` ended up empty, `max()` crashed.
    {"file": 'csharpSRC/Core/GlobalStopWatchInstance.cs', "line": 12, "deep": True,
     "expect": [(3, 12, 12, '~local_declaration_statement')]},
    # (b) MISCOUNT: a transparent frame (namespace) in the chain was counted as +1 depth
    #     (`base = idx + 1`, chain POSITION, not real level) — a field one level inside a
    #     class one level inside a (transparent) namespace showed level 3 instead of 2.
    {"file": 'csharpSRC2/Core/Settings.cs', "line": 13, "deep": True,
     "expect": [(2, 12, 72, 'field: Paths, Metadata, Network, Maintenance, DefaultUser, '
                            'Backends, IsInstalled, InstallDate, …')]},
    # Sanity: a top-level filler (invariant #9) focused directly, unaffected by either fix.
    {"file": 'csharpSRC2/Core/Settings.cs', "line": 4, "deep": True,
     "expect": [(1, 1, 5, 'imports: FreneticUtilities.FreneticDataSyntax, SwarmUI.Backends, '
                          'SwarmUI.Media, SwarmUI.Utils, System.Reflection')]},
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
    # Invariant #9 (extended): `var x = _count;` is itself a narrower filler than the whole
    # method — level 0 (innermost/default) now zooms to that one line; `--ancestor-level 1`
    # still reaches the method.
    {"file": 'Edge/Edge.cs', "line": 41, "level": 0, "expect": (3, 41, 41)},
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

    # --- ambiguous shared-brace-boundary (invariant #8) ---
    # Line 102 is `} else {`: `if (p)` and `else` are SIBLINGS at the same level (6), neither
    # more "inner" than the other. Default resolve (level 0) must NOT arbitrarily pick one —
    # it climbs past the whole tied level to the parent `for` (level 5), the nearest rung held
    # by exactly one candidate.
    {"file": 'tsSRC/src/analyzer.ts', "line": 102, "level": 0, "expect": (5, 97, 106)},
    # A non-ambiguous line one row inside `else` still resolves to `else` itself (sanity check
    # that the climb-on-ambiguity logic doesn't over-fire on ordinary unique lines).
    {"file": 'tsSRC/src/analyzer.ts', "line": 104, "level": 0, "expect": (6, 102, 105)},
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
    # REQ-003: nested package (parent dir 'plugin' undeclared, own dir hyphenated) —
    # `from . import delegate_core` used to resolve to a truncated/wrong dotted name and miss
    # the consumer entirely; path-based resolution fixes it regardless of __init__.py chain.
    'py nested hyphenated package (self-delegate)': {
        "root": 'pythonSRC2', "file": 'self_delegate/plugin/self-delegate/delegate_core.py',
        "expect": ['self_delegate/plugin/self-delegate/__init__.py'],
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
