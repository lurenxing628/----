from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from core.algorithm_contracts.types import ScheduleSummary
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


def _counter_dict(value: Optional[Mapping[str, int]]) -> Dict[str, int]:
    # 计数桶只经 increment_counter / merge_algo_stats 写入，键非空、值是解码自己的整数计数。
    if value is None:
        return {}
    return {key: count for key, count in value.items() if count}


def _build_runtime_state(
    *,
    batches: Dict[str, Batch],
    summary: ScheduleSummary,
    best_metrics: SummaryMetrics,
) -> RuntimeState:
    finish_by_batch = best_metrics._finish_by_batch
    # 半途失败批次的 finish 是被截断的部分完工时间，排除出超期/临期分类，
    # 改走 result_summary 的 incomplete_batches 风险清单（audit 2026-07-20 A18）。
    incomplete_batch_ids = incomplete_batch_ids_from_failure_details(
        summary.failure_details,
        finish_by_batch,
    )
    overdue_items, near_due_items = _build_overdue_items_impl(
        batches=batches,
        finish_by_batch=finish_by_batch,
        incomplete_batch_ids=incomplete_batch_ids,
        due_by_batch=best_metrics._due_by_batch,
    )
    return RuntimeState(
        finish_by_batch=finish_by_batch,
        overdue_items=overdue_items,
        near_due_items=near_due_items,
        invalid_due_count=best_metrics.invalid_due_count,
        invalid_due_batch_ids_sample=list(best_metrics.invalid_due_batch_ids_sample[:10]),
        unscheduled_batch_count=best_metrics.unscheduled_batch_count,
        unscheduled_batch_ids_sample=list(best_metrics.unscheduled_batch_ids_sample[:20]),
        incomplete_batch_ids=incomplete_batch_ids,
    )


def _build_summary_warnings(
    *,
    summary: ScheduleSummary,
    runtime_state: RuntimeState,
) -> List[str]:
    all_warnings = _warning_list(summary.warnings)
    if runtime_state.invalid_due_count > 0:
        sample_ids = "，".join(runtime_state.invalid_due_batch_ids_sample)
        all_warnings = _merge_warning_lists(
            all_warnings,
            [f"存在 {runtime_state.invalid_due_count} 个批次交期写法不对，已忽略超期与临期判断（示例批次：{sample_ids}）"],
        )
    if runtime_state.unscheduled_batch_count > 0:
        all_warnings = _merge_warning_lists(
            all_warnings,
            [f"存在 {runtime_state.unscheduled_batch_count} 个批次未形成完工结果，请到系统管理里的排产历史查看这次排产的详细提醒。"],
        )
    return all_warnings


def _build_fallback_state(algo_stats: Mapping[str, Any]) -> FallbackState:
    fallback_counts = _counter_dict(algo_stats.get("fallback_counts"))
    return FallbackState(
        fallback_counts=fallback_counts,
        ortools_warmstart_failed_count=fallback_counts.get("ortools_warmstart_failed_count", 0),
    )


def _merge_fallback_warnings(all_warnings: List[str], fallback_state: FallbackState) -> List[str]:
    warmstart_count = fallback_state.ortools_warmstart_failed_count
    if warmstart_count > 0:
        all_warnings = _merge_warning_lists(all_warnings, ["OR-Tools 预热失败，系统已改用普通计算方式继续排产。"])
    return all_warnings
