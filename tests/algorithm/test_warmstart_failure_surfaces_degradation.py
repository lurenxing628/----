"""回归测试：OR-Tools 预热（_run_ortools_warmstart）抛异常时不崩溃而是降级并对外可见。守护预热失败返回 best=None、累加 fallback_counts.ortools_warmstart_failed_count=1 并写 warning；随后 build_result_summary 把该计数汇成 degradation_counters.ortools_warmstart_failed=1，且 result_status 仍为 success、warnings 含中文"OR-Tools 预热失败"。"""

from __future__ import annotations

import time
from datetime import datetime
from types import SimpleNamespace
from unittest import mock


class _SummarySvc:
    logger = None

    @staticmethod
    def _normalize_text(value):
        return "" if value is None else str(value).strip()

    @staticmethod
    def _format_dt(value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")


class _Logger:
    def __init__(self) -> None:
        self.warnings = []

    def warning(self, message, *args, **kwargs) -> None:
        self.warnings.append(str(message))


class _Scheduler:
    def schedule(self, *args, **kwargs):
        raise AssertionError("本回归不应真正调用 schedule()")


def test_warmstart_failure_surfaces_degradation() -> None:

    from core.algorithms import ScheduleResult, SortStrategy
    from core.algorithms.evaluation import compute_metrics
    from core.services.scheduler.schedule_optimizer_steps import _run_ortools_warmstart
    from core.services.scheduler.summary.schedule_summary import build_result_summary

    logger = _Logger()
    optimizer_algo_stats = {}
    with mock.patch(
        "core.algorithms.ortools_bottleneck.try_solve_bottleneck_batch_order",
        side_effect=RuntimeError("warmstart boom"),
    ):
        best = _run_ortools_warmstart(
            algo_mode="improve",
            cfg={"ortools_enabled": "yes", "ortools_time_limit_seconds": 5},
            strategy_enum=SortStrategy.PRIORITY_FIRST,
            objective_name="min_overdue",
            deadline=time.time() + 30,
            scheduler=_Scheduler(),
            algo_ops_to_schedule=[],
            batches={},
            start_dt=datetime(2026, 4, 2, 8, 0, 0),
            end_date=None,
            downtime_map={},
            seed_sr_list=[],
            dispatch_mode_cfg="machine_first",
            dispatch_rule_cfg="spt",
            resource_pool=None,
            attempts=[],
            improvement_trace=[],
            best=None,
            t_begin=time.time(),
            logger=logger,
            optimizer_algo_stats=optimizer_algo_stats,
            strict_mode=False,
        )

    assert best is None, best
    fallback_counts = dict(optimizer_algo_stats.get("fallback_counts") or {})
    assert int(fallback_counts.get("ortools_warmstart_failed_count") or 0) == 1, fallback_counts
    assert logger.warnings, "预热失败应写 warning"

    start_dt = datetime(2026, 4, 2, 8, 0, 0)
    result = ScheduleResult(
        op_id=1,
        op_code="OP-1",
        batch_id="B1",
        seq=10,
        source="internal",
        machine_id="MC100",
        operator_id="OP100",
        op_type_name="数车",
        start_time=start_dt,
        end_time=datetime(2026, 4, 2, 10, 0, 0),
    )
    batch = SimpleNamespace(batch_id="B1", due_date="2099-12-31", priority="normal", quantity=1)
    metrics = compute_metrics([result], {"B1": batch})
    summary = SimpleNamespace(success=True, total_ops=1, scheduled_ops=1, failed_ops=0, warnings=[], errors=[])

    _overdue_items, result_status, result_summary_obj, _result_summary_json, _time_cost_ms = build_result_summary(
        _SummarySvc(),
        cfg={"freeze_window_enabled": "no", "auto_assign_enabled": "no"},
        version=9,
        normalized_batch_ids=["B1"],
        start_dt=start_dt,
        end_date=None,
        batches={"B1": batch},
        operations=[],
        results=[result],
        summary=summary,
        used_strategy=SimpleNamespace(value="priority_first"),
        used_params={},
        algo_mode="improve",
        objective_name="min_overdue",
        time_budget_seconds=30,
        best_score=(0.0, 0.0, 2.0, 0.0, 0.0),
        best_metrics=metrics,
        best_order=["B1"],
        attempts=[],
        improvement_trace=[],
        frozen_op_ids=set(),
        algo_stats=optimizer_algo_stats,
        simulate=False,
        t0=time.time() - 0.02,
    )

    assert result_status == "success", result_status
    degradation_counters = dict(result_summary_obj.get("degradation_counters") or {})
    assert int(degradation_counters.get("ortools_warmstart_failed") or 0) == 1, degradation_counters
    warnings = list(result_summary_obj.get("warnings") or [])
    assert any("OR-Tools 预热失败" in w for w in warnings), warnings


