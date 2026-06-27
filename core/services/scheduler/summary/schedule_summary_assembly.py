from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from core.algorithms.objective_specs import best_score_schema, comparison_metric_key
from core.models.enums import YesNo
from core.services.scheduler.config.config_snapshot import ensure_schedule_config_snapshot
from core.services.scheduler.run.auto_assign_resource_errors import auto_assign_failed_op_ids_from_errors
from core.services.scheduler.run.optimizer_search_state import compact_attempts
from core.services.scheduler.run.schedule_persistence_errors import missing_internal_resource_samples

from .due_risk_items import NEAR_DUE_WINDOW_DAYS
from .optimizer_public_summary import project_public_algo_summary
from .schedule_summary_types import (
    AlgorithmSummaryState,
    FallbackState,
    FreezeState,
    RuntimeState,
    SummaryBuildContext,
)
from .summary_visible_degradation import (
    apply_fallback_count_degradation,
    apply_metrics_degradation,
    apply_summary_count_degradation,
    apply_summary_count_errors,
    apply_summary_diagnostics,
    public_summary_error_state,
    record_summary_degradation,
    safe_metrics_dict,
    summary_counts_with_errors,
    warnings_with_graph,
)

_SUMMARY_MERGE_ERROR_CODES = {
    "summary_missing",
    "summary_warnings_assignment_failed",
    "summary_warnings_unavailable",
}


def _config_snapshot_dict(cfg: Any) -> Dict[str, Any]:
    return ensure_schedule_config_snapshot(
        cfg,
        strict_mode=False,
        source="scheduler.summary.config_snapshot",
    ).to_dict()


def _comparison_metric(objective_name: str) -> str:
    return comparison_metric_key(objective_name)


def _best_score_schema(objective_name: str) -> List[Dict[str, Any]]:
    return best_score_schema(objective_name)


def _finish_time_by_batch(results: List[Any]) -> Dict[str, datetime]:
    finish_by_batch: Dict[str, datetime] = {}
    for result in results:
        finish_time = getattr(result, "end_time", None)
        if not finish_time:
            continue
        batch_id = str(getattr(result, "batch_id", "") or "").strip()
        if not batch_id:
            continue
        current = finish_by_batch.get(batch_id)
        if current is None or finish_time > current:
            finish_by_batch[batch_id] = finish_time
    return finish_by_batch


def _positive_result_op_ids(results: List[Any]) -> Set[int]:
    op_ids: Set[int] = set()
    for result in list(results or []):
        try:
            op_id = int(getattr(result, "op_id", 0) or 0)
        except Exception:
            continue
        if op_id > 0:
            op_ids.add(op_id)
    return op_ids


def _positive_int_set(values: Any) -> Set[int]:
    out: Set[int] = set()
    for value in list(values or []):
        try:
            number = int(value or 0)
        except Exception:
            continue
        if number > 0:
            out.add(number)
    return out


def _actionable_missing_internal_resource_op_ids(ctx: SummaryBuildContext) -> Set[int]:
    missing_ids = _positive_int_set(ctx.missing_internal_resource_op_ids)
    if not missing_ids:
        return set()

    if ctx.scheduled_op_ids is None:
        scheduled_ids = _positive_result_op_ids(ctx.results)
    else:
        scheduled_ids = _positive_int_set(ctx.scheduled_op_ids)

    auto_assign_failed_ids = auto_assign_failed_op_ids_from_errors(
        errors=getattr(ctx.summary, "errors", None),
        operations=ctx.operations,
    )
    return missing_ids - scheduled_ids - auto_assign_failed_ids


# _build_overdue_items / _record_invalid_due 已拆至 due_risk_items.py（fusion-due-soon-alert 微重构，只搬不改）。
# 由 summary_runtime_state.build_overdue_items 注入 due_exclusive / append_summary_warning 后调用。


def _algo_downtime_dict(*, auto_assign_enabled: bool, downtime_state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "loaded_ok": bool(downtime_state.get("downtime_load_ok")),
        "degraded": bool(downtime_state.get("downtime_degraded")),
        "degradation_reason": downtime_state.get("downtime_degradation_reason"),
        "extend_attempted": bool(downtime_state.get("downtime_extend_attempted")) if auto_assign_enabled else False,
        "load_partial_fail_count": int(downtime_state.get("load_partial_fail_count") or 0),
        "load_partial_fail_machines_sample": list(downtime_state.get("load_partial_fail_machines_sample") or []),
        "downtime_meta_parse_failed": bool(downtime_state.get("downtime_meta_parse_failed")),
        "extend_partial_fail_count": int(downtime_state.get("extend_partial_fail_count") or 0)
        if auto_assign_enabled
        else 0,
        "extend_partial_fail_machines_sample": list(downtime_state.get("extend_partial_fail_machines_sample") or [])
        if auto_assign_enabled
        else [],
    }


def _algo_input_contract_dict(input_state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "degraded": bool(input_state.get("degraded")),
        "degradation_events": list(input_state.get("degradation_events") or []),
        "degradation_counters": dict(input_state.get("degradation_counters") or {}),
        "empty_reason": input_state.get("empty_reason"),
    }


def _algo_freeze_window_dict(
    state: AlgorithmSummaryState,
) -> Dict[str, Any]:
    freeze_state = state.freeze_state.data
    freeze_window = {
        "enabled": YesNo.YES.value if bool(freeze_state.get("enabled")) else YesNo.NO.value,
        "days": int(freeze_state.get("days") or 0),
        "frozen_op_count": int(len(state.ctx.frozen_op_ids)),
        "frozen_batch_count": int(len(state.frozen_batch_ids)),
        "frozen_batch_ids_sample": state.frozen_batch_ids[:20],
        "degraded": str(freeze_state.get("freeze_state") or "") == "degraded",
        "degradation_reason": freeze_state.get("degradation_reason"),
    }
    expose_state = (
        bool(freeze_state.get("freeze_applied"))
        or bool(freeze_window["degraded"])
        or bool(freeze_state.get("freeze_degradation_codes"))
    )
    if expose_state:
        freeze_window["freeze_state"] = freeze_state.get("freeze_state")
        freeze_window["freeze_applied"] = bool(freeze_state.get("freeze_applied"))
        if freeze_state.get("freeze_application_status") is not None:
            freeze_window["freeze_application_status"] = freeze_state.get("freeze_application_status")
        if freeze_state.get("freeze_degradation_public_code") is not None:
            freeze_window["freeze_degradation_public_code"] = freeze_state.get("freeze_degradation_public_code")
        freeze_window["freeze_degradation_codes"] = list(freeze_state.get("freeze_degradation_codes") or [])
    if (
        str(freeze_state.get("freeze_state") or "").strip().lower() == "disabled"
        and freeze_state.get("freeze_disabled_reason") is not None
    ):
        freeze_window["freeze_disabled_reason"] = freeze_state.get("freeze_disabled_reason")
    return freeze_window


def _algo_resource_pool_dict(
    *,
    resource_pool_attempted: bool,
    resource_pool_degraded: bool,
    resource_pool_degradation_reason: Optional[str],
    resource_pool_enabled: bool,
) -> Dict[str, Any]:
    return {
        "enabled": YesNo.YES.value if bool(resource_pool_enabled) else YesNo.NO.value,
        "attempted": bool(resource_pool_attempted) if resource_pool_enabled else False,
        "degraded": bool(resource_pool_degraded),
        "degradation_reason": resource_pool_degradation_reason,
    }


def _algo_warning_pipeline_dict(
    *,
    summary_warnings: List[str],
    algo_warning_list: List[str],
    warning_pipeline: Dict[str, Any],
) -> Dict[str, Any]:
    summary_merge_error = str(warning_pipeline.get("summary_merge_error") or "").strip()
    if summary_merge_error and summary_merge_error not in _SUMMARY_MERGE_ERROR_CODES:
        summary_merge_error = "summary_warnings_assignment_failed"
    return {
        "algo_warning_count": int(len(algo_warning_list)),
        "summary_warning_count": int(len(summary_warnings)),
        "summary_merge_attempted": bool(warning_pipeline.get("summary_merge_attempted") or False),
        "summary_merge_failed": bool(warning_pipeline.get("summary_merge_failed") or False),
        "summary_merge_error": summary_merge_error or None,
    }


def _graph_analysis_algo_dict(ctx: SummaryBuildContext) -> Dict[str, Any]:
    if ctx.graph_analysis_public is None:
        return {}
    return {"graph_analysis": dict(ctx.graph_analysis_public)}


def _candidate_comparison_algo_dict(ctx: SummaryBuildContext) -> Dict[str, Any]:
    if ctx.candidate_comparison_public is None:
        return {}
    return {"candidate_comparison": dict(ctx.candidate_comparison_public)}


def _summary_failure_details(summary: Any) -> List[Dict[str, Any]]:
    details = getattr(summary, "failure_details", None)
    if not isinstance(details, list):
        return []
    return [dict(item) for item in details if isinstance(item, dict)]


def _apply_optional_algo_fields(algo: Dict[str, Any], state: AlgorithmSummaryState, metrics_state: Any) -> None:
    if metrics_state:
        algo["metrics_state"] = metrics_state
    if state.resource_pool_enabled or (isinstance(state.resource_pool_meta, dict) and bool(state.resource_pool_meta)):
        algo["resource_pool"] = _algo_resource_pool_dict(
            resource_pool_attempted=state.resource_pool_attempted,
            resource_pool_degraded=state.resource_pool_degraded,
            resource_pool_degradation_reason=state.resource_pool_degradation_reason,
            resource_pool_enabled=state.resource_pool_enabled,
        )
    if state.warning_state.algo_warning_list or any(bool(value) for value in state.warning_pipeline.values()):
        algo["warning_pipeline"] = _algo_warning_pipeline_dict(
            summary_warnings=state.warning_state.summary_warnings,
            algo_warning_list=state.warning_state.algo_warning_list,
            warning_pipeline=state.warning_pipeline,
        )


def _apply_fallback_algo_fields(algo: Dict[str, Any], fallback_state: FallbackState) -> None:
    if fallback_state.fallback_counts:
        algo["fallback_counts"] = dict(fallback_state.fallback_counts)
    if fallback_state.fallback_samples:
        algo["fallback_samples"] = dict(fallback_state.fallback_samples)
    if fallback_state.param_fallbacks:
        algo["param_fallbacks"] = dict(fallback_state.param_fallbacks)
    if fallback_state.fallback_count_parse_errors:
        algo["fallback_count_parse_failed"] = True
        algo["fallback_count_parse_errors"] = list(fallback_state.fallback_count_parse_errors[:10])


def _algo_dict(state: AlgorithmSummaryState) -> Dict[str, Any]:
    ctx = state.ctx
    auto_assign_enabled = bool(state.downtime_state.get("auto_assign_enabled"))
    metrics_dict, metrics_state = safe_metrics_dict(ctx.best_metrics)
    algo: Dict[str, Any] = {
        "mode": ctx.algo_mode,
        "objective": ctx.objective_name,
        "comparison_metric": _comparison_metric(ctx.objective_name),
        "config_snapshot": _config_snapshot_dict(ctx.cfg),
        "time_budget_seconds": int(ctx.time_budget_seconds),
        "hard_constraints": list(state.hard_constraints),
        "soft_objectives": [ctx.objective_name],
        "best_score": list(ctx.best_score) if ctx.best_score is not None else None,
        "best_score_schema": _best_score_schema(ctx.objective_name),
        "metrics": metrics_dict,
        "best_batch_order": list(ctx.best_order or []),
        "attempts": compact_attempts(list(ctx.attempts or []), limit=12),
        "improvement_trace": list(ctx.improvement_trace or [])[:200],
        "search_report": dict(ctx.search_report or {}),
        "downtime_avoid": _algo_downtime_dict(
            auto_assign_enabled=auto_assign_enabled, downtime_state=state.downtime_state
        ),
        "input_contract": _algo_input_contract_dict(state.input_state),
        "merge_context_degraded": bool(state.warning_state.merge_context_degraded),
        "merge_context_events": list(state.warning_state.merge_context_events),
        "freeze_window": _algo_freeze_window_dict(state),
    }
    _apply_optional_algo_fields(algo, state, metrics_state)
    _apply_fallback_algo_fields(algo, state.fallback_state)
    algo.update(_graph_analysis_algo_dict(ctx))
    algo.update(_candidate_comparison_algo_dict(ctx))
    return algo


def _apply_visible_degradations(
    *,
    public_algo: Dict[str, Any],
    fallback_state: FallbackState,
    summary: Any,
    warnings: List[str],
    events: List[Dict[str, Any]],
    counters: Dict[str, Any],
    causes: List[str],
    completion_status: str,
    degraded_success: bool,
    graph_analysis_public: Optional[Dict[str, Any]],
    failure_details: List[Dict[str, Any]],
) -> Tuple[bool, int, int, int, List[str]]:
    degraded_success = apply_metrics_degradation(
        metrics_state=public_algo.get("metrics_state"),
        warnings=warnings,
        events=events,
        counters=counters,
        causes=causes,
        completion_status=completion_status,
        degraded_success=degraded_success,
    )
    degraded_success = apply_fallback_count_degradation(
        fallback_parse_errors=list(getattr(fallback_state, "fallback_count_parse_errors", []) or []),
        warnings=warnings,
        events=events,
        counters=counters,
        causes=causes,
        completion_status=completion_status,
        degraded_success=degraded_success,
    )
    op_count, scheduled_ops, failed_ops, summary_count_errors = summary_counts_with_errors(summary)
    degraded_success = apply_summary_count_degradation(
        summary_count_errors=summary_count_errors,
        warnings=warnings,
        events=events,
        counters=counters,
        causes=causes,
        completion_status=completion_status,
        degraded_success=degraded_success,
    )
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
        degraded_success = bool(degraded_success or str(completion_status or "") == "success")
    dispatch_failure_count = _dispatch_failure_detail_count(failure_details)
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
    return degraded_success, op_count, scheduled_ops, failed_ops, summary_count_errors


def _graph_enhancement_degraded(graph_analysis_public: Optional[Dict[str, Any]]) -> bool:
    public = graph_analysis_public if isinstance(graph_analysis_public, dict) else {}
    return bool(
        str(public.get("status") or "").strip().lower() == "available"
        and str(public.get("mode") or "").strip().lower() == "on"
        and public.get("graph_enhancement_allowed") is False
        and str(public.get("graph_enhancement_disabled_reason") or "").strip() == "schedule_graph_cycle"
    )


def _dispatch_failure_detail_count(failure_details: List[Dict[str, Any]]) -> int:
    return sum(1 for item in failure_details if str(item.get("code") or "").strip())


def _build_result_summary_obj(
    svc,
    *,
    ctx: SummaryBuildContext,
    runtime_state: RuntimeState,
    freeze_state: FreezeState,
    fallback_state: FallbackState,
    algorithm_state: AlgorithmSummaryState,
    summary_degradation: Dict[str, Any],
    degraded_success: bool,
    degraded_causes: List[str],
    completion_status: str,
    time_cost_ms: int,
    serialize_end_date_fn: Callable[[Optional[Any]], Optional[str]],
) -> Dict[str, Any]:
    raw_summary_errors = list(getattr(ctx.summary, "errors", None) or [])
    failure_details = _summary_failure_details(ctx.summary)
    public_error_details, public_error_messages = public_summary_error_state(raw_summary_errors, failure_details)
    missing_resource_ops = missing_internal_resource_samples(
        ctx.operations,
        _actionable_missing_internal_resource_op_ids(ctx),
    )
    public_algo, optimizer_diagnostics = project_public_algo_summary(_algo_dict(algorithm_state))
    warnings = warnings_with_graph(freeze_state, ctx)
    degradation_events = list(summary_degradation.get("events") or [])
    degradation_counters = dict(summary_degradation.get("counters") or {})
    result_degraded_causes = list(degraded_causes or [])
    result_degraded_success, op_count, scheduled_ops, failed_ops, summary_count_errors = _apply_visible_degradations(
        public_algo=public_algo,
        fallback_state=fallback_state,
        summary=ctx.summary,
        warnings=warnings,
        events=degradation_events,
        counters=degradation_counters,
        causes=result_degraded_causes,
        completion_status=completion_status,
        degraded_success=bool(degraded_success),
        graph_analysis_public=ctx.graph_analysis_public,
        failure_details=failure_details,
    )

    result_summary = {
        "summary_schema_version": "1.2",
        "is_simulation": bool(ctx.simulate),
        "completion_status": str(completion_status or ""),
        "readiness": {"gate_enabled": bool(ctx.readiness_gate_enabled)},
        "version": int(ctx.version),
        "strategy": ctx.used_strategy.value,
        "strategy_params": ctx.used_params or {},
        "algo": public_algo,
        "selected_batch_ids": list(ctx.normalized_batch_ids),
        "start_time": svc._format_dt(ctx.start_dt),
        "end_date": serialize_end_date_fn(ctx.end_date),
        "invalid_due_count": int(runtime_state.invalid_due_count),
        "invalid_due_batch_ids_sample": list(runtime_state.invalid_due_batch_ids_sample[:10]),
        "unscheduled_batch_count": int(runtime_state.unscheduled_batch_count),
        "unscheduled_batch_ids_sample": list(runtime_state.unscheduled_batch_ids_sample[:20]),
        "legacy_external_days_defaulted_count": int(fallback_state.legacy_external_days_defaulted_count),
        "degradation_events": degradation_events,
        "degradation_counters": degradation_counters,
        "degraded_success": bool(result_degraded_success),
        "degraded_causes": result_degraded_causes,
        "counts": {
            "batch_count": len(ctx.batches),
            "op_count": op_count,
            "scheduled_ops": scheduled_ops,
            "failed_ops": failed_ops,
            "unscheduled_batch_count": int(runtime_state.unscheduled_batch_count),
        },
        "overdue_batches": {"count": len(runtime_state.overdue_items), "items": runtime_state.overdue_items},
        "near_due_batches": {
            "count": len(runtime_state.near_due_items),
            "items": runtime_state.near_due_items,
            "window_days": NEAR_DUE_WINDOW_DAYS,
        },
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
        "time_cost_ms": int(time_cost_ms),
    }
    if ctx.execution_snapshot_revision:
        op_ids = list(ctx.execution_snapshot_op_ids or [])
        result_summary["execution_snapshot"] = {
            "execution_snapshot_revision": str(ctx.execution_snapshot_revision),
            "execution_snapshot_op_ids": op_ids,
            "execution_snapshot_op_count": int(ctx.execution_snapshot_op_count or len(op_ids)),
            "execution_snapshot_op_ids_sample": op_ids[:50],
            "execution_snapshot_op_ids_truncated": len(op_ids) > 50,
        }
    apply_summary_count_errors(result_summary, summary_count_errors)
    apply_summary_diagnostics(result_summary, optimizer_diagnostics, ctx)
    return result_summary
