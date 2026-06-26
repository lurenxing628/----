from __future__ import annotations

from typing import Any, Dict, Tuple

from .graph_public_summary import project_public_graph_analysis
from .optimizer_public_algo_fields import (
    project_config_snapshot,
    project_downtime_avoid,
    project_freeze_window,
    project_improvement_trace,
    project_input_contract,
    project_metrics_state,
    project_resource_pool,
    project_warning_pipeline,
)
from .optimizer_public_attempts import project_attempts
from .optimizer_public_candidates import project_best_score_schema, project_candidate_comparison
from .optimizer_public_safety import (
    project_attempt_score,
    project_degradation_event_list,
    project_public_metrics,
    safe_attempt_text,
    safe_counter_dict,
    safe_metric_key,
    safe_non_negative_int,
    safe_public_text_list,
)

_PUBLIC_ALGO_KEYS = {
    "mode",
    "objective",
    "comparison_metric",
    "config_snapshot",
    "time_budget_seconds",
    "hard_constraints",
    "soft_objectives",
    "best_score",
    "best_score_schema",
    "metrics",
    "attempts",
    "improvement_trace",
    "downtime_avoid",
    "input_contract",
    "merge_context_degraded",
    "merge_context_events",
    "freeze_window",
    "resource_pool",
    "metrics_state",
    "metrics_degraded",
    "metrics_degradation_reasons",
    "fallback_counts",
    "param_fallbacks",
    "fallback_count_parse_failed",
    "fallback_count_parse_errors",
    "graph_analysis",
    "candidate_comparison",
    "warning_pipeline",
}


def project_public_algo_summary(algo: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    raw_algo = algo if isinstance(algo, dict) else {}
    public_algo = {key: raw_algo[key] for key in _PUBLIC_ALGO_KEYS if key in raw_algo}

    _project_text_and_budget_fields(public_algo)
    _project_score_fields(public_algo)
    _project_attempt_fields(public_algo)
    _project_algo_context_fields(public_algo)
    _project_auxiliary_fields(public_algo)
    _project_nested_summary_fields(public_algo)

    diagnostics = _optimizer_diagnostics(public_algo.pop("_diagnostic_attempts", []))
    return public_algo, diagnostics


def _project_text_and_budget_fields(public_algo: Dict[str, Any]) -> None:
    for key in ("mode", "objective"):
        _replace_with_text_or_drop(public_algo, key)

    time_budget_seconds = safe_non_negative_int(public_algo.get("time_budget_seconds"))
    if time_budget_seconds is None:
        public_algo.pop("time_budget_seconds", None)
    else:
        public_algo["time_budget_seconds"] = time_budget_seconds

    _replace_with_mapping_or_drop(public_algo, "config_snapshot", project_config_snapshot)
    _replace_with_text_list_or_drop(public_algo, "hard_constraints")
    _replace_with_text_list_or_drop(public_algo, "soft_objectives")


def _project_score_fields(public_algo: Dict[str, Any]) -> None:
    metric = safe_metric_key(public_algo.get("comparison_metric"))
    if metric:
        public_algo["comparison_metric"] = metric
    else:
        public_algo.pop("comparison_metric", None)

    _replace_with_list_or_drop(public_algo, "best_score", project_attempt_score)
    _project_best_score_schema_field(public_algo)
    _replace_with_mapping_or_drop(public_algo, "metrics", project_public_metrics)


def _project_best_score_schema_field(public_algo: Dict[str, Any]) -> None:
    if "best_score_schema" not in public_algo:
        return
    schema = project_best_score_schema(public_algo.get("best_score_schema"))
    if not schema:
        public_algo.pop("best_score_schema", None)
        return
    public_algo["best_score_schema"] = schema
    if "comparison_metric" not in public_algo:
        _fill_comparison_metric_from_schema(public_algo, schema)


def _fill_comparison_metric_from_schema(public_algo: Dict[str, Any], schema: Any) -> None:
    for item in schema:
        key = str((item or {}).get("key") or "").strip() if isinstance(item, dict) else ""
        if key and key != "failed_ops":
            public_algo["comparison_metric"] = key
            return


def _project_attempt_fields(public_algo: Dict[str, Any]) -> None:
    public_attempts, diagnostic_attempts = project_attempts(public_algo.get("attempts"))
    if isinstance(public_algo.get("attempts"), list):
        public_algo["attempts"] = public_attempts
    else:
        public_algo.pop("attempts", None)
    public_algo["_diagnostic_attempts"] = diagnostic_attempts


def _project_algo_context_fields(public_algo: Dict[str, Any]) -> None:
    _replace_with_list_or_drop(public_algo, "improvement_trace", project_improvement_trace)
    _replace_with_mapping_or_drop(public_algo, "downtime_avoid", project_downtime_avoid)
    _replace_with_mapping_or_drop(public_algo, "freeze_window", project_freeze_window)
    _replace_with_mapping_or_drop(public_algo, "resource_pool", project_resource_pool)
    _replace_with_mapping_or_drop(public_algo, "warning_pipeline", project_warning_pipeline)
    _replace_with_mapping_or_drop(public_algo, "metrics_state", project_metrics_state)


def _project_auxiliary_fields(public_algo: Dict[str, Any]) -> None:
    _replace_with_text_list_or_drop(public_algo, "metrics_degradation_reasons")
    _replace_with_mapping_or_drop(public_algo, "fallback_counts", safe_counter_dict)
    _replace_with_mapping_or_drop(public_algo, "param_fallbacks", safe_counter_dict)
    _replace_with_text_list_or_drop(public_algo, "fallback_count_parse_errors")

    for key in ("merge_context_degraded", "metrics_degraded", "fallback_count_parse_failed"):
        if key in public_algo:
            public_algo[key] = bool(public_algo.get(key))


def _project_nested_summary_fields(public_algo: Dict[str, Any]) -> None:
    _replace_with_mapping_or_drop(public_algo, "graph_analysis", project_public_graph_analysis)
    _replace_with_mapping_or_drop(public_algo, "candidate_comparison", project_candidate_comparison)
    _replace_with_mapping(public_algo, "input_contract", project_input_contract)
    _replace_with_list(public_algo, "merge_context_events", project_degradation_event_list)


def _replace_with_text_or_drop(data: Dict[str, Any], key: str) -> None:
    text = safe_attempt_text(data.get(key))
    if text:
        data[key] = text
    else:
        data.pop(key, None)


def _replace_with_text_list_or_drop(data: Dict[str, Any], key: str) -> None:
    values = safe_public_text_list(data.get(key))
    if values:
        data[key] = values
    else:
        data.pop(key, None)


def _replace_with_mapping_or_drop(data: Dict[str, Any], key: str, projector) -> None:
    if key not in data:
        return
    projected = projector(data.get(key))
    if projected:
        data[key] = projected
    else:
        data.pop(key, None)


def _replace_with_mapping(data: Dict[str, Any], key: str, projector) -> None:
    if key in data:
        data[key] = projector(data.get(key))


def _replace_with_list_or_drop(data: Dict[str, Any], key: str, projector) -> None:
    if key not in data:
        return
    projected = projector(data.get(key))
    if projected:
        data[key] = projected
    else:
        data.pop(key, None)


def _replace_with_list(data: Dict[str, Any], key: str, projector) -> None:
    if key in data:
        data[key] = projector(data.get(key))


def _optimizer_diagnostics(diagnostic_attempts: Any) -> Dict[str, Any]:
    if diagnostic_attempts:
        return {"optimizer": {"attempts": diagnostic_attempts}}
    return {}


def project_public_result_summary(summary: Any) -> Any:
    """把整份 result_summary 收紧为用户可见安全摘要。

    这是 summary 级 public 投影的单一真相源:剔除 diagnostics、对 algo 走
    project_public_algo_summary 投影。页面/viewmodel 默认走本函数,不允许出现
    "未投影就直接渲染 raw summary" 的不安全默认。非 dict 原样返回。
    """
    if not isinstance(summary, dict):
        return summary
    public_summary = dict(summary)
    public_summary.pop("diagnostics", None)
    algo = public_summary.get("algo")
    if isinstance(algo, dict):
        public_algo, _diagnostics = project_public_algo_summary(algo)
        public_summary["algo"] = public_algo
    return public_summary


__all__ = ["project_public_algo_summary", "project_public_result_summary"]
