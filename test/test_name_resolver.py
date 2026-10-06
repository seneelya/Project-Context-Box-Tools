"""get_codeblock --name (get_codeblock/name_resolver.py): a name -> line(s) -> the existing
--line render. Run: python test/test_name_resolver.py"""
import os
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

from get_codeblock.name_resolver import normalize, declarations, resolve_name, header_line

_PASS = _FAIL = 0
_HDR = os.path.join(_HERE, "cppSRC", "ggml", "include", "ggml-backend.h")


def check(name, cond):
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(".", end="", flush=True)
    else:
        _FAIL += 1
        print(f"\nFAIL: {name}")


def names(path):
    return [(".".join(d.quals + [d.name]), d.line) for d in declarations(path)]


def _tmp(d, fname, text):
    p = os.path.join(d, fname)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(text)
    return p


def test_normalize():
    check("normalize: spaces and separators", normalize(" ns :: Foo . bar ") == ["ns", "Foo", "bar"])
    check("normalize: template args dropped", normalize("Foo<T, Bar<U>>::baz") == ["Foo", "baz"])
    check("normalize: operator keeps its brackets", normalize("Foo::operator <<") == ["Foo", "operator<<"])
    check("normalize: destructor", normalize("Foo::~Foo") == ["Foo", "~Foo"])


def test_declarations_c_header():
    ds = dict((n, l) for n, l in names(_HDR))
    check("C header: prototype behind a macro (GGML_API T name(...))", ds.get("ggml_backend_sched_new") == 319)
    check("C header: bodyless typedef", ds.get("ggml_backend_t") == 27)
    check("C header: #define", ds.get("GGML_BACKEND_API") in (9, 10, 13, 16))
    quals = {n.rsplit(".", 1)[0] for n in ds if "." in n}
    check("C header: #ifdef does not qualify, the macro type is not a scope",
          not quals & {"__cplusplus", "GGML_BACKEND_SHARED", "ggml_backend_sched_t"})
    check("C header: enum members / struct fields qualified by their type",
          ds.get("ggml_backend_dev_type.GGML_BACKEND_DEVICE_TYPE_GPU") == 138
          and ds.get("ggml_backend_dev_props.memory_free") == 168)
    check("C header: #if condition is not a name", not any("defined" in n for n in ds))


def test_declarations_languages():
    with tempfile.TemporaryDirectory() as d:
        cpp = _tmp(d, "a.cpp", "namespace ns {\nstruct Foo { int x; void bar(); };\n}\n"
                               "void ns::Foo::bar() {\n    int local = 1;\n}\n"
                               "std::ostream & operator<<(std::ostream & o, const ns::Foo & f) { return o; }\n")
        n = names(cpp)
        check("C++: namespace qualifies members", ("ns.Foo", 2) in n and ("ns.Foo.bar", 2) in n)
        check("C++: out-of-class definition Foo::bar", ("ns.Foo.bar", 4) in n)
        check("C++: operator<<", ("operator<<", 7) in n)
        check("C++: function locals are not names", not any(x.endswith("local") for x, _ in n))
        py = _tmp(d, "a.py", "import os\nfrom x import y\n\nLIMIT = 3\n\nclass Api:\n    def beta(self):\n"
                             "        tmp = 1\n        return tmp\n\ndef top():\n    pass\n")
        n = names(py)
        check("Python: class, method qualified, module constant",
              ("Api", 6) in n and ("Api.beta", 7) in n and ("LIMIT", 4) in n and ("top", 11) in n)
        check("Python: imports and locals are not names", not any(x in ("os", "y", "tmp") for x, _ in n))
        cs = _tmp(d, "a.cs", "using System.Diagnostics;\nnamespace App {\n  public class Svc {\n"
                             "    public void Run() { }\n  }\n}\n")
        n = names(cs)
        check("C#: namespace.class.method, using is not a name",
              ("App.Svc.Run", 4) in n and not any("Diagnostics" in x for x, _ in n))
        md = _tmp(d, "a.md", "# Title\n\n## Install\n\ntext\n")
        check("Markdown: headings by their text", ("Install", 3) in names(md))


def test_matching():
    r = resolve_name(_HDR, "ggml_backend_sched_new")
    check("exact: one hit", r.exact and [h.line for h in r.hits] == [319])
    check("exact: header", header_line(r) == 'name: "ggml_backend_sched_new" — exact, line 319')
    r = resolve_name(_HDR, "GGML_BACKEND_API")
    check("exact: ambiguous (defined per #if branch) -> all, file order",
          r.exact and [h.line for h in r.hits] == [9, 10, 13, 16] and "ambiguous: 4 exact" in header_line(r))
    r = resolve_name(_HDR, "sched_new")
    check("closest: substring", not r.exact and r.hits[0].how == "substring" and r.hits[0].line == 319)
    r = resolve_name(_HDR, "sched new")
    check("closest: words in any order", r.hits and r.hits[0].how == "words" and r.hits[0].line == 319)
    r = resolve_name(_HDR, "ggml_backend_sched_nwe")
    check("closest: typo, the most similar first", r.hits[0].how == "typo" and r.hits[0].line == 319)
    r = resolve_name(_HDR, "GGML_backend_sched_new")
    check("closest: case beats the rest", r.hits[0].how == "case")
    r = resolve_name(_HDR, "ggml_backend_sched_*")
    check("glob: a family, capped with a count",
          len(r.hits) == 10 and r.more > 0 and all(h.how == "glob" for h in r.hits)
          and "+%d more" % r.more in header_line(r))
    r = resolve_name(_HDR, "zzz_nothing")
    check("nothing similar", r.hits == [] and "nothing similar" in header_line(r))


def test_scripts():
    """REQ-012: shell scripts declare functions / labels / variables, not the commands they call."""
    sh = os.path.join(_HERE, "scriptSRC", "sample.sh")
    check("sh: function + top-level var, a command call is not a declaration",
          names(sh) == [("VAR", 4), ("build", 7), ("run", 21)])
    ps = os.path.join(_HERE, "scriptSRC", "sample.ps1")
    check("ps1: hyphenated function name is exact", resolve_name(ps, "Get-Thing").exact)
    check("ps1: class method by bare name", ("Box.Area", 24) in names(ps))
    bat = os.path.join(_HERE, "scriptSRC", "sample.bat")
    check("bat: a label is declared without its colon", ("usage", 20) in names(bat))


def _run(*args):
    r = subprocess.run([sys.executable, os.path.join(_TOOLS, "get_codeblock.py"), *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, r.stdout


def test_cli():
    rc, out = _run("--file", _HDR, "--name", "ggml_backend_sched_new", "--force")
    check("cli exact -> --line N --query (the block text)",
          rc == 0 and out.splitlines()[0] == '//name: "ggml_backend_sched_new" — exact, line 319'
          and "//■BLOCK : 319-320" in out and "ggml_backend_sched_new(ggml_backend_t * backends" in out)
    rc, out = _run("--file", _HDR, "--name", "ggml_backend_sched_new", "--outline")
    check("cli exact + --outline -> the map at that line",
          rc == 0 and "//outline — focus line 319" in out and "[319-320] decl:" in out)
    rc, out = _run("--file", _HDR, "--name", "GGML_BACKEND_API")
    check("cli ambiguous -> --line N1,N2,.. --outline (a ladder per candidate)",
          rc == 0 and "outline batch" in out and "//■BLOCK" not in out)
    rc, out = _run("--file", _HDR, "--name", "sched new")
    check("cli closest -> never a block", rc == 0 and "no exact; closest" in out and "//■BLOCK" not in out)
    rc, out = _run("--file", _HDR, "--name", "zzz_nothing")
    check("cli nothing -> exit 2", rc == 2 and "nothing similar" in out)


if __name__ == "__main__":
    test_normalize()
    test_declarations_c_header()
    test_declarations_languages()
    test_matching()
    test_scripts()
    test_cli()
    print("\n" + "-" * 50)
    print(f"{_PASS} passed, {_FAIL} failed")
    sys.exit(1 if _FAIL else 0)
