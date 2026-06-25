from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.models.scheduler_public_errors import build_public_error_records

from .schedule_summary_types import FreezeState, SummaryBuildContext
from .summary_count_parse import parse_summary_count

OPTIMIZER_METRICS_INVALID_WARNING = "优化指标记录异常，不能按这些指标判断结果。"
FALLBACK_COUNT_PARSE_WARNING = "排产降级统计记录异常，部分降级原因无法完整展示。"
SUMMARY_COUNT_PARSE_WARNING = "排产摘要里的数量记录异常，不能按这些数量判断结果。"


def safe_metrics_dict(metrics: Any) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    if metrics is None:
        return None, None
    try:
        return metrics.to_dict(), None
    except Exception as exc:
        return None, {
            "parse_failed": True,
            "error_type": type(exc).__name__,
            "message": OPTIMIZER_METRICS_INVALID_WARNING,
            "detail": str(exc)[:300],
        }


def append_warning_once(warnings: List[str], message: str) -> None:
    if message not in warnings:
        warnings.append(message)


def record_summary_degradation(
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


def apply_metrics_degradation(
    *,
    metrics_state: Any,
    warnings: List[str],
    events: List[Dict[str, Any]],
    counters: Dict[str, Any],
    causes: List[str],
    completion_status: str,
    degraded_success: bool,
) -> bool:
    if not (isinstance(metrics_state, dict) and metrics_state.get("parse_failed")):
        return degraded_success
    append_warning_once(warnings, OPTIMIZER_METRICS_INVALID_WARNING)
    record_summary_degradation(
        events=events,
        counters=counters,
        causes=causes,
        code="optimizer_metrics_invalid",
        scope="schedule.summary.metrics",
        field="metrics",
        message=OPTIMIZER_METRICS_INVALID_WARNING,
        count=1,
    )
    return bool(degraded_success or str(completion_status or "") == "success")


def apply_fallback_count_degradation(
    *,
    fallback_parse_errors: List[str],
    warnings: List[str],
    events: List[Dict[str, Any]],
    counters: Dict[str, Any],
    causes: List[str],
    completion_status: str,
    degraded_success: bool,
) -> bool:
    if not fallback_parse_errors:
        return degraded_success
    append_warning_once(warnings, FALLBACK_COUNT_PARSE_WARNING)
    record_summary_degradation(
        events=events,
        counters=counters,
        causes=causes,
        code="fallback_count_parse_failed",
        scope="schedule.summary.fallback_counts",
        field="fallback_counts",
        message=FALLBACK_COUNT_PARSE_WARNING,
        count=len(fallback_parse_errors),
    )
    return bool(degraded_success or str(completion_status or "") == "success")


def summary_counts_with_errors(summary: Any) -> Tuple[int, int, int, List[str]]:
    op_count, op_count_error = parse_summary_count(getattr(summary, "total_ops", 0), field="total_ops")
    scheduled_ops, scheduled_ops_error = parse_summary_count(getattr(summary, "scheduled_ops", 0), field="scheduled_ops")
    failed_ops, failed_ops_error = parse_summary_count(getattr(summary, "failed_ops", 0), field="failed_ops")
    errors = [item for item in (op_count_error, scheduled_ops_error, failed_ops_error) if item]
    return op_count, scheduled_ops, failed_ops, errors


def apply_summary_count_degradation(
    *,
    summary_count_errors: List[str],
    warnings: List[str],
    events: List[Dict[str, Any]],
    counters: Dict[str, Any],
    causes: List[str],
    completion_status: str,
    degraded_success: bool,
) -> bool:
    if not summary_count_errors:
        return degraded_success
    append_warning_once(warnings, SUMMARY_COUNT_PARSE_WARNING)
    record_summary_degradation(
        events=events,
        counters=counters,
        causes=causes,
        code="summary_count_parse_failed",
        scope="schedule.summary.counts",
        field="counts",
        message=SUMMARY_COUNT_PARSE_WARNING,
        count=len(summary_count_errors),
    )
    return bool(degraded_success or str(completion_status or "") == "success")


def graph_analysis_summary_warning(ctx: SummaryBuildContext) -> Optional[str]:
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


def warnings_with_graph(freeze_state: FreezeState, ctx: SummaryBuildContext) -> List[str]:
    warnings = list(freeze_state.all_warnings)
    graph_warning = graph_analysis_summary_warning(ctx)
    if graph_warning and graph_warning not in warnings:
        warnings.append(graph_warning)
    return warnings


def public_summary_error_state(raw_summary_errors: List[Any], structured_details: Any = None) -> Tuple[List[Dict[str, Any]], List[str]]:
    details = build_public_error_records(raw_summary_errors, structured_details=structured_details)
    messages = [str(item.get("message") or "") for item in details if item.get("message")]
    return details, messages


def apply_summary_count_errors(result_summary: Dict[str, Any], summary_count_errors: List[str]) -> None:
    if not summary_count_errors:
        return
    result_summary["summary_count_parse_failed"] = True
    result_summary["summary_count_parse_errors"] = summary_count_errors[:10]
    errors_sample = list(result_summary.get("errors_sample") or [])
    for err in summary_count_errors[:10]:
        if err not in errors_sample:
            errors_sample.append(err)
    result_summary["errors_sample"] = errors_sample
    result_summary["error_count"] = max(int(result_summary.get("error_count") or 0), len(errors_sample), len(summary_count_errors))


def apply_summary_diagnostics(result_summary: Dict[str, Any], optimizer_diagnostics: Any, ctx: SummaryBuildContext) -> None:
    diagnostics = dict(optimizer_diagnostics or {})
    if ctx.graph_analysis_diagnostics is not None:
        diagnostics["graph_analysis"] = dict(ctx.graph_analysis_diagnostics)
    if diagnostics:
        result_summary["diagnostics"] = diagnostics
