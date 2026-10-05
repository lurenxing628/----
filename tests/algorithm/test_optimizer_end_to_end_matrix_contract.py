"""Three real candidate-comparison cases, including an independent tiny oracle."""
from __future__ import annotations

from datetime import datetime

import pytest

from tests._support.optimizer_business_cases import OBJECTIVES, run_case

pytestmark = pytest.mark.serial


@pytest.fixture(scope="module")
def tiny_rows():
    return {objective: run_case("tiny_improving", objective) for objective in OBJECTIVES}


def test_full_entry_exercises_outer_plans_optimizer_and_four_objective_oracles(tiny_rows):
    for objective, row in tiny_rows.items():
        assert len(row["outcome"].candidates) == 4
        assert all(plan.status == "completed" for plan in row["outcome"].candidates)
        vectors = row["selected"]["quality_vectors"]
        assert set(vectors) == set(OBJECTIVES)
        assert row["oracle"]["selected_vectors"] == vectors
        assert tuple(vectors[objective]) >= tuple(row["oracle"]["optimum_vectors"][objective])
        assert tuple(vectors[objective]) <= tuple(row["baseline"]["quality_vectors"][objective])
    improving = tiny_rows["min_overdue"]
    assert tuple(improving["selected"]["quality_vectors"]["min_overdue"]) < tuple(
        improving["oracle"]["input_order_vectors"]["min_overdue"]
    )


def test_chain_legitimately_has_no_improvement():
    row = run_case("tiny_chain", "min_overdue")
    assert row["baseline"]["quality_vectors"] == row["selected"]["quality_vectors"]
    assert row["oracle"]["selected_vectors"] == row["oracle"]["optimum_vectors"]


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
