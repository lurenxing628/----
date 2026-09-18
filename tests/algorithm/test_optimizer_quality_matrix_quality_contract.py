"""Portable historical quality checks reuse saved schedules; no decoder is run."""
from __future__ import annotations

import copy
import math
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

from core.algorithm_contracts.date_parsers import due_exclusive
from core.algorithms import GreedyScheduler
from core.algorithms.evaluation import compute_metrics, objective_score
from tests._support.optimizer_quality_matrix_cases import OBJECTIVES, REPO_ROOT, fixture_data
from tests._support.optimizer_quality_matrix_compare import (
    compare_quality_matrices,
    compare_quality_only,
    improved_primary_floor,
)
from tests._support.optimizer_quality_matrix_io import read_snapshot


@pytest.fixture(scope="module")
def historical():
    return read_snapshot(REPO_ROOT / "tests" / "fixtures" / "optimizer_quality_matrix_baseline.json")


@pytest.fixture(autouse=True)
def no_decoder(monkeypatch):
    def unexpected_decode(*args, **kwargs):
        raise AssertionError("saved-snapshot comparison must not schedule again")

    monkeypatch.setattr(GreedyScheduler, "schedule", unexpected_decode)


def _another_machine(snapshot):
    actual = copy.deepcopy(snapshot)
    actual["machine"].update(node="portable-comparison-host", platform="Windows-6.1-SP1",
                             python_executable="C:\\APS\\Python38\\python.exe")
    return actual


def _delay_tiny(payload, objective, hours, selected=None):
    """Delay the selected schedule rows (all by default) and recompute the objective score."""
    for row in payload["schedule"]:
        if selected is not None and not selected(row):
            continue
        for key in ("start_time", "end_time"):
            row[key] = (datetime.fromisoformat(row[key]) + timedelta(hours=hours)).isoformat()
    results = [SimpleNamespace(**dict(row, start_time=datetime.fromisoformat(row["start_time"]),
                                    end_time=datetime.fromisoformat(row["end_time"]))) for row in payload["schedule"]]
    batches = {row["batch_id"]: SimpleNamespace(**row) for row in fixture_data("tiny")["batches"]}
    payload["objective_score"] = [0.0] + list(objective_score(objective, compute_metrics(results, batches)))


def test_other_machine_quality_is_comparable_but_full_runtime_comparison_is_rejected(historical):
    actual = _another_machine(historical)
    quality = compare_quality_only(historical, actual)
    assert quality == {"status": "passed", "failures": [],
                       "claim": "quality_only_not_runtime_or_clean_quality_gate_proof"}
    full = compare_quality_matrices(historical, actual)
    assert full["status"] == "failed"
    assert "machine mismatch; runtime comparison requires same environment and budget" in full["failures"]


@pytest.mark.parametrize("objective", OBJECTIVES)
def test_other_machine_does_not_hide_full_objective_quality_regression(historical, objective):
    actual = _another_machine(historical)
    row = next(row for row in actual["cases"] if row["case_id"] == "tiny/" + objective)
    for role in ("baseline", "improved"):
        _delay_tiny(row[role], objective, hours=14 * 24)
    # The deterministic baseline decode is compared exactly. The improved schedule is only
    # held to its primary target, which a pure delay leaves untouched for min_changeover.
    expected = {"tiny/" + objective + ": baseline objective regressed"}
    if objective != "min_changeover":
        expected.add("tiny/" + objective + ": improved objective regressed")
    quality = compare_quality_only(historical, actual)
    assert quality["status"] == "failed"
    assert set(quality["failures"]) == expected
    full = compare_quality_matrices(historical, actual)
    assert full["status"] == "failed"
    assert expected <= set(full["failures"])


def test_quality_only_does_not_bless_same_machine_runtime_regression(historical):
    actual = copy.deepcopy(historical)
    for key in ("baseline_runtime_ms", "improve_runtime_ms", "runtime_ms"):
        actual["cases"][0][key] *= 1000
    quality = compare_quality_only(historical, actual)
    assert quality["status"] == "passed"
    assert quality["claim"] == "quality_only_not_runtime_or_clean_quality_gate_proof"
    full = compare_quality_matrices(historical, actual)
    assert full["status"] == "failed"
    assert full["runtime_ratio"] == 3.0 and full["runtime_slack_ms"] == 250.0
    assert any("runtime_ms regressed" in failure for failure in full["failures"])


@pytest.mark.parametrize("mutation", ["seed", "fixture", "machine_metadata", "source", "nonfinite_runtime"])
def test_quality_only_keeps_snapshot_fixture_and_config_validation(historical, mutation):
    actual = _another_machine(historical)
    if mutation == "seed":
        actual["config"]["seed"] += 1
    elif mutation == "fixture":
        actual["cases"][0]["fixture_sha256"] = "0" * 64
    elif mutation == "machine_metadata":
        actual["machine"]["node"] = "unknown"
    elif mutation == "source":
        actual["source_after"]["source_sha256"] = "0" * 64
    else:
        actual["cases"][0]["runtime_ms"] = float("inf")
    quality = compare_quality_only(historical, actual)
    assert quality["status"] == "failed"
    assert quality["failures"]


def _late_batches(payload):
    due = {row["batch_id"]: due_exclusive(date.fromisoformat(row["due_date"])) for row in fixture_data("tiny")["batches"]}
    return {row["batch_id"] for row in payload["schedule"] if datetime.fromisoformat(row["end_time"]) > due[row["batch_id"]]}


def _delay_late_batches_past_the_schedule(payload, objective, days):
    """Slip only the already-late batches, and by more than the makespan: no batch becomes late, no slot overlaps."""
    starts = [datetime.fromisoformat(row["start_time"]) for row in payload["schedule"]]
    ends = [datetime.fromisoformat(row["end_time"]) for row in payload["schedule"]]
    span_days = (max(ends) - min(starts)).total_seconds() / 86400.0
    late = _late_batches(payload)
    _delay_tiny(payload, objective, hours=24.0 * (math.ceil(span_days) + days), selected=lambda row: row["batch_id"] in late)


def _delay_last_operation(payload, objective, hours):
    """Delay only the schedule's final operation: tardiness grows by exactly ``hours``, nothing overlaps."""
    last = max(payload["schedule"], key=lambda row: datetime.fromisoformat(row["end_time"]))
    assert last["batch_id"] in _late_batches(payload)
    _delay_tiny(payload, objective, hours=hours, selected=lambda row: row["op_id"] == last["op_id"])


def test_quality_uses_lexicographic_target_order_not_componentwise_non_degradation(historical):
    reference = copy.deepcopy(historical)
    row = next(row for row in reference["cases"] if row["case_id"] == "tiny/min_overdue")
    row["improved"] = copy.deepcopy(row["baseline"])
    reference_score = row["improved"]["objective_score"]
    candidate = copy.deepcopy(next(row for row in historical["cases"] if row["case_id"] == "tiny/min_overdue")["improved"])
    # A valid same-fixture schedule with fewer late batches but more weighted tardiness than
    # the reference. The primary objective improvement must remain accepted.
    assert _late_batches(candidate), "tiny fixture must leave at least one batch late after improvement"
    _delay_late_batches_past_the_schedule(candidate, "min_overdue", days=1)
    score = candidate["objective_score"]
    assert score[1] < reference_score[1] and score[2] > reference_score[2], "tiny fixture must exercise a real lexicographic quality tradeoff"
    actual = _another_machine(reference)
    row = next(row for row in actual["cases"] if row["case_id"] == "tiny/min_overdue")
    row["improved"] = candidate
    assert compare_quality_only(reference, actual)["status"] == "passed"


def test_improved_primary_target_keeps_most_of_the_historical_gain(historical):
    case_id = "tiny/min_tardiness"
    before = next(row for row in historical["cases"] if row["case_id"] == case_id)
    floor = improved_primary_floor(before)
    improved_primary, baseline_primary = before["improved"]["objective_score"][1], before["baseline"]["objective_score"][1]
    assert improved_primary < floor < baseline_primary
    # Real-clock search noise: half an hour more tardiness stays within the retained gain.
    inside = _another_machine(historical)
    row = next(row for row in inside["cases"] if row["case_id"] == case_id)
    _delay_last_operation(row["improved"], "min_tardiness", hours=0.5)
    assert improved_primary < row["improved"]["objective_score"][1] <= floor
    assert compare_quality_only(historical, inside) == {
        "status": "passed", "failures": [], "claim": "quality_only_not_runtime_or_clean_quality_gate_proof"}
    # Giving back more than a quarter of the historical gain is a regression even while still
    # ahead of the deterministic baseline.
    beyond = _another_machine(historical)
    row = next(row for row in beyond["cases"] if row["case_id"] == case_id)
    _delay_last_operation(row["improved"], "min_tardiness", hours=2.0)
    assert floor < row["improved"]["objective_score"][1] < baseline_primary
    quality = compare_quality_only(historical, beyond)
    assert quality["status"] == "failed" and quality["failures"] == [case_id + ": improved objective regressed"]


def test_deterministic_baseline_decode_stays_exact(historical):
    # The same half-hour slip that the improved schedule may absorb is a regression of the
    # deterministic baseline decode.
    actual = _another_machine(historical)
    row = next(row for row in actual["cases"] if row["case_id"] == "tiny/min_tardiness")
    _delay_last_operation(row["baseline"], "min_tardiness", hours=0.5)
    quality = compare_quality_only(historical, actual)
    assert quality["status"] == "failed" and quality["failures"] == ["tiny/min_tardiness: baseline objective regressed"]
