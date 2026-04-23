from __future__ import annotations

from typing import Any, Dict

from core.models.objective import (
    comparison_metric_key,
    metric_label_for,
)
from core.models.objective import (
    objective_choice_labels as _objective_choice_labels,
)


def objective_choice_labels() -> Dict[str, str]:
    return _objective_choice_labels()


def objective_key_from_objective(value: Any) -> str:
    return comparison_metric_key(value)


def objective_label_for(value: Any, *, algo: Any = None) -> str:
    key = str(value or "").strip().lower()
    if not key:
        return "-"

    choice_labels = objective_choice_labels()
    if key in choice_labels:
        return choice_labels[key]

    if isinstance(algo, dict):
        schema = algo.get("best_score_schema")
        if isinstance(schema, list):
            for item in schema:
                if not isinstance(item, dict):
                    continue
                if str(item.get("key") or "").strip().lower() != key:
                    continue
                label = str(item.get("label") or "").strip()
                if label:
                    return label

    return metric_label_for(key)


__all__ = [
    "objective_choice_labels",
    "objective_key_from_objective",
    "objective_label_for",
]
