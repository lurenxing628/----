"""每次 push 抽几个浏览器车道文件真跑一遍，按轮转覆盖整条车道。

为什么要有这个：浏览器验收车道 2026-09-17 建起来之后，127 个文件被移出日常门禁和正式全量
门禁，交给 scripts/run_browser_test_lane.py 单独跑——但没有任何 CI 或定时任务引用那个脚本，
"每周至少跑一次"只写在文档里，结果一次都没跑过。test_frontend_ui_language_polish.py 那 17
条用例烂了三天没人发现就是这么来的。整条车道一次一个多小时，塞不进 push；抽样能把发现问题的
延迟从"没人跑就永远不发现"压到"最多 N 次 push"。

轮转而不是随机：随机会让某些文件长期抽不到，也没法复现。这里记住上次跑的最后一个文件，
下次从它后面接着取，列表增删时按文件名重新定位，取不到就从头开始。

游标写在 evidence/ 下（.gitignore:118 忽略整个目录）。**不能写进版本控制的文件**——
pre-push 阶段写一个被跟踪的文件会让工作区变脏，后面的门禁检查要求干净工作区，直接把 push 卡死。

用法：
  python -m tools.browser_lane_sample --list          # 只看这次会抽到谁
  python -m tools.browser_lane_sample                 # 抽并跑
  python -m tools.browser_lane_sample --count 5       # 改这次的抽样数
  APS_BROWSER_LANE_SAMPLE=0 …                         # 整个跳过（临时关掉）
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_browser_test_lane import lane_targets  # noqa: E402
from scripts.run_workbench_opt_in_browser import runtime_environment  # noqa: E402

CURSOR_PATH = ROOT / "evidence" / "browser-lane" / "sample-cursor.json"
DEFAULT_COUNT = 2
SKIP_ENV = "APS_BROWSER_LANE_SAMPLE"


def read_cursor() -> str:
    """上次跑过的最后一个文件。读不出来就当从没跑过，从头开始。"""
    try:
        payload = json.loads(CURSOR_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    return str(payload.get("last_file") or "")


def write_cursor(last_file: str, *, outcome: str) -> None:
    CURSOR_PATH.parent.mkdir(parents=True, exist_ok=True)
    CURSOR_PATH.write_text(
        json.dumps({"last_file": last_file, "outcome": outcome}, ensure_ascii=False, indent=2),
        encoding="utf-8")


def pick(targets: Sequence[str], count: int, last_file: str) -> List[str]:
    """从上次那个文件之后接着取 count 个，到尾了绕回开头。"""
    if not targets:
        return []
    start = targets.index(last_file) + 1 if last_file in targets else 0
    return [targets[(start + offset) % len(targets)] for offset in range(min(count, len(targets)))]


def run(selected: Sequence[str], env: dict) -> int:
    command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-m", "perf", *selected]
    return subprocess.run(command, cwd=str(ROOT), env=env).returncode


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", type=int, default=int(os.environ.get("APS_BROWSER_LANE_SAMPLE_COUNT") or DEFAULT_COUNT),
                        help=f"这次抽几个文件（默认 {DEFAULT_COUNT}）")
    parser.add_argument("--list", action="store_true", help="只打印这次会抽到谁，不跑")
    args = parser.parse_args(argv)

    if os.environ.get(SKIP_ENV) == "0":
        print(f"[browser-lane-sample] 已按 {SKIP_ENV}=0 跳过。")
        return 0
    if args.count <= 0:
        raise SystemExit("--count 要是正整数。")

    targets = lane_targets()
    selected = pick(targets, args.count, read_cursor())
    if not selected:
        raise SystemExit("浏览器车道一个文件都没有，先检查 tools/browser_lane_files.py。")
    print(f"[browser-lane-sample] 车道共 {len(targets)} 个文件，这次抽 {len(selected)} 个：")
    for path in selected:
        print(f"  {path}")
    if args.list:
        return 0

    try:
        env = runtime_environment()
    except SystemExit as exc:
        # 本机没准备 Chromium 109 时不拦 push：开发机不一定装了运行时，拦下来只会逼人绕过钩子。
        # 但要喊得够响，否则"抽样一直在跳过"和"抽样一直在通过"从输出上分不出来。
        print(f"[browser-lane-sample] 跳过：浏览器运行时没准备好。\n{exc}", file=sys.stderr)
        return 0

    code = run(selected, env)
    write_cursor(selected[-1], outcome="passed" if code == 0 else "failed")
    if code != 0:
        print(f"[browser-lane-sample] 抽到的 {len(selected)} 个文件里有红的，见上面的 pytest 输出。\n"
              f"  整条车道：.venv/bin/python scripts/run_browser_test_lane.py\n"
              f"  只跑这几个：.venv/bin/python -m pytest -m perf {' '.join(selected)}", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
