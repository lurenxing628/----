#!/usr/bin/env python3
"""B 锚点路径重映射:按 p6_path_map.csv 把 B 计划文档里 A/P6 之前的扁平测试路径
(tests/regression_*.py / tests/test_*.py)整体替换为 P6 新路径(tests/<模块>/...)。

只替换【完整带 tests/ 前缀的路径字符串】,其后的 :行号原样保留(git mv 内容不变,行号
大体幸存,B 执行时仍按符号 rg 校准)。6 个被 P1 删 / P5 合并的文件不在 csv,脚本天然
不动它们 —— 由各 dossier 的终态裁定单独回写(见 _B_COMPAT_SAFEGUARDS.md §5 / B-2 / B-6)。

ANCHOR-DRIFT-2026-06-05-POSTCOMMIT.md 由人工补章节,排除在脚本之外避免冲突。

用法:
  python remap_b_anchors.py --dry-run   # 报告影响面,不写回
  python remap_b_anchors.py --apply     # 实际写回两套副本 + _B_COMPAT
"""

from __future__ import annotations

import argparse
import csv
import glob
import os
from typing import Dict, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
CSV_PATH = os.path.join(HERE, "p6_path_map.csv")

PHASE4_DIRS = (
    ".codestable/audits/2026-06-02-underwater-debt-census/fix-plan/phase4-dep-safety",
    "docs/_panorama_data/phase4_dep_safety",
)
EXTRA_FILES = (".codestable/refactors/2026-06-01-test-gate-cleanup/_B_COMPAT_SAFEGUARDS.md",)
EXCLUDE_BASENAMES = frozenset({"ANCHOR-DRIFT-2026-06-05-POSTCOMMIT.md"})


def load_map(csv_path: str) -> Dict[str, str]:
    mapping = {}  # type: Dict[str, str]
    with open(csv_path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            old, new = row["old_path"].strip(), row["new_path"].strip()
            if old and new and old != new:
                mapping[old] = new
    return mapping


def target_files() -> List[str]:
    files = []  # type: List[str]
    for rel_dir in PHASE4_DIRS:
        base = os.path.join(REPO_ROOT, rel_dir)
        # 递归覆盖任意子目录深度的 .md(dossier/redteam/cluster 文本)与 .json(机器注册表,
        # 每债登记 test_consumers 路径,同样需随 P6 重映射对齐)。
        for ext in ("md", "json"):
            files.extend(glob.glob(os.path.join(base, "**", "*." + ext), recursive=True))
    for rel in EXTRA_FILES:
        path = os.path.join(REPO_ROOT, rel)
        if os.path.isfile(path):
            files.append(path)
    return sorted(f for f in files if os.path.basename(f) not in EXCLUDE_BASENAMES)


def remap_text(text: str, ordered: Sequence[Tuple[str, str]]) -> Tuple[str, int]:
    total = 0
    for old, new in ordered:
        hits = text.count(old)
        if hits:
            text = text.replace(old, new)
            total += hits
    return text, total


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="实际写回(默认 dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="只报告不写回")
    args = parser.parse_args(argv)
    apply = args.apply and not args.dry_run

    mapping = load_map(CSV_PATH)
    # 长 old_path 先替换,杜绝一个 old 是另一个前缀的误伤(.py 结尾本已隔离,降序为双保险)
    ordered = sorted(mapping.items(), key=lambda kv: -len(kv[0]))

    changed_files, total_repl = 0, 0
    per_file = []  # type: List[Tuple[str, int]]
    for path in target_files():
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        new_text, n = remap_text(text, ordered)
        if n:
            changed_files += 1
            total_repl += n
            per_file.append((os.path.relpath(path, REPO_ROOT), n))
            if apply:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(new_text)

    per_file.sort(key=lambda item: -item[1])
    mode = "APPLIED" if apply else "DRY-RUN"
    print(f"[{mode}] map_entries={len(mapping)} files_changed={changed_files} total_replacements={total_repl}")
    for rel, n in per_file:
        print(f"  {n:4d}  {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
