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
            "count": count,
        }
    )
    counters[code] = counters.get(code, 0) + count
    if code not in causes:
        causes.append(code)


def summary_counts(summary: ScheduleSummary) -> Tuple[int, int, int]:
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
    structured_details: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    details = build_public_error_records(structured_details)
    messages = [item["message"] for item in details]
    return details, messages


def apply_summary_diagnostics(result_summary: Dict[str, Any], ctx: SummaryBuildContext) -> None:
    if ctx.graph_analysis_diagnostics is not None:
        result_summary["diagnostics"] = {"graph_analysis": dict(ctx.graph_analysis_diagnostics)}
