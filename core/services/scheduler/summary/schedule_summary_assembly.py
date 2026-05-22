from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from core.algorithms.objective_specs import best_score_schema, comparison_metric_key
from core.models.enums import YesNo
from core.models.scheduler_public_errors import build_public_error_records
from core.services.scheduler.config.config_snapshot import ensure_schedule_config_snapshot
from core.services.scheduler.run.optimizer_search_state import compact_attempts
from core.services.scheduler.run.schedule_persistence_errors import missing_internal_resource_samples

from .optimizer_public_summary import project_public_algo_summary
from .schedule_summary_types import (
    AlgorithmSummaryState,
    FallbackState,
    FreezeState,
    RuntimeState,
    SummaryBuildContext,
)

_SUMMARY_MERGE_ERROR_CODES = {
    "summary_missing",
    "summary_warnings_assignment_failed",
    "summary_warnings_unavailable",
}
_OPTIMIZER_METRICS_INVALID_WARNING = "优化指标记录异常，不能按这些指标判断结果。"
_FALLBACK_COUNT_PARSE_WARNING = "排产降级统计记录异常，部分降级原因无法完整展示。"
_SUMMARY_COUNT_PARSE_WARNING = "排产摘要里的数量记录异常，不能按这些数量判断结果。"


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

    return missing_ids - scheduled_ids


def _record_invalid_due(
    *,
    batch_id: str,
    due_text: str,
    invalid_due_ids_sample: List[str],
    invalid_due_raw_sample: List[str],
) -> None:
    if len(invalid_due_ids_sample) < 10:
        invalid_due_ids_sample.append(str(batch_id))
    if len(invalid_due_raw_sample) < 5:
        invalid_due_raw_sample.append(f"{batch_id}={due_text!r}")


def _build_overdue_items(
    svc,
    *,
    batches: Dict[str, Any],
    finish_by_batch: Dict[str, datetime],
    summary: Any,
    due_exclusive_fn: Callable[[Any], datetime],
    append_summary_warning_fn: Callable[[Any, str], bool],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    overdue_items: List[Dict[str, Any]] = []
    invalid_due_count = 0
    invalid_due_ids_sample: List[str] = []
    invalid_due_raw_sample: List[str] = []

    for batch_id, batch in batches.items():
        due_text = svc._normalize_text(getattr(batch, "due_date", None))
        if not due_text:
            continue
        try:
            due_date = datetime.strptime(due_text.replace("/", "-"), "%Y-%m-%d").date()
        except Exception:
            invalid_due_count += 1
            _record_invalid_due(
                batch_id=str(batch_id),
                due_text=due_text,
                invalid_due_ids_sample=invalid_due_ids_sample,
                invalid_due_raw_sample=invalid_due_raw_sample,
            )
            continue

        finish_time = finish_by_batch.get(str(batch_id))
        if finish_time is None or finish_time < due_exclusive_fn(due_date):
            continue
        overdue_items.append(
            {
                "batch_id": batch_id,
                "due_date": due_text,
                "finish_time": svc._format_dt(finish_time),
            }
        )

    if invalid_due_count > 0:
        sample_ids = "，".join(invalid_due_ids_sample[:10])
        message = f"存在 {invalid_due_count} 个批次交期写法不对，已忽略超期判断（示例批次：{sample_ids}）"
        warning_appended = append_summary_warning_fn(summary, message)
        logger = getattr(svc, "logger", None)
        if logger is not None:
            raw_sample = "；".join(invalid_due_raw_sample[:5])
            detail = f"{message}；示例原始交期：{raw_sample}"
            if not warning_appended:
                detail += "；且 summary.warnings 追加失败"
            logger.warning(detail)

    return overdue_items, {
        "invalid_due_count": int(invalid_due_count),
        "invalid_due_batch_ids_sample": list(invalid_due_ids_sample),
        "invalid_due_raw_sample": list(invalid_due_raw_sample),
    }


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


def _safe_metrics_dict(metrics: Any) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    if metrics is None:
        return None, None
    try:
        return metrics.to_dict(), None
    except Exception as exc:
        return None, {
            "parse_failed": True,
            "error_type": type(exc).__name__,
            "message": _OPTIMIZER_METRICS_INVALID_WARNING,
            "detail": str(exc)[:300],
        }


def _parse_summary_count(value: Any, *, field: str) -> Tuple[int, Optional[str]]:
    if value is None or value == "":
        return 0, None
    if isinstance(value, bool):
        return 0, f"{field} 不能是布尔值：{value!r}"
    try:
        if isinstance(value, float):
            if not math.isfinite(value) or not value.is_integer():
                return 0, f"{field} 必须是非负整数：{value!r}"
            number = int(value)
        else:
            text = str(value).strip()
            if not text:
                return 0, None
            if "." in text:
                fv = float(text)
                if not math.isfinite(fv) or not fv.is_integer():
                    return 0, f"{field} 必须是非负整数：{value!r}"
                number = int(fv)
            else:
                number = int(text)
    except Exception:
        return 0, f"{field} 必须是非负整数：{value!r}"
    if number < 0:
        return 0, f"{field} 不能为负数：{value!r}"
    return number, None


def _graph_analysis_summary_warning(ctx: SummaryBuildContext) -> Optional[str]:
    public = ctx.graph_analysis_public if isinstance(ctx.graph_analysis_public, dict) else None
    if not public:
        return None
    status = str(public.get("status") or "").strip().lower()
    if not status or status == "available":
        return None
    reason = str(public.get("reason") or "").strip()
    message = str(public.get("message") or "").strip()
    detail = message or reason or status
    return f"工序图分析没有生成可用报告：{detail}"


def _algo_dict(state: AlgorithmSummaryState) -> Dict[str, Any]:
    ctx = state.ctx
    auto_assign_enabled = bool(state.downtime_state.get("auto_assign_enabled"))
    metrics_dict, metrics_state = _safe_metrics_dict(ctx.best_metrics)
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
        "downtime_avoid": _algo_downtime_dict(
            auto_assign_enabled=auto_assign_enabled, downtime_state=state.downtime_state
        ),
        "input_contract": _algo_input_contract_dict(state.input_state),
        "merge_context_degraded": bool(state.warning_state.merge_context_degraded),
        "merge_context_events": list(state.warning_state.merge_context_events),
        "freeze_window": _algo_freeze_window_dict(state),
    }
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
    if state.fallback_state.fallback_counts:
        algo["fallback_counts"] = dict(state.fallback_state.fallback_counts)
    if state.fallback_state.fallback_samples:
        algo["fallback_samples"] = dict(state.fallback_state.fallback_samples)
    if state.fallback_state.param_fallbacks:
        algo["param_fallbacks"] = dict(state.fallback_state.param_fallbacks)
    if state.fallback_state.fallback_count_parse_errors:
        algo["fallback_count_parse_failed"] = True
        algo["fallback_count_parse_errors"] = list(state.fallback_state.fallback_count_parse_errors[:10])
    algo.update(_graph_analysis_algo_dict(ctx))
    algo.update(_candidate_comparison_algo_dict(ctx))
    return algo


def _append_warning_once(warnings: List[str], message: str) -> None:
    if message not in warnings:
        warnings.append(message)


def _record_summary_degradation(
    *,
    events: List[Dict[str, Any]],
    counters: Dict[str, Any],
    causes: List[str],
    code: str,
    scope: str,
    field: str,
    message: str,
    count: int,
) -> None:
    events.append(
        {
            "code": code,
            "scope": scope,
            "field": field,
            "message": message,
            "count": int(count),
        }
    )
    counters[code] = int(counters.get(code) or 0) + int(count)
    if code not in causes:
        causes.append(code)


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
    public_error_details = build_public_error_records(raw_summary_errors)
    public_error_messages = [str(item.get("message") or "") for item in public_error_details if item.get("message")]
    missing_resource_ops = missing_internal_resource_samples(
        ctx.operations,
        _actionable_missing_internal_resource_op_ids(ctx),
    )
    public_algo, optimizer_diagnostics = project_public_algo_summary(_algo_dict(algorithm_state))
    warnings = list(freeze_state.all_warnings)
    graph_warning = _graph_analysis_summary_warning(ctx)
    if graph_warning and graph_warning not in warnings:
        warnings.append(graph_warning)
    degradation_events = list(summary_degradation.get("events") or [])
    degradation_counters = dict(summary_degradation.get("counters") or {})
    result_degraded_causes = list(degraded_causes or [])
    result_degraded_success = bool(degraded_success)

    metrics_state = public_algo.get("metrics_state") if isinstance(public_algo, dict) else None
    if isinstance(metrics_state, dict) and metrics_state.get("parse_failed"):
        _append_warning_once(warnings, _OPTIMIZER_METRICS_INVALID_WARNING)
        _record_summary_degradation(
            events=degradation_events,
            counters=degradation_counters,
            causes=result_degraded_causes,
            code="optimizer_metrics_invalid",
            scope="schedule.summary.metrics",
            field="metrics",
            message=_OPTIMIZER_METRICS_INVALID_WARNING,
            count=1,
        )
        result_degraded_success = bool(result_degraded_success or str(completion_status or "") == "success")

    fallback_parse_errors = list(getattr(fallback_state, "fallback_count_parse_errors", []) or [])
    if fallback_parse_errors:
        _append_warning_once(warnings, _FALLBACK_COUNT_PARSE_WARNING)
        _record_summary_degradation(
            events=degradation_events,
            counters=degradation_counters,
            causes=result_degraded_causes,
            code="fallback_count_parse_failed",
            scope="schedule.summary.fallback_counts",
            field="fallback_counts",
            message=_FALLBACK_COUNT_PARSE_WARNING,
            count=len(fallback_parse_errors),
        )
        result_degraded_success = bool(result_degraded_success or str(completion_status or "") == "success")

    op_count, op_count_error = _parse_summary_count(getattr(ctx.summary, "total_ops", 0), field="total_ops")
    scheduled_ops, scheduled_ops_error = _parse_summary_count(
        getattr(ctx.summary, "scheduled_ops", 0),
        field="scheduled_ops",
    )
    failed_ops, failed_ops_error = _parse_summary_count(getattr(ctx.summary, "failed_ops", 0), field="failed_ops")
    summary_count_errors = [item for item in (op_count_error, scheduled_ops_error, failed_ops_error) if item]
    if summary_count_errors:
        _append_warning_once(warnings, _SUMMARY_COUNT_PARSE_WARNING)
        _record_summary_degradation(
            events=degradation_events,
            counters=degradation_counters,
            causes=result_degraded_causes,
            code="summary_count_parse_failed",
            scope="schedule.summary.counts",
            field="counts",
            message=_SUMMARY_COUNT_PARSE_WARNING,
            count=len(summary_count_errors),
        )
        result_degraded_success = bool(result_degraded_success or str(completion_status or "") == "success")

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
        "error_count": len(raw_summary_errors),
        "errors": public_error_messages,
        "errors_sample": public_error_messages[:10],
        "public_error_details": public_error_details,
        "raw_error_count": len(raw_summary_errors),
        "missing_internal_resource_count": len(missing_resource_ops),
        "missing_internal_resource_ops": missing_resource_ops,
        "warnings": warnings,
        "time_cost_ms": int(time_cost_ms),
    }
    if summary_count_errors:
        result_summary["summary_count_parse_failed"] = True
        result_summary["summary_count_parse_errors"] = summary_count_errors[:10]
        errors_sample = list(result_summary.get("errors_sample") or [])
        for err in summary_count_errors[:10]:
            if err not in errors_sample:
                errors_sample.append(err)
        result_summary["errors_sample"] = errors_sample
        result_summary["error_count"] = max(int(result_summary.get("error_count") or 0), len(errors_sample), len(summary_count_errors))
    diagnostics = dict(optimizer_diagnostics or {})
    if ctx.graph_analysis_diagnostics is not None:
        diagnostics["graph_analysis"] = dict(ctx.graph_analysis_diagnostics)
    if diagnostics:
        result_summary["diagnostics"] = diagnostics
    return result_summary
