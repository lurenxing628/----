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
from .scheduler_analysis_metrics import build_extra_cards, build_metric_cards, extract_metrics_from_summary, safe_float
from .scheduler_analysis_overview import analysis_choice_label, build_analysis_labels
from .scheduler_analysis_trends import (
    build_selected_details,
    build_trend_charts,
    build_trend_rows,
    sort_and_enrich_attempts,
)
from .scheduler_degradation_presenter import build_primary_degradation, build_summary_degradation_messages
from .scheduler_history_summary import strategy_display_label
from .scheduler_summary_display import build_display_secondary_degradation_messages, build_result_state


def _public_summary_for_template(summary: Any) -> Any:
    if not isinstance(summary, dict):
        return summary
    public_summary = dict(summary)
    public_summary.pop("diagnostics", None)
    return public_summary


def _public_selected_for_template(selected: Any, public_summary: Any) -> Any:
    if not isinstance(selected, dict):
        return selected
    public_selected = dict(selected)
    if "result_summary" in public_selected:
        public_selected["result_summary"] = public_summary
    parse_state = public_selected.get("result_summary_parse_state")
    if isinstance(parse_state, dict):
        public_parse_state = dict(parse_state)
        if "payload" in public_parse_state:
            public_parse_state["payload"] = public_summary
        public_selected["result_summary_parse_state"] = public_parse_state
    return public_selected


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


def _time_budget_seconds_label(value: Any) -> str:
    if value is None or (isinstance(value, str) and not value.strip()):
        return "-"
    if isinstance(value, bool):
        return "记录异常"
    if isinstance(value, int):
        return str(value) if value >= 0 else "记录异常"
    text = str(value or "").strip()
    if not text.isdigit():
        return "记录异常"
    return str(int(text))


def _time_budget_seconds_display(value: Any) -> str:
    label = _time_budget_seconds_label(value)
    return f"{label} 秒" if label.isdigit() else label


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
    metric_cards = build_metric_cards(selected_metrics, prev_metrics)
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
    analysis_labels = build_analysis_labels()
    algo_config_snapshot = selected_algo.get("config_snapshot") if isinstance(selected_algo, dict) else None
    algo_config_snapshot_objective_label = "-"
    algo_config_snapshot_strategy_label = "-"
    algo_config_snapshot_mode_label = "-"
    algo_config_snapshot_dispatch_mode_label = "-"
    algo_config_snapshot_dispatch_rule_label = "-"
    algo_config_snapshot_time_budget_seconds_label = "-"
    algo_config_snapshot_time_budget_seconds_display = "-"
    algo_mode_value = selected_algo.get("mode")
    if isinstance(algo_config_snapshot, dict):
        algo_mode_value = algo_config_snapshot.get("algo_mode") or algo_mode_value
        algo_config_snapshot_objective_label = objective_label_for(
            algo_config_snapshot.get("objective"),
            algo=selected_algo,
        )
        algo_config_snapshot_strategy_label = strategy_display_label(algo_config_snapshot.get("sort_strategy"))
        algo_config_snapshot_mode_label = analysis_choice_label(
            algo_config_snapshot.get("algo_mode"),
            analysis_labels.get("mode", {}),
        )
        algo_config_snapshot_dispatch_mode_label = analysis_choice_label(
            algo_config_snapshot.get("dispatch_mode"),
            analysis_labels.get("dispatch_mode", {}),
        )
        algo_config_snapshot_dispatch_rule_label = analysis_choice_label(
            algo_config_snapshot.get("dispatch_rule"),
            analysis_labels.get("dispatch_rule", {}),
        )
        algo_config_snapshot_time_budget_seconds_label = _time_budget_seconds_label(
            algo_config_snapshot.get("time_budget_seconds")
        )
        algo_config_snapshot_time_budget_seconds_display = _time_budget_seconds_display(
            algo_config_snapshot.get("time_budget_seconds")
        )
    algo_mode_label = analysis_choice_label(algo_mode_value, analysis_labels.get("mode", {}))
    algo_time_budget_seconds_label = _time_budget_seconds_label(selected_algo.get("time_budget_seconds"))
    algo_time_budget_seconds_display = _time_budget_seconds_display(selected_algo.get("time_budget_seconds"))
    algo_objective_label = objective_label_for(
        selected_algo.get("objective"),
        algo=selected_algo,
    )
    objective_key_label = objective_label_for(
        objective_key,
        algo=selected_algo,
    )
    public_selected_summary = _public_summary_for_template(selected_summary)
    public_selected = _public_selected_for_template(selected, public_selected_summary)
    return {
        "selected": public_selected,
        "selected_summary": public_selected_summary,
        "selected_metrics": selected_metrics,
        "prev_metrics": prev_metrics,
        "objective_key": objective_key,
        "algo_objective_label": algo_objective_label,
        "algo_mode_label": algo_mode_label,
        "algo_time_budget_seconds_label": algo_time_budget_seconds_label,
        "algo_time_budget_seconds_display": algo_time_budget_seconds_display,
        "best_score_schema_display": best_score_schema_display,
        "compat_fallback": compat_fallback,
        "candidate_comparison_display": candidate_comparison_display,
        "diagnostic_sections": diagnostic_sections,
        "analysis_labels": analysis_labels,
        "algo_config_snapshot_objective_label": algo_config_snapshot_objective_label,
        "algo_config_snapshot_strategy_label": algo_config_snapshot_strategy_label,
        "algo_config_snapshot_mode_label": algo_config_snapshot_mode_label,
        "algo_config_snapshot_dispatch_mode_label": algo_config_snapshot_dispatch_mode_label,
        "algo_config_snapshot_dispatch_rule_label": algo_config_snapshot_dispatch_rule_label,
        "algo_config_snapshot_time_budget_seconds_label": algo_config_snapshot_time_budget_seconds_label,
        "algo_config_snapshot_time_budget_seconds_display": algo_config_snapshot_time_budget_seconds_display,
        "objective_key_label": objective_key_label,
        "objective_choice_labels": objective_choice_labels(),
        "attempts": attempts,
        "trace_chart": trace_chart,
        "trend_rows": trend_rows,
        "trend_charts": trend_charts,
        "metric_cards": metric_cards,
        "extra_cards": extra_cards,
        "freeze_display": freeze_display,
        "summary_degradation_messages": summary_degradation_messages,
        "display_summary_degradation_messages": display_summary_degradation_messages,
    }


__all__ = [
    "_comparison_metric_from_algo",
    "_objective_key_from_algo_objective",
    "_time_budget_seconds_display",
    "_time_budget_seconds_label",
    "build_analysis_context",
    "build_candidate_comparison_display",
    "extract_metrics_from_summary",
    "objective_label_for",
    "safe_float",
]
