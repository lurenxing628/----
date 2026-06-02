#!/usr/bin/env python3
"""确定性拼装水下语义债普查报告:按文件名排序合并 report-sections/*.md -> REPORT.md。

不改写任何章节内容,只做拼接 + 目录生成 + 完整性校验。
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SEC = os.path.join(HERE, "report-sections")
OUT = os.path.join(HERE, "REPORT.md")

# 预期章节(文件名前缀 -> 是否必需)
EXPECTED = [
    "00-cover",
    "01-scheduler-run", "02-scheduler-dispatch", "03-scheduler-gantt",
    "04-scheduler-exec-diag", "05-scheduler-plan-identity",
    "06-scheduler-config-summary-graph", "07-core-models", "08-core-algorithms",
    "09-core-infra-shared", "10-core-svc-domain", "11-data-repos", "12-web-all",
    "90-load-bearing", "91-real-debt", "92-methodology", "99-appendix",
]


def main():
    files = sorted(f for f in os.listdir(SEC) if f.endswith(".md"))
    present = {os.path.splitext(f)[0]: f for f in files}

    missing = [e for e in EXPECTED if e not in present]
    extra = [f for f in present if f not in EXPECTED]

    print("=== 章节完整性校验 ===")
    print("预期 %d 节, 实到 %d 节" % (len(EXPECTED), len(files)))
    if missing:
        print("⚠️ 缺失章节: %s" % ", ".join(missing))
    if extra:
        print("ℹ️ 额外章节: %s" % ", ".join(extra))
    if not missing:
        print("✅ 全部章节到位")

    parts = []
    for key in EXPECTED:
        if key in present:
            path = os.path.join(SEC, present[key])
            with open(path, encoding="utf-8") as fh:
                parts.append(fh.read().rstrip() + "\n")
    # 额外章节也并入(放在 appendix 前不易,直接追加到末尾)
    for f in files:
        k = os.path.splitext(f)[0]
        if k not in EXPECTED:
            with open(os.path.join(SEC, f), encoding="utf-8") as fh:
                parts.append(fh.read().rstrip() + "\n")

    body = "\n\n---\n\n".join(parts)

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body)
        fh.write("\n")

    nlines = body.count("\n") + 1
    nchars = len(body)
    print("\n=== 拼装完成 ===")
    print("输出: %s" % OUT)
    print("规模: %d 行 / %d 字符" % (nlines, nchars))
    # 统计各节字数,便于核查颗粒度
    print("\n各节规模:")
    for key in EXPECTED:
        if key in present:
            with open(os.path.join(SEC, present[key]), encoding="utf-8") as fh:
                c = len(fh.read())
            bar = "█" * min(40, c // 200)
            print("  %-32s %6d  %s" % (key, c, bar))


if __name__ == "__main__":
    main()
