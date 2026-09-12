"""Lightweight snapshot lifecycle tests; synthetic receipts are never real evidence."""
from __future__ import annotations

import copy
import json
import subprocess
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from tests._scripts_e2e.benchmark_optimizer_end_to_end import main
from tests._support import optimizer_end_to_end_cases as cases
from tests._support import optimizer_end_to_end_io as snapshot_io
from tests._support.optimizer_end_to_end_compare import (
    CLAIM,
    compare_end_to_end_matrices,
    validate_snapshot,
)
from tests._support.optimizer_end_to_end_runner import DEFAULT_RUN_CONFIG, measurement_for_config, oracle_report
from tests._support.optimizer_end_to_end_schedule import quality_vectors
from tests._support.optimizer_quality_matrix_cases import json_hash
from tests._support.optimizer_quality_matrix_compare import MACHINE_KEYS
from tests._support.optimizer_quality_matrix_provenance import proof_binding


def _manual_payload(data, shift_days=0):
    """Serialize a known feasible chain without running any optimizer or timer."""
    start = datetime.fromisoformat(data["start_dt"]) + timedelta(days=shift_days)
    results = []
    for op in data["operations"]:
        end = start + timedelta(hours=op["setup_hours"] + op["unit_hours"])
        results.append(SimpleNamespace(
            op_id=op["id"], op_code=op["op_code"], batch_id=op["batch_id"], seq=op["seq"], source=op["source"],
            machine_id=op["machine_id"], operator_id=op["operator_id"], op_type_name=op["op_type_name"],
            start_time=start, end_time=end,
        ))
        start = end
    batches = {row["batch_id"]: SimpleNamespace(**row) for row in data["batches"]}
    return {
        "failed_ops": 0, "quality_vectors": quality_vectors(results, batches),
        "schedule": [{key: value.isoformat() if isinstance(value, datetime) else value
                      for key, value in vars(row).items()} for row in results],
    }


@pytest.fixture
def matrix():
    data = cases.fixture_data("tiny_chain")
    config = dict(DEFAULT_RUN_CONFIG)
    payload = _manual_payload(data)
    rows = []
    for objective in cases.OBJECTIVES:
        rows.append({
            "case_id": "tiny_chain/" + objective, "scenario": "tiny_chain", "objective": objective,
            "fixture_sha256": json_hash(data), "scheduler_config": cases.scheduler_config("tiny_chain", objective, config),
            "operation_count": len(data["operations"]), "constraint_tags": data["constraint_tags"],
            "runtime_ms": 100.0, "decode_count": 1, "optimizer_call_count": 1, "first_improvement_ms": None,
            "selected_candidate_key": "baseline", "baseline": copy.deepcopy(payload), "selected": copy.deepcopy(payload),
            "candidates": [{"candidate_key": "baseline", "status": "completed", "score": payload["quality_vectors"][objective],
                            "runtime_ms": 90.0, "decode_count": 1, "optimizer_runtime_ms": 80.0,
                            "quality_vectors": copy.deepcopy(payload["quality_vectors"])}],
            "oracle": oracle_report(data, payload), "status": "passed", "errors": [],
        })
        rows[-1]["candidates"].extend({
            "candidate_key": "graph_w" + str(index) + "_of_" + str(config["weight_count"]),
            "status": "skipped", "score": None, "runtime_ms": 0.0, "decode_count": 0,
            "optimizer_runtime_ms": 0.0, "quality_vectors": None,
        } for index in range(1, config["weight_count"] + 1))
    source = {
        "repo_root": str(snapshot_io.REPO_ROOT), "head": "1" * 40, "branch": "unit-test",
        "status_porcelain": [], "worktree_clean": True, "diff_sha256": "2" * 64, "source_sha256": "3" * 64,
    }
    return {
        "schema_version": 1, "kind": "optimizer_end_to_end_matrix", "claim": CLAIM,
        "config": config, "coverage": {"scenarios": ["tiny_chain"], "objectives": list(cases.OBJECTIVES)},
        "measurement": measurement_for_config(config), "started_at": "2026-01-05T00:00:00+00:00", "finished_at": "2026-01-05T00:00:01+00:00",
        "machine": {key: 1 if key == "cpu_count" else "unit-test" for key in MACHINE_KEYS},
        "source_before": copy.deepcopy(source), "source_after": copy.deepcopy(source),
        "proof_binding": proof_binding(source, source), "cases": rows, "status": "passed",
    }


def test_snapshot_check_recomputes_quality_without_running_optimizer(matrix, tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("snapshot validation must not run the optimizer")

    monkeypatch.setattr("core.services.scheduler.run.schedule_optimizer.optimize_schedule", forbidden)
    path = tmp_path / "diagnostic.json"
    snapshot_io.write_diagnostic(path, matrix, snapshot_io.REPO_ROOT)
    assert snapshot_io.read_snapshot(path) == matrix
    assert main(["check", "--snapshot", str(path)]) == 0
    assert main(["compare", "--baseline", str(path), "--actual", str(path)]) == 0


@pytest.mark.parametrize("mutation", (
    "unknown_top", "missing_case", "duplicate_case", "missing_vector", "score_nan", "score_bool", "candidate_bool",
    "missing_operation", "fixture_drift", "scheduler_bool", "unknown_candidate", "missing_candidate", "unknown_candidate_key",
    "duplicate_candidate", "decode_lie", "optimizer_calls_lie", "inferior_selection",
    "selected_lie", "runtime_zero", "runtime_bool", "runtime_accounting", "late_improvement", "oracle_lie",
    "oracle_bool", "source_changed", "head_changed", "root_changed", "dirty_clean_lie", "unknown_machine", "failed_status",
))
def test_snapshot_mutations_fail_closed(matrix, mutation):
    actual = copy.deepcopy(matrix)
    row = actual["cases"][0]
    candidate = row["candidates"][0]
    if mutation == "unknown_top":
        actual["extra"] = True
    elif mutation == "missing_case":
        actual["cases"].pop()
    elif mutation == "duplicate_case":
        actual["cases"][-1] = copy.deepcopy(row)
    elif mutation == "missing_vector":
        row["selected"]["quality_vectors"].pop("min_changeover")
    elif mutation in {"score_nan", "score_bool"}:
        row["selected"]["quality_vectors"][row["objective"]][0] = float("nan") if mutation == "score_nan" else False
    elif mutation == "candidate_bool":
        candidate["score"][0] = False
    elif mutation == "missing_operation":
        row["selected"]["schedule"].pop()
    elif mutation == "fixture_drift":
        row["fixture_sha256"] = "0" * 64
    elif mutation == "scheduler_bool":
        row["scheduler_config"]["time_budget_seconds"] = True
    elif mutation == "unknown_candidate":
        candidate["status"] = "unknown"
    elif mutation == "missing_candidate":
        row["candidates"].pop()
    elif mutation == "unknown_candidate_key":
        row["candidates"][-1]["candidate_key"] = "unknown"
    elif mutation == "duplicate_candidate":
        row["candidates"].append(copy.deepcopy(candidate))
    elif mutation == "decode_lie":
        row["decode_count"] += 1
    elif mutation == "optimizer_calls_lie":
        row["optimizer_call_count"] += 1
    elif mutation == "inferior_selection":
        better = row["candidates"][1]
        better.update(copy.deepcopy(candidate), candidate_key=better["candidate_key"], runtime_ms=1.0, optimizer_runtime_ms=0.5)
        better["quality_vectors"][row["objective"]][-2] -= 1
        better["score"] = better["quality_vectors"][row["objective"]]
        row["decode_count"] += 1
        row["optimizer_call_count"] += 1
    elif mutation == "selected_lie":
        row["selected_candidate_key"] = "missing"
    elif mutation in {"runtime_zero", "runtime_bool"}:
        row["runtime_ms"] = 0 if mutation == "runtime_zero" else True
    elif mutation == "runtime_accounting":
        candidate["optimizer_runtime_ms"] = 200.0
    elif mutation == "late_improvement":
        row["first_improvement_ms"] = 101.0
    elif mutation == "oracle_lie":
        row["oracle"]["reason"] = "general_optimality"
    elif mutation == "oracle_bool":
        row["oracle"]["applicable"] = 1
    elif mutation in {"source_changed", "head_changed", "root_changed"}:
        key, value = {"source_changed": ("source_sha256", "a" * 64), "head_changed": ("head", "a" * 40),
                      "root_changed": ("repo_root", "/different-checkout")}[mutation]
        actual["source_after"][key] = value
        actual["proof_binding"] = proof_binding(actual["source_before"], actual["source_after"])
    elif mutation == "dirty_clean_lie":
        actual["source_before"]["status_porcelain"] = [" M example.py"]
    elif mutation == "unknown_machine":
        actual["machine"]["node"] = "unknown"
    else:
        actual["status"] = "failed"
    assert compare_end_to_end_matrices(matrix, actual)["status"] == "failed", mutation


def test_clean_to_dirty_diagnostic_comparison_and_machine_budget_guards(matrix):
    actual = copy.deepcopy(matrix)
    for key in ("source_before", "source_after"):
        actual[key].update(head="a" * 40, source_sha256="b" * 64, worktree_clean=False, status_porcelain=[" M example.py"])
    actual["proof_binding"] = proof_binding(actual["source_before"], actual["source_after"])
    assert compare_end_to_end_matrices(matrix, actual)["status"] == "passed"
    actual["machine"]["node"] = "another-machine"
    assert compare_end_to_end_matrices(matrix, actual)["status"] == "failed"
    actual["machine"] = copy.deepcopy(matrix["machine"])
    actual["config"]["run_time_budget_seconds"] += 1
    assert compare_end_to_end_matrices(matrix, actual)["status"] == "failed"


@pytest.mark.parametrize("mode", ("native", "uncounted"))
def test_runtime_guard_is_tolerant_but_rejects_large_regression(matrix, mode):
    matrix = _uncounted_snapshot(matrix) if mode == "uncounted" else matrix
    actual = copy.deepcopy(matrix)
    actual["cases"][0]["runtime_ms"] = 551.0
    assert compare_end_to_end_matrices(matrix, actual)["status"] == "failed"
    actual["cases"][0]["runtime_ms"] = 550.0
    result = compare_end_to_end_matrices(matrix, actual)
    assert result["status"] == "passed"
    assert result["runtime_interpretation"] == "single_run_large_regression_guard_not_speedup_evidence"


@pytest.mark.parametrize("objective", cases.OBJECTIVES)
@pytest.mark.parametrize("mode", ("native", "uncounted"))
def test_saved_primary_quality_regression_fails_for_each_objective(matrix, objective, mode):
    matrix = _uncounted_snapshot(matrix) if mode == "uncounted" else matrix
    actual = copy.deepcopy(matrix)
    row = next(row for row in actual["cases"] if row["objective"] == objective)
    data = cases.fixture_data(row["scenario"])
    payload = _manual_payload(data, shift_days=10)
    row.update(baseline=copy.deepcopy(payload), selected=copy.deepcopy(payload), oracle=oracle_report(data, payload))
    row["candidates"][0].update(score=payload["quality_vectors"][objective], quality_vectors=payload["quality_vectors"])
    validate_snapshot(actual)
    comparison = compare_end_to_end_matrices(matrix, actual)
    assert comparison["status"] == "failed"
    assert any(objective + " quality regressed" in failure for failure in comparison["failures"])


@pytest.mark.parametrize("raw", ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}', '{}', '[]'))
def test_snapshot_reader_rejects_ambiguous_or_unknown_json(tmp_path, raw):
    path = tmp_path / "invalid.json"
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(ValueError):
        snapshot_io.read_snapshot(path)


def test_baseline_promotion_requires_full_coverage_live_clean_source_and_machine(matrix, tmp_path, monkeypatch):
    target = tmp_path / "optimizer_end_to_end_baseline.json"
    with pytest.raises(ValueError, match="every scenario"):
        snapshot_io.update_baseline(matrix, target, snapshot_io.REPO_ROOT)
    # Restrict the unit-test universe and mock receipts only inside this lifecycle test.
    monkeypatch.setattr(cases, "SCENARIOS", ("tiny_chain",))
    source = copy.deepcopy(matrix["source_after"])
    monkeypatch.setattr(snapshot_io, "capture_end_to_end_source", lambda root: source)
    monkeypatch.setattr(snapshot_io, "machine_metadata", lambda: matrix["machine"])
    snapshot_io.update_baseline(matrix, target, snapshot_io.REPO_ROOT)
    original = target.read_bytes()
    source["head"] = "f" * 40
    with pytest.raises(ValueError, match="current clean source"):
        snapshot_io.update_baseline(matrix, target, snapshot_io.REPO_ROOT)
    source["head"] = matrix["source_after"]["head"]
    monkeypatch.setattr(snapshot_io, "machine_metadata", lambda: dict(matrix["machine"], node="other"))
    with pytest.raises(ValueError, match="machine/runtime"):
        snapshot_io.update_baseline(matrix, target, snapshot_io.REPO_ROOT)
    assert target.read_bytes() == original


def test_reserved_paths_and_dirty_promotion_fail_before_writing(matrix, tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="reserved"):
        snapshot_io.write_diagnostic(tmp_path / "optimizer_quality_matrix.json", matrix, snapshot_io.REPO_ROOT)
    with pytest.raises(ValueError, match="reserved"):
        snapshot_io.write_diagnostic(tmp_path / "Optimizer_End_To_End_baseline.json", matrix, snapshot_io.REPO_ROOT)
    with pytest.raises(ValueError, match="in-repo diagnostics"):
        snapshot_io.write_diagnostic(snapshot_io.REPO_ROOT / "unexpected_snapshot.json", matrix, snapshot_io.REPO_ROOT)
    monkeypatch.setattr(cases, "SCENARIOS", ("tiny_chain",))
    for key in ("source_before", "source_after"):
        matrix[key].update(worktree_clean=False, status_porcelain=[" M example.py"])
    matrix["proof_binding"] = proof_binding(matrix["source_before"], matrix["source_after"])
    diagnostic = tmp_path / "diagnostic.json"
    target = tmp_path / "optimizer_end_to_end_baseline.json"
    snapshot_io.write_diagnostic(diagnostic, matrix, snapshot_io.REPO_ROOT)
    assert main(["update-baseline", "--snapshot", str(diagnostic), "--baseline", str(target)]) == 2
    assert not target.exists()


def test_source_receipt_hashes_untracked_new_helpers_and_excludes_diagnostics(tmp_path):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(tmp_path)] + list(args), stderr=subprocess.STDOUT)

    git("init", "-q")
    git("-c", "user.name=Unit Test", "-c", "user.email=test@example.invalid", "commit", "--allow-empty", "-qm", "fixture")
    for relative in ("core/example.py", "data/example.py", "schema.sql", "tests/_support/optimizer_end_to_end_probe.py",
                     "tests/_support/optimizer_exact_oracle.py", "tests/_scripts_e2e/benchmark_optimizer_end_to_end.py",
                     "tests/algorithm/test_optimizer_end_to_end_snapshot_contract.py"):
        previous = snapshot_io.capture_end_to_end_source(tmp_path)
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# changed source\n", encoding="utf-8")
        current = snapshot_io.capture_end_to_end_source(tmp_path)
        assert current["source_sha256"] != previous["source_sha256"], relative
        assert current["worktree_clean"] is False
    (tmp_path / "diagnostic.json").write_text(json.dumps({"status": "diagnostic"}), encoding="utf-8")
    assert snapshot_io.capture_end_to_end_source(tmp_path)["source_sha256"] == current["source_sha256"]


def test_case_insensitive_checkout_alias_cannot_escape_diagnostic_directory(tmp_path):
    alias = tmp_path.with_name(tmp_path.name.swapcase())
    if not alias.exists() or not alias.samefile(tmp_path):
        pytest.skip("filesystem is case-sensitive")
    with pytest.raises(ValueError, match="in-repo diagnostics"):
        snapshot_io.write_diagnostic(alias / "outside.json", {}, tmp_path)
    assert not (tmp_path / "outside.json").exists()


def _uncounted_snapshot(matrix):
    snapshot = copy.deepcopy(matrix)
    snapshot["config"]["decoder_count_mode"] = "uncounted"
    snapshot["measurement"] = measurement_for_config(snapshot["config"])
    for row in snapshot["cases"]:
        row["decode_count"] = None
        for candidate in row["candidates"]:
            candidate["decode_count"] = None
    return snapshot


def test_uncounted_roundtrip_and_comparison_are_diagnostic_only(matrix, tmp_path):
    uncounted = _uncounted_snapshot(matrix)
    assert uncounted["measurement"]["decoder_count_source"] == "unmeasured"
    assert matrix["measurement"]["decoder_count_source"] == "native_scheduler_counter"
    path = tmp_path / "uncounted.json"
    snapshot_io.write_diagnostic(path, uncounted, snapshot_io.REPO_ROOT)
    assert snapshot_io.read_snapshot(path) == uncounted
    assert main(["check", "--snapshot", str(path)]) == 0
    assert main(["compare", "--baseline", str(path), "--actual", str(path)]) == 0
    comparison = compare_end_to_end_matrices(matrix, uncounted)
    assert comparison["status"] == "failed"
    assert any("config mismatch" in failure for failure in comparison["failures"])
    assert any("measurement mismatch" in failure for failure in comparison["failures"])


@pytest.mark.parametrize("mode,target,value", (
    ("native", "row", None), ("native", "completed", None), ("native", "skipped", None),
    ("native", "completed", 0), ("native", "row", True), ("native", "completed", 1.0),
    ("uncounted", "row", 0), ("uncounted", "completed", 1), ("uncounted", "skipped", 0),
))
def test_decoder_count_modes_reject_missing_or_fabricated_values(matrix, mode, target, value):
    snapshot = _uncounted_snapshot(matrix) if mode == "uncounted" else copy.deepcopy(matrix)
    row = snapshot["cases"][0]
    item = row if target == "row" else row["candidates"][0 if target == "completed" else 1]
    item["decode_count"] = value
    with pytest.raises(ValueError, match="decode_count"):
        validate_snapshot(snapshot)


def test_decoder_count_metadata_cannot_be_relabeled_or_promoted(matrix, tmp_path, monkeypatch):
    uncounted = _uncounted_snapshot(matrix)
    uncounted["measurement"]["decoder_count_source"] = "native_scheduler_counter"
    with pytest.raises(ValueError, match="measurement"):
        validate_snapshot(uncounted)
    uncounted = _uncounted_snapshot(matrix)
    monkeypatch.setattr(cases, "SCENARIOS", ("tiny_chain",))
    target = tmp_path / "optimizer_end_to_end_baseline.json"
    with pytest.raises(ValueError, match="requires native decoder counts"):
        snapshot_io.update_baseline(uncounted, target, snapshot_io.REPO_ROOT)
    assert not target.exists()


def test_uncounted_does_not_relax_optimizer_calls_or_allow_unknown_modes(matrix):
    snapshot = _uncounted_snapshot(matrix)
    snapshot["cases"][0]["optimizer_call_count"] = None
    with pytest.raises(ValueError, match="optimizer_call_count"):
        validate_snapshot(snapshot)
    matrix["config"]["decoder_count_mode"] = "estimated"
    with pytest.raises(ValueError):
        validate_snapshot(matrix)


@pytest.mark.parametrize("status", ("skipped", "failed"))
@pytest.mark.parametrize("field", ("decode_count", "optimizer_runtime_ms"))
def test_unexecuted_candidates_cannot_fabricate_native_work(matrix, status, field):
    row = matrix["cases"][0]
    candidate = row["candidates"][1]
    candidate.update(status=status, runtime_ms=1.0)
    candidate[field] = 1
    if field == "decode_count":
        row["decode_count"] += 1
    with pytest.raises(ValueError, match="unexecuted candidate"):
        validate_snapshot(matrix)
