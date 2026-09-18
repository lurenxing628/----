"""2026-09-18 revision of A18: explained incompleteness scores the completed batches; unexplained stays unknown.

``failed_ops`` remains the first key of every candidate score (prepended by the callers). Behind it an
incomplete candidate whose every missing batch carries failure evidence compares on the real metrics of its
completed batches, so equal-failed_ops candidates order by numbers instead of tying. Incompleteness without
evidence, partial evidence or unexpected results keep the all-components sentinel, which never beats a
finite complete score. Complete candidates are untouched.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from core.algorithms import GreedyScheduler, ScheduleResult, SortStrategy
from core.algorithms.evaluation import compute_metrics, objective_score
from core.algorithms.evaluation_completion import UNKNOWN_OBJECTIVE_VALUE
from core.algorithms.objective_specs import objective_metric_keys
from core.services.scheduler.contracts.optimizer_public_safety import project_attempt_metrics, project_public_metrics
from core.services.scheduler.run.optimizer_proof_oracle import _ContinuousCalendar, _default_config

OBJECTIVES = ("min_overdue", "min_tardiness", "min_weighted_tardiness", "min_changeover")
START = datetime(2026, 1, 1, 8)


def _op(op_id, bid):
    return SimpleNamespace(id=op_id, batch_id=bid)


def _result(op_id, bid, *, hours):
    return ScheduleResult(op_id=op_id, op_code=f"OP{op_id}", batch_id=bid, seq=1, machine_id="M1", operator_id="O1",
                          start_time=START, end_time=START + timedelta(hours=hours), source="internal", op_type_name="t")


def _batches(**priorities):
    return {bid: SimpleNamespace(batch_id=bid, due_date="2026-01-01", priority=priority) for bid, priority in priorities.items()}


def _failure(op_id, bid):
    return {"code": "dispatch_operation_failed", "op_id": op_id, "batch_id": bid}


OPERATIONS = [_op(1, "B1"), _op(2, "B2"), _op(3, "B3")]


def _explained(*, b2_hours):
    """B1 fails with evidence; B2 completes ``b2_hours`` after the start; B3 completes on time."""
    results = [_result(2, "B2", hours=b2_hours), _result(3, "B3", hours=1)]
    return compute_metrics(results, _batches(B1="critical", B2="normal", B3="urgent"), expected_operations=OPERATIONS,
                           seed_results=[], failure_details=[_failure(1, "B1")])


@pytest.mark.parametrize("objective", OBJECTIVES)
def test_explained_incompleteness_scores_the_completed_batches_only(objective):
    metrics = _explained(b2_hours=26)
    score = objective_score(objective, metrics)
    assert score == tuple(float(getattr(metrics, key)) for key in objective_metric_keys(objective))
    assert all(item < UNKNOWN_OBJECTIVE_VALUE for item in score)
    assert (metrics.overdue_count, metrics.total_tardiness_hours) == (1, 10.0)
    evidence = metrics.to_dict()["completion"]
    assert evidence["objective_defined"] is False
    assert evidence["objective_score_policy"] == "completed_batches_only"
    assert evidence["objective_scope"] == "completed_batches_only"
    assert evidence["unknown_objective_value"] is None
    assert evidence["incomplete_work_weight"] == 3.0
    assert evidence["incomplete_batch_ids_sample"] == ["B1"]
    json.dumps(metrics.to_dict(), allow_nan=False)


@pytest.mark.parametrize("objective", ("min_overdue", "min_tardiness", "min_weighted_tardiness"))
def test_equal_failed_ops_candidates_order_by_their_completed_batches_instead_of_tying(objective):
    better = (1.0,) + objective_score(objective, _explained(b2_hours=4))
    worse = (1.0,) + objective_score(objective, _explained(b2_hours=26))
    assert better < worse
    assert (0.0,) + objective_score(objective, _explained(b2_hours=4)) < worse


def test_explained_incompleteness_never_outranks_a_complete_candidate_behind_failed_ops():
    complete = compute_metrics([_result(1, "B1", hours=1), _result(2, "B2", hours=90), _result(3, "B3", hours=1)],
                               _batches(B1="critical", B2="normal", B3="urgent"), expected_operations=OPERATIONS)
    assert complete.completion.objective_defined
    assert complete.completion.objective_score_policy == "original"
    assert complete.to_dict()["completion"]["objective_scope"] == "all_batches"
    assert complete.to_dict()["completion"]["incomplete_work_weight"] == 0.0
    for objective in OBJECTIVES:
        assert (0.0,) + objective_score(objective, complete) < (1.0,) + objective_score(objective, _explained(b2_hours=1))


@pytest.mark.parametrize("objective", OBJECTIVES)
def test_missing_operations_without_evidence_stay_unknown(objective):
    unknown = (UNKNOWN_OBJECTIVE_VALUE,) * len(objective_metric_keys(objective))
    no_evidence = compute_metrics([_result(2, "B2", hours=1), _result(3, "B3", hours=1)], _batches(B1="normal", B2="normal", B3="normal"),
                                  expected_operations=OPERATIONS, seed_results=[], failure_details=[])
    assert objective_score(objective, no_evidence) == unknown
    assert no_evidence.to_dict()["completion"]["objective_score_policy"] == "unknown_all_components"
    assert no_evidence.to_dict()["completion"]["unknown_objective_value"] == sys.float_info.max
    partly = compute_metrics([_result(3, "B3", hours=1)], _batches(B1="normal", B2="normal", B3="normal"),
                             expected_operations=OPERATIONS, seed_results=[], failure_details=[_failure(1, "B1")])
    assert objective_score(objective, partly) == unknown
    assert partly.to_dict()["completion"]["objective_scope"] == "unknown"
    unexpected = compute_metrics([_result(2, "B2", hours=1), _result(3, "B3", hours=1), _result(9, "B9", hours=1)],
                                 _batches(B1="normal", B2="normal", B3="normal"),
                                 expected_operations=OPERATIONS, seed_results=[], failure_details=[_failure(1, "B1")])
    assert objective_score(objective, unexpected) == unknown


def test_real_scheduler_window_failure_is_explained_and_scores_behind_failed_ops():
    operations = [
        SimpleNamespace(id=op_id, batch_id="B1", op_code=f"OP{op_id}", seq=op_id, source="internal", setup_hours=hours,
                        unit_hours=0.0, machine_id="M1", operator_id="O1", op_type_id="", op_type_name="cut")
        for op_id, hours in ((1, 1.0), (2, 48.0))
    ]
    batches = {"B1": SimpleNamespace(batch_id="B1", due_date="2026-01-01", priority="urgent", quantity=1)}
    scheduler = GreedyScheduler(calendar_service=_ContinuousCalendar(), config_service=_default_config())
    results, summary, _strategy, _params = scheduler.schedule(
        operations=operations, batches=batches, strategy=SortStrategy.PRIORITY_FIRST,
        start_dt=START, end_date=START.date(), dispatch_mode="sgs", strict_mode=True,
    )
    assert summary.failed_ops == 1
    metrics = compute_metrics(results, batches, expected_operations=operations, seed_results=[],
                              failure_details=summary.failure_details)
    assert metrics.completion.explained
    assert metrics.completion.incomplete_work_weight == 2.0
    score = (float(summary.failed_ops),) + objective_score("min_tardiness", metrics)
    assert score == (1.0, 0.0, 0.0, 0.0, 1.0, 0.0)


@pytest.mark.parametrize("project", [project_attempt_metrics, project_public_metrics])
def test_public_projection_carries_the_completed_subset_scope_without_samples(project):
    projected = project(_explained(b2_hours=26).to_dict())["completion"]
    assert projected["objective_score_policy"] == "completed_batches_only"
    assert projected["objective_scope"] == "completed_batches_only"
    assert projected["incomplete_work_weight"] == 3.0
    assert "B1" not in json.dumps(projected)
