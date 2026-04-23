from __future__ import annotations

import pytest

from core.algorithms.evaluation import ScheduleMetrics, objective_score
from core.algorithms.objective_specs import metric_label_for, objective_choice_labels
from core.services.scheduler.schedule_summary import best_score_schema, comparison_metric
from web.viewmodels.scheduler_analysis_vm import _comparison_metric_from_algo, objective_label_for


@pytest.mark.parametrize(
    ("objective_name", "expected_keys"),
    [
        (
            "min_overdue",
            ["overdue_count", "weighted_tardiness_hours", "total_tardiness_hours", "makespan_hours", "changeover_count"],
        ),
        (
            "min_tardiness",
            ["total_tardiness_hours", "overdue_count", "weighted_tardiness_hours", "makespan_hours", "changeover_count"],
        ),
        (
            "min_weighted_tardiness",
            ["weighted_tardiness_hours", "total_tardiness_hours", "makespan_hours", "changeover_count"],
        ),
        (
            "min_changeover",
            ["changeover_count", "overdue_count", "total_tardiness_hours", "weighted_tardiness_hours", "makespan_hours"],
        ),
    ],
)
def test_objective_score_schema_and_analysis_projection_stay_in_sync(objective_name: str, expected_keys: list[str]) -> None:
    metrics = ScheduleMetrics(
        overdue_count=1,
        total_tardiness_hours=2.0,
        weighted_tardiness_hours=3.0,
        makespan_hours=4.0,
        changeover_count=5,
    )
    metric_values = {
        "overdue_count": 1.0,
        "total_tardiness_hours": 2.0,
        "weighted_tardiness_hours": 3.0,
        "makespan_hours": 4.0,
        "changeover_count": 5.0,
    }
    assert objective_score(objective_name, metrics) == tuple(metric_values[key] for key in expected_keys)

    schema = best_score_schema(objective_name)
    schema_keys = [item.get("key") for item in schema if isinstance(item, dict)]
    assert schema_keys == ["failed_ops", *expected_keys]
    assert comparison_metric(objective_name) == expected_keys[0]

    algo = {
        "objective": objective_name,
        "comparison_metric": comparison_metric(objective_name),
        "best_score_schema": schema,
    }
    assert _comparison_metric_from_algo(algo) == expected_keys[0]
    assert objective_label_for(expected_keys[0], algo=algo) == schema[1]["label"]


@pytest.mark.parametrize(
    ("objective_name", "comparison_key"),
    [
        ("min_overdue", "overdue_count"),
        ("min_tardiness", "total_tardiness_hours"),
        ("min_weighted_tardiness", "weighted_tardiness_hours"),
        ("min_changeover", "changeover_count"),
    ],
)
def test_objective_label_fallback_without_schema_uses_objective_specs(objective_name: str, comparison_key: str) -> None:
    labels = objective_choice_labels()

    assert objective_label_for(objective_name) == labels[objective_name]
    assert objective_label_for(comparison_key) == metric_label_for(comparison_key)
