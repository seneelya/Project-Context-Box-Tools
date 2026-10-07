"""Replay logged get_codeblock calls on the OLD (git HEAD) and NEW tool, compare stdout+code."""
import json, subprocess, sys, os, glob

OLD = r"c:\RAM_Cache\Temp\hermes-filetools\gcb_old"
NEW = r"c:\RAM_Cache\Temp\hermes-filetools\gcb_new"
LOGS = {
    r"T:\AgentsWork\hermes-filetools\__HQ\tools\_logs\get_codeblock.log.jsonl": r"T:\AgentsWork\hermes-filetools",
    r"T:\AgentsWork\ProjectStarter\__HQ\tools\_logs\get_codeblock.log.jsonl": r"T:\AgentsWork\ProjectStarter",
    r"Y:\SRC\llama.cpp_mix\__HQ\tools\_logs\get_codeblock.log.jsonl": r"Y:\SRC\llama.cpp_mix",
}
limit = int(sys.argv[1]) if len(sys.argv) > 1 else 10**9

seen, calls = set(), []
for log, root in LOGS.items():
    for l in open(log, encoding="utf-8"):
        if not l.strip():
            continue
        argv = json.loads(l)["argv"]
        key = (root, tuple(argv))
        if key not in seen and "--help" not in argv:
            seen.add(key)
            calls.append((root, argv))
calls = calls[-limit:]

env = dict(os.environ, PYTHONIOENCODING="utf-8")


def run(tool_dir, root, argv):
    r = subprocess.run([sys.executable, os.path.join(tool_dir, "get_codeblock.py"), "--project-root", root] + argv,
                       cwd=root, capture_output=True, env=env)
    return r.returncode, r.stdout, r.stderr


diff = 0
for i, (root, argv) in enumerate(calls):
    o, n = run(OLD, root, argv), run(NEW, root, argv)
    last = lambda e: (e.strip().splitlines()[-1] if e.strip() else b"").replace(b"gcb_old", b"gcb").replace(b"gcb_new", b"gcb")
    if o[:2] != n[:2] or last(o[2]) != last(n[2]):
        diff += 1
        if True:
            print("DIFF", root, argv, o[0], n[0])
            print("  old:", o[1][:300], o[2][:300])
            print("  new:", n[1][:300], n[2][:300])
print(f"{len(calls)} calls, {diff} differ")
