from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from core.models.enums import YesNo
from core.models.schedule_candidate import ScheduleCandidate
from core.services.scheduler.summary.graph_public_summary import project_public_graph_analysis
from core.services.scheduler.summary.optimizer_public_search_report import project_search_report

from .schedule_candidate_specs import CANDIDATE_KIND_CRITICAL_CHAIN
from .schedule_candidate_summary import (
    candidate_comparison_log_summary,
    candidate_detail_saved,
    candidate_health_summary,
    candidate_metrics_summary,
    candidate_public_summary,
)


def _json_or_none(payload: Optional[Dict[str, Any]]) -> Optional[str]:
    if payload is None:
        return None
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _score_json(candidate: Any) -> Optional[str]:
    score = getattr(candidate, "score", None)
    if score is None:
        return None
    return json.dumps([float(item) for item in tuple(score)], ensure_ascii=False, separators=(",", ":"))


def _candidate_kind(candidate: Any) -> str:
    return str(getattr(candidate, "kind", "") or "")


def _is_critical_chain(kind: str) -> bool:
    return kind == CANDIDATE_KIND_CRITICAL_CHAIN


def _critical_chain_value(kind: str, value: Optional[int]) -> Optional[int]:
    return value if _is_critical_chain(kind) else None


def _text_attr(candidate: Any, field_name: str) -> str:
    return str(getattr(candidate, field_name, "") or "")


def _optional_text_attr(candidate: Any, field_name: str) -> Optional[str]:
    return _text_attr(candidate, field_name) or None


def _objective(candidate: Any) -> Optional[str]:
    value = getattr(candidate, "objective", "") or getattr(candidate, "objective_name", "") or ""
    return str(value) or None


def _int_attr(candidate: Any, field_name: str) -> int:
    return int(getattr(candidate, field_name, 0) or 0)


def _elapsed_ms(candidate: Any) -> int:
    return int(round(float(getattr(candidate, "elapsed_seconds", 0.0) or 0.0) * 1000))


def build_candidate_model(
    candidate: Any,
    *,
    version: int,
    roles: List[str],
    selection_reason: Optional[str],
    weight_count: int,
) -> ScheduleCandidate:
    kind = _candidate_kind(candidate)
    detail_saved = candidate_detail_saved(candidate, roles)
    return ScheduleCandidate(
        id=None,
        version=int(version),
        candidate_key=_text_attr(candidate, "candidate_key"),
        candidate_label=_text_attr(candidate, "label"),
        candidate_kind=kind,
        status=_text_attr(candidate, "status"),
        graph_enabled=YesNo.YES.value if _is_critical_chain(kind) else YesNo.NO.value,
        weight_level=_critical_chain_value(kind, int(getattr(candidate, "sequence", 0) or 0)),
        weight_count=_critical_chain_value(kind, int(weight_count)),
        critical_weight=_int_attr(candidate, "graph_critical_weight"),
        impact_weight=_int_attr(candidate, "graph_impact_weight"),
        downstream_weight=_int_attr(candidate, "graph_downstream_weight"),
        sort_strategy=_optional_text_attr(candidate, "sort_strategy"),
        dispatch_mode=_optional_text_attr(candidate, "dispatch_mode"),
        dispatch_rule=_optional_text_attr(candidate, "dispatch_rule"),
        objective=_objective(candidate),
        score_json=_score_json(candidate),
        metrics_json=_json_or_none(candidate_metrics_summary(candidate)),
        health_json=_json_or_none(candidate_health_summary(candidate)),
        summary_json=_json_or_none(candidate_public_summary(candidate, roles=roles)),
        selection_reason=selection_reason,
        failure_reason=_optional_text_attr(candidate, "failure_reason"),
        detail_saved=YesNo.YES.value if detail_saved else YesNo.NO.value,
        elapsed_ms=_elapsed_ms(candidate),
    )


def _copy_known_algo_fields(out: Dict[str, Any], algo: Dict[str, Any]) -> None:
    for key in ("mode", "objective", "comparison_metric", "time_budget_seconds"):
        if key in algo:
            out[key] = algo.get(key)


def _copy_graph_analysis(out: Dict[str, Any], algo: Dict[str, Any]) -> None:
    graph_analysis = algo.get("graph_analysis")
    if isinstance(graph_analysis, dict):
        public_graph = project_public_graph_analysis(graph_analysis)
        if public_graph:
            out["graph_analysis"] = public_graph


def _copy_candidate_comparison(out: Dict[str, Any], algo: Dict[str, Any]) -> None:
    candidate_comparison = candidate_comparison_log_summary(algo.get("candidate_comparison"))
    if candidate_comparison:
        out["candidate_comparison"] = candidate_comparison


def _copy_search_report(out: Dict[str, Any], algo: Dict[str, Any]) -> None:
    search_report = algo.get("search_report")
    if not isinstance(search_report, dict):
        return
    public_report, _diagnostics = project_search_report(search_report)
    if public_report:
        out["search_report"] = public_report


def operation_log_algo_summary(result_summary_obj: Dict[str, Any]) -> Any:
    algo = result_summary_obj.get("algo")
    if not isinstance(algo, dict):
        return algo
    out: Dict[str, Any] = {}
    _copy_known_algo_fields(out, algo)
    _copy_search_report(out, algo)
    _copy_graph_analysis(out, algo)
    _copy_candidate_comparison(out, algo)
    return out or None


__all__ = [
    "build_candidate_model",
    "operation_log_algo_summary",
]
