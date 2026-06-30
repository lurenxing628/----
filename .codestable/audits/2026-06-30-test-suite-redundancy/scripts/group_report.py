#!/usr/bin/env python3
"""把 findings.json 的重复组按一级模块目录分包,补行号,供分发给 subagent 核实。"""
import collections
import json
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
fnd = json.load(open(os.path.join(OUT, "findings.json"), encoding="utf-8"))
idx = json.load(open(os.path.join(OUT, "func_index.json"), encoding="utf-8"))


def fid_of(m):
    return m["id"] if isinstance(m, dict) else m


def line_of(fid):
    e = idx.get(fid)
    return e["line"] if e else "?"


def file_of(fid):
    return fid.split("::")[0]


def func_of(fid):
    return fid.split("::", 1)[1]


def topdir(fid):
    p = file_of(fid).split("/")
    return p[1] if len(p) > 1 else "?"


groups = []
for g in fnd["exact_duplicates"]:
    groups.append(("EXACT", g["count"], g.get("stmts", "-"), [fid_of(m) for m in g["members"]]))
for g in fnd["skeleton_duplicates"]:
    groups.append(("SKEL", g["count"], g.get("stmts", "-"), [fid_of(m) for m in g["members"]]))

by_dir = collections.defaultdict(list)
for kind, cnt, st, ms in groups:
    files = {file_of(x) for x in ms}
    dirs = {topdir(x) for x in ms}
    scope = "same-file" if len(files) == 1 else ("same-dir" if len(dirs) == 1 else "cross-dir")
    rec = {
        "kind": kind, "scope": scope, "count": cnt, "stmts": st,
        "members": [{"file": file_of(x), "func": func_of(x), "line": line_of(x)} for x in ms],
    }
    by_dir[topdir(ms[0])].append(rec)

json.dump(by_dir, open(os.path.join(OUT, "groups_by_module.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

print("=== 重复组按模块分布(供 subagent 分包) ===")
total = 0
for d in sorted(by_dir, key=lambda k: -len(by_dir[k])):
    recs = by_dir[d]
    total += len(recs)
    sf = sum(1 for r in recs if r["scope"] == "same-file")
    sd = sum(1 for r in recs if r["scope"] == "same-dir")
    cd = sum(1 for r in recs if r["scope"] == "cross-dir")
    ex = sum(1 for r in recs if r["kind"] == "EXACT")
    print(f"  {d:<22} groups={len(recs):2d}  (same-file={sf} same-dir={sd} cross-dir={cd}, exact={ex})")
print("  TOTAL groups =", total)
