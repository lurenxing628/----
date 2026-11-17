"""Shared archive owns arrangements and compares only matching completion scopes."""

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta

import pytest

from core.algorithms.evaluation import objective_score
from core.algorithms.evaluation_completion import UNKNOWN_OBJECTIVE_VALUE
from core.models.objective import target_objectives_for
from tests._support.shared_schedule_archive import BATCHES, _archive, _candidate, _failure, _result

FIELD_ORDERS = {
    "min_overdue": ("failed_ops", "overdue_count", "weighted_tardiness_hours", "total_tardiness_hours",
                    "makespan_hours", "changeover_count"),
    "min_tardiness": ("failed_ops", "total_tardiness_hours", "overdue_count", "weighted_tardiness_hours",
                      "makespan_hours", "changeover_count"),
    "min_weighted_tardiness": ("failed_ops", "weighted_tardiness_hours", "total_tardiness_hours",
                               "makespan_hours", "changeover_count"),
    "min_changeover": ("failed_ops", "changeover_count", "overdue_count", "total_tardiness_hours",
                       "weighted_tardiness_hours", "makespan_hours"),
}


def _observe(archive, candidate, elapsed, *, phase="baseline", direction="min_tardiness"):
    observed = archive.register_decode(candidate, verified=True, elapsed_ms=elapsed)
    if observed.entry_id in archive:
        archive.finish_observation(observed, candidate, origin={"phase": phase, "direction": direction})
    return observed


def _selected(archive):
    return {objective: archive.selected_entry(objective) for objective in archive.target_objectives}


def _current(archive):
    return {objective: archive.current_entry(objective) for objective in archive.target_objectives}


def _assert_evaluations(archive, entry_id, candidate):
    entry = archive.entry(entry_id)
    for objective, evaluation in entry.evaluations.items():
        assert evaluation.field_order == FIELD_ORDERS[objective]
        assert evaluation.score == (float(candidate["summary"].failed_ops),) + objective_score(
            objective, candidate["metrics"],
        )


def test_content_identity_owns_every_mutable_payload():
    archive = _archive(limit=5)
    rows = [_result(index, hour, machine=f"M{index}") for index, hour in ((1, 0), (2, 2), (3, 4))]
    rows[0].seed_source = "execution_fact"
    fixed_seed = (rows[0],)
    candidate = _candidate(rows, fixed_seed=fixed_seed)
    origin = {"phase": "baseline", "direction": "min_tardiness", "profile": {"weights": [1]}}
    first = archive.register_decode(candidate, verified=True, elapsed_ms=17)
    archive.finish_observation(first, candidate, origin=origin)
    assert first.entry_id is not None and not first.reused and not first.restored
    assert first.initialized_objectives == target_objectives_for("min_tardiness")
    assert first.improved_objectives == ()
    _assert_evaluations(archive, first.entry_id, candidate)

    repeated = deepcopy(candidate)
    repeated["results"].reverse()
    repeated.update(objective="min_changeover", order=["B3", "B2", "B1"], score=(999.0,))
    reused = _observe(archive, repeated, 29, phase="multi_start", direction="min_changeover")
    entry = archive.entry(first.entry_id)
    assert reused.entry_id == first.entry_id and reused.reused and not reused.restored
    assert entry.first_found_elapsed_ms == 17
    assert entry.score_scope.scheduled_operation_ids == frozenset({1, 2, 3})
    assert entry.score_scope.complete_batch_ids == frozenset(BATCHES)
    assert entry.score_scope.is_complete and entry.score_scope.components_known
    assert entry.score_scope.objective_scope == "all_batches"
    assert not hasattr(entry, "results")

    original = deepcopy(candidate)
    stage = archive.materialize(first.entry_id, objective="min_changeover")
    assert stage["results"] == original["results"]
    assert stage["summary"] == original["summary"] and stage["metrics"] == original["metrics"]
    assert stage["score"] == archive.entry(first.entry_id).evaluations["min_changeover"].score
    assert archive.entry(first.entry_id).evidence_origin["profile"]["weights"] == [1]
    stage["results"][1].end_time += timedelta(hours=100)
    stage["summary"].warnings.append("stage warning")
    stage["metrics"].total_tardiness_hours = 500.0
    stage["order"].reverse()
    stage["algo_stats"]["visited"].clear()
    restored_stage = archive.materialize(first.entry_id)
    for key in ("results", "summary", "metrics", "order", "algo_stats"):
        assert restored_stage[key] == original[key]
        assert restored_stage[key] is not stage[key]

    # Changes to real arrangement identity remain distinct even when all objective components tie.
    variants = []
    resource = deepcopy(original)
    resource["results"][0].machine_id = "replacement-M1"
    variants.append(resource)
    microsecond = deepcopy(original)
    microsecond["results"][1].start_time += timedelta(microseconds=1)
    microsecond["results"][1].end_time += timedelta(microseconds=1)
    variants.append(microsecond)
    external = deepcopy(original)
    external["results"][1].source = "external"
    variants.append(external)
    seed_origin = deepcopy(original)
    seed_origin["results"][0].seed_source = "freeze_window"
    variants.append(seed_origin)
    ids = []
    for index, variant in enumerate(variants):
        variant = _candidate(variant["results"], fixed_seed=fixed_seed)
        assert objective_score("min_tardiness", variant["metrics"]) == objective_score("min_tardiness", original["metrics"])
        observed = _observe(archive, variant, 40 + index)
        assert observed.entry_id != first.entry_id and not observed.reused
        assert archive.entry(observed.entry_id).content_key != entry.content_key
        ids.append(observed.entry_id)
        if index == 0:
            archive.accept_exploration("min_changeover", observed.entry_id)
    archive.set_starting_entries("min_tardiness", [ids[1], ids[2], ids[3], ids[1]])
    assert archive.starting_entries("min_tardiness") == tuple(ids[1:])
    with pytest.raises(ValueError):
        archive.set_starting_entries("min_tardiness", [ids[1], ids[2], ids[3], first.entry_id])
    protected = {first.entry_id, *ids}
    assert all(entry_id in archive for entry_id in protected)

    displaced_candidates = []
    displaced_ids = []
    for index in (1, 2):
        displaced = deepcopy(original)
        displaced["results"][1].operator_id = f"unused-O{index}"
        observed = _observe(archive, displaced, 100 + index)
        displaced_candidates.append(displaced)
        displaced_ids.append(observed.entry_id)
    observed_ids = protected | set(displaced_ids)
    assert len(protected) == archive.retention_limit == 5
    assert {entry_id for entry_id in observed_ids if entry_id in archive} == protected
    for entry_id in displaced_ids:
        with pytest.raises(KeyError):
            archive.materialize(entry_id)
    archive.set_starting_entries("min_tardiness", ids[1:3])
    revisited = _observe(archive, displaced_candidates[0], 200, phase="redecode")
    assert revisited.entry_id == displaced_ids[0] and revisited.restored
    assert archive.entry(revisited.entry_id).first_found_elapsed_ms == 101
    assert archive.materialize(revisited.entry_id)["results"] == displaced_candidates[0]["results"]
    assert sum(entry_id in archive for entry_id in observed_ids) <= archive.retention_limit
    assert archive.has_complete_best()
    assert _selected(archive) == {objective: first.entry_id for objective in target_objectives_for("min_tardiness")}


def test_all_target_scores_separate_bests_strict_improvements_and_exploration():
    archive = _archive()
    targets = target_objectives_for("min_tardiness")
    assert targets == ("min_tardiness", "min_overdue", "min_changeover")
    baseline = _candidate([_result(1, 0), _result(2, 2), _result(3, 4)])
    first = _observe(archive, baseline, 10)
    assert first.initialized_objectives == targets and first.improved_objectives == ()
    assert archive.has_complete_best() and _selected(archive) == {objective: first.entry_id for objective in targets}
    assert _current(archive) == {objective: None for objective in targets}
    assert archive.improvement_counts == {objective: 0 for objective in targets}
    expected_scores = {
        "min_tardiness": (0.0, 1.0, 1.0, 2.0, 5.0, 2.0),
        "min_overdue": (0.0, 1.0, 2.0, 1.0, 5.0, 2.0),
        "min_changeover": (0.0, 2.0, 1.0, 1.0, 2.0, 5.0),
    }
    _assert_evaluations(archive, first.entry_id, baseline)
    assert {objective: evaluation.score for objective, evaluation in archive.entry(first.entry_id).evaluations.items()} == expected_scores

    fewer_changes = _candidate([_result(1, 0), _result(3, 2), _result(2, 5)], objective="min_changeover")
    changed = _observe(archive, fewer_changes, 20, phase="local_search", direction="min_changeover")
    assert changed.improved_objectives == ("min_changeover",)
    assert _selected(archive) == {
        "min_tardiness": first.entry_id, "min_overdue": first.entry_id, "min_changeover": changed.entry_id,
    }
    _assert_evaluations(archive, changed.entry_id, fewer_changes)

    on_time = _candidate([_result(1, 0), _result(3, 1), _result(2, 2)], objective="min_changeover")
    improved = _observe(archive, on_time, 30, phase="local_search", direction="min_changeover")
    assert improved.improved_objectives == targets
    assert _selected(archive) == {objective: improved.entry_id for objective in targets}
    assert archive.improvement_counts == {"min_tardiness": 1, "min_overdue": 1, "min_changeover": 2}
    assert archive.entry(improved.entry_id).evidence_origin["direction"] == "min_changeover"
    tied = _candidate([replace(row, machine_id="M2") for row in on_time["results"]])
    equal = _observe(archive, tied, 31, phase="multi_start")
    assert equal.entry_id != improved.entry_id and equal.improved_objectives == ()
    assert _selected(archive) == {objective: improved.entry_id for objective in targets}
    assert archive.entry(improved.entry_id).first_found_elapsed_ms == 30
    assert archive.improvement_counts == {"min_tardiness": 1, "min_overdue": 1, "min_changeover": 2}

    worse = _candidate([_result(1, 7), _result(2, 9), _result(3, 11)])
    explored = _observe(archive, worse, 40, phase="sa")
    archive.accept_exploration("min_tardiness", explored.entry_id)
    assert _current(archive) == {
        "min_tardiness": explored.entry_id, "min_overdue": None, "min_changeover": None,
    }
    assert _selected(archive) == {objective: improved.entry_id for objective in targets}
    assert archive.improvement_counts == {"min_tardiness": 1, "min_overdue": 1, "min_changeover": 2}

    # Priority weights can favor a real arrangement with more ordinary tardiness.
    weighted = _archive("min_weighted_tardiness")
    weighted_targets = target_objectives_for("min_weighted_tardiness")
    assert weighted_targets == ("min_weighted_tardiness", "min_overdue", "min_changeover")
    assert target_objectives_for("min_overdue") == ("min_overdue", "min_tardiness", "min_changeover")
    assert target_objectives_for("min_changeover") == ("min_changeover", "min_overdue", "min_tardiness")
    heavy_late = _candidate([_result(1, 5, machine="M1"), _result(2, 2, machine="M2"), _result(3, 1, machine="M3")],
                            objective="min_weighted_tardiness")
    heavy = _observe(weighted, heavy_late, 1, direction="min_weighted_tardiness")
    light_late = _candidate([_result(1, 2, machine="M1"), _result(2, 6, machine="M2"), _result(3, 1, machine="M3")],
                            objective="min_weighted_tardiness")
    light = _observe(weighted, light_late, 2, direction="min_changeover")
    assert heavy_late["metrics"].total_tardiness_hours == 2.0 < light_late["metrics"].total_tardiness_hours == 3.0
    assert weighted.entry(heavy.entry_id).evaluations["min_weighted_tardiness"].score == (0.0, 6.0, 2.0, 5.0, 0.0)
    assert weighted.entry(light.entry_id).evaluations["min_weighted_tardiness"].score == (0.0, 3.0, 3.0, 6.0, 0.0)
    assert weighted.selected_entry("min_weighted_tardiness") == light.entry_id
    _assert_evaluations(weighted, heavy.entry_id, heavy_late)
    _assert_evaluations(weighted, light.entry_id, light_late)


def test_partial_scopes_use_real_completion_scope_and_reject_unvalidated_trials():
    archive = _archive()
    targets = target_objectives_for("min_tardiness")
    first_partial = _candidate([_result(1, 5), _result(2, 7)], failures=(_failure(3),))
    first = _observe(archive, first_partial, 10)
    scope = archive.entry(first.entry_id).score_scope
    assert scope.scheduled_operation_ids == frozenset({1, 2})
    assert scope.complete_batch_ids == frozenset({"B1", "B2"})
    assert scope.objective_scope == "completed_batches_only" and scope.components_known and not scope.is_complete
    assert first.initialized_objectives == targets and first.improved_objectives == ()
    assert not archive.has_complete_best() and _selected(archive) == {objective: first.entry_id for objective in targets}
    better_partial = _candidate([_result(1, 0), _result(2, 2)], failures=(_failure(3),))
    better = _observe(archive, better_partial, 20)
    assert better.initialized_objectives == () and better.improved_objectives == targets
    other_partial = _candidate([_result(1, 0), _result(3, 1)], failures=(_failure(2),))
    other = _observe(archive, other_partial, 30)
    # An equal-coverage scope keeps its own best; the first-observed scope stays selected.
    assert other.initialized_objectives == targets and other.improved_objectives == ()
    assert _selected(archive) == {objective: better.entry_id for objective in targets}
    assert all(entry_id in archive for entry_id in (first.entry_id, better.entry_id, other.entry_id))
    _assert_evaluations(archive, better.entry_id, better_partial)

    unknown = _candidate([_result(1, 0)])
    # A success flag alone cannot supply missing completion evidence.
    unknown["summary"].success = True
    unknown_result = _observe(archive, unknown, 40)
    unknown_entry = archive.entry(unknown_result.entry_id)
    assert unknown_entry.score_scope.objective_scope == "unknown"
    assert not unknown_entry.score_scope.components_known and not unknown_entry.score_scope.is_complete
    assert unknown_result.entry_id in archive and not unknown_result.reused
    assert unknown_result.initialized_objectives == () and unknown_result.improved_objectives == ()
    assert set(unknown_entry.evaluations) == set(targets)
    for objective, evaluation in unknown_entry.evaluations.items():
        assert evaluation.field_order == FIELD_ORDERS[objective]
        assert evaluation.score == (2.0,) + (UNKNOWN_OBJECTIVE_VALUE,) * (len(FIELD_ORDERS[objective]) - 1)

    unsuccessful = _candidate([_result(1, 0), _result(3, 1), _result(2, 2)])
    unsuccessful["summary"].success = False
    not_complete = _observe(archive, unsuccessful, 45)
    unsuccessful_scope = archive.entry(not_complete.entry_id).score_scope
    assert unsuccessful_scope.scheduled_operation_ids == frozenset({1, 2, 3})
    assert unsuccessful_scope.components_known and not unsuccessful_scope.is_complete
    # The widest partial scope is selected while no complete schedule exists.
    assert not archive.has_complete_best() and _selected(archive) == {objective: not_complete.entry_id for objective in targets}

    complete = _candidate([_result(1, 7), _result(2, 9), _result(3, 11)])
    retained = (first.entry_id, better.entry_id, other.entry_id, unknown_result.entry_id, not_complete.entry_id)
    for _ in range(3):
        rejected = archive.register_decode(complete, verified=False, elapsed_ms=50)
        assert rejected.entry_id not in retained and rejected.reason and not rejected.reused and not rejected.restored
        assert rejected.entry_id not in archive and all(entry_id in archive for entry_id in retained)
        assert not archive.has_complete_best()
    valid = _observe(archive, complete, 60)
    assert valid.initialized_objectives == targets and valid.improved_objectives == ()
    assert archive.has_complete_best() and _selected(archive) == {objective: valid.entry_id for objective in targets}
    late_partial = _candidate([_result(1, 0), _result(2, 1)], failures=(_failure(3),))
    _observe(archive, late_partial, 70)
    assert _selected(archive) == {objective: valid.entry_id for objective in targets}
    assert archive.improvement_counts == {objective: 0 for objective in targets}

    # Completed decodes share one payload cap. Only three coverage scopes protect partial bests.
    bounded = _archive(limit=4)
    high_scopes = []
    for index, included in enumerate(((1, 2), (1, 3), (2, 3))):
        partial = _candidate([_result(op_id, 4 + 2 * offset) for offset, op_id in enumerate(included)],
                             failures=tuple(_failure(op_id) for op_id in (1, 2, 3) if op_id not in included))
        observed = _observe(bounded, partial, 100 + index)
        high_scopes.append(observed.entry_id)
    low_current = _candidate([_result(1, 5)], failures=(_failure(2), _failure(3)))
    low = _observe(bounded, low_current, 110)
    bounded.accept_exploration("min_tardiness", low.entry_id)
    improved_low = _candidate([_result(1, 0)], failures=(_failure(2), _failure(3)))
    displaced = _observe(bounded, improved_low, 120)
    assert displaced.improved_objectives == targets
    bounded_ids = (*high_scopes, low.entry_id, displaced.entry_id)
    assert {entry_id for entry_id in bounded_ids if entry_id in bounded} == {*high_scopes, low.entry_id}
    with pytest.raises(KeyError):
        bounded.materialize(displaced.entry_id)
    # Eviction hands the scope's best back to the kept member, so the evicted arrangement improves on it again.
    redecoded = _observe(bounded, improved_low, 125)
    assert redecoded.entry_id == displaced.entry_id and redecoded.restored
    assert redecoded.improved_objectives == targets and displaced.entry_id not in bounded
    assert bounded.current_entry("min_tardiness") == low.entry_id
    assert not bounded.has_complete_best() and bounded.improvement_counts == {objective: 0 for objective in targets}

    bounded.accept_exploration("min_tardiness", high_scopes[0])
    next_low = _candidate([_result(2, 0)], failures=(_failure(1), _failure(3)))
    next_observed = _observe(bounded, next_low, 130)
    assert next_observed.initialized_objectives == targets
    bounded_ids += (next_observed.entry_id,)
    assert {entry_id for entry_id in bounded_ids if entry_id in bounded} == {*high_scopes, next_observed.entry_id}
    with pytest.raises(KeyError):
        bounded.materialize(low.entry_id)

    completed = _observe(bounded, complete, 140)
    assert bounded.has_complete_best() and _selected(bounded) == {objective: completed.entry_id for objective in targets}
    bounded_ids += (completed.entry_id,)
    assert sum(entry_id in bounded for entry_id in bounded_ids) == bounded.retention_limit == 4
    assert bounded.current_entry("min_tardiness") == high_scopes[0]
    assert high_scopes[0] in bounded and completed.entry_id in bounded
    assert high_scopes[1] not in bounded
    assert bounded.improvement_counts == {objective: 0 for objective in targets}

    # Unknown components still have real coverage; a selected scope keeps its first valid payload.
    unknown_bounded = _archive(limit=3)
    unknown_high = _candidate([_result(1, 0), _result(2, 2)])
    unknown_high_result = _observe(unknown_bounded, unknown_high, 200)
    high_scope = unknown_bounded.entry(unknown_high_result.entry_id).score_scope
    assert not high_scope.components_known and high_scope.complete_batch_ids == frozenset({"B1", "B2"})
    assert unknown_high_result.initialized_objectives == ()
    explained_high_ids = []
    for index, included in enumerate(((1, 3), (2, 3))):
        partial = _candidate([_result(op_id, 2 * offset) for offset, op_id in enumerate(included)],
                             failures=tuple(_failure(op_id) for op_id in (1, 2, 3) if op_id not in included))
        observed = _observe(unknown_bounded, partial, 210 + index)
        explained_high_ids.append(observed.entry_id)
    lower_coverage = _observe(unknown_bounded, improved_low, 220)
    unknown_ids = (unknown_high_result.entry_id, *explained_high_ids, lower_coverage.entry_id)
    assert {entry_id for entry_id in unknown_ids if entry_id in unknown_bounded} == {
        unknown_high_result.entry_id, *explained_high_ids}
    assert unknown_bounded.materialize(unknown_high_result.entry_id)["results"] == unknown_high["results"]
    assert _selected(unknown_bounded) == {objective: unknown_high_result.entry_id for objective in targets}
    with pytest.raises(KeyError):
        unknown_bounded.materialize(lower_coverage.entry_id)


def test_decode_registration_owns_one_payload_and_trials_keep_only_temporary_numbers():
    from unittest.mock import patch

    from core.services.scheduler.run.optimizer.candidate_fingerprint import schedule_content_key

    archive = _archive()
    candidate = _candidate([_result(1, 0), _result(2, 2), _result(3, 4)])
    with patch("core.services.scheduler.run.optimizer.shared_archive.schedule_content_key",
               wraps=schedule_content_key) as content_key:
        observed = archive.register_decode(candidate, verified=True, elapsed_ms=10)
        archive.finish_observation(observed, candidate, origin={"phase": "baseline"})
        first = archive.view(observed.entry_id)
        second = archive.view(observed.entry_id, objective="min_changeover")
        assert first is not second
        assert first["results"] is second["results"] is candidate["results"]
        assert first["metrics"] is second["metrics"] is candidate["metrics"]
        assert first["summary"] is second["summary"] is candidate["summary"]
        first["order"] = ["B3", "B1", "B2"]
        assert second["order"] == candidate["order"]
        assert content_key.call_count == 1

        known = archive.register_decode(candidate, verified=False, elapsed_ms=20)
        assert known.entry_id == observed.entry_id and known.reused
        unknown = _candidate([_result(1, 7), _result(2, 9), _result(3, 11)])
        before = dict(archive._identities)
        trial = archive.register_decode(unknown, verified=False, elapsed_ms=30)
        retry = archive.register_decode(unknown, verified=False, elapsed_ms=40)
        assert trial.entry_id != retry.entry_id
        assert trial.entry_id not in archive
        assert archive._identities == before
        assert _selected(archive) == dict.fromkeys(archive.target_objectives, observed.entry_id)

    public = archive.materialize(observed.entry_id)
    public["results"][0].machine_id = "published caller change"
    public["summary"].warnings.append("published caller change")
    assert archive.view(observed.entry_id)["results"][0].machine_id == "M1"
    assert archive.view(observed.entry_id)["summary"].warnings == ["original warning"]
