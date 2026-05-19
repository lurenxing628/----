from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.run.schedule_candidate_health import (
    HEALTH_BETTER,
    HEALTH_UNAVAILABLE,
    CandidateHealth,
    unavailable_health,
)
from core.services.scheduler.run.schedule_candidate_runner import CandidatePlan
from core.services.scheduler.run.schedule_candidate_selection import select_candidate_plan


def _plan(
    key: str,
    kind: str,
    score,
    *,
    sequence: int,
    status: str = "completed",
    overdue_count: int = 0,
    total_tardiness_hours: float = 0.0,
    health_state: str = HEALTH_UNAVAILABLE,
) -> CandidatePlan:
    return CandidatePlan(
        sequence=sequence,
        candidate_key=key,
        kind=kind,
        label=key,
        status=status,
        score=tuple(score) if score is not None else None,
        graph_critical_weight=0,
        graph_impact_weight=0,
        graph_downstream_weight=0,
        metrics=SimpleNamespace(
            overdue_count=overdue_count,
            total_tardiness_hours=total_tardiness_hours,
        ),
        health=CandidateHealth(
            state=health_state,
            score=1 if health_state == HEALTH_BETTER else 0,
            reason_code=health_state,
            critical_chain_finish_hours_delta=None,
            critical_chain_wait_hours_delta=None,
            top_impact_ops_avg_start_hours_delta=None,
            critical_chain_slack_hours_delta=None,
            critical_chain_node_count=0,
            top_impact_op_count=0,
        ),
    )


def test_score_only_selects_smallest_raw_score() -> None:
    selection = select_candidate_plan(
        [
            _plan("baseline", "baseline", (0, 2, 0), sequence=0),
            _plan("graph_w1_of_5", "critical_chain", (0, 1, 0), sequence=1, health_state=HEALTH_BETTER),
        ],
        policy="score_only",
    )

    assert selection.selected_candidate_key == "graph_w1_of_5"
    assert selection.reason_code == "score_only_raw_score"


def test_raw_score_tie_prefers_baseline_then_generation_order() -> None:
    selection = select_candidate_plan(
        [
            _plan("graph_w1_of_5", "critical_chain", (0, 1, 0), sequence=1, health_state=HEALTH_BETTER),
            _plan("baseline", "baseline", (0, 1, 0), sequence=0),
        ],
        policy="score_only",
    )

    assert selection.selected_candidate_key == "baseline"


def test_balanced_allows_healthy_critical_candidate_to_override_within_tolerance() -> None:
    selection = select_candidate_plan(
        [
            _plan("baseline", "baseline", (0, 0, 10), sequence=0, total_tardiness_hours=10.0),
            _plan(
                "graph_w2_of_5",
                "critical_chain",
                (0, 0, 11),
                sequence=2,
                total_tardiness_hours=11.0,
                health_state=HEALTH_BETTER,
            ),
        ],
        policy="balanced",
        graph_tardiness_tolerance_ratio=0.10,
    )

    assert selection.selected_candidate_key == "graph_w2_of_5"
    assert selection.reason_code == "balanced_health_override"


def test_balanced_does_not_override_when_health_is_unavailable() -> None:
    selection = select_candidate_plan(
        [
            _plan("baseline", "baseline", (0, 0, 10), sequence=0, total_tardiness_hours=10.0),
            _plan(
                "graph_w2_of_5",
                "critical_chain",
                (0, 0, 11),
                sequence=2,
                total_tardiness_hours=11.0,
                health_state=HEALTH_UNAVAILABLE,
            ),
        ],
        policy="balanced",
    )

    assert selection.selected_candidate_key == "baseline"
    assert selection.reason_code == "balanced_raw_score"


def test_balanced_selection_does_not_override_when_critical_health_unavailable() -> None:
    baseline = SimpleNamespace(
        candidate_key="baseline",
        kind="baseline",
        status="completed",
        sequence=0,
        score=(0.0, 0.0),
        metrics=SimpleNamespace(overdue_count=0, total_tardiness_hours=0.0),
        health=None,
    )
    critical = SimpleNamespace(
        candidate_key="critical",
        kind="critical_chain",
        status="completed",
        sequence=1,
        score=(0.0, 1.0),
        metrics=SimpleNamespace(overdue_count=0, total_tardiness_hours=0.0),
        health=unavailable_health("critical_path_sample_only"),
    )

    selection = select_candidate_plan([baseline, critical], policy="balanced")

    assert selection.selected_candidate_key == "baseline"
    assert selection.reason_code == "balanced_raw_score"
    assert selection.critical_health_best_key is None


def test_selection_fails_when_no_candidate_completed() -> None:
    with pytest.raises(ValidationError) as exc_info:
        select_candidate_plan([_plan("baseline", "baseline", None, sequence=0, status="failed")])

    assert exc_info.value.field == "candidate_selection"
