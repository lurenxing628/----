"""Markdown report writer for folded FJSP benchmark runs."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Sequence

from tests._support.optimizer_fjsp_dataset import DATASET_SOURCES


def write_report_md(repo_root: Path, runs: Sequence[Dict[str, Any]], report_path: str) -> str:
    path = _resolve_report_path(repo_root, report_path)
    lines = _report_header()
    lines.extend(_summary_lines(_group_by_instance(runs)))
    lines.extend(_conclusion_lines())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def _resolve_report_path(repo_root: Path, report_path: str) -> Path:
    path = Path(report_path)
    if not path.is_absolute():
        path = repo_root / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _report_header() -> List[str]:
    return [
        "# FJSP 基准评测报告（APS）",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 数据集：Brandimarte (1993) FJSP，来源 `Lei-Kun/FJSP-benchmarks`",
        "- 口径：统一 `due_date=2099-12-31` + 注入 24h WorkCalendar，使优化器主要按 makespan 比较。",
        "- 重要局限：FJSP 的“多机可选且工时随机器变化”在 APS 模型里会折叠为单机绑定，因此 gap 只能做参考对照。",
        "",
    ]


def _group_by_instance(runs: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for run in runs:
        grouped.setdefault(str(run.get("instance") or ""), []).append(run)
    return grouped


def _summary_lines(grouped: Dict[str, List[Dict[str, Any]]]) -> List[str]:
    lines = ["## 汇总（按实例）", ""]
    for instance_key in sorted(key for key in grouped if key):
        lines.extend(_instance_lines(instance_key, grouped.get(instance_key) or []))
    return lines


def _instance_lines(instance_key: str, runs: List[Dict[str, Any]]) -> List[str]:
    if not runs:
        return []
    meta = DATASET_SOURCES.get(instance_key) or {}
    lines = [
        f"- **{instance_key}**（{runs[0].get('jobs')} jobs x {runs[0].get('machines')} machines；"
        f"{meta.get('ref_type')}={meta.get('ref_makespan')}）"
    ]
    lines.append(_best_line(runs))
    lines.extend(_run_line(run) for run in sorted(runs, key=lambda item: (str(item.get("algo_mode")), str(item.get("fold_strategy")))))
    lines.append("")
    return lines


def _best_line(runs: List[Dict[str, Any]]) -> str:
    valid_runs = [run for run in runs if run.get("valid")]
    if not valid_runs:
        return "  - 最佳：NA（所有 run 都无有效排程或 failed_ops>0）"
    best = min(valid_runs, key=lambda run: float(run.get("makespan_hours") or 1e18))
    return (
        f"  - 最佳：{best.get('algo_mode')} + {best.get('fold_strategy')} "
        f"makespan={_fmt_float(best.get('makespan_hours'))}h "
        f"gap={_fmt_float(best.get('gap_percent'), 2)}% time={best.get('time_cost_ms')}ms"
    )


def _run_line(run: Dict[str, Any]) -> str:
    metrics = run.get("metrics") if isinstance(run.get("metrics"), dict) else {}
    return (
        "  - "
        + f"{run.get('algo_mode')} + {run.get('fold_strategy')}: "
        + f"makespan={_fmt_float(run.get('makespan_hours'))}h "
        + f"gap={_fmt_float(run.get('gap_percent'), 2)}% "
        + f"failed_ops={run.get('failed_ops')} time={run.get('time_cost_ms')}ms "
        + f"util_avg={_fmt_float(metrics.get('machine_util_avg'), 6)} "
        + f"load_cv={_fmt_float(metrics.get('machine_load_cv'), 6)}"
    )


def _conclusion_lines() -> List[str]:
    return [
        "## 结论（自动摘要）",
        "",
        "- 本报告仅提供“可重复运行的量化对照”；最终评价以你对业务目标（交期/换型/利用率）权衡为准。",
        "",
    ]


def _fmt_float(value: Any, nd: int = 4) -> str:
    try:
        number = float(value)
    except Exception:
        return "NA"
    return f"{number:.{nd}f}"
