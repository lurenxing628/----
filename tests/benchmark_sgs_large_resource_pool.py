from __future__ import annotations

import os
import sys
import time
from contextlib import ExitStack
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Dict, List, Tuple
from unittest import mock


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


class _Calendar:
    def adjust_to_working_time(self, dt: datetime, priority=None, operator_id=None) -> datetime:
        return dt

    def add_working_hours(self, dt: datetime, hours: float, priority=None, operator_id=None) -> datetime:
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt: datetime, operator_id=None) -> float:
        return 1.0

    def add_calendar_days(self, dt: datetime, days: float, machine_id=None, operator_id=None) -> datetime:
        return dt + timedelta(days=float(days or 0.0))


def _write_report(path: str, lines: List[str]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def _resource_pool(machine_count: int, operators_per_machine: int) -> Tuple[Dict[str, object], int]:
    machines = [f"M{idx:03d}" for idx in range(1, machine_count + 1)]
    operators_by_machine = {}
    machines_by_operator = {}
    pair_rank = {}
    pair_count = 0
    for machine_index, machine_id in enumerate(machines, start=1):
        operator_ids = []
        for operator_index in range(1, operators_per_machine + 1):
            operator_id = f"O{machine_index:03d}_{operator_index:02d}"
            operator_ids.append(operator_id)
            machines_by_operator.setdefault(operator_id, []).append(machine_id)
            pair_rank[(operator_id, machine_id)] = operator_index
            pair_count += 1
        operators_by_machine[machine_id] = operator_ids
    return {
        "machines_by_op_type": {"OT1": machines},
        "operators_by_machine": operators_by_machine,
        "machines_by_operator": machines_by_operator,
        "pair_rank": pair_rank,
    }, pair_count


def _run_case(*, name: str, operations, batches, start_dt: datetime, resource_pool, seed_results=None):
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    import core.algorithms.greedy.auto_assign as auto_assign_module
    import core.algorithms.greedy.dispatch.sgs as sgs_module
    import core.algorithms.greedy.internal_slot as internal_slot_module
    import core.algorithms.greedy.scheduler as scheduler_module
    from core.algorithms import GreedyScheduler

    scheduler = GreedyScheduler(calendar_service=_Calendar(), config_service={"auto_assign_enabled": "yes"})
    estimate_calls = 0
    original_estimator = internal_slot_module.estimate_internal_slot

    def _wrapped_estimator(*args, **kwargs):
        nonlocal estimate_calls
        estimate_calls += 1
        return original_estimator(*args, **kwargs)

    t0 = time.perf_counter()
    with ExitStack() as stack:
        stack.enter_context(mock.patch.object(internal_slot_module, "estimate_internal_slot", side_effect=_wrapped_estimator))
        stack.enter_context(mock.patch.object(auto_assign_module, "estimate_internal_slot", side_effect=_wrapped_estimator))
        stack.enter_context(mock.patch.object(sgs_module, "estimate_internal_slot", side_effect=_wrapped_estimator))
        stack.enter_context(mock.patch.object(scheduler_module, "estimate_internal_slot", side_effect=_wrapped_estimator))
        results, summary, _strategy, _params = scheduler.schedule(
            operations=operations,
            batches=batches,
            start_dt=start_dt,
            dispatch_mode="sgs",
            dispatch_rule="slack",
            resource_pool=resource_pool,
            seed_results=seed_results or [],
        )
    elapsed = time.perf_counter() - t0
    return {
        "name": name,
        "elapsed_seconds": elapsed,
        "estimate_calls": estimate_calls,
        "scheduled_ops": int(summary.scheduled_ops),
        "failed_ops": int(summary.failed_ops),
        "seed_fragments": int(len(seed_results or [])),
        "result_count": int(len(results)),
    }


def main() -> None:
    repo_root = find_repo_root()
    start_dt = datetime(2026, 1, 1, 8, 0, 0)

    pool_large, pair_count = _resource_pool(machine_count=30, operators_per_machine=10)
    large_pool_batches = {
        "B_POOL": SimpleNamespace(
            batch_id="B_POOL",
            priority="normal",
            due_date="2026-01-10",
            ready_status="yes",
            ready_date=None,
            created_at=None,
            quantity=1,
        )
    }
    large_pool_ops = [
        SimpleNamespace(
            id=1,
            op_code="OP_POOL",
            batch_id="B_POOL",
            seq=1,
            source="internal",
            machine_id="",
            operator_id="",
            setup_hours=1.0,
            unit_hours=0.0,
            op_type_id="OT1",
            op_type_name="车削",
        )
    ]

    fragmented_batches = {
        "B_SEED": SimpleNamespace(
            batch_id="B_SEED",
            priority="normal",
            due_date="2026-01-10",
            ready_status="yes",
            ready_date=None,
            created_at=None,
            quantity=1,
        )
    }
    fragmented_ops = [
        SimpleNamespace(
            id=2,
            op_code="OP_SEED",
            batch_id="B_SEED",
            seq=1,
            source="internal",
            machine_id="M001",
            operator_id="O001_01",
            setup_hours=0.25,
            unit_hours=0.0,
            op_type_id="OT1",
            op_type_name="车削",
        )
    ]
    fragmented_seed_results = []
    current = start_dt
    for idx in range(1200):
        end_time = current + timedelta(minutes=15)
        fragmented_seed_results.append(
            SimpleNamespace(
                op_id=10000 + idx,
                op_code=f"SEED_{idx}",
                batch_id=f"SEED_{idx}",
                seq=1,
                machine_id="M001",
                operator_id="O001_01",
                start_time=current,
                end_time=end_time,
                source="internal",
                op_type_name="车削",
            )
        )
        current = end_time

    cases = [
        {
            "name": "候选对大于 200 的大资源池",
            "operations": large_pool_ops,
            "batches": large_pool_batches,
            "resource_pool": pool_large,
            "seed_results": [],
            "candidate_pairs": pair_count,
        },
        {
            "name": "1000+ seed 碎片时间线",
            "operations": fragmented_ops,
            "batches": fragmented_batches,
            "resource_pool": pool_large,
            "seed_results": fragmented_seed_results,
            "candidate_pairs": 1,
        },
    ]

    lines = [
        "# SGS 大资源池基准报告",
        "",
        f"- 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 项目根目录：`{repo_root}`",
        "",
    ]

    for case in cases:
        outcome = _run_case(
            name=case["name"],
            operations=case["operations"],
            batches=case["batches"],
            start_dt=start_dt,
            resource_pool=case["resource_pool"],
            seed_results=case["seed_results"],
        )
        lines.extend(
            [
                f"## {case['name']}",
                "",
                f"- 候选对总数：{case['candidate_pairs']}",
                f"- seed 碎片段数：{outcome['seed_fragments']}",
                f"- 统一估算器调用次数：{outcome['estimate_calls']}",
                f"- scheduled_ops={outcome['scheduled_ops']} failed_ops={outcome['failed_ops']} result_count={outcome['result_count']}",
                f"- 总耗时：{round(outcome['elapsed_seconds'], 6)}s",
                "",
            ]
        )

    report_path = os.path.join(repo_root, "evidence", "Benchmark", "sgs_large_resource_pool_report.md")
    _write_report(report_path, lines)
    print(f"[benchmark_sgs_large_resource_pool] report: {report_path}")


if __name__ == "__main__":
    main()
