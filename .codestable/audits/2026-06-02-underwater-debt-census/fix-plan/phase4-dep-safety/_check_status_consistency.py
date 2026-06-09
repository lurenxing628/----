#!/usr/bin/env python3
"""registry↔index 逐 ID status 对账自检——每次提交 phase4 台账前必跑。

背景:2026-06-10 深度复审发现 1d72d7fe(R13 收口提交)把 _registry.json 的 R30 与
_registry_index.json 的 R08 各误翻一处(planned→fixed),两错互相抵消使两文件的
fixed/planned 总数完全一致——只对总数的核查永远抓不住这类错位,必须逐 ID 对账。

用法: python3 _check_status_consistency.py
退出码: 0 = registry↔index 逐 ID 完全一致; 1 = 存在错位(打印明细)。
_layer1_input.json 的 dossier.st 仅作警告输出,不影响退出码——该文件"冻结快照 vs
活台账"口径未裁定,更早批次的 fixed 债在其中仍标 planned 属已知历史状态(见
R66/G09 系列选择性维护记录);G09 起触碰过的债(R13/R15/R18/R19/R66)应保持同步。
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    reg = json.loads((HERE / "_registry.json").read_text(encoding="utf-8"))
    idx = json.loads((HERE / "_registry_index.json").read_text(encoding="utf-8"))

    mismatches = []
    for debt_id in sorted(set(reg) | set(idx)):
        reg_status = reg.get(debt_id, {}).get("status_2026_06_05")
        idx_status = idx.get(debt_id, {}).get("status")
        if reg_status != idx_status:
            mismatches.append((debt_id, reg_status, idx_status))

    print(f"registry 计数: {dict(Counter(v.get('status_2026_06_05') for v in reg.values()))}")
    print(f"index    计数: {dict(Counter(v.get('status') for v in idx.values()))}")
    if mismatches:
        print(f"\n❌ registry↔index 逐 ID 错位 {len(mismatches)} 处:")
        for debt_id, reg_status, idx_status in mismatches:
            print(f"  {debt_id}: registry={reg_status} index={idx_status}")
    else:
        print("✅ registry↔index 逐 ID 全一致")

    layer1 = json.loads((HERE / "_layer1_input.json").read_text(encoding="utf-8"))
    stale = [
        (entry["i"], entry.get("st"), reg.get(entry.get("i"), {}).get("status_2026_06_05"))
        for entry in layer1.get("dossier", [])
        if entry.get("st") != reg.get(entry.get("i"), {}).get("status_2026_06_05")
    ]
    if stale:
        print(f"\n⚠ layer1 dossier.st 与 registry 不一致 {len(stale)} 处(仅提示,口径见文件头 docstring):")
        for debt_id, layer1_status, reg_status in stale:
            print(f"  {debt_id}: layer1={layer1_status} registry={reg_status}")

    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
