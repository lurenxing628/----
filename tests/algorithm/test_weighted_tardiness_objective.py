"""加权拖期按其目标比较优劣，并由共同运行配置接收。"""

from __future__ import annotations

from core.algorithms.evaluation import ScheduleMetrics, objective_score
from core.models.schedule_config_runtime import ensure_schedule_config_snapshot
from core.models.schedule_config_runtime_fields import default_snapshot_values


def test_weighted_tardiness_objective_contract() -> None:
    metrics_a = ScheduleMetrics(
        overdue_count=1,
        total_tardiness_hours=10.0,
        makespan_hours=100.0,
        changeover_count=1,
        weighted_tardiness_hours=30.0,
    )
    metrics_b = ScheduleMetrics(
        overdue_count=1,
        total_tardiness_hours=20.0,
        makespan_hours=100.0,
        changeover_count=1,
        weighted_tardiness_hours=20.0,
    )

    assert objective_score("min_tardiness", metrics_a) < objective_score("min_tardiness", metrics_b)
    assert objective_score("min_weighted_tardiness", metrics_b) < objective_score("min_weighted_tardiness", metrics_a)

    snapshot = ensure_schedule_config_snapshot(
        dict(default_snapshot_values(), objective="min_weighted_tardiness"), strict_mode=True,
    )
    assert snapshot.objective == "min_weighted_tardiness"
