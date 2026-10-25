from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.algorithm_contracts.types import ScheduleResult, ScheduleSummary
from core.models.batch import Batch
from core.services.scheduler.contracts.schedule_summary_types import (
    FallbackState,
    RuntimeState,
    SummaryMetrics,
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


def _append_summary_warning(summary: Optional[ScheduleSummary], message: str) -> None:
    if summary is not None:
        summary.warnings.append(message)


def _counter_dict(value: Any) -> Dict[str, int]:
    # 计数桶只经 increment_counter / merge_algo_stats 写入，键非空、值是校验过的整数。
    if not isinstance(value, dict):
        return {}
    return {key: count for key, count in value.items() if count}


def _build_runtime_state(
    *,
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


def _build_summary_warnings(
    *,
    summary: Optional[ScheduleSummary],
    runtime_state: RuntimeState,
) -> List[str]:
    all_warnings = _warning_list(summary.warnings if summary is not None else None)
    if runtime_state.unscheduled_batch_count > 0:
        all_warnings = _merge_warning_lists(
            all_warnings,
            [f"存在 {runtime_state.unscheduled_batch_count} 个批次未形成完工结果，请到系统管理里的排产历史查看这次排产的详细提醒。"],
        )
    return all_warnings


def _build_fallback_state(algo_stats: Optional[Dict[str, Any]]) -> FallbackState:
    algo_stats_dict = algo_stats if isinstance(algo_stats, dict) else {}
    fallback_counts = _counter_dict(algo_stats_dict.get("fallback_counts"))
    return FallbackState(
        fallback_counts=fallback_counts,
        param_fallbacks=_counter_dict(algo_stats_dict.get("param_fallbacks")),
        ortools_warmstart_failed_count=int(fallback_counts.get("ortools_warmstart_failed_count") or 0),
    )


def _merge_fallback_warnings(all_warnings: List[str], fallback_state: FallbackState) -> List[str]:
    warmstart_count = fallback_state.ortools_warmstart_failed_count
    if warmstart_count > 0:
        all_warnings = _merge_warning_lists(all_warnings, ["OR-Tools 预热失败，系统已改用普通计算方式继续排产。"])
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
