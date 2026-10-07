import json, collections, glob

files = [r"T:\AgentsWork\hermes-filetools\__HQ\tools\_logs\get_codeblock.log.jsonl",
         r"Y:\SRC\llama.cpp_mix\__HQ\tools\_logs\get_codeblock.log.jsonl"]
files += glob.glob(r"T:\AgentsWork\*\__HQ\tools\_logs\get_codeblock.log.jsonl")
seen = set()
for f in files:
    if f.lower() in seen:
        continue
    seen.add(f.lower())
    c = collections.Counter()
    sizes = collections.Counter()
    try:
        rows = [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
    except FileNotFoundError:
        continue
    for r in rows:
        a = r.get("argv", [])
        def val(flag):
            return a[a.index(flag) + 1] if flag in a and a.index(flag) + 1 < len(a) else None
        line, lvl = val("--line"), val("--level")
        q, o = "--query" in a, "--outline" in a
        mode = "query" if q else "outline" if o else ("survey" if line else "bare-outline")
        if "--name" in a:
            mode = "name"
        arr = bool(line and "," in line)
        c[(mode, "array" if arr else "single")] += 1
        if arr:
            sizes[len(line.split(","))] += 1
        if lvl:
            c[("with --level", "array" if "," in lvl else "single")] += 1
    print(f"\n{f}  calls={len(rows)}  {rows[0].get('ts')} .. {rows[-1].get('ts')}")
    for k, v in sorted(c.items(), key=lambda kv: -kv[1]):
        print(f"  {k[0]:14} {k[1]:6} {v}")
    print("  array sizes:", dict(sorted(sizes.items())))
