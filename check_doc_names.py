"""check_doc_names: a ROUGH check that the code names a markdown doc quotes still exist in the code.

!!! THIS IS A ROUGH CHECK, NOT A PROOF !!!
It takes every `backticked` token of a doc that LOOKS like a code identifier (CamelCase, snake_case,
kConstant, ALL_CAPS) or a file path, and looks for it as a whole word in the project's code files
(or as a file under the sources, the HQ or the doc's own folder). So:
  * a name that is gone from the code but still sits in a comment or a string PASSES (false OK);
  * a math symbol written like an identifier (`r_apo`, `v_target`), a system macro (`FLT_MAX`) or a
    file outside the project is REPORTED (false alarm): silence it per doc with an HTML comment
    anywhere in the doc:   <!-- check_doc_names: ignore r_apo v_target FLT_MAX -->
  * placeholders are read as wildcards: `TASKn.md`, `bench_roundN.cpp`, `test_plan02_*.cpp`, `kLaw*`;
  * it says nothing about whether the doc's SENTENCES are true: only that the names exist.
A rough check is still better than none: renamed or deleted names show up at once.

Usage:
    python check_doc_names.py <doc.md | dir> [...]   # dirs: every *.md below them
    python check_doc_names.py __HQ/docs --root <src>  # default root: CONFIG__TOOLS.PROJECT_ROOT

Exit code: 0 nothing reported, 1 a name or a path not found, 2 bad arguments.
"""
import argparse
import fnmatch
import os
import re
import sys
from pathlib import Path

# The hardcoded rule (no config yet).
CODE_EXT = {'.h', '.hpp', '.hh', '.c', '.cc', '.cpp', '.cxx', '.cu', '.cuh', '.comp', '.glsl', '.vert', '.frag',
            '.geom', '.tesc', '.tese', '.py', '.js', '.mjs', '.ts', '.tsx', '.jsx', '.cs', '.cmake', '.txt', '.bat',
            '.cmd', '.ps1', '.sh', '.json', '.yaml', '.yml', '.toml'}
FILE_EXT = CODE_EXT | {'.md', '.html', '.css', '.spv', '.exe', '.dll', '.csv', '.npz'}   # what makes a token a file
ALWAYS_SKIP = {'.git', '__pycache__', 'node_modules', '__HQ'}
MIN_LEN = 3                # shorter names are not checked
DOC_GLOB = '*.md'

TOOLS_DIR = Path(__file__).resolve().parent
IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
IGNORE_NOTE = re.compile(r'<!--\s*check_doc_names:\s*ignore\s+([^>]*?)-->')
# A placeholder N / n of a series: TASKn.md, bench_roundN.cpp, contact_testsN, CONTACT_TESTN_NO_MAIN.
PLACEHOLDER = re.compile(r'(?<=[a-z_])N(?=[._*/]|$)|(?<=[A-Z])n(?=[._*]|$)|(?<=[A-Z])N(?=_)')


def looks_like_code(n):
    """CamelCase inside, snake_case, kConstant or ALL_CAPS: the shapes of code names, not of English words."""
    if len(n) < MIN_LEN:
        return False
    if re.match(r'^k[A-Z]', n) or re.match(r'^[A-Z][A-Z0-9_]{3,}$', n):
        return True
    return bool(re.search(r'[a-z]', n)) and (bool(re.search(r'[A-Z]', n[1:])) or '_' in n.strip('_'))


def is_file_token(tok):
    """A path or a file name: has a known extension at its end, or ends with '/' and has a slash."""
    if ' ' in tok or tok.count('`'):
        return False
    if tok.endswith('/') and len(tok) > 1:
        return True
    last = tok.rsplit('/', 1)[-1]
    return Path(last).suffix.lower() in FILE_EXT


def config_root():
    sys.path.insert(0, str(TOOLS_DIR))
    try:
        import CONFIG__TOOLS as cfg
        return Path(cfg.PROJECT_ROOT), set(getattr(cfg, 'BLACKLIST_DIRS', []))
    except Exception:
        return None, set()


def walk(base, skip, keep):
    for dp, dn, fn in os.walk(base):
        dn[:] = [d for d in dn if d not in skip]
        for f in fn:
            if keep(f):
                yield Path(dp) / f


def file_found(tok, bases, rel_paths):
    """Glob the token (placeholders as *) under each base; a bare name matches any file of that name."""
    is_dir = tok.endswith('/')
    pat = PLACEHOLDER.sub('*', re.sub(r'<[^>]*>', '*', tok.replace('\\', '/').rstrip('/')))
    if is_dir:                                            # a folder: it exists, or some file lies below it
        if any((b / pat).is_dir() or b.name == pat for b in bases):
            return True
        return any(any(fnmatch.fnmatch(r, pat + '/*') or fnmatch.fnmatch(r, '*/' + pat + '/*') for r in rels)
                   for rels in rel_paths)
    variants = [pat]
    m = re.match(r'^(.*)\.(\w+)/\.(\w+)$', pat)          # src/batch_gate.h/.cpp
    if m:
        variants = [f'{m.group(1)}.{m.group(2)}', f'{m.group(1)}.{m.group(3)}']
    for v in variants:
        hit = False
        for rels in rel_paths:
            if '/' in v:
                hit = any(fnmatch.fnmatch(r, v) or fnmatch.fnmatch(r, '*/' + v) for r in rels)
            else:
                hit = any(fnmatch.fnmatch(r.rsplit('/', 1)[-1], v) for r in rels)
            if hit:
                break
        if not hit:
            hit = any((b / v).exists() for b in bases if '*' not in v)
        if not hit:
            return False
    return True


def name_found(name, words, stems):
    """A word of the code, a file's stem (a tool, a doc: `get_codeblock`, `Doc__10`), or a placeholder series."""
    if name in words or name in stems or any(s.startswith(name + '_') for s in stems if name.startswith('Doc__')):
        return True
    if PLACEHOLDER.search(name):
        pat = re.compile('^' + PLACEHOLDER.sub(r'\\w*', re.escape(name).replace('\\*', '*')) + '$')
        return any(pat.match(w) for w in words)
    return False


def docs_of(args):
    for a in args:
        p = Path(a)
        if p.is_dir():
            yield from sorted(p.rglob(DOC_GLOB))
        elif p.is_file():
            yield p
        else:
            print(f'not found: {a}', file=sys.stderr)
            sys.exit(2)


def main():
    ap = argparse.ArgumentParser(description='ROUGH check: do the code names a doc quotes still exist in the code?')
    ap.add_argument('paths', nargs='+', help='markdown docs or directories')
    ap.add_argument('--root', help='the sources (default: CONFIG__TOOLS.PROJECT_ROOT)')
    ap.add_argument('--hq', help='the HQ whose files a doc may name (default: the folder above this tool)')
    a = ap.parse_args()
    root, skip = config_root()
    if a.root:
        root = Path(a.root)
    if root is None or not root.is_dir():
        print('no source root: pass --root or set CONFIG__TOOLS.PROJECT_ROOT', file=sys.stderr)
        return 2
    hq = Path(a.hq) if a.hq else TOOLS_DIR.parent
    skip |= ALWAYS_SKIP
    code = list(walk(root, skip, lambda f: Path(f).suffix.lower() in CODE_EXT or f == 'CMakeLists.txt'))
    # paths may name generated files (build/*_spv.h): every file counts, only the words skip the blacklist
    src_rel = [f.relative_to(root).as_posix() for f in walk(root, ALWAYS_SKIP, lambda f: True)]
    hq_rel = [f.relative_to(hq).as_posix() for f in walk(hq, {'.git', '__pycache__'}, lambda f: True)]
    stems = {Path(r).stem for r in src_rel + hq_rel}
    words = set()
    for f in code:
        try:
            words.update(IDENT.findall(f.read_text(encoding='utf-8', errors='ignore')))
        except OSError:
            pass
    print(f'ROUGH check: {len(code)} code files under {root}, files of {hq} '
          '(a name in a comment passes; math symbols alarm)')
    bad = 0
    for doc in docs_of(a.paths):
        text = doc.read_text(encoding='utf-8', errors='replace')
        ignore = set(' '.join(IGNORE_NOTE.findall(text)).split())
        doc_rel = [f.relative_to(doc.parent).as_posix() for f in walk(doc.parent, {'.git'}, lambda f: True)]
        bases = [root, hq, doc.parent]
        seen, missing, paths = set(), [], []
        fence = False
        for n, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith(('```', '~~~')):
                fence = not fence
                continue
            if fence:
                continue
            for tok in re.findall(r'`([^`\n]+)`', line):
                tok = tok.strip()
                if is_file_token(tok):
                    if tok not in seen:
                        seen.add(tok)
                        if tok not in ignore and not file_found(tok, bases, [src_rel, hq_rel, doc_rel]):
                            paths.append((n, tok))
                    continue
                for m in IDENT.finditer(tok):
                    name = m.group(0)
                    if name in seen or not looks_like_code(name):
                        continue
                    seen.add(name)
                    star = tok[m.end():m.end() + 1] == '*'          # a prefix: shot_grid_*, kLaw*
                    ok = any(w.startswith(name) for w in words) if star else name_found(name, words, stems)
                    if not ok and name not in ignore:
                        missing.append((n, name))
        if missing or paths:
            bad += 1
            print(f'CHECK {doc}: {len(seen)} names, not found: {len(missing)} names, {len(paths)} paths')
            for n, name in missing:
                print(f'        L{n} {name}')
            for n, p in paths:
                print(f'        L{n} path {p}')
    if bad:
        print(f'{bad} doc(s): a name not found may be renamed or deleted in the code, or a math symbol '
              '(silence those with <!-- check_doc_names: ignore ... -->).')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
