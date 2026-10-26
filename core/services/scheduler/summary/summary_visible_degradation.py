from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.algorithm_contracts.types import ScheduleSummary
from core.models.scheduler_public_errors import build_public_error_records
from core.services.scheduler.contracts.schedule_summary_types import SummaryBuildContext


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


def summary_counts(summary: Optional[ScheduleSummary]) -> Tuple[int, int, int]:
    # ScheduleSummary 构造时已校验三项计数都是非负整数；没有摘要（排产未产出）时计数为 0。
    if summary is None:
        return 0, 0, 0
    return summary.total_ops, summary.scheduled_ops, summary.failed_ops


def graph_analysis_summary_warning(graph_analysis_public: Optional[Dict[str, Any]]) -> Optional[str]:
    if not graph_analysis_public:
        return None
    if graph_analysis_public["status"] == "available":
        return None
    # Non-available projections always carry a literal reason and message=str(exc) (schedule_graph_report.py).
    detail = graph_analysis_public["message"].strip() or graph_analysis_public["reason"]
    return f"工序图分析没有生成可用报告：{detail}"


def warnings_with_graph(all_warnings: List[str], graph_analysis_public: Optional[Dict[str, Any]]) -> List[str]:
    warnings = list(all_warnings)
    graph_warning = graph_analysis_summary_warning(graph_analysis_public)
    if graph_warning and graph_warning not in warnings:
        warnings.append(graph_warning)
    return warnings


def public_summary_error_state(
    raw_summary_errors: List[Any], structured_details: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    details = build_public_error_records(raw_summary_errors, structured_details=structured_details)
    messages = [item["message"] for item in details if item.get("message")]
    return details, messages


def apply_summary_diagnostics(
    result_summary: Dict[str, Any], optimizer_diagnostics: Dict[str, Any], ctx: SummaryBuildContext,
) -> None:
    diagnostics = dict(optimizer_diagnostics)
    if ctx.graph_analysis_diagnostics is not None:
        diagnostics["graph_analysis"] = dict(ctx.graph_analysis_diagnostics)
    if diagnostics:
        result_summary["diagnostics"] = diagnostics
