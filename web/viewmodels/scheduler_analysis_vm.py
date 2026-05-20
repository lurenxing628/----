from __future__ import annotations

from typing import Any, Dict, List, Optional

from .scheduler_analysis_candidates import build_candidate_comparison_display
from .scheduler_analysis_compat import _best_score_schema_display, _compat_fallback_state
from .scheduler_analysis_diagnostics import build_diagnostic_sections
from .scheduler_analysis_freeze import build_freeze_display
from .scheduler_analysis_labels import (
    objective_choice_labels,
    objective_key_from_objective,
    objective_label_for,
)
from .scheduler_analysis_metrics import build_extra_cards, extract_metrics_from_summary, safe_float
from .scheduler_analysis_overview import build_analysis_labels
from .scheduler_analysis_trends import (
    build_selected_details,
    build_trend_charts,
    build_trend_rows,
    safe_int,
    sort_and_enrich_attempts,
)
from .scheduler_degradation_presenter import build_primary_degradation, build_summary_degradation_messages
from .scheduler_summary_display import build_display_secondary_degradation_messages, build_result_state


def _comparison_metric_from_algo(algo: Any) -> str:
    if isinstance(algo, dict):
        metric = str(algo.get("comparison_metric") or "").strip()
        if metric:
            return metric
        schema = algo.get("best_score_schema")
        if isinstance(schema, list):
            for item in schema:
                if not isinstance(item, dict):
                    continue
                key = str(item.get("key") or "").strip()
                if key and key != "failed_ops":
                    return key
    obj = algo.get("objective") if isinstance(algo, dict) else None
    return objective_key_from_objective(obj)


def _objective_key_from_algo_objective(value: Any) -> str:
    return objective_key_from_objective(value)


def build_analysis_context(
    *,
    selected_ver: Optional[int],
    raw_hist: List[Any],
    selected_item: Any,
    plan_role_options: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    trend_all, trend_rows = build_trend_rows(raw_hist, extract_metrics_from_summary=extract_metrics_from_summary)
    trend_charts = build_trend_charts(trend_rows)
    (
        selected,
        selected_summary,
        selected_metrics,
        prev_metrics,
        objective_key,
        attempts_rows,
        trace_chart,
    ) = build_selected_details(
        selected_ver=selected_ver,
        selected_item=selected_item,
        trend_all=trend_all,
        extract_metrics_from_summary=extract_metrics_from_summary,
        comparison_metric_from_algo=_comparison_metric_from_algo,
    )
    extra_cards = build_extra_cards(selected_summary, selected_metrics, prev_metrics)
    freeze_display = build_freeze_display(selected_summary)
    summary_degradation_messages = build_summary_degradation_messages(selected_summary)
    result_state = build_result_state(
        result_status=(selected or {}).get("result_status"),
        summary=selected_summary if isinstance(selected_summary, dict) else None,
    )
    primary_degradation = build_primary_degradation(
        selected_summary,
        result_state=result_state,
        completion_status=str(result_state.get("outcome_status") or ""),
    )
    display_summary_degradation_messages = build_display_secondary_degradation_messages(
        primary_degradation,
        summary_degradation_messages,
    )
    attempts = sort_and_enrich_attempts(attempts_rows, selected_metrics=selected_metrics, objective_key=objective_key)
    selected_algo = selected_summary.get("algo") if isinstance(selected_summary, dict) else None
    selected_algo = selected_algo if isinstance(selected_algo, dict) else {}
    best_score_schema_display = _best_score_schema_display(selected_summary)
    compat_fallback = _compat_fallback_state(selected_summary)
    candidate_comparison_display = build_candidate_comparison_display(
        selected_summary,
        selected_ver=selected_ver,
        plan_role_options=plan_role_options,
    )
    diagnostic_sections = build_diagnostic_sections(
        selected_summary,
        selected_ver=selected_ver,
    )
    algo_config_snapshot = selected_algo.get("config_snapshot") if isinstance(selected_algo, dict) else None
    algo_config_snapshot_objective_label = "-"
    if isinstance(algo_config_snapshot, dict):
        algo_config_snapshot_objective_label = objective_label_for(
            algo_config_snapshot.get("objective"),
            algo=selected_algo,
        )
    algo_objective_label = objective_label_for(
        selected_algo.get("objective"),
        algo=selected_algo,
    )
    objective_key_label = objective_label_for(
        objective_key,
        algo=selected_algo,
    )
    return {
        "selected": selected,
        "selected_summary": selected_summary,
        "selected_metrics": selected_metrics,
        "prev_metrics": prev_metrics,
        "objective_key": objective_key,
        "algo_objective_label": algo_objective_label,
        "best_score_schema_display": best_score_schema_display,
        "compat_fallback": compat_fallback,
        "candidate_comparison_display": candidate_comparison_display,
        "diagnostic_sections": diagnostic_sections,
        "analysis_labels": build_analysis_labels(),
        "algo_config_snapshot_objective_label": algo_config_snapshot_objective_label,
        "objective_key_label": objective_key_label,
        "objective_choice_labels": objective_choice_labels(),
        "attempts": attempts,
        "trace_chart": trace_chart,
        "trend_rows": trend_rows,
        "trend_charts": trend_charts,
        "extra_cards": extra_cards,
        "freeze_display": freeze_display,
        "summary_degradation_messages": summary_degradation_messages,
        "display_summary_degradation_messages": display_summary_degradation_messages,
    }


__all__ = [
    "_comparison_metric_from_algo",
    "_objective_key_from_algo_objective",
    "build_analysis_context",
    "build_candidate_comparison_display",
    "extract_metrics_from_summary",
    "objective_label_for",
    "safe_float",
    "safe_int",
]
