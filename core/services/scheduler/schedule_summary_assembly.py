from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from core.models.enums import YesNo

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
    *,
    freeze_state: Dict[str, Any],
    frozen_op_ids: Set[int],
    frozen_batch_ids: List[str],
) -> Dict[str, Any]:
    freeze_window = {
        "enabled": YesNo.YES.value if bool(freeze_state.get("enabled")) else YesNo.NO.value,
        "days": int(freeze_state.get("days") or 0),
        "frozen_op_count": int(len(frozen_op_ids)),
        "frozen_batch_count": int(len(frozen_batch_ids)),
        "frozen_batch_ids_sample": frozen_batch_ids[:20],
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


def _algo_dict(
    *,
    cfg: Any,
    algo_mode: str,
    objective_name: str,
    time_budget_seconds: int,
    best_score: Optional[Tuple[float, ...]],
    best_metrics: Optional[Any],
    best_order: List[str],
    attempts: List[Dict[str, Any]],
    improvement_trace: List[Dict[str, Any]],
    hard_constraints: List[str],
    downtime_state: Dict[str, Any],
    input_state: Dict[str, Any],
    merge_context_degraded: bool,
    merge_context_events: List[Dict[str, Any]],
    freeze_state: Dict[str, Any],
    frozen_op_ids: Set[int],
    frozen_batch_ids: List[str],
    resource_pool_meta: Optional[Dict[str, Any]],
    resource_pool_enabled: bool,
    resource_pool_degraded: bool,
    resource_pool_degradation_reason: Optional[str],
    resource_pool_attempted: bool,
    warning_pipeline: Dict[str, Any],
    summary_warnings: List[str],
    algo_warning_list: List[str],
    fallback_counts: Dict[str, int],
    param_fallbacks: Dict[str, int],
) -> Dict[str, Any]:
    auto_assign_enabled = bool(downtime_state.get("auto_assign_enabled"))
    algo: Dict[str, Any] = {
        "mode": algo_mode,
        "objective": objective_name,
        "comparison_metric": _comparison_metric(objective_name),
        "config_snapshot": _config_snapshot_dict(cfg),
        "time_budget_seconds": int(time_budget_seconds),
        "hard_constraints": list(hard_constraints),
        "soft_objectives": [objective_name],
        "best_score": list(best_score) if best_score is not None else None,
        "best_score_schema": _best_score_schema(objective_name),
        "metrics": best_metrics.to_dict() if best_metrics is not None else None,
        "best_batch_order": list(best_order or []),
        "attempts": list(attempts or [])[:12],
        "improvement_trace": list(improvement_trace or [])[:200],
        "downtime_avoid": _algo_downtime_dict(auto_assign_enabled=auto_assign_enabled, downtime_state=downtime_state),
        "input_contract": _algo_input_contract_dict(input_state),
        "merge_context_degraded": bool(merge_context_degraded),
        "merge_context_events": list(merge_context_events),
        "freeze_window": _algo_freeze_window_dict(
            freeze_state=freeze_state,
            frozen_op_ids=frozen_op_ids,
            frozen_batch_ids=frozen_batch_ids,
        ),
    }
    if resource_pool_enabled or (isinstance(resource_pool_meta, dict) and bool(resource_pool_meta)):
        algo["resource_pool"] = _algo_resource_pool_dict(
            cfg,
            resource_pool_attempted=resource_pool_attempted,
            resource_pool_degraded=resource_pool_degraded,
            resource_pool_degradation_reason=resource_pool_degradation_reason,
            resource_pool_enabled=resource_pool_enabled,
        )
    if algo_warning_list or any(bool(value) for value in warning_pipeline.values()):
        algo["warning_pipeline"] = _algo_warning_pipeline_dict(
            summary_warnings=summary_warnings,
            algo_warning_list=algo_warning_list,
            warning_pipeline=warning_pipeline,
        )
    if fallback_counts:
        algo["fallback_counts"] = dict(fallback_counts)
    if param_fallbacks:
        algo["param_fallbacks"] = dict(param_fallbacks)
    return algo


def _build_result_summary_obj(
    svc,
    *,
    cfg: Any,
    version: int,
    normalized_batch_ids: List[str],
    start_dt: datetime,
    end_date: Optional[Any],
    batches: Dict[str, Any],
    summary: Any,
    used_strategy: Any,
    used_params: Dict[str, Any],
    algo_mode: str,
    objective_name: str,
    time_budget_seconds: int,
    best_score: Optional[Tuple[float, ...]],
    best_metrics: Optional[Any],
    best_order: List[str],
    attempts: List[Dict[str, Any]],
    improvement_trace: List[Dict[str, Any]],
    frozen_op_ids: Set[int],
    frozen_batch_ids: List[str],
    freeze_state: Dict[str, Any],
    input_state: Dict[str, Any],
    merge_context_degraded: bool,
    merge_context_events: List[Dict[str, Any]],
    downtime_state: Dict[str, Any],
    hard_constraints: List[str],
    resource_pool_meta: Optional[Dict[str, Any]],
    resource_pool_enabled: bool,
    resource_pool_degraded: bool,
    resource_pool_degradation_reason: Optional[str],
    resource_pool_attempted: bool,
    warning_pipeline: Dict[str, Any],
    summary_warnings: List[str],
    algo_warning_list: List[str],
    fallback_counts: Dict[str, int],
    param_fallbacks: Dict[str, int],
    invalid_due_count: int,
    invalid_due_batch_ids_sample: List[str],
    unscheduled_batch_count: int,
    unscheduled_batch_ids_sample: List[str],
    legacy_external_days_defaulted_count: int,
    summary_degradation: Dict[str, Any],
    overdue_items: List[Dict[str, Any]],
    all_warnings: List[str],
    time_cost_ms: int,
    simulate: bool,
    serialize_end_date_fn: Callable[[Optional[Any]], Optional[str]],
) -> Dict[str, Any]:
    return {
        "summary_schema_version": "1.1",
        "is_simulation": bool(simulate),
        "version": int(version),
        "strategy": used_strategy.value,
        "strategy_params": used_params or {},
        "algo": _algo_dict(
            cfg=cfg,
            algo_mode=algo_mode,
            objective_name=objective_name,
            time_budget_seconds=int(time_budget_seconds),
            best_score=best_score,
            best_metrics=best_metrics,
            best_order=best_order,
            attempts=attempts,
            improvement_trace=improvement_trace,
            hard_constraints=hard_constraints,
            downtime_state=downtime_state,
            input_state=input_state,
            merge_context_degraded=bool(merge_context_degraded),
            merge_context_events=merge_context_events,
            freeze_state=freeze_state,
            frozen_op_ids=frozen_op_ids,
            frozen_batch_ids=frozen_batch_ids,
            resource_pool_meta=resource_pool_meta,
            resource_pool_enabled=bool(resource_pool_enabled),
            resource_pool_degraded=bool(resource_pool_degraded),
            resource_pool_degradation_reason=resource_pool_degradation_reason,
            resource_pool_attempted=bool(resource_pool_attempted),
            warning_pipeline=warning_pipeline,
            summary_warnings=summary_warnings,
            algo_warning_list=algo_warning_list,
            fallback_counts=fallback_counts,
            param_fallbacks=param_fallbacks,
        ),
        "selected_batch_ids": list(normalized_batch_ids),
        "start_time": svc._format_dt(start_dt),
        "end_date": serialize_end_date_fn(end_date),
        "invalid_due_count": int(invalid_due_count),
        "invalid_due_batch_ids_sample": list(invalid_due_batch_ids_sample[:10]),
        "unscheduled_batch_count": int(unscheduled_batch_count),
        "unscheduled_batch_ids_sample": list(unscheduled_batch_ids_sample[:20]),
        "legacy_external_days_defaulted_count": int(legacy_external_days_defaulted_count),
        "degradation_events": list(summary_degradation.get("events") or []),
        "degradation_counters": dict(summary_degradation.get("counters") or {}),
        "counts": {
            "batch_count": len(batches),
            "op_count": int(getattr(summary, "total_ops", 0)),
            "scheduled_ops": int(getattr(summary, "scheduled_ops", 0)),
            "failed_ops": int(getattr(summary, "failed_ops", 0)),
            "unscheduled_batch_count": int(unscheduled_batch_count),
        },
        "overdue_batches": {"count": len(overdue_items), "items": overdue_items},
        "errors_sample": (getattr(summary, "errors", None) or [])[:10],
        "warnings": list(all_warnings),
        "time_cost_ms": int(time_cost_ms),
    }
