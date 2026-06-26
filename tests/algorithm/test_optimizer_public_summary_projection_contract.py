"""回归测试：优化器尝试（attempts）公开摘要投影契约（project_public_algo_summary / build_result_summary）。守护公开 algo.attempts 剥离 tag/used_params/algo_stats/source/origin 内部诊断字段并打上 source_label "多起点方案"；内部诊断保留在 diagnostics.optimizer.attempts；无内部字段时省略 diagnostics；candidate_rejected 尝试只进诊断不进公开；尝试压缩后被拒诊断仍存活；超大诊断在落 JSON 前按 SUMMARY_SIZE_LIMIT_BYTES 截断并置 summary_truncated/diagnostics_truncated。"""

from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace

from core.algorithms.evaluation import ScheduleMetrics
from core.services.scheduler.run.optimizer_search_state import compact_attempts
from core.services.scheduler.summary.optimizer_public_summary import (
    project_public_algo_summary,
    project_public_result_summary,
)
from core.services.scheduler.summary.schedule_summary import build_result_summary
from core.services.scheduler.summary.schedule_summary_types import SummaryBuildContext


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
                    "score": [0.0, "op:SECRET-SCORE"],
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
        attempt for attempt in diagnostics["optimizer"]["attempts"] if attempt.get("source") == "candidate_rejected"
    ][0]
    assert diagnostic_attempt["tag"] == "local:swap"
    assert diagnostic_attempt["strategy"] == "priority_first"
    assert diagnostic_attempt["dispatch_mode"] == "sgs"
    assert diagnostic_attempt["dispatch_rule"] == "slack"
    assert diagnostic_attempt["source"] == "candidate_rejected"
    assert diagnostic_attempt["origin"]["field"] == "resource"


def test_public_algo_summary_projects_attempts_and_graph_by_whitelist() -> None:
    public_algo, diagnostics = project_public_algo_summary(
        {
            "candidate_id": "TOP-CANDIDATE-SECRET",
            "source_table": "top_level_debug",
            "origin": {"node_id": "op:TOP-SECRET"},
            "used_params": {"node_id": "op:TOP-SECRET"},
            "algo_stats": {"source_table": "top_level_debug"},
            "config_snapshot": {
                "sort_strategy": "priority_first",
                "dispatch_mode": "sgs",
                "dispatch_rule": "op:SECRET-RULE",
                "algo_mode": "improve",
                "objective": "min_overdue",
                "time_budget_seconds": "15",
                "freeze_window_enabled": "yes",
                "freeze_window_days": 3,
                "node_id": "op:SECRET-CONFIG",
            },
            "comparison_metric": "source_table",
            "best_score_schema": [
                {"index": 0, "key": "source_table", "label": "candidate_rows"},
                {"index": 1, "key": "overdue_count", "label": "超期批次"},
            ],
            "metrics": {"source_table": "candidate_rows", "overdue_count": 1},
            "best_batch_order": ["B001", "op:SECRET-BATCH"],
            "improvement_trace": [
                {
                    "elapsed_ms": 10,
                    "score": [1.0, "op:SECRET-TRACE-SCORE"],
                    "metrics": {"overdue_count": 1, "source_table": "candidate_rows"},
                    "candidate_id": "CANDIDATE-TRACE",
                },
                {
                    "elapsed_ms": "op:SECRET-TIME",
                    "score": ["op:SECRET-TRACE-SCORE"],
                    "metrics": {"overdue_count": "op:SECRET-METRIC"},
                },
            ],
            "downtime_avoid": {
                "loaded_ok": True,
                "degraded": True,
                "degradation_reason": "停机资料不完整，本次先按可用数据继续。",
                "extend_attempted": True,
                "load_partial_fail_count": 1,
                "load_partial_fail_machines_sample": ["op:SECRET-MACHINE"],
                "extend_partial_fail_count": 2,
                "extend_partial_fail_machines_sample": ["op:SECRET-MACHINE"],
                "downtime_meta_parse_failed": False,
                "source_table": "downtime_debug",
            },
            "freeze_window": {
                "enabled": "yes",
                "days": 3,
                "frozen_op_count": 2,
                "frozen_batch_count": 1,
                "frozen_batch_ids_sample": ["op:SECRET-BATCH"],
                "degraded": False,
                "degradation_reason": "op:SECRET-FREEZE",
                "freeze_state": "applied",
                "freeze_applied": True,
                "freeze_degradation_codes": ["freeze_seed_unavailable", "op:SECRET-FREEZE"],
            },
            "resource_pool": {
                "enabled": "yes",
                "attempted": True,
                "degraded": True,
                "degradation_reason": "自动分配设备人员所需资料不完整。",
                "source_table": "resource_debug",
                "sample": ["op:SECRET-RESOURCE"],
            },
            "metrics_state": {
                "parse_failed": True,
                "error_type": "ValueError",
                "message": "优化指标记录异常。",
                "detail": "op:SECRET-DETAIL",
            },
            "fallback_counts": {"resource_pool_degraded": 1, "op:SECRET-COUNT": 2},
            "fallback_count_parse_errors": ["resource_pool_degraded", "op:SECRET-ERROR"],
            "warning_pipeline": {
                "algo_warning_count": 2,
                "summary_warning_count": 1,
                "summary_merge_attempted": True,
                "summary_merge_failed": True,
                "summary_merge_error": "summary_warnings_assignment_failed",
                "raw_error": "op:SECRET-WARNING",
            },
            "graph_analysis": {
                "status": "available",
                "node_count": 2,
                "edge_count": 1,
                "critical_path_node_count": 2,
                "node_id": "op:SECRET-NODE",
                "op_id": 7,
                "candidate_id": "CANDIDATE-SECRET",
                "source_table": "graph_nodes",
                "critical_path_sample": ["op:SECRET-NODE"],
                "resource_matching": {
                    "status": "available",
                    "ready_operation_count": 2,
                    "matched_operation_count": 1,
                    "unmatched_operation_count": 1,
                    "unmatched_operation_ids_sample": ["op:SECRET-RESOURCE"],
                    "source_table": "resource_debug",
                },
            },
            "attempts": [
                {
                    "strategy": "priority_first",
                    "dispatch_mode": "sgs",
                    "dispatch_rule": "cr",
                    "score": [0.0, "op:SECRET-SCORE"],
                    "failed_ops": 0,
                    "candidate_status": "accepted",
                    "candidate_id": "CANDIDATE-SECRET",
                    "source_table": "attempts_debug",
                    "metrics": {
                        "overdue_count": 1,
                        "changeover_count": 2,
                        "makespan_hours": "op:SECRET-METRIC",
                        "candidate_id": "CANDIDATE-SECRET",
                    },
                },
                {
                    "tag": "local:swap",
                    "source": "candidate_rejected",
                    "origin": {"node_id": "op:SECRET-NODE", "source_table": "attempts_debug"},
                },
            ],
            "candidate_comparison": {
                "enabled": True,
                "planned_candidate_count": 2,
                "completed_candidate_count": 1,
                "failed_candidate_count": 1,
                "skipped_candidate_count": 0,
                "time_budget_reached": False,
                "run_time_budget_seconds": 10.0,
                "adopted_candidate_key": "graph_w1_of_2",
                "baseline_best_candidate_key": "baseline",
                "critical_best_candidate_key": "graph_w1_of_2",
                "skipped_candidate_labels": ["graph_w2_of_2", "candidate_rows"],
                "selection_reason_code": "balanced_raw_score_best",
                "candidates": [
                    {
                        "candidate_key": "graph_w1_of_2",
                        "label": "graph_w1_of_2",
                        "status": "completed",
                        "score": [0.0, "op:SECRET-CANDIDATE-SCORE"],
                        "metrics": {"overdue_count": 1, "source_table": "candidate_rows"},
                        "roles": ["adopted", "critical_best", "source_table"],
                        "failure_reason": "candidate_rows node_id=op:SECRET op_code=OP010",
                        "source_table": "candidate_rows",
                    }
                ],
            },
        }
    )

    public_text = json.dumps(public_algo, ensure_ascii=False, sort_keys=True)
    for forbidden in (
        "op:",
        "node_id",
        "op_id",
        "candidate_id",
        "source_table",
        "critical_path_sample",
        "unmatched_operation_ids_sample",
        "CANDIDATE-SECRET",
        "TOP-CANDIDATE-SECRET",
        "top_level_debug",
        "origin",
        "used_params",
        "algo_stats",
        "SECRET",
        "graph_w1_of_2",
        "graph_w2_of_2",
        "best_batch_order",
        "frozen_batch_ids_sample",
        "load_partial_fail_machines_sample",
        "extend_partial_fail_machines_sample",
        "detail",
        "raw_error",
    ):
        assert forbidden not in public_text
    assert public_algo["config_snapshot"] == {
        "sort_strategy": "priority_first",
        "dispatch_mode": "sgs",
        "algo_mode": "improve",
        "objective": "min_overdue",
        "freeze_window_enabled": "yes",
        "time_budget_seconds": 15,
        "freeze_window_days": 3,
    }
    assert public_algo["comparison_metric"] == "overdue_count"
    assert public_algo["best_score_schema"] == [{"index": 1, "key": "overdue_count", "label": "超期批次"}]
    assert public_algo["metrics"] == {"overdue_count": 1}
    assert public_algo["improvement_trace"] == [
        {
            "elapsed_ms": 10,
            "score": [1.0],
            "metrics": {"overdue_count": 1},
        }
    ]
    assert public_algo["downtime_avoid"] == {
        "loaded_ok": True,
        "degraded": True,
        "extend_attempted": True,
        "downtime_meta_parse_failed": False,
        "load_partial_fail_count": 1,
        "extend_partial_fail_count": 2,
        "degradation_reason": "停机资料不完整，本次先按可用数据继续。",
    }
    assert public_algo["freeze_window"] == {
        "enabled": "yes",
        "freeze_state": "applied",
        "days": 3,
        "frozen_op_count": 2,
        "frozen_batch_count": 1,
        "degraded": False,
        "freeze_applied": True,
        "freeze_degradation_codes": ["freeze_seed_unavailable"],
    }
    assert public_algo["resource_pool"] == {
        "enabled": "yes",
        "degradation_reason": "自动分配设备人员所需资料不完整。",
        "attempted": True,
        "degraded": True,
    }
    assert public_algo["metrics_state"] == {
        "parse_failed": True,
        "error_type": "ValueError",
        "message": "优化指标记录异常。",
    }
    assert public_algo["fallback_counts"] == {"resource_pool_degraded": 1}
    assert public_algo["fallback_count_parse_errors"] == ["resource_pool_degraded"]
    assert public_algo["warning_pipeline"] == {
        "algo_warning_count": 2,
        "summary_warning_count": 1,
        "summary_merge_attempted": True,
        "summary_merge_failed": True,
        "summary_merge_error": "summary_warnings_assignment_failed",
    }
    assert public_algo["graph_analysis"]["resource_matching"] == {
        "status": "available",
        "ready_operation_count": 2,
        "matched_operation_count": 1,
        "unmatched_operation_count": 1,
    }
    assert public_algo["attempts"] == [
        {
            "strategy": "priority_first",
            "dispatch_mode": "sgs",
            "dispatch_rule": "cr",
            "score": [0.0],
            "failed_ops": 0,
            "candidate_status": "accepted",
            "metrics": {"overdue_count": 1, "changeover_count": 2},
        }
    ]
    assert public_algo["candidate_comparison"]["candidates"] == [
        {
            "label": "重点工序优先方案 1/2",
            "status": "completed",
            "score": [0.0],
            "metrics": {"overdue_count": 1},
            "roles": ["adopted", "critical_best"],
            "failure_reason": "candidate_failed",
        }
    ]
    diagnostic_text = json.dumps(diagnostics, ensure_ascii=False, sort_keys=True)
    assert "candidate_rejected" in diagnostic_text
    assert "node_id" in diagnostic_text


def test_public_algo_summary_drops_malformed_attempts_dict() -> None:
    public_algo, diagnostics = project_public_algo_summary(
        {
            "metrics": {"overdue_count": 1},
            "attempts": {
                "candidate_id": "CANDIDATE-SECRET",
                "node_id": "op:SECRET",
                "source_table": "attempts_debug",
                "metrics": {"overdue_count": 1},
            },
        }
    )

    public_text = json.dumps(public_algo, ensure_ascii=False, sort_keys=True)
    for forbidden in ("attempts", "candidate_id", "node_id", "op:", "source_table", "attempts_debug", "SECRET"):
        assert forbidden not in public_text
    assert public_algo == {"metrics": {"overdue_count": 1}}
    assert diagnostics == {}


def test_rejected_diagnostic_survives_summary_attempt_compaction() -> None:
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
        attempts=attempts,
        improvement_trace=[],
        frozen_op_ids=set(),
        algo_stats={"fallback_counts": {}, "param_fallbacks": {}},
        simulate=False,
        t0=0.0,
    )

    _overdue, _status, result_summary_obj, _json, _elapsed = build_result_summary(_SummarySvc(), ctx=ctx)

    public_attempts = (result_summary_obj.get("algo") or {}).get("attempts") or []
    diagnostics = result_summary_obj.get("diagnostics") or {}
    diagnostic_attempts = (diagnostics.get("optimizer") or {}).get("attempts") or []
    rejected_attempts = [attempt for attempt in diagnostic_attempts if attempt.get("source") == "candidate_rejected"]
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
    from core.services.scheduler.summary.schedule_summary import SUMMARY_SIZE_LIMIT_BYTES

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


def test_project_public_result_summary_is_default_safe_single_source() -> None:
    """单一真相源:summary 级 public 投影必须剔除 diagnostics 并对 algo 脱敏内部候选 key,且不就地改入参。"""
    raw = {
        "result_status": "ok",
        "diagnostics": {"optimizer": {"attempts": [{"tag": "start:1"}]}},
        "algo": {
            "mode": "improve",
            "candidate_comparison": {
                "adopted_candidate_key": "graph_w1_of_3",
                "candidates": [{"label": "baseline", "status": "completed"}],
            },
        },
    }
    public = project_public_result_summary(raw)
    assert "diagnostics" not in public
    assert public["result_status"] == "ok"
    assert "diagnostics" in raw  # 原始入参不被就地篡改
    algo = public["algo"]
    assert "adopted_candidate_key" not in (algo.get("candidate_comparison") or {})


def test_project_public_result_summary_non_dict_passthrough() -> None:
    assert project_public_result_summary(None) is None
    assert project_public_result_summary("x") == "x"
