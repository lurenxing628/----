#!/usr/bin/env python3
"""全量测试结构化清单生成器（L2）—— 纯静态提取，不跑测试、不用 LLM。"""
from __future__ import annotations

import csv
import os
import re
import sys
from pathlib import Path

ROOT = Path("/Users/lurenxing/Documents/GitHub/----")
TESTS = ROOT / "tests"

RE_TEST = re.compile(r"^\s*def test_", re.M)
RE_MAIN = re.compile(r"^\s*def main\s*\(", re.M)
RE_ASSERT = re.compile(r"^\s*assert\b", re.M)
RE_CJK_ASSERT = re.compile(r"assert[^\n]*['\"][^'\"]*[一-鿿]+[^'\"]*['\"]")
RE_DOM_ASSERT = re.compile(r"assert[^\n]*\bin\s+(source|html|css|body|js|content|markup|rendered|page|text|tpl|template)\b")
RE_IMP_BIZ = re.compile(r"^\s*(?:from|import)\s+(core|web|data)\b[.\w]*", re.M)
RE_SUBPROC = re.compile(r"\bsubprocess\.(Popen|run|call|check_)")
RE_MONKEY = re.compile(r"\bmonkeypatch\b")
RE_GLOBAL_PATCH = re.compile(r"(sys\.modules\[|setattr\(|\.Popen\s*=|time\.time\s*=)")
RE_FINALLY = re.compile(r"^\s*finally\s*:", re.M)
RE_CREATE_APP = re.compile(r"\b(create_app|test_client|app\.test_client)\b")
RE_DB = re.compile(r"\b(ensure_schema|sqlite3\.connect)\b")
RE_FRR = re.compile(r"def find_repo_root|find_repo_root\(\)")

def biz_modules(text):
    mods = set()
    for m in RE_IMP_BIZ.finditer(text):
        # 取前两段，如 core.services.scheduler
        line = m.group(0)
        parts = re.split(r"\s+", line.strip())
        target = parts[-1] if parts[0] == "import" else parts[1]
        mods.add(".".join(target.split(".")[:3]))
    return sorted(mods)

def classify(name, text, ntest, has_main, is_main_style, n_assert, n_cjk, n_dom,
             biz, uses_app, uses_db, glob_patch, has_finally):
    # 自指：测门禁工具自己
    if re.search(r"long_gate|full_test_debt|quality_gate|test_registry|debt_ledger|"
                 r"manifest|fingerprint|architecture_scan|git_hook|quickref|codestable", name):
        if not biz:  # 不碰业务模块
            return "META自指"
    # 纯快照：断言几乎全是字符串子串、不碰业务执行
    if n_assert > 0 and (n_cjk + n_dom) >= max(3, n_assert * 0.6) and not uses_app and not uses_db:
        return "脆性快照"
    # 重量级 main-style
    if is_main_style and uses_app:
        return "B1-起app"
    if is_main_style and uses_db:
        return "B2-起db"
    if is_main_style and glob_patch and not has_finally:
        return "C-全局污染"
    if is_main_style:
        return "A-轻量"
    # 微文件
    if ntest <= 2 and not is_main_style:
        return "微文件"
    return "常规"

rows = []
for p in sorted(TESTS.rglob("*.py")):
    if "__pycache__" in p.parts:
        continue
    rel = p.relative_to(ROOT).as_posix()
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        continue
    ntest = len(RE_TEST.findall(text))
    has_main = bool(RE_MAIN.search(text))
    is_main_style = has_main and ntest == 0
    n_assert = len(RE_ASSERT.findall(text))
    n_cjk = len(RE_CJK_ASSERT.findall(text))
    n_dom = len(RE_DOM_ASSERT.findall(text))
    biz = biz_modules(text)
    uses_app = bool(RE_CREATE_APP.search(text))
    uses_db = bool(RE_DB.search(text))
    glob_patch = bool(RE_GLOBAL_PATCH.search(text))
    has_finally = bool(RE_FINALLY.search(text))
    uses_subproc = bool(RE_SUBPROC.search(text))
    has_frr = bool(RE_FRR.search(text))
    cls = classify(p.name, text, ntest, has_main, is_main_style, n_assert, n_cjk, n_dom,
                   biz, uses_app, uses_db, glob_patch, has_finally)
    rows.append(dict(
        file=rel, lines=text.count("\n")+1, ntest=ntest, main_style=int(is_main_style),
        n_assert=n_assert, n_cjk=n_cjk, n_dom=n_dom, uses_app=int(uses_app),
        uses_db=int(uses_db), glob_patch=int(glob_patch), has_finally=int(has_finally),
        subproc=int(uses_subproc), find_repo_root=int(has_frr),
        biz="|".join(biz[:3]), classification=cls,
    ))

# 写 CSV
out = ROOT / ".codestable/refactors/2026-06-01-test-gate-cleanup/test_inventory.csv"
with out.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

# 聚合统计
from collections import Counter

cls_count = Counter(r["classification"] for r in rows)
cls_lines = Counter()
cls_asserts = Counter()
for r in rows:
    cls_lines[r["classification"]] += r["lines"]
    cls_asserts[r["classification"]] += r["n_assert"]

print(f"清单已写: {out}")
print(f"总文件: {len(rows)}  总行数: {sum(r['lines'] for r in rows)}  总assert: {sum(r['n_assert'] for r in rows)}")
print("\n=== 按分类聚合 ===")
print(f"{'分类':<14}{'文件数':>6}{'行数':>9}{'assert数':>9}")
for c, n in cls_count.most_common():
    print(f"{c:<14}{n:>6}{cls_lines[c]:>9}{cls_asserts[c]:>9}")

# 脆性快照里 assert 最多的 top10（最该瘦身）
print("\n=== 脆性快照: 字符串断言最多的 top10 ===")
snap = [r for r in rows if r["classification"] == "脆性快照"]
for r in sorted(snap, key=lambda x: -(x["n_cjk"]+x["n_dom"]))[:10]:
    print(f"  {r['n_cjk']+r['n_dom']:>4}条字符串断言  {r['file']}")

# 业务模块覆盖热度 top15（哪些核心模块被最多文件测）
print("\n=== 被测业务模块热度 top15 ===")
mod_count = Counter()
for r in rows:
    for m in r["biz"].split("|"):
        if m:
            mod_count[m] += 1
for m, n in mod_count.most_common(15):
    print(f"  {n:>3} 文件  {m}")
