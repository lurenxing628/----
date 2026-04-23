from __future__ import annotations

from typing import Any, Dict, List, Tuple

DEFAULT_OBJECTIVE = "min_overdue"

_METRIC_LABELS: Dict[str, str] = {
    "failed_ops": "失败工序数",
    "overdue_count": "超期批次数",
    "total_tardiness_hours": "总拖期小时",
    "weighted_tardiness_hours": "加权拖期小时",
    "makespan_hours": "总工期小时",
    "changeover_count": "换型次数",
}

_OBJECTIVE_METRIC_KEYS: Dict[str, Tuple[str, ...]] = {
    "min_overdue": (
        "overdue_count",
        "weighted_tardiness_hours",
        "total_tardiness_hours",
        "makespan_hours",
        "changeover_count",
    ),
    "min_tardiness": (
        "total_tardiness_hours",
        "overdue_count",
        "weighted_tardiness_hours",
        "makespan_hours",
        "changeover_count",
    ),
    "min_weighted_tardiness": (
        "weighted_tardiness_hours",
        "total_tardiness_hours",
        "makespan_hours",
        "changeover_count",
    ),
    "min_changeover": (
        "changeover_count",
        "overdue_count",
        "total_tardiness_hours",
        "weighted_tardiness_hours",
        "makespan_hours",
    ),
}

_OBJECTIVE_CHOICE_LABELS: Dict[str, str] = {
    "min_overdue": "最少超期",
    "min_tardiness": "最少拖期小时",
    "min_weighted_tardiness": "最少加权拖期小时",
    "min_changeover": "最少换型次数",
}


def normalize_objective_name(objective: Any) -> str:
    text = str(objective or DEFAULT_OBJECTIVE).strip().lower()
    return text if text in _OBJECTIVE_METRIC_KEYS else DEFAULT_OBJECTIVE


def objective_metric_keys(objective: Any) -> Tuple[str, ...]:
    return _OBJECTIVE_METRIC_KEYS[normalize_objective_name(objective)]


def comparison_metric_key(objective: Any) -> str:
    return objective_metric_keys(objective)[0]


def metric_label_for(metric_key: Any) -> str:
    key = str(metric_key or "").strip().lower()
    return _METRIC_LABELS.get(key, key or "-")


def best_score_schema_parts(objective: Any) -> Tuple[Tuple[str, str], ...]:
    metric_keys = objective_metric_keys(objective)
    return (("failed_ops", metric_label_for("failed_ops")),) + tuple(
        (key, metric_label_for(key)) for key in metric_keys
    )


def best_score_schema(objective: Any) -> List[Dict[str, Any]]:
    return [
        {"index": int(idx), "key": key, "label": label}
        for idx, (key, label) in enumerate(best_score_schema_parts(objective))
    ]


def objective_choice_labels() -> Dict[str, str]:
    return dict(_OBJECTIVE_CHOICE_LABELS)


__all__ = [
    "DEFAULT_OBJECTIVE",
    "best_score_schema",
    "best_score_schema_parts",
    "comparison_metric_key",
    "metric_label_for",
    "normalize_objective_name",
    "objective_choice_labels",
    "objective_metric_keys",
]
