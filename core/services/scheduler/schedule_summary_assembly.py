from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.models.enums import YesNo

from .schedule_summary_types import (
    AlgorithmSummaryState,
    FallbackState,
    FreezeState,
    RuntimeState,
    SummaryBuildContext,
)

_CONFIG_SNAPSHOT_KEYS = (
    "sort_strategy",
    "priority_weight",
    "due_weight",
    "ready_weight",
    "holiday_default_efficiency",
    "enforce_ready_default",
    "prefer_primary_skill",
    "dispatch_mode",
    "dispatch_rule",
    "auto_assign_enabled",
    "ortools_enabled",
    "ortools_time_limit_seconds",
    "algo_mode",
    "time_budget_seconds",
    "objective",
    "freeze_window_enabled",
    "freeze_window_days",
)

_COMPARISON_METRICS = {
    "min_tardiness": "total_tardiness_hours",
    "min_weighted_tardiness": "weighted_tardiness_hours",
    "min_changeover": "changeover_count",
}

_BEST_SCORE_SCHEMA_PARTS: Dict[str, List[Tuple[str, str]]] = {
    "min_tardiness": [
        ("failed_ops", "失败工序数"),
        ("total_tardiness_hours", "总拖期小时"),
        ("overdue_count", "超期批次数"),
        ("makespan_hours", "总工期小时"),
        ("changeover_count", "换型次数"),
    ],
    "min_weighted_tardiness": [
        ("failed_ops", "失败工序数"),
        ("weighted_tardiness_hours", "加权拖期小时"),
        ("overdue_count", "超期批次数"),
        ("total_tardiness_hours", "总拖期小时"),
        ("makespan_hours", "总工期小时"),
        ("changeover_count", "换型次数"),
    ],
    "min_changeover": [
        ("failed_ops", "失败工序数"),
        ("changeover_count", "换型次数"),
        ("overdue_count", "超期批次数"),
        ("total_tardiness_hours", "总拖期小时"),
        ("makespan_hours", "总工期小时"),
    ],
    "min_overdue": [
        ("failed_ops", "失败工序数"),
        ("overdue_count", "超期批次数"),
        ("total_tardiness_hours", "总拖期小时"),
        ("makespan_hours", "总工期小时"),
        ("changeover_count", "换型次数"),
    ],
}


def _cfg_value(cfg: Any, key: str, default: Any = None) -> Any:
    from core.algorithms.greedy.config_adapter import cfg_get

    return cfg_get(cfg, key, default)


def _config_snapshot_dict(cfg: Any) -> Dict[str, Any]:
    if cfg is None:
        return {}
    if isinstance(cfg, dict):
        return dict(cfg)

    to_dict = getattr(cfg, "to_dict", None)
    if callable(to_dict):
        obj = to_dict()
        if isinstance(obj, dict):
            return dict(obj)

    out: Dict[str, Any] = {}
    for key in _CONFIG_SNAPSHOT_KEYS:
        if not hasattr(cfg, key):
            continue
        value = getattr(cfg, key)
        if value is None:
            continue
        out[key] = value if isinstance(value, (str, int, float, bool)) else str(value)
    return out


def _comparison_metric(objective_name: str) -> str:
    obj = str(objective_name or "min_overdue").strip().lower()
    return _COMPARISON_METRICS.get(obj, "overdue_count")


def _best_score_schema(objective_name: str) -> List[Dict[str, Any]]:
    obj = str(objective_name or "min_overdue").strip().lower()
    parts = _BEST_SCORE_SCHEMA_PARTS.get(obj, _BEST_SCORE_SCHEMA_PARTS["min_overdue"])
    return [{"index": int(idx), "key": key, "label": label} for idx, (key, label) in enumerate(parts)]


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
        message = f"存在 {invalid_due_count} 个批次 due_date 格式不合法，已忽略超期判断（示例批次：{sample_ids}）"
        warning_appended = append_summary_warning_fn(summary, message)
        logger = getattr(svc, "logger", None)
        if logger is not None:
            raw_sample = "；".join(invalid_due_raw_sample[:5])
            detail = f"{message}；示例原始 due_date：{raw_sample}"
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
        "extend_partial_fail_count": int(downtime_state.get("extend_partial_fail_count") or 0) if auto_assign_enabled else 0,
        "extend_partial_fail_machines_sample": list(downtime_state.get("extend_partial_fail_machines_sample") or []) if auto_assign_enabled else [],
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
    expose_state = bool(freeze_state.get("freeze_applied")) or bool(freeze_window["degraded"]) or bool(
        freeze_state.get("freeze_degradation_codes")
    )
    if expose_state:
        freeze_window["freeze_state"] = freeze_state.get("freeze_state")
        freeze_window["freeze_applied"] = bool(freeze_state.get("freeze_applied"))
        freeze_window["freeze_degradation_codes"] = list(freeze_state.get("freeze_degradation_codes") or [])
    return freeze_window


def _algo_resource_pool_dict(
    cfg: Any,
    *,
    resource_pool_attempted: bool,
    resource_pool_degraded: bool,
    resource_pool_degradation_reason: Optional[str],
    resource_pool_enabled: bool,
) -> Dict[str, Any]:
    return {
        "enabled": _cfg_value(cfg, "auto_assign_enabled", "no"),
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
    return {
        "algo_warning_count": int(len(algo_warning_list)),
        "summary_warning_count": int(len(summary_warnings)),
        "summary_merge_attempted": bool(warning_pipeline.get("summary_merge_attempted") or False),
        "summary_merge_failed": bool(warning_pipeline.get("summary_merge_failed") or False),
        "summary_merge_error": warning_pipeline.get("summary_merge_error"),
    }


def _algo_dict(state: AlgorithmSummaryState) -> Dict[str, Any]:
    ctx = state.ctx
    auto_assign_enabled = bool(state.downtime_state.get("auto_assign_enabled"))
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
        "metrics": ctx.best_metrics.to_dict() if ctx.best_metrics is not None else None,
        "best_batch_order": list(ctx.best_order or []),
        "attempts": list(ctx.attempts or [])[:12],
        "improvement_trace": list(ctx.improvement_trace or [])[:200],
        "downtime_avoid": _algo_downtime_dict(auto_assign_enabled=auto_assign_enabled, downtime_state=state.downtime_state),
        "input_contract": _algo_input_contract_dict(state.input_state),
        "merge_context_degraded": bool(state.warning_state.merge_context_degraded),
        "merge_context_events": list(state.warning_state.merge_context_events),
        "freeze_window": _algo_freeze_window_dict(state),
    }
    if state.resource_pool_enabled or (isinstance(state.resource_pool_meta, dict) and bool(state.resource_pool_meta)):
        algo["resource_pool"] = _algo_resource_pool_dict(
            ctx.cfg,
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
    if state.fallback_state.param_fallbacks:
        algo["param_fallbacks"] = dict(state.fallback_state.param_fallbacks)
    return algo


def _build_result_summary_obj(
    svc,
    *,
    ctx: SummaryBuildContext,
    runtime_state: RuntimeState,
    freeze_state: FreezeState,
    fallback_state: FallbackState,
    algorithm_state: AlgorithmSummaryState,
    summary_degradation: Dict[str, Any],
    time_cost_ms: int,
    serialize_end_date_fn: Callable[[Optional[Any]], Optional[str]],
) -> Dict[str, Any]:
    return {
        "summary_schema_version": "1.1",
        "is_simulation": bool(ctx.simulate),
        "version": int(ctx.version),
        "strategy": ctx.used_strategy.value,
        "strategy_params": ctx.used_params or {},
        "algo": _algo_dict(algorithm_state),
        "selected_batch_ids": list(ctx.normalized_batch_ids),
        "start_time": svc._format_dt(ctx.start_dt),
        "end_date": serialize_end_date_fn(ctx.end_date),
        "invalid_due_count": int(runtime_state.invalid_due_count),
        "invalid_due_batch_ids_sample": list(runtime_state.invalid_due_batch_ids_sample[:10]),
        "unscheduled_batch_count": int(runtime_state.unscheduled_batch_count),
        "unscheduled_batch_ids_sample": list(runtime_state.unscheduled_batch_ids_sample[:20]),
        "legacy_external_days_defaulted_count": int(fallback_state.legacy_external_days_defaulted_count),
        "degradation_events": list(summary_degradation.get("events") or []),
        "degradation_counters": dict(summary_degradation.get("counters") or {}),
        "counts": {
            "batch_count": len(ctx.batches),
            "op_count": int(getattr(ctx.summary, "total_ops", 0)),
            "scheduled_ops": int(getattr(ctx.summary, "scheduled_ops", 0)),
            "failed_ops": int(getattr(ctx.summary, "failed_ops", 0)),
            "unscheduled_batch_count": int(runtime_state.unscheduled_batch_count),
        },
        "overdue_batches": {"count": len(runtime_state.overdue_items), "items": runtime_state.overdue_items},
        "errors_sample": (getattr(ctx.summary, "errors", None) or [])[:10],
        "warnings": list(freeze_state.all_warnings),
        "time_cost_ms": int(time_cost_ms),
    }
