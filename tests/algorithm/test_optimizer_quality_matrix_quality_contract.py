"""Portable historical quality checks reuse saved schedules; no decoder is run."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from core.algorithms import GreedyScheduler
from core.algorithms.evaluation import compute_metrics, objective_score
from tests._support.optimizer_quality_matrix_cases import OBJECTIVES, REPO_ROOT, fixture_data
from tests._support.optimizer_quality_matrix_compare import compare_quality_matrices, compare_quality_only
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


def _delay_tiny(payload, objective, hours):
    for row in payload["schedule"]:
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
    quality = compare_quality_only(historical, actual)
    assert quality["status"] == "failed"
    assert "tiny/" + objective + ": improved objective regressed" in quality["failures"]
    full = compare_quality_matrices(historical, actual)
    assert full["status"] == "failed"
    assert "tiny/" + objective + ": improved objective regressed" in full["failures"]


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


def test_quality_uses_lexicographic_target_order_not_componentwise_non_degradation(historical):
    reference = copy.deepcopy(historical)
    row = next(row for row in reference["cases"] if row["case_id"] == "tiny/min_overdue")
    row["improved"] = copy.deepcopy(row["baseline"])
    reference_score = row["improved"]["objective_score"]
    original = next(row for row in historical["cases"] if row["case_id"] == "tiny/min_overdue")["improved"]
    # Construct a valid same-fixture schedule with fewer late batches but more
    # weighted tardiness. The primary objective improvement must remain accepted.
    selected = None
    for half_hours in range(1, 25):
        candidate = copy.deepcopy(original)
        _delay_tiny(candidate, "min_overdue", hours=half_hours / 2.0)
        score = candidate["objective_score"]
        if score[1] < reference_score[1] and score[2] > reference_score[2]:
            selected = candidate
            break
    assert selected is not None, "tiny fixture must exercise a real lexicographic quality tradeoff"
    actual = _another_machine(reference)
    row = next(row for row in actual["cases"] if row["case_id"] == "tiny/min_overdue")
    row["improved"] = selected
    assert compare_quality_only(reference, actual)["status"] == "passed"
