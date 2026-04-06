from __future__ import annotations

import pstats
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = Path(__file__).resolve().parent / "20260316_perf_profile_artifacts"
REPORT_PATH = Path(__file__).resolve().parent / "20260316_perf_profile_report.md"

TARGET_FUNCTIONS: List[Tuple[str, str, str]] = [
    ("dispatch_sgs", "core/algorithms/greedy/dispatch/sgs.py", "dispatch_sgs"),
    ("calendar_add_working_hours", "core/services/scheduler/calendar_engine.py", "add_working_hours"),
    ("calendar_adjust_to_working_time", "core/services/scheduler/calendar_engine.py", "adjust_to_working_time"),
    ("auto_assign_internal_resources", "core/algorithms/greedy/auto_assign.py", "auto_assign_internal_resources"),
    ("build_dispatch_key", "core/algorithms/dispatch_rules.py", "build_dispatch_key"),
]

SCENARIOS = [
    {
        "id": "smoke_phase7",
        "title": "smoke_phase7",
        "command": ["tests/smoke_phase7.py"],
    },
    {
        "id": "smoke_phase10_sgs_auto_assign",
        "title": "smoke_phase10_sgs_auto_assign",
        "command": ["tests/smoke_phase10_sgs_auto_assign.py"],
    },
    {
        "id": "synthetic_improve",
        "title": "run_synthetic_case improve",
        "command": [
            "tests/run_synthetic_case.py",
            "--mode",
            "improve",
            "--objective",
            "min_weighted_tardiness",
            "--time-budget",
            "10",
            "--parts",
            "16",
            "--batches-min",
            "2",
            "--batches-max",
            "4",
            "--ops-per-part",
            "6",
            "--calendar-days",
            "60",
        ],
    },
]


def _norm(path: str) -> str:
    return path.replace("\\", "/")


def _aggregate_target_stats(stats: pstats.Stats) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    for label, suffix, func_name in TARGET_FUNCTIONS:
        calls = 0.0
        self_s = 0.0
        cum_s = 0.0
        for (filename, _line, func), (_cc, nc, tt, ct, _callers) in stats.stats.items():
            if not _norm(filename).endswith(suffix):
                continue
            if func != func_name:
                continue
            calls += float(nc)
            self_s += float(tt)
            cum_s += float(ct)
        out[label] = {
            "calls": calls,
            "self_s": round(self_s, 6),
            "cum_s": round(cum_s, 6),
        }
    return out


def _top_functions(stats: pstats.Stats, *, limit: int = 12) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for (filename, line_no, func), (_cc, nc, tt, ct, _callers) in stats.stats.items():
        path = _norm(filename)
        if "/aps test/" not in path.lower():
            continue
        rows.append(
            {
                "func": f"{Path(path).name}:{func}:{line_no}",
                "calls": int(nc),
                "self_s": float(tt),
                "cum_s": float(ct),
            }
        )
    rows.sort(key=lambda x: float(x["cum_s"]), reverse=True)
    return rows[:limit]


def _run_profile(title: str, command_parts: List[str], prof_path: Path) -> Dict[str, object]:
    full_cmd = [sys.executable, "-m", "cProfile", "-o", str(prof_path)] + list(command_parts)
    t0 = time.perf_counter()
    proc = subprocess.run(
        full_cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    elapsed_s = time.perf_counter() - t0

    stats = pstats.Stats(str(prof_path))
    target_stats = _aggregate_target_stats(stats)
    top_rows = _top_functions(stats)
    return {
        "title": title,
        "command": " ".join(full_cmd),
        "exit_code": int(proc.returncode),
        "elapsed_s": round(float(elapsed_s), 3),
        "stdout_tail": "\n".join((proc.stdout or "").splitlines()[-20:]),
        "stderr_tail": "\n".join((proc.stderr or "").splitlines()[-20:]),
        "total_tt_s": round(float(stats.total_tt), 6),
        "target_stats": target_stats,
        "top_rows": top_rows,
    }


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results: List[Dict[str, object]] = []
    for scenario in SCENARIOS:
        prof_path = OUTPUT_DIR / f"{scenario['id']}.prof"
        results.append(_run_profile(str(scenario["title"]), list(scenario["command"]), prof_path))

    lines: List[str] = []
    lines.append("# 排产性能画像报告")
    lines.append("")
    lines.append(f"- 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- 项目根目录：`{REPO_ROOT.as_posix()}`")
    lines.append(f"- Profile 目录：`{OUTPUT_DIR.as_posix()}`")
    lines.append("")

    for item in results:
        lines.append(f"## {item['title']}")
        lines.append("")
        lines.append(f"- 命令：`{item['command']}`")
        lines.append(f"- 退出码：{item['exit_code']}")
        lines.append(f"- 墙钟耗时：{item['elapsed_s']}s")
        lines.append(f"- cProfile 总 self time：{item['total_tt_s']}s")
        lines.append("")
        lines.append("| 指标 | calls | self_s | cum_s |")
        lines.append("|------|-------|--------|-------|")
        for label, payload in (item.get("target_stats") or {}).items():
            lines.append(
                f"| {label} | {int(payload.get('calls', 0))} | {payload.get('self_s', 0.0):.6f} | {payload.get('cum_s', 0.0):.6f} |"
            )
        lines.append("")
        lines.append("Top 热点（按 cum_s）:")
        for row in item.get("top_rows") or []:
            lines.append(
                f"- `{row['func']}`：calls={row['calls']} self={float(row['self_s']):.6f}s cum={float(row['cum_s']):.6f}s"
            )
        stderr_tail = str(item.get("stderr_tail") or "").strip()
        if stderr_tail:
            lines.append("")
            lines.append("stderr tail:")
            lines.append("```text")
            lines.append(stderr_tail)
            lines.append("```")
        stdout_tail = str(item.get("stdout_tail") or "").strip()
        if stdout_tail:
            lines.append("")
            lines.append("stdout tail:")
            lines.append("```text")
            lines.append(stdout_tail)
            lines.append("```")
        lines.append("")

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT_PATH.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
