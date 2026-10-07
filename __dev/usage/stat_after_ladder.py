"""What follows a ladder call (--line without --query/--outline) on the same file."""
import json, collections, glob

files = glob.glob(r"T:\AgentsWork\*\__HQ\tools\_logs\get_codeblock.log.jsonl")
files.append(r"Y:\SRC\llama.cpp_mix\__HQ\tools\_logs\get_codeblock.log.jsonl")


def kind(a):
    if "--name" in a:
        return "name"
    if "--query" in a:
        return "query"
    if "--outline" in a:
        return "outline"
    if "--line" in a:
        return "ladder"
    return "outline" if "--file" in a else "other"


def fval(a, k):
    return a[a.index(k) + 1] if k in a and a.index(k) + 1 < len(a) else None


after = collections.Counter()
first = collections.Counter()
for f in files:
    rows = [json.loads(l)["argv"] for l in open(f, encoding="utf-8") if l.strip()]
    prev_file = None
    for i, a in enumerate(rows):
        fl = fval(a, "--file")
        if fl != prev_file:
            first[kind(a)] += 1           # first call on a new file
        prev_file = fl
        if kind(a) != "ladder":
            continue
        nxt = rows[i + 1] if i + 1 < len(rows) else None
        if nxt is None or fval(nxt, "--file") != fl:
            after["other file / end"] += 1
        else:
            after[kind(nxt)] += 1
print("after a ladder call:", after.most_common())
print("first call on a file:", first.most_common())
