from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from core.services.common.build_outcome import BuildOutcome

from .schedule_summary_assembly import (
    _best_score_schema as best_score_schema,
)
from .schedule_summary_assembly import (
    _build_overdue_items as _build_overdue_items_impl,
)
from .schedule_summary_assembly import (
    _build_result_summary_obj,
)
from .schedule_summary_assembly import (
    _cfg_value as cfg_value,
)
from .schedule_summary_assembly import (
    _comparison_metric as comparison_metric,
)
from .schedule_summary_assembly import (
    _config_snapshot_dict as config_snapshot_dict,
)
from .schedule_summary_assembly import (
    _finish_time_by_batch as finish_time_by_batch,
)
from .schedule_summary_degradation import (
    _compute_downtime_degradation,
    _compute_resource_pool_degradation,
    _hard_constraints,
    _input_build_state,
    _metric_int,
    _metric_sample,
    _summary_degradation_state,
)
from .schedule_summary_freeze import (
    _compute_result_status,
    _extract_freeze_warnings,
    _freeze_meta_dict,
    _frozen_batch_ids,
)

__all__ = [
    "SUMMARY_SIZE_LIMIT_BYTES",
    "apply_summary_size_guard",
    "best_score_schema",
    "build_overdue_items",
    "cfg_value",
    "comparison_metric",
    "config_snapshot_dict",
    "due_exclusive",
    "finish_time_by_batch",
    "serialize_end_date",
    "build_result_summary",
]

SUMMARY_SIZE_LIMIT_BYTES = 512 * 1024



def serialize_end_date(end_date: Optional[Any]) -> Optional[str]:
    if end_date is None:
        return None
    if isinstance(end_date, str):
        text = end_date.strip()
        return text if text else None
    try:
        isoformat = getattr(end_date, "isoformat", None)
        if callable(isoformat):
            return str(isoformat())
    except Exception:
        pass
    text = str(end_date).strip()
    return text if text else None


def due_exclusive(due_date) -> datetime:
    if not due_date:
        return datetime.max
    return datetime(due_date.year, due_date.month, due_date.day) + timedelta(days=1)


def _warning_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = [value]
    elif isinstance(value, dict):
        raw_items = [value]
    elif isinstance(value, list):
        raw_items = value
    elif isinstance(value, tuple):
        raw_items = list(value)
    else:
        try:
            raw_items = list(value)
        except Exception:
            raw_items = [value]

    out: List[str] = []
    for item in raw_items:
        try:
            text = str(item)
        except Exception:
            continue
        if text:
            out.append(text)
    return out


def _merge_warning_lists(primary: Any, extra: Any) -> List[str]:
    merged = _warning_list(primary)
    seen = set(merged)
    for text in _warning_list(extra):
        if text in seen:
            continue
        seen.add(text)
        merged.append(text)
    return merged


def _append_summary_warning(summary: Any, message: str) -> bool:
    if isinstance(summary, dict):
        warnings = _warning_list(summary.get("warnings"))
        warnings.append(message)
        summary["warnings"] = warnings
        return True

    warnings = getattr(summary, "warnings", None)
    if isinstance(warnings, list):
        warnings.append(message)
        return True

    normalized_warnings = _warning_list(warnings)
    normalized_warnings.append(message)
    try:
        summary.warnings = normalized_warnings
        return True
    except Exception:
        return False


def _counter_dict(value: Any) -> Dict[str, int]:
    if not isinstance(value, dict):
        return {}
    out: Dict[str, int] = {}
    for key, raw in value.items():
        try:
            count = int(raw)
        except Exception:
            continue
        if count != 0:
            out[str(key)] = int(count)
    return out


def _summary_size_bytes(obj: Dict[str, Any]) -> int:
    return len(json.dumps(obj, ensure_ascii=False).encode("utf-8"))


def apply_summary_size_guard(result_summary_obj: Dict[str, Any]) -> Dict[str, Any]:
    original_size = _summary_size_bytes(result_summary_obj)
    if original_size <= SUMMARY_SIZE_LIMIT_BYTES:
        return result_summary_obj

    algo = result_summary_obj.get("algo")
    algo_dict = algo if isinstance(algo, dict) else {}
    trace = algo_dict.get("improvement_trace")
    warnings = result_summary_obj.get("warnings")
    attempts = algo_dict.get("attempts")
    best_batch_order = algo_dict.get("best_batch_order")
    selected_batch_ids = result_summary_obj.get("selected_batch_ids")
    overdue_batches = result_summary_obj.get("overdue_batches")
    overdue_items = overdue_batches.get("items") if isinstance(overdue_batches, dict) else None

    def _trim_trace(limit: int) -> None:
        if isinstance(trace, list):
            algo_dict["improvement_trace"] = trace[:limit]

    def _trim_warnings(limit: int) -> None:
        if isinstance(warnings, list):
            result_summary_obj["warnings"] = warnings[:limit]

    def _trim_attempts(limit: int) -> None:
        if isinstance(attempts, list):
            algo_dict["attempts"] = attempts[:limit]

    def _trim_best_batch_order(limit: int) -> None:
        if isinstance(best_batch_order, list):
            algo_dict["best_batch_order"] = best_batch_order[:limit]

    def _trim_selected_batch_ids(limit: int) -> None:
        if isinstance(selected_batch_ids, list):
            result_summary_obj["selected_batch_ids"] = selected_batch_ids[:limit]

    def _trim_overdue_items(limit: int) -> None:
        if isinstance(overdue_batches, dict) and isinstance(overdue_items, list):
            overdue_batches["items"] = overdue_items[:limit]

    for trace_limit, warning_limit, attempt_limit, best_order_limit, selected_ids_limit, overdue_items_limit in (
        (80, 50, 12, None, None, None),
        (20, 20, 12, None, None, None),
        (0, 20, 12, None, None, None),
        (0, 10, 6, None, None, None),
        (0, 0, 6, 2000, 2000, 500),
        (0, 0, 6, 500, 1000, 200),
        (0, 0, 6, 100, 200, 50),
        (0, 0, 6, 0, 50, 20),
        (0, 0, 0, 0, 0, 0),
    ):
        _trim_trace(trace_limit)
        _trim_warnings(warning_limit)
        _trim_attempts(attempt_limit)
        if best_order_limit is not None:
            _trim_best_batch_order(best_order_limit)
        if selected_ids_limit is not None:
            _trim_selected_batch_ids(selected_ids_limit)
        if overdue_items_limit is not None:
            _trim_overdue_items(overdue_items_limit)
        result_summary_obj["summary_truncated"] = True
        result_summary_obj["original_size_bytes"] = int(original_size)
        if _summary_size_bytes(result_summary_obj) <= SUMMARY_SIZE_LIMIT_BYTES:
            return result_summary_obj

    return result_summary_obj


def build_overdue_items(
    svc,
    *,
    batches: Dict[str, Any],
    finish_by_batch: Dict[str, datetime],
    summary: Any,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    return _build_overdue_items_impl(
        svc,
        batches=batches,
        finish_by_batch=finish_by_batch,
        summary=summary,
        due_exclusive_fn=due_exclusive,
        append_summary_warning_fn=_append_summary_warning,
    )


def _build_runtime_state(
    *,
    svc,
    batches: Dict[str, Any],
    results: List[Any],
    summary: Any,
    best_metrics: Optional[Any],
) -> Dict[str, Any]:
    finish_by_batch = finish_time_by_batch(results)
    overdue_items, overdue_meta = build_overdue_items(svc, batches=batches, finish_by_batch=finish_by_batch, summary=summary)
    invalid_due_count = _metric_int(best_metrics, "invalid_due_count") or int(overdue_meta.get("invalid_due_count") or 0)
    invalid_due_batch_ids_sample = _metric_sample(best_metrics, "invalid_due_batch_ids_sample", limit=10) or list(
        overdue_meta.get("invalid_due_batch_ids_sample") or []
    )
    unscheduled_batch_ids_all = [
        str(batch_id).strip()
        for batch_id in sorted(batches.keys(), key=lambda item: str(item).strip())
        if str(batch_id).strip() and str(batch_id).strip() not in finish_by_batch
    ]
    unscheduled_batch_count = _metric_int(best_metrics, "unscheduled_batch_count") or int(len(unscheduled_batch_ids_all))
    unscheduled_batch_ids_sample = _metric_sample(best_metrics, "unscheduled_batch_ids_sample", limit=20) or list(
        unscheduled_batch_ids_all[:20]
    )
    return {
        "finish_by_batch": finish_by_batch,
        "overdue_items": overdue_items,
        "invalid_due_count": int(invalid_due_count),
        "invalid_due_batch_ids_sample": list(invalid_due_batch_ids_sample),
        "unscheduled_batch_count": int(unscheduled_batch_count),
        "unscheduled_batch_ids_sample": list(unscheduled_batch_ids_sample),
    }


def _build_warning_state(
    *,
    summary: Any,
    algo_warnings: Optional[List[str]],
    input_state: Dict[str, Any],
    runtime_state: Dict[str, Any],
) -> Dict[str, Any]:
    summary_warnings = _warning_list(getattr(summary, "warnings", None))
    algo_warning_list = _warning_list(algo_warnings)
    all_warnings = _merge_warning_lists(summary_warnings, algo_warning_list)
    merge_context_degraded = bool(input_state.get("merge_context_degraded"))
    merge_context_events = list(input_state.get("merge_context_events") or [])
    if merge_context_degraded:
        all_warnings = _merge_warning_lists(
            all_warnings,
            ["组合并语义已退化：部分外协工序缺少模板或外部组，已按逐道外协语义继续排产。"],
        )
    if int(runtime_state.get("unscheduled_batch_count") or 0) > 0:
        sample_text = "、".join(list(runtime_state.get("unscheduled_batch_ids_sample") or [])[:10])
        all_warnings = _merge_warning_lists(
            all_warnings,
            [f"存在 {int(runtime_state.get('unscheduled_batch_count') or 0)} 个批次未形成完工结果（示例批次：{sample_text}）。"],
        )
    return {
        "summary_warnings": summary_warnings,
        "algo_warning_list": algo_warning_list,
        "all_warnings": all_warnings,
        "merge_context_degraded": merge_context_degraded,
        "merge_context_events": merge_context_events,
    }


def _build_freeze_state(
    *,
    cfg: Any,
    frozen_op_ids: Set[int],
    freeze_meta: Optional[Dict[str, Any]],
    all_warnings: List[str],
) -> Tuple[Dict[str, Any], List[str]]:
    freeze_warnings = _extract_freeze_warnings(all_warnings)
    freeze_state = _freeze_meta_dict(
        cfg,
        frozen_op_ids=frozen_op_ids,
        freeze_meta=freeze_meta,
        freeze_warnings=freeze_warnings,
    )
    if str(freeze_state.get("freeze_state") or "") == "degraded" and freeze_state.get("degradation_reason"):
        all_warnings = _merge_warning_lists(all_warnings, [f"【冻结窗口】未生效：{freeze_state.get('degradation_reason')}"])
    return freeze_state, all_warnings


def _build_fallback_state(algo_stats: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    algo_stats_dict = algo_stats if isinstance(algo_stats, dict) else {}
    fallback_counts = _counter_dict(algo_stats_dict.get("fallback_counts"))
    param_fallbacks = _counter_dict(algo_stats_dict.get("param_fallbacks"))
    return {
        "warning_pipeline": algo_stats_dict,
        "fallback_counts": fallback_counts,
        "param_fallbacks": param_fallbacks,
        "legacy_external_days_defaulted_count": int(fallback_counts.get("legacy_external_days_defaulted_count") or 0),
        "ortools_warmstart_failed_count": int(fallback_counts.get("ortools_warmstart_failed_count") or 0),
    }


def _merge_fallback_warnings(all_warnings: List[str], fallback_state: Dict[str, Any]) -> List[str]:
    legacy_count = int(fallback_state.get("legacy_external_days_defaulted_count") or 0)
    warmstart_count = int(fallback_state.get("ortools_warmstart_failed_count") or 0)
    if legacy_count > 0:
        all_warnings = _merge_warning_lists(all_warnings, [f"存在 {legacy_count} 道外协工序使用了历史兼容周期 1.0 天。"])
    if warmstart_count > 0:
        all_warnings = _merge_warning_lists(all_warnings, ["OR-Tools 预热失败，已回退到常规求解路径。"])
    return all_warnings


def build_result_summary(
    svc,
    *,
    cfg: Any,
    version: int,
    normalized_batch_ids: List[str],
    start_dt: datetime,
    end_date: Optional[Any],
    batches: Dict[str, Any],
    operations: List[Any],
    results: List[Any],
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
    freeze_meta: Optional[Dict[str, Any]] = None,
    input_build_outcome: Optional[BuildOutcome[Any]] = None,
    downtime_meta: Optional[Dict[str, Any]] = None,
    resource_pool_meta: Optional[Dict[str, Any]] = None,
    algo_stats: Optional[Dict[str, Any]] = None,
    algo_warnings: Optional[List[str]] = None,
    warning_merge_status: Optional[Dict[str, Any]] = None,
    simulate: bool,
    t0: float,
) -> Tuple[List[Dict[str, Any]], str, Dict[str, Any], str, int]:
    runtime_state = _build_runtime_state(svc=svc, batches=batches, results=results, summary=summary, best_metrics=best_metrics)
    result_status = _compute_result_status(summary, simulate=simulate)
    time_cost_ms = int((time.time() - float(t0)) * 1000)
    frozen_batch_ids = _frozen_batch_ids(operations, frozen_op_ids=frozen_op_ids)
    input_state = _input_build_state(input_build_outcome)
    warning_state = _build_warning_state(
        summary=summary,
        algo_warnings=algo_warnings,
        input_state=input_state,
        runtime_state=runtime_state,
    )
    freeze_state, all_warnings = _build_freeze_state(
        cfg=cfg,
        frozen_op_ids=frozen_op_ids,
        freeze_meta=freeze_meta,
        all_warnings=list(warning_state["all_warnings"]),
    )
    downtime_state = _compute_downtime_degradation(cfg, downtime_meta=downtime_meta)
    resource_pool_enabled, resource_pool_degraded, resource_pool_degradation_reason, resource_pool_attempted = _compute_resource_pool_degradation(
        cfg, resource_pool_meta=resource_pool_meta
    )
    hard_constraints = _hard_constraints(
        cfg,
        downtime_degraded=bool(downtime_state.get("downtime_degraded")),
        freeze_state=str(freeze_state.get("freeze_state") or "disabled"),
    )
    fallback_state = _build_fallback_state(algo_stats)
    all_warnings = _merge_fallback_warnings(all_warnings, fallback_state)
    warning_pipeline = warning_merge_status if isinstance(warning_merge_status, dict) else {}
    summary_degradation = _summary_degradation_state(
        input_state=input_state,
        invalid_due_count=runtime_state["invalid_due_count"],
        invalid_due_batch_ids_sample=runtime_state["invalid_due_batch_ids_sample"],
        legacy_external_days_defaulted_count=fallback_state["legacy_external_days_defaulted_count"],
        freeze_state=freeze_state,
        downtime_state=downtime_state,
        resource_pool_enabled=resource_pool_enabled,
        resource_pool_degraded=resource_pool_degraded,
        resource_pool_degradation_reason=resource_pool_degradation_reason,
        ortools_warmstart_failed_count=fallback_state["ortools_warmstart_failed_count"],
    )
    result_summary_obj = _build_result_summary_obj(
        svc,
        cfg=cfg,
        version=version,
        normalized_batch_ids=normalized_batch_ids,
        start_dt=start_dt,
        end_date=end_date,
        batches=batches,
        summary=summary,
        used_strategy=used_strategy,
        used_params=used_params,
        algo_mode=algo_mode,
        objective_name=objective_name,
        time_budget_seconds=time_budget_seconds,
        best_score=best_score,
        best_metrics=best_metrics,
        best_order=best_order,
        attempts=attempts,
        improvement_trace=improvement_trace,
        frozen_op_ids=frozen_op_ids,
        frozen_batch_ids=frozen_batch_ids,
        freeze_state=freeze_state,
        input_state=input_state,
        merge_context_degraded=warning_state["merge_context_degraded"],
        merge_context_events=warning_state["merge_context_events"],
        downtime_state=downtime_state,
        hard_constraints=hard_constraints,
        resource_pool_meta=resource_pool_meta,
        resource_pool_enabled=resource_pool_enabled,
        resource_pool_degraded=resource_pool_degraded,
        resource_pool_degradation_reason=resource_pool_degradation_reason,
        resource_pool_attempted=resource_pool_attempted,
        warning_pipeline=warning_pipeline,
        summary_warnings=warning_state["summary_warnings"],
        algo_warning_list=warning_state["algo_warning_list"],
        fallback_counts=fallback_state["fallback_counts"],
        param_fallbacks=fallback_state["param_fallbacks"],
        invalid_due_count=runtime_state["invalid_due_count"],
        invalid_due_batch_ids_sample=runtime_state["invalid_due_batch_ids_sample"],
        unscheduled_batch_count=runtime_state["unscheduled_batch_count"],
        unscheduled_batch_ids_sample=runtime_state["unscheduled_batch_ids_sample"],
        legacy_external_days_defaulted_count=fallback_state["legacy_external_days_defaulted_count"],
        summary_degradation=summary_degradation,
        overdue_items=runtime_state["overdue_items"],
        all_warnings=all_warnings,
        time_cost_ms=time_cost_ms,
        simulate=simulate,
        serialize_end_date_fn=serialize_end_date,
    )
    result_summary_obj = apply_summary_size_guard(result_summary_obj)
    result_summary_json = json.dumps(result_summary_obj, ensure_ascii=False)
    return runtime_state["overdue_items"], result_status, result_summary_obj, result_summary_json, time_cost_ms
