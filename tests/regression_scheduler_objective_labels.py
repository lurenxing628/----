from __future__ import annotations

from core.algorithms.objective_specs import metric_label_for, objective_choice_labels
from core.services.scheduler.config.config_field_spec import choice_label_map_for
from web.viewmodels.scheduler_analysis_vm import _comparison_metric_from_algo, objective_label_for


def test_scheduler_objective_labels_follow_registry_projection() -> None:
    objective_labels = objective_choice_labels()

    assert choice_label_map_for("objective") == objective_labels
    assert objective_label_for("min_overdue") == "最少超期"
    assert objective_label_for("min_weighted_tardiness") == objective_labels["min_weighted_tardiness"]
    assert objective_label_for("min_changeover") == objective_labels["min_changeover"]
    assert objective_label_for("overdue_count") == "超期批次数"
    assert objective_label_for("weighted_tardiness_hours") == metric_label_for("weighted_tardiness_hours")
    assert objective_label_for("changeover_count") == metric_label_for("changeover_count")


def test_analysis_prefers_comparison_metric_and_schema_over_objective_fallback() -> None:
    algo_with_metric = {
        "objective": "min_tardiness",
        "comparison_metric": "changeover_count",
        "best_score_schema": [
            {"index": 0, "key": "failed_ops", "label": "失败工序数"},
            {"index": 1, "key": "total_tardiness_hours", "label": "总拖期小时"},
        ],
    }
    assert _comparison_metric_from_algo(algo_with_metric) == "changeover_count"

    algo_with_schema = {
        "objective": "min_changeover",
        "best_score_schema": [
            {"index": 0, "key": "failed_ops", "label": "失败工序数"},
            {"index": 1, "key": "weighted_tardiness_hours", "label": "加权拖期小时"},
        ],
    }
    assert _comparison_metric_from_algo(algo_with_schema) == "weighted_tardiness_hours"
