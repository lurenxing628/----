from __future__ import annotations

from typing import Any, Dict, List, Optional

from .scheduler_analysis_labels import (
    objective_choice_labels,
    objective_key_from_objective,
    objective_label_for,
)
from .scheduler_analysis_trends import (
    build_selected_details,
    build_trend_charts,
    build_trend_rows,
    safe_int,
    sort_and_enrich_attempts,
)
from .scheduler_degradation_presenter import build_primary_degradation, build_summary_degradation_messages
from .scheduler_summary_display import build_display_secondary_degradation_messages, build_result_state


def safe_float(v: Any, default: float = 0.0) -> float:
    from .scheduler_analysis_trends import safe_float as _safe_float

    return _safe_float(v, default=default)


def extract_metrics_from_summary(summary: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    algo = summary.get("algo") if isinstance(summary, dict) else None
    if isinstance(algo, dict):
        metrics = algo.get("metrics")
        if isinstance(metrics, dict) and metrics:
            return metrics
    return None


_EXTRA_CARD_SPECS = (
    ("invalid_due_count", "数据异常批次数", "type-info"),
    ("unscheduled_batch_count", "未排批次数", ""),
)

_FREEZE_STATE_LABELS = {
    "disabled": "未启用",
    "active": "已生效",
    "degraded": "已降级",
}

_COMPAT_FALLBACK_FIELD_LABELS = {
    "comparison_metric": "优化对比指标",
    "best_score_schema": "评分顺序",
}


def _summary_metric_value(
    selected_summary: Optional[Dict[str, Any]],
    selected_metrics: Optional[Dict[str, Any]],
    key: str,
) -> Optional[Any]:
    if selected_metrics and key in selected_metrics:
        return selected_metrics[key]
    if selected_summary and key in selected_summary:
        return selected_summary[key]
    return None


def build_extra_cards(
    selected_summary: Optional[Dict[str, Any]],
    selected_metrics: Optional[Dict[str, Any]],
    prev_metrics: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    cards: List[Dict[str, Any]] = []
    for key, label, type_class in _EXTRA_CARD_SPECS:
        value = _summary_metric_value(selected_summary, selected_metrics, key)
        if value is None:
            continue
        delta = int(value) - int(prev_metrics[key]) if prev_metrics and key in prev_metrics else None
        cards.append(
            {
                "key": key,
                "label": label,
                "value": int(value),
                "delta": delta,
                "type_class": type_class,
            }
        )
    return cards


def build_freeze_display(selected_summary: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    algo = selected_summary.get("algo") if selected_summary else None
    if not algo or "freeze_window" not in algo:
        return None

    freeze_window = algo.get("freeze_window")
    if not freeze_window:
        return None

    enabled = str(freeze_window.get("enabled", "")).strip().lower() == "yes"
    applied = bool(freeze_window.get("freeze_applied"))
    raw_state = str(freeze_window.get("freeze_state") or "").strip().lower()
    sample_batches = list(freeze_window.get("frozen_batch_ids_sample") or [])[:5]
    sample_total = int(freeze_window.get("frozen_batch_count") or 0)
    degraded = bool(freeze_window.get("degraded")) or raw_state == "degraded"
    if degraded:
        state = "degraded"
    elif raw_state in _FREEZE_STATE_LABELS:
        state = raw_state
    elif enabled and applied:
        state = "active"
    else:
        state = "disabled"
    return {
        "enabled": enabled,
        "days": int(freeze_window.get("days") or 0),
        "state": state,
        "state_label": _FREEZE_STATE_LABELS[state],
        "applied": applied,
        "frozen_op_count": int(freeze_window.get("frozen_op_count") or 0),
        "frozen_batch_count": sample_total,
        "sample_batches": sample_batches,
        "sample_total": sample_total,
        "sample_more_count": max(sample_total - len(sample_batches), 0),
        "degraded": degraded,
        "degradation_reason": freeze_window.get("degradation_reason") or None,
    }


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


def _best_score_schema_display(selected_summary: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    algo = selected_summary.get("algo") if isinstance(selected_summary, dict) else None
    if not isinstance(algo, dict):
        return []

    rows: List[Dict[str, Any]] = []
    for raw_item in algo.get("best_score_schema") or []:
        if not isinstance(raw_item, dict):
            continue
        row = dict(raw_item)
        row["display_label"] = str(row.get("label") or "").strip() or objective_label_for(row.get("key"), algo=algo)
        rows.append(row)
    return rows


def _compat_fallback_state(selected_summary: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    algo = selected_summary.get("algo") if isinstance(selected_summary, dict) else None
    if not isinstance(algo, dict):
        return {"used": False, "missing_fields": [], "message": None}

    missing_fields: List[str] = []
    if not str(algo.get("comparison_metric") or "").strip():
        missing_fields.append("comparison_metric")
    if not isinstance(algo.get("best_score_schema"), list):
        missing_fields.append("best_score_schema")
    if not missing_fields:
        return {"used": False, "missing_fields": [], "missing_field_labels": [], "message": None}
    return {
        "used": True,
        "missing_fields": missing_fields,
        "missing_field_labels": [_COMPAT_FALLBACK_FIELD_LABELS.get(field, "分析字段") for field in missing_fields],
        "message": "当前版本摘要缺少部分分析字段，页面已按旧版本数据继续展示。",
    }


def build_analysis_context(
    *,
    selected_ver: Optional[int],
    raw_hist: List[Any],
    selected_item: Any,
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
    "extract_metrics_from_summary",
    "objective_label_for",
    "safe_float",
    "safe_int",
]
