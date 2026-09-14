"""Fast real-entry cases and an independent oracle; the full matrix stays an explicit serial run."""
from __future__ import annotations

import copy
from dataclasses import replace
from datetime import datetime
from types import SimpleNamespace

import pytest

from core.algorithms import GreedyScheduler
from core.services.scheduler.run.schedule_optimizer import _default_runtime
from tests._support import optimizer_end_to_end_runner as runner
from tests._support.optimizer_end_to_end_cases import OBJECTIVES, SCENARIOS, audit_payload, fixture_data
from tests._support.optimizer_end_to_end_runner import DEFAULT_RUN_CONFIG, oracle_report, run_case, validate_config

pytestmark = pytest.mark.serial


@pytest.fixture(scope="module")
def tiny_rows():
    return {objective: run_case("tiny_improving", objective) for objective in OBJECTIVES}


def test_full_entry_exercises_outer_plans_optimizer_and_four_objective_oracles(tiny_rows):
    for objective, row in tiny_rows.items():
        assert row["status"] == "passed", row["errors"]
        # Tiers with identical optimizer inputs reuse a sibling's plan instead of spending an optimizer call.
        reused = sum(1 for candidate in row["candidates"] if candidate["reused_from"])
        assert row["optimizer_call_count"] == 4 - reused
        assert len(row["candidates"]) == 4
        assert row["decode_count"] >= row["optimizer_call_count"]
        assert sum(item["decode_count"] for item in row["candidates"]) == row["decode_count"]
        assert row["runtime_ms"] > 0
        assert set(row["selected"]["quality_vectors"]) == set(OBJECTIVES)
        assert row["oracle"]["applicable"]
        assert row["oracle"]["selected_vectors"] == row["selected"]["quality_vectors"]
        assert tuple(row["selected"]["quality_vectors"][objective]) >= tuple(row["oracle"]["optimum_vectors"][objective])
    assert 0 < tiny_rows["min_overdue"]["first_improvement_ms"] < tiny_rows["min_overdue"]["runtime_ms"]


def test_chain_legitimately_has_no_improvement():
    row = run_case("tiny_chain", "min_overdue")
    assert row["status"] == "passed"
    assert row["first_improvement_ms"] is None
    assert row["baseline"]["quality_vectors"] == row["selected"]["quality_vectors"]
    assert all(gap["optimal"] for gap in row["oracle"]["lexicographic_gaps"].values())


@pytest.fixture(scope="module")
def mixed_row():
    return run_case("frozen_ready_external", "min_overdue")


def test_frozen_readiness_external_constraints_are_effective(mixed_row):
    assert mixed_row["status"] == "passed", mixed_row["errors"]
    data = fixture_data("frozen_ready_external")
    audit_payload(mixed_row["selected"], data)
    rows = mixed_row["selected"]["schedule"]
    by_id = {row["op_id"]: row for row in rows}
    for seed in data["seed_results"]:
        assert by_id[seed["op_id"]] == seed
    future_batch = next(batch for batch in data["batches"] if batch["ready_status"] == "no")
    assert all(datetime.fromisoformat(row["start_time"]) >= datetime.fromisoformat(future_batch["ready_date"])
               for row in rows if row["batch_id"] == future_batch["batch_id"])
    assert any(row["source"] == "external" for row in rows)
    assert any(row["source"] == "internal" and row["start_time"][:10] != "2026-01-05" for row in rows)
    assert not mixed_row["oracle"]["applicable"]


@pytest.mark.parametrize("mutation", ("seed", "ready", "external", "external_resource", "missing", "score"))
def test_serialized_constraint_and_quality_mutations_are_rejected(mixed_row, mutation):
    data = fixture_data("frozen_ready_external")
    payload = copy.deepcopy(mixed_row["selected"])
    if mutation == "seed":
        row = next(row for row in payload["schedule"] if row["op_id"] == data["seed_results"][0]["op_id"])
        row["machine_id"] = "M2"
    elif mutation == "ready":
        row = next(row for row in payload["schedule"] if row["batch_id"] == data["batches"][1]["batch_id"])
        row["start_time"] = "2026-01-05T08:00:00"
    elif mutation == "external":
        row = next(row for row in payload["schedule"] if row["source"] == "external")
        row["end_time"] = "2026-02-01T08:00:00"
    elif mutation == "external_resource":
        row = next(row for row in payload["schedule"] if row["source"] == "external")
        row.update(machine_id="M0", operator_id="O0")
    elif mutation == "missing":
        payload["schedule"].pop()
    else:
        payload["quality_vectors"]["min_overdue"][1] += 1
    with pytest.raises(ValueError):
        audit_payload(payload, data)


def test_fixture_shapes_expand_coverage_without_claiming_piece_pipeline():
    assert len(SCENARIOS) == 5
    wide = fixture_data("wide_parallel_chains")
    assert len(wide["batches"]) == 12 and len(wide["operations"]) == 24
    pairs = {(op["machine_id"], op["operator_id"]) for op in wide["operations"]}
    assert len(pairs) == 12
    assert len({machine for machine, _ in pairs}) == len({operator for _, operator in pairs}) == 12
    for batch in wide["batches"]:
        assert len({(op["machine_id"], op["operator_id"]) for op in wide["operations"] if op["batch_id"] == batch["batch_id"]}) == 1
    for op in wide["operations"]:
        assert op["machine_id"] in wide["resource_pool"]["machines_by_op_type"][op["op_type_id"]]
        assert wide["resource_pool"]["operators_by_machine"][op["machine_id"]] == [op["operator_id"]]
        assert wide["resource_pool"]["machines_by_operator"][op["operator_id"]] == [op["machine_id"]]
    assert "disjoint_machine_operator_pairs" in wide["constraint_tags"]
    assert not {"shared_operator", "scarce_machine_pool"}.intersection(wide["constraint_tags"])
    pool = fixture_data("shift_pool")
    assert len(pool["operations"]) == 48
    assert pool["resource_pool"]["machines_by_op_type"]["TYPE1"] == ["M0"]
    assert len(pool["resource_pool"]["machines_by_op_type"]["TYPE0"]) == 3
    assert pool["downtime"] and {row["shift_hours"] for row in pool["calendar"]} == {8.0}


def test_independent_oracle_rejects_a_false_production_score(tiny_rows):
    payload = copy.deepcopy(tiny_rows["min_overdue"]["selected"])
    payload["quality_vectors"]["min_overdue"][1] = 0
    with pytest.raises(ValueError, match="independent oracle disagrees"):
        oracle_report(fixture_data("tiny_improving"), payload)


@pytest.mark.parametrize("change", ({"workers": 2}, {"weight_count": 1}, {"seed": -1},
                                   {"run_time_budget_seconds": float("nan")}, {"time_budget_seconds": 0},
                                   {"selection_policy": "balanced"}, {"decoder_count_mode": "estimated"}, {"unexpected": True}))
def test_invalid_config_fails_before_running(change):
    with pytest.raises(ValueError):
        validate_config(dict(DEFAULT_RUN_CONFIG, **change))


def test_parallel_measurement_is_rejected(monkeypatch):
    monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw0")
    with pytest.raises(ValueError, match="without xdist"):
        run_case("tiny_chain", "min_overdue")


def test_native_counter_keeps_decoder_unpatched_and_allows_real_sgs_reuse(monkeypatch):
    original_schedule, original_optimize = GreedyScheduler.schedule, runner.optimize_schedule
    instances = []

    def observe_optimizer(**kwargs):
        assert GreedyScheduler.schedule is original_schedule
        runtime = _default_runtime()

        def observe_factory(**factory_kwargs):
            scheduler = runtime.scheduler_factory(**factory_kwargs)
            instances.append(scheduler)
            return scheduler

        outcome = original_optimize(_runtime=replace(runtime, scheduler_factory=observe_factory), **kwargs)
        assert outcome.search_report["decoder_invocations"] == instances[-1]._decode_invocations
        return outcome

    monkeypatch.setattr(runner, "optimize_schedule", observe_optimizer)
    row = run_case("wide_parallel_chains", "min_overdue")
    assert row["status"] == "passed", row["errors"]
    assert GreedyScheduler.schedule is original_schedule
    assert row["decode_count"] == sum(scheduler._decode_invocations for scheduler in instances)
    assert any(scheduler._last_sgs_reuse_stats["hits"] > 0 for scheduler in instances)
    payload = copy.deepcopy(row["selected"])
    payload["schedule"][0]["operator_id"] = "O2" if payload["schedule"][0]["operator_id"] != "O2" else "O0"
    with pytest.raises(ValueError, match="fixed resource changed"):
        audit_payload(payload, fixture_data("wide_parallel_chains"))


def test_explicit_uncounted_mode_never_synthesizes_legacy_decode_numbers():
    row = run_case("tiny_chain", "min_overdue", dict(DEFAULT_RUN_CONFIG, decoder_count_mode="uncounted"))
    assert row["status"] == "passed"
    assert row["decode_count"] is None
    assert row["optimizer_call_count"] == 4 - sum(1 for candidate in row["candidates"] if candidate["reused_from"])
    assert all(candidate["decode_count"] is None for candidate in row["candidates"])


@pytest.mark.parametrize("value", (None, 0, True, 1.0, -1))
def test_native_count_does_not_fall_back_to_candidate_report_counts(monkeypatch, value):
    report = {"evaluated_candidates": 999}
    if value is not None:
        report["decoder_invocations"] = value
    monkeypatch.setattr(runner, "optimize_schedule", lambda **kwargs: SimpleNamespace(search_report=report))
    measurement = runner._Measurement("min_overdue", "native")
    with pytest.raises(ValueError, match="native decoder counter unavailable"):
        measurement.optimize()


def test_legacy_mode_accepts_absent_counter_and_marks_it_unmeasured(monkeypatch):
    monkeypatch.setattr(runner, "optimize_schedule", lambda **kwargs: SimpleNamespace(search_report={"evaluated_candidates": 999}))
    measurement = runner._Measurement("min_overdue", "uncounted")
    measurement.optimize()
    assert measurement.decode_count is None
    assert measurement.optimizer_calls[0]["decode_count"] is None
    config = dict(DEFAULT_RUN_CONFIG, decoder_count_mode="uncounted")
    assert runner.measurement_for_config(config)["decoder_count_source"] == "unmeasured"
