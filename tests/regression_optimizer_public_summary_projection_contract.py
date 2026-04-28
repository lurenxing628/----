from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace

from core.algorithms.evaluation import ScheduleMetrics
from core.services.scheduler.run.optimizer_search_state import compact_attempts
from core.services.scheduler.schedule_summary import build_result_summary
from core.services.scheduler.schedule_summary_types import SummaryBuildContext
from core.services.scheduler.summary.optimizer_public_summary import project_public_algo_summary


class _SummarySvc:
    logger = None

    @staticmethod
    def _format_dt(value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _normalize_text(value):
        text = "" if value is None else str(value).strip()
        return text or None


def test_public_algo_summary_strips_attempt_internal_diagnostics_but_keeps_diagnostics_trace() -> None:
    start = datetime(2026, 4, 1, 8, 0, 0)
    metrics = ScheduleMetrics(
        overdue_count=0,
        total_tardiness_hours=0.0,
        makespan_hours=0.0,
        changeover_count=0,
        weighted_tardiness_hours=0.0,
    )
    ctx = SummaryBuildContext(
        cfg=SimpleNamespace(
            sort_strategy="priority_first",
            priority_weight=0.4,
            due_weight=0.5,
            dispatch_mode="sgs",
            dispatch_rule="cr",
            auto_assign_enabled="no",
            ortools_enabled="no",
            ortools_time_limit_seconds=5,
            algo_mode="improve",
            time_budget_seconds=5,
            objective="min_overdue",
            freeze_window_enabled="no",
            freeze_window_days=0,
        ),
        version=1,
        normalized_batch_ids=["B001"],
        start_dt=start,
        end_date=None,
        batches={},
        operations=[],
        results=[],
        summary=SimpleNamespace(success=True, total_ops=0, scheduled_ops=0, failed_ops=0, warnings=[], errors=[]),
        used_strategy=SimpleNamespace(value="priority_first"),
        used_params={"sort_strategy": "priority_first"},
        algo_mode="improve",
        objective_name="min_overdue",
        time_budget_seconds=5,
        best_score=(0.0,),
        best_metrics=metrics,
        best_order=["B001"],
        attempts=[
            {
                "tag": "start:priority_first|sgs:cr",
                "strategy": "priority_first",
                "dispatch_mode": "sgs",
                "dispatch_rule": "cr",
                "used_params": {"internal_weight": 1},
                "score": [0.0],
                "failed_ops": 0,
                "metrics": {"overdue_count": 0},
                "algo_stats": {"fallback_counts": {"hidden": 1}},
            }
        ],
        improvement_trace=[],
        frozen_op_ids=set(),
        algo_stats={"fallback_counts": {"visible": 2}, "param_fallbacks": {}},
        simulate=False,
        t0=0.0,
    )

    _overdue, _status, result_summary_obj, _json, _elapsed = build_result_summary(_SummarySvc(), ctx=ctx)

    algo = result_summary_obj.get("algo") or {}
    attempt = (algo.get("attempts") or [{}])[0]
    assert "algo_stats" not in attempt
    assert "used_params" not in attempt
    assert "tag" not in attempt
    assert attempt["dispatch_mode"] == "sgs"
    assert attempt["source_label"] == "多起点方案"

    diagnostics = result_summary_obj.get("diagnostics") or {}
    optimizer_diagnostics = diagnostics.get("optimizer") or {}
    diagnostic_attempt = (optimizer_diagnostics.get("attempts") or [{}])[0]
    assert diagnostic_attempt["tag"] == "start:priority_first|sgs:cr"
    assert diagnostic_attempt["used_params"] == {"internal_weight": 1}
    assert diagnostic_attempt["algo_stats"] == {"fallback_counts": {"hidden": 1}}


def test_public_summary_omits_empty_diagnostics_when_no_internal_attempt_fields() -> None:
    start = datetime(2026, 4, 1, 8, 0, 0)
    metrics = ScheduleMetrics(
        overdue_count=0,
        total_tardiness_hours=0.0,
        makespan_hours=0.0,
        changeover_count=0,
        weighted_tardiness_hours=0.0,
    )
    ctx = SummaryBuildContext(
        cfg=SimpleNamespace(
            sort_strategy="priority_first",
            priority_weight=0.4,
            due_weight=0.5,
            dispatch_mode="sgs",
            dispatch_rule="cr",
            auto_assign_enabled="no",
            ortools_enabled="no",
            ortools_time_limit_seconds=5,
            algo_mode="improve",
            time_budget_seconds=5,
            objective="min_overdue",
            freeze_window_enabled="no",
            freeze_window_days=0,
        ),
        version=1,
        normalized_batch_ids=["B001"],
        start_dt=start,
        end_date=None,
        batches={},
        operations=[],
        results=[],
        summary=SimpleNamespace(success=True, total_ops=0, scheduled_ops=0, failed_ops=0, warnings=[], errors=[]),
        used_strategy=SimpleNamespace(value="priority_first"),
        used_params={"sort_strategy": "priority_first"},
        algo_mode="improve",
        objective_name="min_overdue",
        time_budget_seconds=5,
        best_score=(0.0,),
        best_metrics=metrics,
        best_order=["B001"],
        attempts=[
            {
                "strategy": "priority_first",
                "dispatch_mode": "sgs",
                "dispatch_rule": "cr",
                "score": [0.0],
                "failed_ops": 0,
                "metrics": {"overdue_count": 0},
            }
        ],
        improvement_trace=[],
        frozen_op_ids=set(),
        algo_stats={"fallback_counts": {"visible": 2}, "param_fallbacks": {}},
        simulate=False,
        t0=0.0,
    )

    _overdue, _status, result_summary_obj, _json, _elapsed = build_result_summary(_SummarySvc(), ctx=ctx)

    assert "diagnostics" not in result_summary_obj


def test_candidate_rejected_attempt_is_diagnostic_only() -> None:
    public_algo, diagnostics = project_public_algo_summary(
        {
            "attempts": [
                {
                    "tag": "start:priority_first|batch_order:slack",
                    "strategy": "priority_first",
                    "dispatch_mode": "batch_order",
                    "dispatch_rule": "slack",
                    "score": [0.0],
                    "failed_ops": 0,
                    "metrics": {"overdue_count": 0},
                },
                {
                    "tag": "local:swap",
                    "strategy": "priority_first",
                    "dispatch_mode": "sgs",
                    "dispatch_rule": "slack",
                    "source": "candidate_rejected",
                    "origin": {"type": "ValidationError", "field": "resource", "message": "缺少资源"},
                },
            ]
        }
    )

    assert public_algo["attempts"] == [
        {
            "strategy": "priority_first",
            "dispatch_mode": "batch_order",
            "dispatch_rule": "slack",
            "score": [0.0],
            "failed_ops": 0,
            "metrics": {"overdue_count": 0},
            "source_label": "多起点方案",
        }
    ]
    diagnostic_attempt = [
        attempt
        for attempt in diagnostics["optimizer"]["attempts"]
        if attempt.get("source") == "candidate_rejected"
    ][0]
    assert diagnostic_attempt["tag"] == "local:swap"
    assert diagnostic_attempt["strategy"] == "priority_first"
    assert diagnostic_attempt["dispatch_mode"] == "sgs"
    assert diagnostic_attempt["dispatch_rule"] == "slack"
    assert diagnostic_attempt["source"] == "candidate_rejected"
    assert diagnostic_attempt["origin"]["field"] == "resource"


def test_rejected_diagnostic_survives_compaction_before_summary_projection() -> None:
    start = datetime(2026, 4, 1, 8, 0, 0)
    metrics = ScheduleMetrics(
        overdue_count=0,
        total_tardiness_hours=0.0,
        makespan_hours=0.0,
        changeover_count=0,
        weighted_tardiness_hours=0.0,
    )
    attempts = [
        {
            "tag": f"start:priority_first|batch_order:r{index}",
            "strategy": "priority_first",
            "dispatch_mode": "batch_order",
            "dispatch_rule": f"r{index}",
            "used_params": {"internal_weight": index},
            "score": [float(index)],
            "failed_ops": 0,
            "metrics": {"overdue_count": 0},
            "algo_stats": {"fallback_counts": {"hidden": index}},
        }
        for index in range(12)
    ]
    attempts.append(
        {
            "tag": "start:priority_first|sgs:slack",
            "strategy": "priority_first",
            "dispatch_mode": "sgs",
            "dispatch_rule": "slack",
            "source": "candidate_rejected",
            "origin": {
                "type": "ValidationError",
                "field": "resource",
                "message": "候选方案缺少可用资源",
            },
        }
    )
    ctx = SummaryBuildContext(
        cfg=SimpleNamespace(
            sort_strategy="priority_first",
            priority_weight=0.4,
            due_weight=0.5,
            dispatch_mode="batch_order",
            dispatch_rule="slack",
            auto_assign_enabled="no",
            ortools_enabled="no",
            ortools_time_limit_seconds=5,
            algo_mode="improve",
            time_budget_seconds=5,
            objective="min_overdue",
            freeze_window_enabled="no",
            freeze_window_days=0,
        ),
        version=1,
        normalized_batch_ids=["B001"],
        start_dt=start,
        end_date=None,
        batches={},
        operations=[],
        results=[],
        summary=SimpleNamespace(success=True, total_ops=0, scheduled_ops=0, failed_ops=0, warnings=[], errors=[]),
        used_strategy=SimpleNamespace(value="priority_first"),
        used_params={},
        algo_mode="improve",
        objective_name="min_overdue",
        time_budget_seconds=5,
        best_score=(0.0,),
        best_metrics=metrics,
        best_order=["B001"],
        attempts=compact_attempts(attempts, limit=12),
        improvement_trace=[],
        frozen_op_ids=set(),
        algo_stats={"fallback_counts": {}, "param_fallbacks": {}},
        simulate=False,
        t0=0.0,
    )

    _overdue, _status, result_summary_obj, _json, _elapsed = build_result_summary(_SummarySvc(), ctx=ctx)

    public_attempts = ((result_summary_obj.get("algo") or {}).get("attempts") or [])
    diagnostics = result_summary_obj.get("diagnostics") or {}
    diagnostic_attempts = (diagnostics.get("optimizer") or {}).get("attempts") or []
    rejected_attempts = [
        attempt
        for attempt in diagnostic_attempts
        if attempt.get("source") == "candidate_rejected"
    ]
    assert len(public_attempts) == 11
    assert all(attempt.get("source") != "candidate_rejected" for attempt in public_attempts)
    assert all("source" not in attempt for attempt in public_attempts)
    assert all("tag" not in attempt for attempt in public_attempts)
    assert all("used_params" not in attempt for attempt in public_attempts)
    assert all("algo_stats" not in attempt for attempt in public_attempts)
    assert all("origin" not in attempt for attempt in public_attempts)
    assert len(rejected_attempts) == 1
    assert rejected_attempts[0]["origin"] == {
        "type": "ValidationError",
        "field": "resource",
        "message": "候选方案缺少可用资源",
    }
    assert "score" not in rejected_attempts[0]


def test_large_optimizer_diagnostics_are_truncated_before_summary_json_persistence() -> None:
    from core.services.scheduler.schedule_summary import SUMMARY_SIZE_LIMIT_BYTES

    start = datetime(2026, 4, 1, 8, 0, 0)
    payload = "x" * 12000
    metrics = ScheduleMetrics(
        overdue_count=0,
        total_tardiness_hours=0.0,
        makespan_hours=0.0,
        changeover_count=0,
        weighted_tardiness_hours=0.0,
    )
    ctx = SummaryBuildContext(
        cfg=SimpleNamespace(
            sort_strategy="priority_first",
            priority_weight=0.4,
            due_weight=0.5,
            dispatch_mode="sgs",
            dispatch_rule="cr",
            auto_assign_enabled="no",
            ortools_enabled="no",
            ortools_time_limit_seconds=5,
            algo_mode="improve",
            time_budget_seconds=5,
            objective="min_overdue",
            freeze_window_enabled="no",
            freeze_window_days=0,
        ),
        version=1,
        normalized_batch_ids=["B001"],
        start_dt=start,
        end_date=None,
        batches={},
        operations=[],
        results=[],
        summary=SimpleNamespace(success=True, total_ops=0, scheduled_ops=0, failed_ops=0, warnings=[], errors=[]),
        used_strategy=SimpleNamespace(value="priority_first"),
        used_params={"sort_strategy": "priority_first"},
        algo_mode="improve",
        objective_name="min_overdue",
        time_budget_seconds=5,
        best_score=(0.0,),
        best_metrics=metrics,
        best_order=["B001"],
        attempts=[
            {
                "tag": "start:priority_first|sgs:cr",
                "strategy": "priority_first",
                "dispatch_mode": "sgs",
                "dispatch_rule": "cr",
                "used_params": {"payload": payload},
                "score": [0.0],
                "failed_ops": 0,
                "metrics": {"overdue_count": 0},
                "algo_stats": {"fallback_samples": {"huge": [{"payload": payload} for _ in range(20)]}},
            }
            for _ in range(4)
        ],
        improvement_trace=[],
        frozen_op_ids=set(),
        algo_stats={"fallback_counts": {"visible": 2}, "param_fallbacks": {}},
        simulate=False,
        t0=0.0,
    )

    _overdue, _status, result_summary_obj, result_summary_json, _elapsed = build_result_summary(_SummarySvc(), ctx=ctx)

    assert len(result_summary_json.encode("utf-8")) <= SUMMARY_SIZE_LIMIT_BYTES
    assert bool(result_summary_obj.get("summary_truncated"))
    assert bool(result_summary_obj.get("diagnostics_truncated"))
    algo_attempt = ((result_summary_obj.get("algo") or {}).get("attempts") or [{}])[0]
    assert "algo_stats" not in algo_attempt
    assert "used_params" not in algo_attempt
    assert "tag" not in algo_attempt
    json.loads(result_summary_json)
