import json, collections, glob

files = glob.glob(r"T:\AgentsWork\*\__HQ\tools\_logs\get_codeblock.log.jsonl")
files.append(r"Y:\SRC\llama.cpp_mix\__HQ\tools\_logs\get_codeblock.log.jsonl")
flags = collections.Counter()
levels = collections.Counter()
combos = collections.Counter()
total = 0
for f in files:
    for l in open(f, encoding="utf-8"):
        if not l.strip():
            continue
        a = json.loads(l).get("argv", [])
        total += 1
        fl = sorted(x for x in a if x.startswith("--") and x not in ("--file", "--project-root"))
        for x in fl:
            flags[x] += 1
        combos[" ".join(fl)] += 1
        for k in ("--level", "--ancestor-level"):
            if k in a:
                levels[(k, a[a.index(k) + 1])] += 1
print("calls", total)
print("flags:", flags.most_common())
print("levels:", levels.most_common(15))
print("combos:")
for c, n in combos.most_common(15):
    print(f"  {n:5} {c}")
