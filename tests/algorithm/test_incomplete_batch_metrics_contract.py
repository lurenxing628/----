"""A18: missing operations are unknown completion, never shorter tardiness."""

from __future__ import annotations

import json
import math
import random
import sys
from dataclasses import replace
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from core.algorithms import ScheduleResult
from core.algorithms.evaluation import ScheduleMetrics, compute_metrics, objective_score
from core.algorithms.evaluation_completion import UNKNOWN_OBJECTIVE_VALUE
from core.algorithms.objective_specs import objective_metric_keys
from core.services.scheduler.run.optimizer_acceptance import decide_acceptance

OBJECTIVES = ("min_overdue", "min_tardiness", "min_weighted_tardiness", "min_changeover")
START = datetime(2026, 1, 1, 8)


def _op(op_id, bid="B1"):
    return SimpleNamespace(id=op_id, batch_id=bid)


def _result(op_id, bid="B1", *, hours=1, source="internal"):
    return ScheduleResult(
        op_id=op_id, op_code=f"OP{op_id}", batch_id=bid, seq=op_id,
        start_time=START, end_time=START + timedelta(hours=hours),
        machine_id="M1", operator_id="O1", source=source,
    )


def _batches(*ids, due="2026-01-01"):
    return {bid: SimpleNamespace(batch_id=bid, due_date=due, priority="Urgent") for bid in ids}


def test_partial_finish_is_not_tardiness_and_completed_batch_keeps_old_contribution():
    batches = _batches("B1", "B2")
    results = [_result(1, hours=48), _result(3, "B2", hours=24)]
    metrics = compute_metrics(results, batches, expected_operations=[_op(1), _op(2), _op(3, "B2")])
    assert (metrics.overdue_count, metrics.total_tardiness_hours, metrics.weighted_tardiness_hours) == (1, 8, 16)
    assert metrics.makespan_hours == 48
    assert metrics.machine_busy_hours_total == 72
    assert metrics.unscheduled_batch_count == 0
    evidence = metrics.to_dict()["completion"]
    assert evidence["objective_defined"] is False
    assert evidence["complete_batch_count"] == 1
    assert evidence["missing_operation_count"] == 1
    assert evidence["incomplete_batch_count"] == evidence["partial_batch_count"] == 1
    assert evidence["incomplete_batch_ids_sample"] == ["B1"]
    assert evidence["due_metrics_scope"] == "completed_batches_only"
    assert evidence["resource_metrics_scope"] == "scheduled_results_only"
    assert evidence["unknown_objective_value"] == sys.float_info.max
    json.dumps(metrics.to_dict(), allow_nan=False)


@pytest.mark.parametrize("objective", OBJECTIVES)
def test_incomplete_candidates_tie_even_when_partial_horizon_and_completed_subset_differ(objective):
    batches = _batches("B1", "B2")
    operations = [_op(1), _op(2), _op(3, "B2")]
    early = compute_metrics([_result(1)], batches, expected_operations=operations)
    late = compute_metrics([_result(1, hours=96), _result(3, "B2", hours=72)], batches, expected_operations=operations)
    assert early.completion.incomplete_batch_ids != late.completion.incomplete_batch_ids
    assert early.total_tardiness_hours != late.total_tardiness_hours
    assert objective_score(objective, early) == objective_score(objective, late)
    assert objective_score(objective, early) == (UNKNOWN_OBJECTIVE_VALUE,) * len(objective_metric_keys(objective))


@pytest.mark.parametrize("objective", OBJECTIVES)
@pytest.mark.parametrize("value", [-sys.float_info.max, -1.0, 0.0, 1.0, 1e300, sys.float_info.max])
def test_unknown_never_beats_any_finite_complete_score_including_negative_directions(objective, value):
    complete = ScheduleMetrics(0, 0.0, 0.0, 0)
    for key in objective_metric_keys(objective):
        setattr(complete, key, value)
    unknown = compute_metrics([], _batches("B1"), expected_operations=[_op(1)])
    complete_score = objective_score(objective, complete)
    unknown_score = objective_score(objective, unknown)
    assert all(math.isfinite(item) for item in unknown_score)
    assert not unknown_score < complete_score
    assert len(complete_score) == len(unknown_score) == len(objective_metric_keys(objective))


@pytest.mark.parametrize("objective", OBJECTIVES)
@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_complete_score_fails_loudly(objective, value):
    complete = ScheduleMetrics(0, 0.0, 0.0, 0)
    setattr(complete, objective_metric_keys(objective)[0], value)
    with pytest.raises(ValueError, match="finite"):
        objective_score(objective, complete)


@pytest.mark.parametrize("objective", OBJECTIVES)
def test_complete_run_retains_old_metrics_values_and_score_length(objective):
    results = [_result(1, hours=16), _result(2, "B2", hours=24)]
    batches = _batches("B1", "B2")
    old = compute_metrics(results, batches)
    new = compute_metrics(results, batches, expected_operations=[_op(1), _op(2, "B2")])
    payload = new.to_dict()
    assert payload.pop("completion")["objective_defined"] is True
    assert payload == old.to_dict()
    assert objective_score(objective, new) == objective_score(objective, old)
    assert new.overdue_count == 2  # due_exclusive boundary remains overdue with zero hours.


def test_failed_ops_remains_first_and_improve_only_rejects_unknown_tie():
    unknown = compute_metrics([_result(1)], _batches("B1"), expected_operations=[_op(1), _op(2)])
    complete = compute_metrics([_result(1, hours=48)], _batches("B1"), expected_operations=[_op(1)])
    suffix = objective_score("min_overdue", unknown)
    complete_suffix = objective_score("min_overdue", complete)
    assert (0.0,) + suffix < (1.0,) + complete_suffix
    assert (1.0,) + complete_suffix < (1.0,) + suffix
    score = (1.0,) + suffix
    decision = decide_acceptance(
        acceptance_name="improve_only", candidate_score=score, current_score=score,
        best_score=score, iteration=1, max_iterations=10, random_seed=1, rnd=random.Random(1),
    )
    assert not decision.accepted
    assert decision.score_delta == 0
    assert decision.acceptance_reason == "not_improved"


@pytest.mark.parametrize("due", [None, "not-a-date", "2026-01-01"])
def test_wholly_unscheduled_and_missing_due_are_still_incomplete(due):
    metrics = compute_metrics([], _batches("B1", due=due), expected_operations=[_op(1)])
    assert metrics.unscheduled_batch_count == 1
    assert metrics.completion.missing_operation_count == 1
    assert metrics.completion.partial_batch_ids == ()
    assert not metrics.completion.objective_defined
    assert metrics.invalid_due_count == int(due == "not-a-date")


@pytest.mark.parametrize("source", ["freeze_window", "execution_fact"])
def test_frozen_or_completed_seed_must_be_present_in_real_output(source):
    seed = replace(_result(1), seed_source=source)
    remaining = _result(2, hours=24)
    batches = _batches("B1")
    full = compute_metrics([seed, remaining], batches, expected_operations=[_op(2)], seed_results=[seed])
    assert full.completion.objective_defined
    assert full.completion.expected_operation_count == 2
    assert full.total_tardiness_hours == 8
    missing_seed = compute_metrics([remaining], batches, expected_operations=[_op(2)], seed_results=[seed])
    assert missing_seed.completion.missing_operation_count == 1
    assert not missing_seed.completion.objective_defined


def test_overlapping_seed_and_expected_operation_count_once():
    seed = _result(1)
    metrics = compute_metrics([seed], _batches("B1"), expected_operations=[_op(1)], seed_results=[seed])
    assert metrics.completion.expected_operation_count == 1
    assert metrics.completion.objective_defined


def test_merged_external_members_each_require_an_operation_result():
    rows = [_result(1, source="external", hours=24), _result(2, source="external", hours=24)]
    batches, operations = _batches("B1"), [_op(1), _op(2)]
    full = compute_metrics(rows, batches, expected_operations=operations)
    assert full.completion.objective_defined
    assert full.total_tardiness_hours == 8
    assert full.machine_busy_hours_total == 0
    partial = compute_metrics(rows[:1], batches, expected_operations=operations)
    assert partial.completion.missing_operation_count == 1
    assert partial.total_tardiness_hours == 0  # Completed-batch subtotal, not an estimate for B1.
    assert not partial.to_dict()["completion"]["objective_defined"]


def test_failure_details_veto_present_output_and_can_resolve_batch_from_id():
    for detail in ({"batch_id": "B1", "op_id": 1}, {"op_id": 1}):
        metrics = compute_metrics(
            [_result(1, hours=48)], _batches("B1"), expected_operations=[_op(1)], failure_details=[detail],
        )
        assert metrics.completion.missing_operation_count == 0
        assert metrics.completion.failure_detail_count == 1
        assert metrics.completion.failure_batch_ids == ("B1",)
        assert not metrics.completion.objective_defined
        assert metrics.overdue_count == 0


def test_zero_duration_counts_but_missing_or_reversed_time_does_not():
    rows = [_result(1, hours=0)]
    assert compute_metrics(rows, _batches("B1"), expected_operations=[_op(1)]).completion.objective_defined
    for row in (replace(rows[0], end_time=None), replace(rows[0], end_time=START - timedelta(hours=1))):
        metrics = compute_metrics([row], _batches("B1"), expected_operations=[_op(1)])
        assert metrics.completion.missing_operation_count == 1
        assert not metrics.completion.objective_defined


def test_equal_row_count_does_not_hide_missing_identity_or_wrong_batch():
    operations = [_op(1), _op(2)]
    for rows in ([_result(1), _result(1)], [_result(1), _result(2, "B2")]):
        metrics = compute_metrics(rows, _batches("B1"), expected_operations=operations)
        assert metrics.completion.missing_operation_count == 1
        assert not metrics.completion.objective_defined


def test_empty_expected_set_is_not_a_request_for_legacy_scoring():
    metrics = compute_metrics([_result(1)], _batches("B1"), expected_operations=[])
    assert metrics.completion.unexpected_result_count == 1
    assert not metrics.completion.objective_defined


def test_missing_expected_universe_or_unattributable_failure_is_not_silently_ignored():
    with pytest.raises(ValueError, match="expected_operations"):
        compute_metrics([], _batches("B1"), failure_details=[])
    with pytest.raises(ValueError, match="attributed"):
        compute_metrics([], _batches("B1"), expected_operations=[_op(1)], failure_details=[{}])
