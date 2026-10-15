"""Shared business representatives retain independent oracles and hard constraints."""
from __future__ import annotations

from datetime import datetime

import pytest

from tests._support.optimizer_business_cases import OBJECTIVES, run_case

pytestmark = pytest.mark.serial


@pytest.fixture(scope="module")
def tiny_rows():
    return {objective: run_case("tiny_improving", objective) for objective in OBJECTIVES}


def test_full_entry_exercises_shared_winners_and_four_objective_oracles(tiny_rows):
    for objective, row in tiny_rows.items():
        outcome = row["outcome"]
        assert 1 <= len(outcome.candidates) <= 3
        assert all(plan.status == "completed" for plan in outcome.candidates)
        assert outcome.primary_objective == objective
        assert set(row["winners"]) == set(outcome.target_objectives)
        for key, representative in row["representatives"].items():
            assert set(representative["quality_vectors"]) == set(OBJECTIVES)
            assert row["oracles"][key]["selected_vectors"] == representative["quality_vectors"]
        for target, key in outcome.selection.objective_winners.items():
            vector = tuple(row["winners"][target]["quality_vectors"][target])
            assert vector >= tuple(row["oracles"][key]["optimum_vectors"][target])
            assert vector == min(tuple(event["evaluations"][target]["score"]) for event in row["observations"])
        assert row["selected"] is row["winners"][objective]
    improving = tiny_rows["min_overdue"]
    assert tuple(improving["selected"]["quality_vectors"]["min_overdue"]) < tuple(
        improving["oracle"]["input_order_vectors"]["min_overdue"]
    )


def test_chain_legitimately_has_no_improvement():
    row = run_case("tiny_chain", "min_overdue")
    assert row["oracle"]["selected_vectors"] == row["oracle"]["optimum_vectors"]
    first = row["observations"][0]["evaluations"]
    for target, winner in row["winners"].items():
        assert first[target]["score"] == winner["quality_vectors"][target]
        assert row["outcome"].unified_process["targets"][target]["archive_improvement_count"] == 0


def test_frozen_readiness_external_constraints_are_effective():
    row = run_case("frozen_ready_external", "min_overdue")
    data, rows = row["data"], row["selected"]["schedule"]
    by_id = {item["op_id"]: item for item in rows}
    for seed in data["seed_results"]:
        assert by_id[seed["op_id"]] == seed
    future_batch = next(batch for batch in data["batches"] if batch["ready_status"] == "no")
    assert all(datetime.fromisoformat(item["start_time"]) >= datetime.fromisoformat(future_batch["ready_date"])
               for item in rows if item["batch_id"] == future_batch["batch_id"])
    assert any(item["source"] == "external" for item in rows)
    assert any(item["source"] == "internal" and item["start_time"][:10] != "2026-01-05" for item in rows)
