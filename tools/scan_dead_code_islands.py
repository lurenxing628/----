#!/usr/bin/env python3
"""死代码孤岛防回潮扫描器(warn-only / 只告警不拦)。

复用静态调用图工具 .codestable/checkup/scripts/callgraph_extract.py:把它的产物输出
经 CHECKUP_CALLGRAPH 重定向到 OS 临时目录(绝不弄脏已提交的 latest/callgraph/、
不破坏净树证明),读临时目录里算好的 islands.json(口径=in_degree==0 且
out_degree==0 的全孤立函数),与已提交基线对比:

  新增孤岛(当前 − 基线)→ 打印 ⚠️ 警告:这些函数失去了所有调用方,疑似死代码回潮
  消失孤岛(基线 − 当前)→ info:已清理 / 已接线,可 --refresh 收敛基线

设计为 warn-only:无论检出多少新孤岛、甚至扫描本身失败,都 return 0,绝不阻断
调用方(pre-push 快检 / 完整门禁)。--refresh 把基线受控重写为当前孤岛集。

Py3.8 兼容、纯标准库 + 子进程复用 callgraph_extract(不改后者,后者已贴近 500 行门禁)。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from typing import List, Optional, Sequence, Set

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CALLGRAPH_EXTRACT = os.path.join(REPO_ROOT, ".codestable", "checkup", "scripts", "callgraph_extract.py")
BASELINE_PATH = os.path.join(REPO_ROOT, ".codestable", "checkup", "dead_code_islands_baseline.json")
BASELINE_REL = os.path.relpath(BASELINE_PATH, REPO_ROOT)


def _compute_current_islands() -> List[str]:
    """跑 callgraph_extract 到临时目录,返回当前静态孤岛全限定名列表。"""
    tmp_dir = tempfile.mkdtemp(prefix="dead_code_islands_")
    try:
        env = dict(os.environ)
        env["CHECKUP_CALLGRAPH"] = tmp_dir
        proc = subprocess.run(
            [sys.executable, CALLGRAPH_EXTRACT],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        islands_path = os.path.join(tmp_dir, "islands.json")
        if proc.returncode != 0 or not os.path.isfile(islands_path):
            tail = (proc.stderr or proc.stdout or "").strip()[-600:]
            raise RuntimeError("callgraph_extract 未产出 islands.json：" + tail)
        with open(islands_path, encoding="utf-8") as handle:
            data = json.load(handle)
        return [str(item) for item in data]
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _load_baseline() -> Optional[Set[str]]:
    """读基线孤岛集;无基线返回 None(首次需 --refresh 建立)。"""
    if not os.path.isfile(BASELINE_PATH):
        return None
    with open(BASELINE_PATH, encoding="utf-8") as handle:
        data = json.load(handle)
    return {str(item) for item in (data.get("islands") or [])}


def _write_baseline(islands: Sequence[str]) -> None:
    payload = {
        "note": (
            "静态死代码孤岛基线（in_degree==0 且 out_degree==0 的全孤立函数）。"
            "warn-only 防回潮用：新增孤岛=疑似死代码回潮。受控更新：python tools/scan_dead_code_islands.py --refresh。"
        ),
        "count": len(islands),
        "islands": sorted(islands),
    }
    os.makedirs(os.path.dirname(BASELINE_PATH), exist_ok=True)
    with open(BASELINE_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=1)
        handle.write("\n")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="死代码孤岛防回潮扫描器（warn-only）")
    parser.add_argument("--refresh", action="store_true", help="把基线重写为当前孤岛集（受控接受新基线）")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        current = _compute_current_islands()
    except Exception as exc:  # warn-only：连扫描失败都不阻断调用方
        print(f"[dead-code-islands] 跳过（扫描失败，不拦）：{exc}", flush=True)
        return 0

    if args.refresh:
        _write_baseline(current)
        print(f"[dead-code-islands] 基线已刷新：{len(current)} 个孤岛 -> {BASELINE_REL}", flush=True)
        return 0

    baseline = _load_baseline()
    if baseline is None:
        print(
            "[dead-code-islands] 未建立基线（先跑 `python tools/scan_dead_code_islands.py --refresh`）；本次跳过对比。",
            flush=True,
        )
        return 0

    current_set = set(current)
    new_islands = sorted(current_set - baseline)
    gone_islands = sorted(baseline - current_set)

    if new_islands:
        print(
            f"⚠️ [dead-code-islands] 检出 {len(new_islands)} 个新死代码孤岛（失去全部调用方，疑似回潮）：",
            flush=True,
        )
        for qual in new_islands:
            print(f"    + {qual}", flush=True)
        print(
            "  处理：确认是真死代码就删；若是新入口/有意保留，"
            "跑 `python tools/scan_dead_code_islands.py --refresh` 接受进基线。",
            flush=True,
        )
    else:
        print(f"[dead-code-islands] 无新增孤岛（基线 {len(baseline)} 个）。", flush=True)

    if gone_islands:
        print(
            f"[dead-code-islands] {len(gone_islands)} 个基线孤岛已消失（已清理/已接线）；可 --refresh 收敛基线。",
            flush=True,
        )

    return 0  # warn-only：永远不拦


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
