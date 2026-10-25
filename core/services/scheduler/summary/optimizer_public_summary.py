from __future__ import annotations

from typing import Any, Dict, Tuple, cast

from core.services.scheduler.contracts.graph_public_summary import project_public_graph_analysis
from core.services.scheduler.contracts.optimizer_public_safety import (
    project_attempt_score,
    project_public_metrics,
    safe_attempt_text,
    safe_counter_dict,
    safe_metric_key,
    safe_non_negative_int,
    safe_public_text_list,
)
from core.services.scheduler.contracts.optimizer_public_search_report import project_search_report
from core.services.scheduler.run.schedule_candidate_summary import is_unified_generation

from .optimizer_public_algo_fields import (
    project_config_snapshot,
    project_downtime_avoid,
    project_freeze_window,
    project_improvement_trace,
    project_resource_pool,
)
from .optimizer_public_attempts import project_attempts
from .optimizer_public_candidates import project_best_score_schema, project_candidate_comparison

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
    "freeze_window",
    "resource_pool",
    "fallback_counts",
    "param_fallbacks",
    "graph_analysis",
    "candidate_comparison",
    "search_report",
}


def project_public_algo_summary(algo: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    raw_algo = algo if isinstance(algo, dict) else {}
    public_algo = {key: raw_algo[key] for key in _PUBLIC_ALGO_KEYS if key in raw_algo}
    comparison = raw_algo.get("candidate_comparison")
    unified = is_unified_generation(raw_algo) or is_unified_generation(comparison)
    if unified:
        policy = cast(Dict[str, Any], raw_algo if is_unified_generation(raw_algo) else comparison)
        for key in ("generation_policy_version", "primary_objective", "target_objectives"):
            if key in policy:
                public_algo[key] = policy[key]
        selection = (comparison or {}).get("selection") or {}
        if "selected_score" in selection:
            public_algo["best_score"] = list(selection["selected_score"])

    _project_text_and_budget_fields(public_algo)
    _project_score_fields(public_algo, unified=unified)
    search_report_diagnostics = _project_search_report_field(public_algo)
    _project_attempt_fields(public_algo)
    _project_algo_context_fields(public_algo)
    _project_auxiliary_fields(public_algo)
    _project_nested_summary_fields(public_algo)

    diagnostics = _optimizer_diagnostics(
        public_algo.pop("_diagnostic_attempts", []),
        search_report_diagnostics=search_report_diagnostics,
    )
    return public_algo, diagnostics


def _project_text_and_budget_fields(public_algo: Dict[str, Any]) -> None:
    for key in ("mode", "objective"):
        _replace_with_text_or_drop(public_algo, key)

    time_budget_seconds = safe_non_negative_int(public_algo.get("time_budget_seconds"))
    if time_budget_seconds is None:
        public_algo.pop("time_budget_seconds", None)
    else:
        public_algo["time_budget_seconds"] = time_budget_seconds

    _replace_projected_or_drop(public_algo, "config_snapshot", project_config_snapshot)
    _replace_with_text_list_or_drop(public_algo, "hard_constraints")
    _replace_with_text_list_or_drop(public_algo, "soft_objectives")


def _project_score_fields(public_algo: Dict[str, Any], *, unified: bool = False) -> None:
    metric = safe_metric_key(public_algo.get("comparison_metric"))
    if metric:
        public_algo["comparison_metric"] = metric
    else:
        public_algo.pop("comparison_metric", None)

    if not unified:
        _replace_projected_or_drop(public_algo, "best_score", project_attempt_score)
    _project_best_score_schema_field(public_algo)
    _replace_projected_or_drop(public_algo, "metrics", project_public_metrics)


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


def _project_search_report_field(public_algo: Dict[str, Any]) -> Dict[str, Any]:
    if "search_report" not in public_algo:
        return {}
    public_report, diagnostics = project_search_report(public_algo.get("search_report"))
    if public_report:
        public_algo["search_report"] = public_report
    else:
        public_algo.pop("search_report", None)
    return diagnostics


def _project_algo_context_fields(public_algo: Dict[str, Any]) -> None:
    _replace_projected_or_drop(public_algo, "improvement_trace", project_improvement_trace)
    _replace_projected_or_drop(public_algo, "downtime_avoid", project_downtime_avoid)
    _replace_projected_or_drop(public_algo, "freeze_window", project_freeze_window)
    _replace_projected_or_drop(public_algo, "resource_pool", project_resource_pool)


def _project_auxiliary_fields(public_algo: Dict[str, Any]) -> None:
    _replace_projected_or_drop(public_algo, "fallback_counts", safe_counter_dict)
    _replace_projected_or_drop(public_algo, "param_fallbacks", safe_counter_dict)


def _project_nested_summary_fields(public_algo: Dict[str, Any]) -> None:
    _replace_projected_or_drop(public_algo, "graph_analysis", project_public_graph_analysis)
    _replace_projected_or_drop(public_algo, "candidate_comparison", project_candidate_comparison)


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


def _replace_projected_or_drop(data: Dict[str, Any], key: str, projector) -> None:
    if key not in data:
        return
    projected = projector(data.get(key))
    if projected:
        data[key] = projected
    else:
        data.pop(key, None)


def _optimizer_diagnostics(diagnostic_attempts: Any, *, search_report_diagnostics: Any = None) -> Dict[str, Any]:
    optimizer: Dict[str, Any] = {}
    if diagnostic_attempts:
        optimizer["attempts"] = diagnostic_attempts
    if search_report_diagnostics:
        optimizer["search_report"] = search_report_diagnostics
    if optimizer:
        return {"optimizer": optimizer}
    return {}


__all__ = ["project_public_algo_summary"]
