"""加权拖期按其目标比较优劣，并由共同运行配置接收。"""

from __future__ import annotations

from core.algorithms.evaluation import ScheduleMetrics, objective_score
from core.algorithms.evaluation_completion import BatchCompletion
from core.models.schedule_config_runtime_fields import default_snapshot_values
from core.services.scheduler.config.config_snapshot import build_schedule_config_snapshot

COMPLETE = BatchCompletion(expected_operation_count=1, missing_operation_count=0, unexpected_result_count=0,
                           complete_batch_count=1, incomplete_batch_ids=(), partial_batch_ids=(),
                           failure_detail_count=0, failure_batch_ids=())


def test_weighted_tardiness_objective_contract() -> None:
    metrics_a = ScheduleMetrics(
        overdue_count=1,
        total_tardiness_hours=10.0,
        makespan_hours=100.0,
        changeover_count=1,
        completion=COMPLETE,
        weighted_tardiness_hours=30.0,
    )
    metrics_b = ScheduleMetrics(
        overdue_count=1,
        total_tardiness_hours=20.0,
        makespan_hours=100.0,
        changeover_count=1,
        completion=COMPLETE,
        weighted_tardiness_hours=20.0,
    )

    assert objective_score("min_tardiness", metrics_a) < objective_score("min_tardiness", metrics_b)
    assert objective_score("min_weighted_tardiness", metrics_b) < objective_score("min_weighted_tardiness", metrics_a)

    values = dict(default_snapshot_values(), objective="min_weighted_tardiness")
    snapshot = build_schedule_config_snapshot(rows=[{"config_key": key, "config_value": value} for key, value in values.items()])
    assert snapshot.objective == "min_weighted_tardiness"
