from __future__ import annotations

from datetime import datetime

from core.algorithms import ScheduleResult
from core.services.scheduler.run.schedule_candidate_health import (
    HEALTH_BETTER,
    HEALTH_UNAVAILABLE,
    HEALTH_WORSE,
    evaluate_candidate_health,
)


def _result(op_id: int, start_hour: int, end_hour: int) -> ScheduleResult:
    return ScheduleResult(
        op_id=op_id,
        op_code=f"OP{op_id}",
        batch_id="B1",
        seq=op_id,
        start_time=datetime(2026, 5, 1, start_hour, 0, 0),
        end_time=datetime(2026, 5, 1, end_hour, 0, 0),
    )


def test_candidate_health_is_better_when_critical_chain_finishes_earlier_and_waits_less() -> None:
    baseline = [_result(1, 8, 10), _result(2, 11, 13)]
    candidate = [_result(1, 8, 9), _result(2, 9, 11)]

    health = evaluate_candidate_health(
        baseline_results=baseline,
        candidate_results=candidate,
        graph_metrics={
            "critical_path_sample": ["op:1", "op:2"],
            "graph_score_sample": [{"op_id": 1, "impact_count": 3}, {"op_id": 2, "impact_count": 1}],
        },
    )

    assert health.state == HEALTH_BETTER
    assert health.critical_chain_finish_hours_delta == -2.0
    assert health.critical_chain_wait_hours_delta == -1.0
    assert health.top_impact_op_count == 2


def test_candidate_health_is_worse_when_critical_chain_finishes_later_and_waits_more() -> None:
    baseline = [_result(1, 8, 9), _result(2, 9, 10)]
    candidate = [_result(1, 8, 10), _result(2, 12, 14)]

    health = evaluate_candidate_health(
        baseline_results=baseline,
        candidate_results=candidate,
        graph_metrics={"critical_path_sample": ["op:1", "op:2"]},
    )

    assert health.state == HEALTH_WORSE
    assert health.critical_chain_finish_hours_delta == 4.0
    assert health.critical_chain_wait_hours_delta == 2.0


def test_candidate_health_is_unavailable_without_critical_path_metrics() -> None:
    health = evaluate_candidate_health(
        baseline_results=[_result(1, 8, 10)],
        candidate_results=[_result(1, 8, 9)],
        graph_metrics={},
    )

    assert health.state == HEALTH_UNAVAILABLE
    assert health.reason_code == "critical_path_unavailable"
