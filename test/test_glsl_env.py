"""D7 isolated CLI checks; --upstream DIR tests a real unmodified upstream wheel."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig
import tempfile

TOOLS = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--upstream', type=Path)
    ap.add_argument('--before', type=Path, help='optional pre-change tools snapshot')
    args = ap.parse_args()
    import tree_sitter
    with tempfile.TemporaryDirectory(prefix='glsl-env-') as tmp:
        root = Path(tmp)
        # -S prevents the real venv grammar from leaking into the isolated test.
        shutil.copytree(Path(tree_sitter.__file__).parent, root / 'tree_sitter')
        sys.path.insert(0, str(TOOLS))
        from get_codeblock.env_check import LANGUAGE_MODULES
        artifacts = LANGUAGE_MODULES['glsl']['artifacts']
        wheel = TOOLS / artifacts[sysconfig.get_platform()]
        fixture = TOOLS / 'test/glslSRC/declarations.glsl'

        def run(extra='', prelude='pass', file=fixture, base=TOOLS):
            code = (f'import sys; sys.path[:0] = [{str(base)!r}, {str(root)!r}{extra}]; '
                    + prelude + f'; sys.argv = ["get_codeblock.py", "--file", {str(file)!r}, "--outline"]; '
                    'from get_codeblock.core import main; main()')
            return subprocess.run([sys.executable, '-B', '-S', '-c', code], cwd=root,
                                  capture_output=True, encoding='utf-8', timeout=45)

        def refused(result):
            assert result.returncode != 0, result.stdout
            assert 'Traceback' not in result.stderr + result.stdout, result.stderr
            return result.stderr + result.stdout

        message = refused(run())
        assert 'not installed' in message and str(wheel) in message, message
        assert '--force-reinstall --no-deps' in message and sys.executable in message
        print('PASS absent module / absolute artifact command / foreign cwd')

        if args.upstream:
            extra = ', ' + repr(str(args.upstream.resolve()))
        else:
            pkg = root / 'legacy/tree_sitter_glsl_spec'
            pkg.mkdir(parents=True)
            (pkg / '__init__.py').write_text('def language():\n    return 123\n', encoding='utf-8')
            extra = ', ' + repr(str(pkg.parent))
        message = refused(run(extra=extra))
        assert 'incompatible installed build' in message and str(wheel) in message, message
        assert '--force-reinstall --no-deps' in message
        print('PASS legacy integer binding / refusal before Language(int)')

        for target, artifact in artifacts.items():
            message = refused(run(prelude=f"import sysconfig; sysconfig.get_platform = lambda: {target!r}"))
            assert str(TOOLS / artifact) in message and '--force-reinstall --no-deps' in message, message
            print('PASS artifact command for ' + target)

        message = refused(run(prelude="import sysconfig; sysconfig.get_platform = lambda: 'linux-aarch64'"))
        assert 'No prebuilt wheel for this platform' in message and 'README.md' in message
        assert 'pip install' not in message, message
        print('PASS unsupported platform / build instructions / no invalid install command')

        # A vendored copy (hermes-filetools/vendor) has no wheels/ beside it: no false path.
        vendored = root / 'vendored'
        shutil.copytree(TOOLS / 'get_codeblock', vendored / 'get_codeblock',
                        ignore=shutil.ignore_patterns('__pycache__'))
        message = refused(run(base=vendored))
        assert 'not installed' in message and 'tools repo' in message, message
        assert str(vendored / 'wheels') not in message, message
        print('PASS vendored copy without wheels/ / points to the tools repo')

        # Existing list-style language dependency messages are byte-identical.
        code = f'''
import importlib.util, sys
sys.path.insert(0, {str(TOOLS)!r})
from get_codeblock import env_check as current
spec=importlib.util.spec_from_file_location('env_before', {str(args.before / 'get_codeblock/env_check.py') if args.before else ''!r})
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
for lang in old.LANGUAGE_MODULES:
 def result(module):
  module.importlib.util.find_spec=lambda name: None
  try: module.ensure_language(lang, path=current.REQUIREMENTS)
  except module.EnvError as e: return str(e)
 assert result(current)==result(old), lang
print('PASS unchanged dependency messages for all previous languages')
'''
        # The old snapshot comparison is optional outside the development machine.
        if args.before:
            r = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, encoding='utf-8', timeout=45)
            assert r.returncode == 0, r.stderr
            print(r.stdout.strip())


if __name__ == '__main__':
    main()
