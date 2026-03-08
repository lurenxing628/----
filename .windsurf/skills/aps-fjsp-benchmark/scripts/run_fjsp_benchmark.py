from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Sequence


def _find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for p in [here.parent] + list(here.parents):
        if (p / "app.py").exists() and (p / "schema.sql").exists():
            return p
    raise RuntimeError("未找到项目根目录（要求存在 app.py 与 schema.sql）")


def _build_args(mode: str, *, time_budget: int, allow_download: bool) -> List[str]:
    # Delegate to tests/benchmark_fjsp.py, only choose a stable default matrix here.
    m = (mode or "").strip().lower() or "full"
    base = ["--time-budget", str(int(time_budget))]
    if allow_download:
        base.append("--allow-download")

    if m == "fast":
        # Smoke: only mk01 (script default will run 3 runs for mk01)
        return ["--instances", "mk01"] + base
    if m == "standard":
        # Default instances, minimal matrix (15 runs)
        return base
    if m == "full":
        # Full matrix (20 runs): greedy/improve x fold(A/B) for each instance
        return ["--full-matrix"] + base
    raise ValueError(f"未知 mode：{mode!r}（允许：fast/standard/full）")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="full", choices=["fast", "standard", "full"], help="benchmark mode")
    ap.add_argument("--time-budget", type=int, default=20, help="time_budget_seconds for improve mode")
    ap.add_argument("--allow-download", action="store_true", help="try downloading raw .fjs from GitHub")
    args = ap.parse_args(list(argv) if argv is not None else None)

    repo_root = _find_repo_root()
    script = repo_root / "tests" / "benchmark_fjsp.py"
    if not script.exists():
        raise RuntimeError("缺少 tests/benchmark_fjsp.py（请先生成基准脚本）")

    cmd = [sys.executable, str(script)] + _build_args(args.mode, time_budget=int(args.time_budget), allow_download=bool(args.allow_download))
    print("Running:", " ".join(cmd), flush=True)
    r = subprocess.run(cmd, cwd=str(repo_root))
    return int(r.returncode)


if __name__ == "__main__":
    raise SystemExit(main())

