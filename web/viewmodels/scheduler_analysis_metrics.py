from __future__ import annotations

from typing import Any, Dict, List, Optional

from .scheduler_analysis_trends import safe_float as _trend_safe_float


def safe_float(v: Any, default: float = 0.0) -> float:
    return _trend_safe_float(v, default=default)


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


__all__ = [
    "build_extra_cards",
    "extract_metrics_from_summary",
    "safe_float",
]
