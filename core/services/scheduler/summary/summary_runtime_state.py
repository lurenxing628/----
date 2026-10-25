from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Set, Tuple

from core.algorithm_contracts.types import ScheduleResult, ScheduleSummary
from core.models.batch import Batch
from core.models.schedule_config_runtime import ScheduleConfigSnapshot
from core.services.scheduler.contracts.schedule_summary_types import (
    FallbackState,
    FreezeState,
    RuntimeState,
    SummaryMetrics,
    WarningState,
)

from .due_risk_items import (
    _build_overdue_items as _build_overdue_items_impl,
)
from .due_risk_items import (
    incomplete_batch_ids_from_failure_details,
)
from .schedule_summary_assembly import (
    _finish_time_by_batch as finish_time_by_batch,
)
from .schedule_summary_freeze import _extract_freeze_warnings, _freeze_meta_dict


def _metric_int(metrics: Any, key: str) -> Optional[int]:
    if metrics is None:
        return None
    raw = getattr(metrics, key, None)
    if raw is None:
        return None
    return max(0, int(raw))


def _metric_sample(metrics: Any, key: str, *, limit: int) -> Optional[List[str]]:
    if metrics is None:
        return None
    raw = getattr(metrics, key, None)
    if not isinstance(raw, (list, tuple)):
        return None
    out: List[str] = []
    for item in raw:
        text = str(item).strip()
        if not text or text in out:
            continue
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _warning_list(value: Optional[List[str]]) -> List[str]:
    out: List[str] = []
    for item in value or []:
        text = str(item)
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


def _dedupe_text_list(values: Any) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in values or []:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _append_summary_warning(summary: Optional[ScheduleSummary], message: str) -> bool:
    if summary is None:
        return False
    summary.warnings.append(message)
    return True


def _parse_counter_value(raw: Any, *, bucket_name: str, key_text: str) -> Tuple[Optional[int], Optional[str]]:
    if raw is None or raw == "":
        return None, None
    if isinstance(raw, bool):
        return None, f"{bucket_name}.{key_text} 不能是布尔值：{raw!r}"
    try:
        if isinstance(raw, int):
            count = raw
        else:
            decimal_value = Decimal(str(raw).strip())
            if not decimal_value.is_finite() or decimal_value != decimal_value.to_integral_value():
                return None, f"{bucket_name}.{key_text} 必须是整数：{raw!r}"
            count = int(decimal_value)
    except (InvalidOperation, TypeError, ValueError):
        return None, f"{bucket_name}.{key_text} 必须是整数：{raw!r}"
    if count < 0:
        return None, f"{bucket_name}.{key_text} 不能为负数：{raw!r}"
    return count, None


def _counter_dict(value: Any, *, bucket_name: str) -> Tuple[Dict[str, int], List[str]]:
    if not isinstance(value, dict):
        return {}, []
    out: Dict[str, int] = {}
    errors: List[str] = []
    for key, raw in value.items():
        key_text = str(key or "").strip()
        if not key_text:
            continue
        count, error = _parse_counter_value(raw, bucket_name=bucket_name, key_text=key_text)
        if error:
            errors.append(error)
        if count:
            out[key_text] = int(count)
    return out, errors


def _build_runtime_state(
    *,
    logger: Any,
    batches: Dict[str, Batch],
    results: List[ScheduleResult],
    summary: Optional[ScheduleSummary],
    best_metrics: Optional[SummaryMetrics],
) -> RuntimeState:
    finish_by_batch = finish_time_by_batch(results)
    # 半途失败批次的 finish 是被截断的部分完工时间，排除出超期/临期分类，
    # 改走 result_summary 的 incomplete_batches 风险清单（audit 2026-07-20 A18）。
    incomplete_batch_ids = incomplete_batch_ids_from_failure_details(
        summary.failure_details if summary is not None else None,
        finish_by_batch,
    )
    overdue_items, overdue_meta = _build_overdue_items_impl(
        logger=logger,
        batches=batches,
        finish_by_batch=finish_by_batch,
        summary=summary,
        append_summary_warning_fn=_append_summary_warning,
        incomplete_batch_ids=incomplete_batch_ids,
    )
    metric_invalid_count = _metric_int(best_metrics, "invalid_due_count")
    invalid_due_count = (
        metric_invalid_count if metric_invalid_count is not None else overdue_meta["invalid_due_count"]
    )
    metric_invalid_sample = _metric_sample(best_metrics, "invalid_due_batch_ids_sample", limit=10)
    invalid_due_batch_ids_sample = (
        metric_invalid_sample
        if metric_invalid_sample is not None
        else overdue_meta["invalid_due_batch_ids_sample"]
    )
    metric_unscheduled_count = _metric_int(best_metrics, "unscheduled_batch_count")
    metric_unscheduled_sample = _metric_sample(best_metrics, "unscheduled_batch_ids_sample", limit=20)
    if metric_unscheduled_count is not None and metric_unscheduled_sample is not None:
        unscheduled_batch_count = metric_unscheduled_count
        unscheduled_batch_ids_sample = metric_unscheduled_sample
    else:
        normalized_batch_ids = [str(batch_id).strip() for batch_id in batches]
        unscheduled_batch_ids_all = [
            batch_id for batch_id in sorted(normalized_batch_ids) if batch_id and batch_id not in finish_by_batch
        ]
        unscheduled_batch_count = (
            metric_unscheduled_count if metric_unscheduled_count is not None else len(unscheduled_batch_ids_all)
        )
        unscheduled_batch_ids_sample = (
            metric_unscheduled_sample if metric_unscheduled_sample is not None else unscheduled_batch_ids_all[:20]
        )
    return RuntimeState(
        finish_by_batch=finish_by_batch,
        overdue_items=overdue_items,
        near_due_items=overdue_meta["near_due_items"],
        invalid_due_count=invalid_due_count,
        invalid_due_batch_ids_sample=invalid_due_batch_ids_sample,
        unscheduled_batch_count=unscheduled_batch_count,
        unscheduled_batch_ids_sample=unscheduled_batch_ids_sample,
        incomplete_batch_ids=incomplete_batch_ids,
    )


def _build_warning_state(
    *,
    summary: Optional[ScheduleSummary],
    algo_warnings: Optional[List[str]],
    input_state: Dict[str, Any],
    runtime_state: RuntimeState,
) -> WarningState:
    summary_warnings = _warning_list(summary.warnings if summary is not None else None)
    algo_warning_list = _warning_list(algo_warnings)
    all_warnings = _merge_warning_lists(summary_warnings, algo_warning_list)
    merge_context_degraded = bool(input_state.get("merge_context_degraded"))
    merge_context_events = list(input_state.get("merge_context_events") or [])
    if runtime_state.unscheduled_batch_count > 0:
        all_warnings = _merge_warning_lists(
            all_warnings,
            [f"存在 {runtime_state.unscheduled_batch_count} 个批次未形成完工结果，请到系统管理里的排产历史查看这次排产的详细提醒。"],
        )
    return WarningState(
        summary_warnings=summary_warnings,
        algo_warning_list=algo_warning_list,
        all_warnings=all_warnings,
        merge_context_degraded=merge_context_degraded,
        merge_context_events=merge_context_events,
    )


def _build_freeze_state(
    *,
    cfg: ScheduleConfigSnapshot,
    frozen_op_ids: Set[int],
    freeze_meta: Optional[Dict[str, Any]],
    all_warnings: List[str],
) -> FreezeState:
    freeze_warnings = _extract_freeze_warnings(all_warnings)
    freeze_data = _freeze_meta_dict(
        cfg,
        frozen_op_ids=frozen_op_ids,
        freeze_meta=freeze_meta,
        freeze_warnings=freeze_warnings,
    )
    merged_warnings = list(all_warnings)
    if (
        freeze_warnings
        and str(freeze_data.get("freeze_state") or "") == "degraded"
        and not bool(freeze_data.get("degradation_from_warning_fallback"))
    ):
        freeze_warning_set = {str(item) for item in freeze_warnings}
        merged_warnings = [item for item in merged_warnings if str(item) not in freeze_warning_set]
    return FreezeState(
        data=freeze_data,
        all_warnings=merged_warnings,
    )


def _build_fallback_state(algo_stats: Optional[Dict[str, Any]]) -> FallbackState:
    algo_stats_dict = algo_stats if isinstance(algo_stats, dict) else {}
    fallback_counts, fallback_count_errors = _counter_dict(
        algo_stats_dict.get("fallback_counts"),
        bucket_name="fallback_counts",
    )
    param_fallbacks, param_fallback_errors = _counter_dict(
        algo_stats_dict.get("param_fallbacks"),
        bucket_name="param_fallbacks",
    )
    return FallbackState(
        fallback_counts=fallback_counts,
        param_fallbacks=param_fallbacks,
        legacy_external_days_defaulted_count=int(fallback_counts.get("legacy_external_days_defaulted_count") or 0),
        ortools_warmstart_failed_count=int(fallback_counts.get("ortools_warmstart_failed_count") or 0),
        fallback_count_parse_errors=fallback_count_errors + param_fallback_errors,
    )


def _merge_fallback_warnings(all_warnings: List[str], fallback_state: FallbackState) -> List[str]:
    legacy_count = fallback_state.legacy_external_days_defaulted_count
    warmstart_count = fallback_state.ortools_warmstart_failed_count
    if legacy_count > 0:
        all_warnings = _merge_warning_lists(all_warnings, [f"有 {legacy_count} 道外协工序缺少可用周期，本次先按 1 天计算。"])
    if warmstart_count > 0:
        all_warnings = _merge_warning_lists(all_warnings, ["OR-Tools 预热失败，系统已改用普通计算方式继续排产。"])
    if fallback_state.fallback_count_parse_errors:
        all_warnings = _merge_warning_lists(all_warnings, ["排产降级统计记录异常，部分降级原因无法完整展示。"])
    return all_warnings


def _degraded_cause_codes(
    *,
    summary_degradation: Dict[str, Any],
) -> List[str]:
    causes: List[str] = []
    summary_events = summary_degradation.get("events") if isinstance(summary_degradation, dict) else None
    for raw_event in summary_events or ():
        if not isinstance(raw_event, dict):
            continue
        code = str(raw_event.get("code") or "").strip()
        if code in {
            "config_fallback",
            "input_fallback",
            "freeze_window_degraded",
            "downtime_avoid_degraded",
            "resource_pool_degraded",
            "merge_context_degraded",
            "summary_merge_failed",
            "optimizer_metrics_invalid",
            "fallback_count_parse_failed",
            "graph_enhancement_degraded",
            "dispatch_failure_details",
        }:
            causes.append(code)
    return _dedupe_text_list(causes)


def _degraded_success_state(
    *,
    summary_degradation: Dict[str, Any],
    completion_status: str,
) -> Tuple[bool, List[str]]:
    deduped = _degraded_cause_codes(
        summary_degradation=summary_degradation,
    )
    return completion_status == "success" and bool(deduped), deduped
