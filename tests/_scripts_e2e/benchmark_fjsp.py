#!/usr/bin/env python3
"""Folded FJSP benchmark command-line entrypoint."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


def _find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for probe in [here.parent] + list(here.parents):
        if (probe / "app.py").exists() and (probe / "schema.sql").exists():
            return probe
    raise RuntimeError("未找到项目根目录（要求存在 app.py 与 schema.sql）")


REPO_ROOT = _find_repo_root()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests._support.benchmark_parallel import (  # noqa: E402
    DEFAULT_BENCHMARK_WORKERS,
    parallel_map_ordered,
    positive_worker_count,
)
from tests._support.optimizer_fjsp_dataset import (  # noqa: E402
    DATASET_SOURCES,
    FjspInstance,
    assign_machines,
    choose_machine_for_op,
    load_instance_text,
    parse_fjsp,
)
from tests._support.optimizer_fjsp_report import write_report_md  # noqa: E402
from tests._support.optimizer_fjsp_runner import run_one_case  # noqa: E402


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run folded FJSP benchmark cases through APS.")
    parser.add_argument("--instances", default="mk01,mk04,mk06,mk08,mk10", help="comma separated instance keys")
    parser.add_argument("--allow-download", action="store_true", help="try downloading raw .fjs from GitHub")
    parser.add_argument("--calendar-days", type=int, default=120, help="how many days to seed 24h calendar")
    parser.add_argument("--time-budget", type=int, default=20, help="time_budget_seconds for improve mode")
    parser.add_argument("--workers", type=int, default=DEFAULT_BENCHMARK_WORKERS, help="parallel worker processes")
    parser.add_argument("--full-matrix", action="store_true", help="run all fold strategies for all algo modes")
    parser.add_argument("--allow-invalid", action="store_true", help="write the report even if a run has failed_ops or no makespan")
    parser.add_argument(
        "--report-path",
        default="evidence/QualityGate/long_gate/optimizer_benchmark/fjsp_benchmark_report.md",
        help="Markdown report path. Default is ignored by git; use evidence/Benchmark explicitly for tracked evidence.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    selected = _selected_instances(args.instances)
    runs = _run_matrix(selected, args)
    report_path = write_report_md(REPO_ROOT, runs, args.report_path)
    print(report_path)
    print(f"runs={len(runs)} valid={_valid_count(runs)}")
    if _valid_count(runs) != len(runs) and not args.allow_invalid:
        _emit_invalid_runs(runs)
        return 1
    return 0


def _selected_instances(raw_instances: str) -> List[str]:
    selected = [item.strip().lower() for item in str(raw_instances or "").split(",") if item.strip()]
    unknown = [item for item in selected if item not in DATASET_SOURCES]
    if unknown:
        raise SystemExit(f"unknown instance key: {unknown[0]!r}")
    return selected


def _run_matrix(selected: Sequence[str], args: argparse.Namespace) -> List[Dict[str, Any]]:
    start_dt = datetime(2026, 1, 1, 0, 0, 0)
    due_date = "2099-12-31"
    tasks: List[Dict[str, Any]] = []
    for instance_key in selected:
        tasks.extend(_run_instance_tasks(instance_key, args, start_dt=start_dt, due_date=due_date))
    return parallel_map_ordered(_run_case_task, tasks, workers=positive_worker_count(args.workers))


def _run_instance_tasks(
    instance_key: str,
    args: argparse.Namespace,
    *,
    start_dt: datetime,
    due_date: str,
) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    for fold_strategy in ("A_shortest", "B_balanced"):
        tasks.append(_case_task(instance_key, fold_strategy, "greedy", args, start_dt=start_dt, due_date=due_date))
        if args.full_matrix:
            tasks.append(_case_task(instance_key, fold_strategy, "improve", args, start_dt=start_dt, due_date=due_date))
    if not args.full_matrix:
        tasks.append(_case_task(instance_key, "B_balanced", "improve", args, start_dt=start_dt, due_date=due_date))
    return tasks


def _case_task(
    instance_key: str,
    fold_strategy: str,
    algo_mode: str,
    args: argparse.Namespace,
    *,
    start_dt: datetime,
    due_date: str,
) -> Dict[str, Any]:
    return {
        "instance_key": instance_key,
        "fold_strategy": fold_strategy,
        "algo_mode": algo_mode,
        "time_budget_seconds": int(args.time_budget),
        "allow_download": bool(args.allow_download),
        "calendar_days": int(args.calendar_days),
        "start_dt": start_dt,
        "due_date": due_date,
    }


def _run_case_task(task: Dict[str, Any]) -> Dict[str, Any]:
    return run_one_case(
        repo_root=REPO_ROOT,
        instance_key=str(task["instance_key"]),
        fold_strategy=str(task["fold_strategy"]),
        algo_mode=str(task["algo_mode"]),
        time_budget_seconds=int(task["time_budget_seconds"]),
        allow_download=bool(task["allow_download"]),
        calendar_days=int(task["calendar_days"]),
        start_dt=task["start_dt"],
        due_date=str(task["due_date"]),
    )


def _valid_count(runs: Sequence[Dict[str, Any]]) -> int:
    return sum(1 for run in runs if run.get("valid"))


def _emit_invalid_runs(runs: Sequence[Dict[str, Any]]) -> None:
    for run in [item for item in runs if not item.get("valid")]:
        print(
            "invalid run: "
            + f"instance={run.get('instance')} algo={run.get('algo_mode')} fold={run.get('fold_strategy')} "
            + f"failed_ops={run.get('failed_ops')} makespan_hours={run.get('makespan_hours')}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    raise SystemExit(main())
