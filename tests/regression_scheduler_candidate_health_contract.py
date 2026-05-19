from __future__ import annotations

from datetime import datetime

from core.algorithms import ScheduleResult
from core.services.scheduler.run.schedule_candidate_health import (
    HEALTH_BETTER,
    HEALTH_SAME,
    HEALTH_UNAVAILABLE,
    HEALTH_WORSE,
    evaluate_candidate_health,
)


def _result(
    op_id: int,
    start_hour: int,
    end_hour: int,
    *,
    start_minute: int = 0,
    end_minute: int = 0,
) -> ScheduleResult:
    return ScheduleResult(
        op_id=op_id,
        op_code=f"OP{op_id}",
        batch_id="B1",
        seq=op_id,
        start_time=datetime(2026, 5, 1, start_hour, start_minute, 0),
        end_time=datetime(2026, 5, 1, end_hour, end_minute, 0),
    )


def test_candidate_health_is_better_when_critical_chain_finishes_earlier_and_waits_less() -> None:
    baseline = [_result(1, 8, 10), _result(2, 11, 13)]
    candidate = [_result(1, 8, 9), _result(2, 9, 11)]

    health = evaluate_candidate_health(
        baseline_results=baseline,
        candidate_results=candidate,
        graph_metrics={
            "critical_path_op_ids": [1, 2],
            "top_impact_op_ids": [1, 2],
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
        graph_metrics={"critical_path_op_ids": [1, 2]},
    )

    assert health.state == HEALTH_WORSE
    assert health.critical_chain_finish_hours_delta == 4.0
    assert health.critical_chain_wait_hours_delta == 2.0


def test_candidate_health_treats_small_relative_improvement_as_same() -> None:
    baseline = [_result(1, 8, 13), _result(2, 13, 18)]
    candidate = [_result(1, 8, 13), _result(2, 13, 17, end_minute=48)]

    health = evaluate_candidate_health(
        baseline_results=baseline,
        candidate_results=candidate,
        graph_metrics={"critical_path_op_ids": [1, 2]},
    )

    assert health.state == HEALTH_SAME
    assert health.score == 0


def test_candidate_health_requires_at_least_two_positive_signals_for_better() -> None:
    baseline = [_result(1, 8, 13), _result(2, 13, 18)]
    candidate = [_result(1, 8, 13), _result(2, 13, 17, end_minute=20)]

    health = evaluate_candidate_health(
        baseline_results=baseline,
        candidate_results=candidate,
        graph_metrics={"critical_path_op_ids": [1, 2]},
    )

    assert health.state == HEALTH_SAME
    assert health.score == 1


def test_candidate_health_marks_better_when_two_signals_improve_beyond_threshold() -> None:
    baseline = [_result(1, 8, 10), _result(2, 12, 18)]
    candidate = [_result(1, 8, 10), _result(2, 10, 17, start_minute=30, end_minute=20)]

    health = evaluate_candidate_health(
        baseline_results=baseline,
        candidate_results=candidate,
        graph_metrics={"critical_path_op_ids": [1, 2]},
    )

    assert health.state == HEALTH_BETTER
    assert health.score >= 2


def test_candidate_health_marks_worse_when_two_signals_degrade_beyond_threshold() -> None:
    baseline = [_result(1, 8, 10), _result(2, 10, 18, start_minute=30)]
    candidate = [_result(1, 8, 10), _result(2, 12, 19, start_minute=30)]

    health = evaluate_candidate_health(
        baseline_results=baseline,
        candidate_results=candidate,
        graph_metrics={"critical_path_op_ids": [1, 2]},
    )

    assert health.state == HEALTH_WORSE
    assert health.score <= -2


def test_candidate_health_is_unavailable_without_critical_path_metrics() -> None:
    health = evaluate_candidate_health(
        baseline_results=[_result(1, 8, 10)],
        candidate_results=[_result(1, 8, 9)],
        graph_metrics={},
    )

    assert health.state == HEALTH_UNAVAILABLE
    assert health.reason_code == "critical_path_unavailable"


def test_candidate_health_rejects_critical_path_sample_only() -> None:
    baseline = [_result(1, 8, 10), _result(2, 11, 13)]
    candidate = [_result(1, 8, 9), _result(2, 9, 11)]

    health = evaluate_candidate_health(
        baseline_results=baseline,
        candidate_results=candidate,
        graph_metrics={
            "critical_path_sample": ["op:1", "op:2"],
            "critical_path_count": 2,
            "critical_path_truncated": False,
        },
    )

    assert health.state == HEALTH_UNAVAILABLE
    assert health.reason_code == "critical_path_sample_only"


def test_candidate_health_rejects_truncated_critical_path_sample() -> None:
    baseline = [_result(1, 8, 10), _result(2, 11, 13)]
    candidate = [_result(1, 8, 9), _result(2, 9, 11)]

    health = evaluate_candidate_health(
        baseline_results=baseline,
        candidate_results=candidate,
        graph_metrics={
            "critical_path_sample": ["op:1", "op:2"],
            "critical_path_count": 60,
            "critical_path_truncated": True,
        },
    )

    assert health.state == HEALTH_UNAVAILABLE
    assert health.reason_code == "critical_path_sample_only"


def test_candidate_health_ignores_graph_score_sample_for_top_impact_signal() -> None:
    baseline = [
        _result(1, 8, 10),
        _result(2, 10, 12),
        _result(3, 12, 13),
    ]
    candidate = [
        _result(1, 8, 10),
        _result(2, 10, 11),
        _result(3, 11, 12),
    ]

    health = evaluate_candidate_health(
        baseline_results=baseline,
        candidate_results=candidate,
        graph_metrics={
            "critical_path_op_ids": [1, 2],
            "graph_score_sample": [{"op_id": 3, "impact_count": 99}],
            "graph_score_sample_count": 100,
            "graph_score_sample_truncated": True,
        },
    )

    assert health.state == HEALTH_SAME
    assert health.score == 1
    assert health.top_impact_op_count == 0
