"""统计项目代码量、token 估算，辅助判断上下文策略。"""
from __future__ import annotations

import os
import sys


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        if os.path.exists(os.path.join(here, "app.py")):
            return here
        here = os.path.dirname(here)
    raise RuntimeError("not found")


def count_dir(base, ext=".py", skip_prefix="__"):
    files = chars = lines = 0
    if not os.path.isdir(base):
        return files, lines, chars
    for root, _, fnames in os.walk(base):
        for f in fnames:
            if not f.endswith(ext) or f.startswith(skip_prefix):
                continue
            fp = os.path.join(root, f)
            try:
                txt = open(fp, encoding="utf-8", errors="replace").read()
                files += 1
                lines += len(txt.splitlines())
                chars += len(txt)
            except Exception:
                pass
    return files, lines, chars


def est_tokens(chars):
    return int(chars / 3.5)


def main():
    repo = find_repo_root()
    os.chdir(repo)

    py_dirs = [
        "web/routes", "core/services", "data/repositories",
        "core/models", "core/infrastructure", "core/algorithms", "tests",
    ]
    total_f = total_l = total_c = 0
    print("=" * 65)
    print("  APS Project Size Report")
    print("=" * 65)
    print()
    print("--- Python Code ---")
    for d in py_dirs:
        f, line_count, c = count_dir(d, ".py")
        total_f += f
        total_l += line_count
        total_c += c
        print(f"  {d:42s}  {f:3d} files  {line_count:6d} lines  ~{est_tokens(c):6d} tok")
    print(f"  {'TOTAL':42s}  {total_f:3d} files  {total_l:6d} lines  ~{est_tokens(total_c):6d} tok")

    print()
    tf, _, tc = count_dir("templates", ".html")
    print(f"--- Templates ---  {tf} files  ~{est_tokens(tc)} tok")

    doc_c = 0
    doc_f = 0
    for entry in os.listdir("."):
        full = os.path.join(".", entry)
        if os.path.isdir(full):
            ef, _, ec = count_dir(full, ".md", skip_prefix="")
            if ec > 0 and ("ADR" in entry or "\u5f00\u53d1" in entry or "docs" in entry.lower()):
                doc_f += ef
                doc_c += ec
    print(f"--- Dev Docs ---   {doc_f} files  ~{est_tokens(doc_c)} tok")

    rule_c = 0
    for root, _, fnames in os.walk(".limcode"):
        for fn in fnames:
            if fn.endswith(".mdc") or fn.endswith(".md"):
                try:
                    txt = open(os.path.join(root, fn), encoding="utf-8", errors="replace").read()
                    rule_c += len(txt)
                except Exception:
                    pass
    print(f"--- Rules+Skills ---  ~{est_tokens(rule_c)} tok")

    grand = total_c + tc + doc_c + rule_c
    gt = est_tokens(grand)
    print()
    print("=" * 65)
    print(f"  GRAND TOTAL:  ~{gt} tokens  ({gt / 1000:.0f}K)")
    print(f"  250K context: {gt / 250000 * 100:.1f}% usage")
    print(f"  200K context: {gt / 200000 * 100:.1f}% usage")
    print("=" * 65)

    print()
    print("--- Token Budget Breakdown ---")
    items = [
        ("Python code", est_tokens(total_c)),
        ("Templates", est_tokens(tc)),
        ("Dev docs", est_tokens(doc_c)),
        ("Rules+Skills (auto-injected)", est_tokens(rule_c)),
        ("System prompt + conversation", 15000),
    ]
    for label, tok in items:
        print(f"  {label:40s}  ~{tok:6d} tok  ({tok / 2500:.0f}%)")


if __name__ == "__main__":
    main()
