from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from core.algorithm_contracts.types import ScheduleSummary
from core.models.enums import YesNo
from core.models.objective import best_score_schema, comparison_metric_key
from core.services.scheduler.contracts.graph_public_summary import project_public_graph_analysis
from core.services.scheduler.contracts.schedule_summary_types import (
    AlgorithmSummaryState,
    FallbackState,
    RuntimeState,
    SummaryBuildContext,
)
from core.services.scheduler.run.auto_assign_resource_errors import auto_assign_failed_op_ids_from_failure_details
from core.services.scheduler.run.schedule_candidate_summary import is_unified_generation
from core.services.scheduler.run.schedule_persistence_errors import missing_internal_resource_samples
from core.shared.local_datetime import format_local_datetime as fmt_dt

from .due_risk_items import NEAR_DUE_WINDOW_DAYS, incomplete_batches_payload
from .summary_visible_degradation import (
    apply_summary_diagnostics,
    public_summary_error_state,
    record_summary_degradation,
    summary_counts,
    warnings_with_graph,
)


def _actionable_missing_internal_resource_op_ids(
    ctx: SummaryBuildContext, failure_details: List[Dict[str, Any]]
) -> Set[int]:
    # 两个集合都由本次排产在进程内构造：缺资源 id 取自已校验的 BatchOperation.id，
    # 已排 id 取自 build_validated_schedule_payload 校验过的结果行。
    missing_ids = ctx.missing_internal_resource_op_ids
    if not missing_ids:
        return set()
    auto_assign_failed_ids = auto_assign_failed_op_ids_from_failure_details(failure_details)
    return missing_ids - ctx.scheduled_op_ids - auto_assign_failed_ids


def _algo_freeze_window_dict(
    state: AlgorithmSummaryState,
) -> Dict[str, Any]:
    freeze_state = state.freeze_state
    freeze_window = {
        "enabled": YesNo.YES.value if bool(freeze_state.get("enabled")) else YesNo.NO.value,
        "days": freeze_state["days"],
        "frozen_op_count": len(state.ctx.frozen_op_ids),
        "frozen_batch_count": len(state.frozen_batch_ids),
    }
    if freeze_state.get("freeze_applied"):
        freeze_window["freeze_state"] = freeze_state.get("freeze_state")
        freeze_window["freeze_applied"] = True
        freeze_window["freeze_application_status"] = freeze_state.get("freeze_application_status")
    if (
        freeze_state["freeze_state"] == "disabled"
        and freeze_state.get("freeze_disabled_reason") is not None
    ):
        freeze_window["freeze_disabled_reason"] = freeze_state.get("freeze_disabled_reason")
    return freeze_window


def _algo_resource_pool_dict(
    *,
    resource_pool_attempted: bool,
    resource_pool_enabled: bool,
) -> Dict[str, Any]:
    return {
        "enabled": YesNo.YES.value if resource_pool_enabled else YesNo.NO.value,
        "attempted": resource_pool_attempted if resource_pool_enabled else False,
    }


def _apply_optional_algo_fields(algo: Dict[str, Any], state: AlgorithmSummaryState) -> None:
    if state.resource_pool_enabled or (isinstance(state.resource_pool_meta, dict) and bool(state.resource_pool_meta)):
        algo["resource_pool"] = _algo_resource_pool_dict(
            resource_pool_attempted=state.resource_pool_attempted,
            resource_pool_enabled=state.resource_pool_enabled,
        )


def _apply_fallback_algo_fields(algo: Dict[str, Any], fallback_state: FallbackState) -> None:
    if fallback_state.fallback_counts:
        algo["fallback_counts"] = fallback_state.fallback_counts


def _algo_dict(state: AlgorithmSummaryState) -> Dict[str, Any]:
    ctx = state.ctx
    comparison = ctx.candidate_comparison_public
    unified = comparison is not None and is_unified_generation(comparison)
    best_score = (
        list(comparison["selection"]["selected_score"])
        if unified and comparison is not None
        else list(ctx.best_score)
    )
    metrics = ctx.best_metrics.public_dict()
    algo: Dict[str, Any] = {
        "mode": ctx.algo_mode,
        "objective": ctx.objective_name,
        "comparison_metric": comparison_metric_key(ctx.objective_name),
        "config_snapshot": ctx.cfg.public_config_snapshot(),
        "time_budget_seconds": ctx.time_budget_seconds,
        "hard_constraints": state.hard_constraints,
        "soft_objectives": [ctx.objective_name],
        "best_score_schema": best_score_schema(ctx.objective_name),
        "attempts": [],
        # 停机扩展只在自动分配开启且资源池建成时由 extend_downtime_map_for_resource_pool 写入。
        "downtime_avoid": {"extend_attempted": bool(ctx.downtime_meta.get("downtime_extend_attempted", False))},
        "freeze_window": _algo_freeze_window_dict(state),
        "best_score": best_score,
    }
    if metrics:
        algo["metrics"] = metrics
    if unified and comparison is not None:
        for key in ("generation_policy_version", "primary_objective", "target_objectives"):
            algo[key] = comparison[key]
    if ctx.graph_analysis_public is not None:
        graph_analysis = project_public_graph_analysis(ctx.graph_analysis_public)
        if graph_analysis:
            algo["graph_analysis"] = graph_analysis
    if comparison:
        algo["candidate_comparison"] = comparison
    _apply_optional_algo_fields(algo, state)
    _apply_fallback_algo_fields(algo, state.fallback_state)
    return algo


def _apply_visible_degradations(
    *,
    summary: ScheduleSummary,
    events: List[Dict[str, Any]],
    counters: Dict[str, Any],
    causes: List[str],
    completion_status: str,
    graph_analysis_public: Optional[Dict[str, Any]],
    failure_details: List[Dict[str, Any]],
) -> Tuple[bool, int, int, int]:
    degraded_success = False
    op_count, scheduled_ops, failed_ops = summary_counts(summary)
    if _graph_enhancement_degraded(graph_analysis_public):
        record_summary_degradation(
            events=events,
            counters=counters,
            causes=causes,
            code="graph_enhancement_degraded",
            scope="schedule.summary.graph_analysis",
            field="graph_analysis",
            message="工序图报告已生成，但图增强排队因循环依赖关闭，本次退回普通排法。",
            count=1,
        )
        degraded_success = completion_status == "success"
    # Every failure detail carries a literal code (run_state._failure_detail).
    dispatch_failure_count = len(failure_details)
    if dispatch_failure_count:
        # 注意：这里不像上面 graph 分支那样抬 degraded_success——这是刻意的，不是漏写。
        # 有派工失败/跳过明细蕴含 failed_count>0，故 completion_status 必非 "success"，二者代码层面互斥；
        # 补 `or completion=="success"` 只会引入一条永不成立的死逻辑。
        record_summary_degradation(
            events=events,
            counters=counters,
            causes=causes,
            code="dispatch_failure_details",
            scope="schedule.summary.failure_details",
            field="failure_details",
            message="部分工序没有形成有效排程，摘要已保留失败和跳过明细。",
            count=dispatch_failure_count,
        )
    return degraded_success, op_count, scheduled_ops, failed_ops


def _graph_enhancement_degraded(graph_analysis_public: Optional[Dict[str, Any]]) -> bool:
    # Every graph public projection carries literal status/mode (schedule_graph_report.py); a disallowed
    # enhancement always names its literal disabled reason (schedule_graph_dispatch_context.py).
    if graph_analysis_public is None:
        return False
    public = graph_analysis_public
    return bool(
        public["status"] == "available"
        and public["mode"] == "on"
        and public.get("graph_enhancement_allowed") is False
        and public["graph_enhancement_disabled_reason"] == "schedule_graph_cycle"
    )


def _build_result_summary_obj(
    *,
    ctx: SummaryBuildContext,
    runtime_state: RuntimeState,
    warnings: List[str],
    algorithm_state: AlgorithmSummaryState,
    summary_degradation: Dict[str, Any],
    completion_status: str,
    time_cost_ms: int,
) -> Dict[str, Any]:
    failure_details = ctx.summary.failure_details
    public_error_details, public_error_messages = public_summary_error_state(failure_details)
    missing_resource_ops = missing_internal_resource_samples(
        ctx.operations,
        _actionable_missing_internal_resource_op_ids(ctx, failure_details),
    )
    public_algo = _algo_dict(algorithm_state)
    warnings = warnings_with_graph(warnings, public_algo.get("graph_analysis"))
    degradation_events = list(summary_degradation["events"])
    degradation_counters = dict(summary_degradation["counters"])
    result_degraded_causes: List[str] = []
    result_degraded_success, op_count, scheduled_ops, failed_ops = _apply_visible_degradations(
        summary=ctx.summary,
        events=degradation_events,
        counters=degradation_counters,
        causes=result_degraded_causes,
        completion_status=completion_status,
        graph_analysis_public=ctx.graph_analysis_public,
        failure_details=failure_details,
    )

    result_summary = {
        "summary_schema_version": "1.2",
        "is_simulation": ctx.simulate,
        "completion_status": completion_status,
        "readiness": {"gate_enabled": ctx.readiness_gate_enabled},
        "version": ctx.version,
        "strategy": ctx.used_strategy.value,
        "strategy_params": ctx.used_params,
        "algo": public_algo,
        "selected_batch_ids": list(ctx.normalized_batch_ids),
        "start_time": fmt_dt(ctx.start_dt),
        "end_date": None if ctx.end_date is None else ctx.end_date.isoformat(),
        "invalid_due_count": runtime_state.invalid_due_count,
        "invalid_due_batch_ids_sample": runtime_state.invalid_due_batch_ids_sample,
        "unscheduled_batch_count": runtime_state.unscheduled_batch_count,
        "unscheduled_batch_ids_sample": runtime_state.unscheduled_batch_ids_sample,
        "degradation_events": degradation_events,
        "degradation_counters": degradation_counters,
        "degraded_success": result_degraded_success,
        "degraded_causes": result_degraded_causes,
        "counts": {
            "batch_count": len(ctx.batches),
            "op_count": op_count,
            "scheduled_ops": scheduled_ops,
            "failed_ops": failed_ops,
            "unscheduled_batch_count": runtime_state.unscheduled_batch_count,
        },
        "overdue_batches": {"count": len(runtime_state.overdue_items), "items": runtime_state.overdue_items},
        "near_due_batches": {
            "count": len(runtime_state.near_due_items),
            "items": runtime_state.near_due_items,
            "window_days": NEAR_DUE_WINDOW_DAYS,
        },
        # 排产未完成批次（有失败工序、finish 为截断值）不进超期/临期"健康"分类，
        # 在此单列风险口径（audit 2026-07-20 A18），构造口径见 due_risk_items。
        "incomplete_batches": incomplete_batches_payload(
            failure_details=failure_details,
            finish_by_batch=runtime_state.finish_by_batch,
            batches=ctx.batches,
            results=ctx.results,
            incomplete_batch_ids=runtime_state.incomplete_batch_ids,
        ),
        "error_count": len(public_error_messages),
        "errors": public_error_messages,
        "errors_sample": public_error_messages[:10],
        "public_error_details": public_error_details,
        # failure_detail_count 是被 dispatch_error_summary 消费的“真实失败总数”（去重/采样前）。
        # 原始 failure_details 列表与 raw_error_count 此前落库却无任何消费端，已移除以免摘要膨胀；
        # 失败的对外展示统一走 public_error_details。
        "failure_detail_count": len(failure_details),
        "missing_internal_resource_count": len(missing_resource_ops),
        "missing_internal_resource_ops": missing_resource_ops,
        "warnings": warnings,
        "time_cost_ms": time_cost_ms,
    }
    if ctx.execution_snapshot_revision:
        op_ids = list(ctx.execution_snapshot_op_ids)
        result_summary["execution_snapshot"] = {
            "revision_kind": "content_v2",
            "execution_snapshot_op_ids": op_ids,
            "execution_snapshot_op_count": ctx.execution_snapshot_op_count,
            "execution_snapshot_op_ids_sample": op_ids[:50],
            "execution_snapshot_op_ids_truncated": len(op_ids) > 50,
        }
    apply_summary_diagnostics(result_summary, ctx)
    return result_summary
