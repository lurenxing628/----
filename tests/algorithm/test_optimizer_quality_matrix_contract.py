"""Production runs plus mutations: a passed flag cannot bypass matrix contracts."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta
from time import sleep
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.algorithms.evaluation import compute_metrics, objective_score
from core.services.scheduler.run import optimizer_graph_ready as production_graph
from tests._scripts_e2e.benchmark_optimizer_quality_matrix import main
from tests._support.optimizer_quality_matrix import DEFAULT_RUN_CONFIG, build_quality_matrix, run_case
from tests._support.optimizer_quality_matrix_cases import (
    OBJECTIVES,
    REPO_ROOT,
    SCENARIOS,
    case_environment,
    fixture_data,
)
from tests._support.optimizer_quality_matrix_compare import compare_quality_matrices, validate_snapshot
from tests._support.optimizer_quality_matrix_io import read_snapshot, update_baseline, write_diagnostic
from tests._support.optimizer_quality_matrix_provenance import proof_binding
from tests._support.optimizer_quality_matrix_schedule import audit_schedule

pytestmark = pytest.mark.serial


@pytest.fixture(scope="module")
def matrix():
    return build_quality_matrix(REPO_ROOT)


def test_real_matrix_minimum_coverage_feasibility_and_provenance(matrix):
    validate_snapshot(matrix)
    assert matrix["status"] == "passed"
    assert len(matrix["cases"]) == len(OBJECTIVES) * len(SCENARIOS) == 8
    assert matrix["config"] == DEFAULT_RUN_CONFIG
    assert matrix["measurement"]["clock"] == "time.perf_counter"
    for row in matrix["cases"]:
        assert row["operation_count"] == (8 if row["scenario"] == "tiny" else 48)
        assert row["counts"]["baseline_decode_count"] == 1
        assert row["counts"]["graph_decode_count"] > 0
        assert row["counts"]["repair_decode_count"] > 0
        assert row["repair"]["repair_scope"] == "production_core"
        assert tuple(row["improved"]["objective_score"]) <= tuple(row["baseline"]["objective_score"])
    for key in ("source_before", "source_after"):
        assert matrix[key]["worktree_clean"] == (not matrix[key]["status_porcelain"])
        assert len(matrix[key]["source_sha256"]) == 64
    assert matrix["proof_binding"] == proof_binding(matrix["source_before"], matrix["source_after"])
    assert "not_optimality" in matrix["claim"]


def test_real_production_repair_and_sgs_are_called_without_test_clock():
    from core.algorithms.greedy import scheduler as production_scheduler

    with patch.object(production_graph, "run_graph_ready_elite_repair", wraps=production_graph.run_graph_ready_elite_repair) as repair, patch.object(
            production_scheduler, "dispatch_sgs", wraps=production_scheduler.dispatch_sgs) as sgs:
        row = run_case("tiny", "min_overdue")
    assert repair.call_count == 1
    assert sgs.call_count == sum(row["counts"].values())
    assert repair.call_args.kwargs["clock"].__name__ == "perf_counter"
    assert row["status"] == "passed"


def test_shift_pool_fixture_is_effective_not_metadata_only(matrix):
    data = fixture_data("medium_shift_pool")
    assert {day["shift_hours"] for day in data["calendar"]} == {8.0}
    assert data["downtime"] and data["resource_pool"]
    rows = [row for row in matrix["cases"] if row["scenario"] == "medium_shift_pool"]
    for row in rows:
        schedule = row["improved"]["schedule"]
        assert len({r["machine_id"] for r in schedule}) >= 2
        assert len({r["operator_id"] for r in schedule}) >= 2
        assert len({r["start_time"][:10] for r in schedule}) >= 2
        m0 = [r for r in schedule if r["machine_id"] == "M0"]
        assert m0 and min(r["start_time"] for r in m0) >= "2026-01-05T13:00:00"


def test_tiny_quality_and_decodes_repeat_with_same_seed(matrix):
    previous = matrix["cases"][0]
    repeated = run_case("tiny", "min_overdue")
    assert repeated["baseline"]["objective_score"] == previous["baseline"]["objective_score"]
    assert repeated["improved"]["objective_score"] == previous["improved"]["objective_score"]
    assert repeated["counts"] == previous["counts"]


def _shift_schedule(payload, days, scenario, objective):
    for row in payload["schedule"]:
        for key in ("start_time", "end_time"):
            row[key] = (datetime.fromisoformat(row[key]) + timedelta(days=days)).isoformat()
    results = [SimpleNamespace(**dict(row, start_time=datetime.fromisoformat(row["start_time"]),
                                    end_time=datetime.fromisoformat(row["end_time"]))) for row in payload["schedule"]]
    batches = {row["batch_id"]: SimpleNamespace(**row) for row in fixture_data(scenario)["batches"]}
    payload["objective_score"] = [0.0] + list(objective_score(objective, compute_metrics(results, batches)))


@pytest.mark.parametrize("objective", OBJECTIVES)
def test_saved_quality_regression_fails_even_with_valid_self_comparison(matrix, objective):
    worse = copy.deepcopy(matrix)
    row = next(row for row in worse["cases"] if row["case_id"] == "tiny/" + objective)
    for role in ("baseline", "improved"):
        _shift_schedule(row[role], 10, "tiny", objective)
    validate_snapshot(worse)
    result = compare_quality_matrices(matrix, worse)
    assert result["status"] == "failed"
    assert any("objective regressed" in failure for failure in result["failures"])


def test_same_environment_baseline_quality_guard_cannot_be_replaced_by_passed_flag(matrix):
    worse = copy.deepcopy(matrix)
    row = worse["cases"][0]
    _shift_schedule(row["improved"], 10, "tiny", row["objective"])
    with pytest.raises(ValueError, match="quality regressed"):
        validate_snapshot(worse)


def test_large_real_runtime_regression_fails_and_tolerant_noise_passes(matrix):
    worse = copy.deepcopy(matrix)
    row = worse["cases"][0]
    for key in ("baseline_runtime_ms", "improve_runtime_ms", "runtime_ms"):
        row[key] *= 1000
    result = compare_quality_matrices(matrix, worse)
    assert result["status"] == "failed"
    assert any("runtime_ms regressed" in failure for failure in result["failures"])
    assert compare_quality_matrices(matrix, worse, runtime_ratio=1001)["status"] == "passed"
    noise = copy.deepcopy(matrix)
    for key in ("baseline_runtime_ms", "improve_runtime_ms", "runtime_ms"):
        noise["cases"][0][key] *= 2
    assert compare_quality_matrices(matrix, noise)["status"] == "passed"


def test_injected_wall_time_delay_is_measured_and_rejected(matrix):
    from tests._support import optimizer_quality_matrix as runner

    original = runner.run_graph_ready_candidates

    def slow_production_call(**kwargs):
        sleep(0.5)
        return original(**kwargs)

    with patch.object(runner, "run_graph_ready_candidates", side_effect=slow_production_call):
        slow = runner.run_case("tiny", "min_overdue")
    assert slow["improve_runtime_ms"] >= 500
    actual = copy.deepcopy(matrix)
    actual["cases"][0] = slow
    comparison = compare_quality_matrices(matrix, actual, runtime_ratio=1.1, runtime_slack_ms=1)
    assert comparison["status"] == "failed"
    assert any("improve_runtime_ms regressed" in failure for failure in comparison["failures"])


@pytest.mark.parametrize("mutation", ("missing_case", "duplicate_case", "case_seed", "all_seed", "budget", "candidate_budget",
                                      "workers", "failed_ops", "unknown_top", "unknown_machine", "unknown_git", "unknown_case",
                                      "unknown_config", "unknown_repair", "score_shape", "score_bool", "score_nan", "score_lie",
                                      "zero_runtime", "negative_runtime", "unknown_runtime", "missing_operation", "duplicate_operation",
                                      "dirty_clean_claim", "failed_status", "unknown_binding", "fixture_drift", "decode_lie"))
def test_saved_matrix_mutations_fail_closed(matrix, mutation):
    actual = copy.deepcopy(matrix)
    row = actual["cases"][0]
    if mutation == "missing_case":
        actual["cases"].pop()
    elif mutation == "duplicate_case":
        actual["cases"][-1] = copy.deepcopy(row)
    elif mutation == "case_seed":
        row["seed"] += 1
    elif mutation == "all_seed":
        actual["config"]["seed"] += 1
        for item in actual["cases"]:
            item["seed"] += 1
    elif mutation == "budget":
        actual["config"]["time_budget_seconds"] += 1
        for item in actual["cases"]:
            item["scheduler_config"]["time_budget_seconds"] += 1
    elif mutation == "candidate_budget":
        actual["config"]["max_candidates"] += 1
    elif mutation == "workers":
        actual["config"]["workers"] = 2
    elif mutation == "failed_ops":
        row["improved"]["failed_ops"] = 1
    elif mutation == "unknown_top":
        actual["new_metadata"] = True
    elif mutation == "unknown_machine":
        actual["machine"]["python_version"] = "unknown"
    elif mutation == "unknown_git":
        actual["source_before"]["head"] = "unknown"
    elif mutation == "unknown_case":
        row["new_metadata"] = True
    elif mutation == "unknown_config":
        actual["config"]["new_metadata"] = True
    elif mutation == "unknown_repair":
        row["repair"]["new_metadata"] = True
    elif mutation == "score_shape":
        row["improved"]["objective_score"].pop()
    elif mutation == "score_bool":
        row["improved"]["objective_score"][0] = False
    elif mutation == "score_nan":
        row["improved"]["objective_score"][0] = float("nan")
    elif mutation == "score_lie":
        row["improved"]["objective_score"][1] = 0
    elif mutation == "zero_runtime":
        row["runtime_ms"] = 0
    elif mutation == "negative_runtime":
        row["runtime_ms"] = -1
    elif mutation == "unknown_runtime":
        actual["measurement"]["clock"] = "simulatedclock"
    elif mutation == "missing_operation":
        row["improved"]["schedule"].pop()
    elif mutation == "duplicate_operation":
        row["improved"]["schedule"][-1] = copy.deepcopy(row["improved"]["schedule"][0])
    elif mutation == "dirty_clean_claim":
        actual["source_before"]["worktree_clean"] = True
        actual["source_before"]["status_porcelain"] = [" M sample.py"]
    elif mutation == "failed_status":
        actual["status"] = "failed"
    elif mutation == "unknown_binding":
        actual["proof_binding"] = "clean_proof"
    elif mutation == "fixture_drift":
        row["fixture_sha256"] = "0" * 64
    else:
        row["counts"]["repair_decode_count"] += 1
    assert compare_quality_matrices(matrix, actual)["status"] == "failed", mutation


@pytest.mark.parametrize("mutation", ("resource", "precedence", "downtime", "calendar", "pool"))
def test_schedule_constraint_mutations_fail(matrix, mutation):
    scenario = "medium_shift_pool" if mutation in {"downtime", "calendar", "pool"} else "tiny"
    row = next(row for row in matrix["cases"] if row["scenario"] == scenario)
    payload = copy.deepcopy(row["improved"])
    with case_environment(scenario) as env:
        results = payload["schedule"]
        if mutation == "pool":
            results[0]["machine_id"] = "OUTSIDE_POOL"
        elif mutation == "calendar":
            results[0]["start_time"] = "2026-01-05T23:00:00"
            results[0]["end_time"] = "2026-01-06T01:00:00"
        elif mutation == "downtime":
            results[0].update(machine_id="M0", operator_id="O0", start_time="2026-01-05T08:00:00", end_time="2026-01-05T10:00:00")
        else:
            first = min(results, key=lambda result: result["start_time"])
            if mutation == "precedence":
                target = next(result for result in results if result["batch_id"] == first["batch_id"] and result["seq"] > first["seq"])
            else:
                target = next(result for result in results if result["batch_id"] != first["batch_id"])
            target["start_time"] = first["start_time"]
            op = next(op for op in env["operations"] if op.id == target["op_id"])
            target["end_time"] = (datetime.fromisoformat(first["start_time"]) + timedelta(hours=op.setup_hours + op.unit_hours)).isoformat()
        with pytest.raises(ValueError, match="overlap|calendar|pool"):
            audit_schedule(payload, env, row["objective"])


def test_diagnostic_roundtrip_compare_and_dirty_promotion_rejection(matrix, tmp_path):
    path = tmp_path / "diagnostic.json"
    write_diagnostic(path, matrix, REPO_ROOT)
    assert compare_quality_matrices(matrix, read_snapshot(path))["status"] == "passed"
    assert main(["compare", "--baseline", str(path), "--actual", str(path)]) == 0
    dirty = copy.deepcopy(matrix)
    for key in ("source_before", "source_after"):
        dirty[key]["worktree_clean"] = False
        dirty[key]["status_porcelain"] = [" M sample.py"]
    dirty["proof_binding"] = proof_binding(dirty["source_before"], dirty["source_after"])
    write_diagnostic(path, dirty, REPO_ROOT)
    target = tmp_path / "optimizer_quality_matrix_baseline.json"
    assert main(["update-baseline", "--snapshot", str(path), "--baseline", str(target)]) == 2
    assert not target.exists()


def test_baseline_update_rechecks_live_source_and_rejects_unknown_metadata(matrix, tmp_path):
    clean = copy.deepcopy(matrix)
    source = copy.deepcopy(clean["source_after"])
    source.update(worktree_clean=True, status_porcelain=[])
    clean.update(source_before=copy.deepcopy(source), source_after=copy.deepcopy(source), proof_binding="clean_matrix_run_not_full_quality_gate")
    target = tmp_path / "optimizer_quality_matrix_baseline.json"
    # Mocked receipts test lifecycle branches only; they are never emitted as real evidence.
    with patch("tests._support.optimizer_quality_matrix_io.capture_source", return_value=source), patch(
            "tests._support.optimizer_quality_matrix_io.machine_metadata", return_value=clean["machine"]):
        update_baseline(clean, target, REPO_ROOT)
        original = target.read_bytes()
        for changed in (dict(clean, status="failed"), dict(clean, unknown_metadata=1)):
            with pytest.raises(ValueError):
                update_baseline(changed, target, REPO_ROOT)
            assert target.read_bytes() == original
        source["head"] = "f" * 40
        with pytest.raises(ValueError, match="current clean source"):
            update_baseline(clean, target, REPO_ROOT)
        assert target.read_bytes() == original


@pytest.mark.parametrize("raw", ('{"a": 1, "a": 2}', '{"a": NaN}', '{"a": Infinity}'))
def test_json_reader_rejects_duplicate_and_nonfinite_metadata(tmp_path, raw):
    path = tmp_path / "invalid.json"
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(ValueError):
        read_snapshot(path)


def test_cli_refuses_parallel_measurement_and_old_baseline_write(matrix, tmp_path):
    assert main(["run", "--workers", "2", "--output", str(tmp_path / "out.json")]) == 2
    assert not (tmp_path / "out.json").exists()
    with pytest.raises(ValueError, match="diagnostics"):
        write_diagnostic(REPO_ROOT / "tests/fixtures/old_baseline.json", matrix, REPO_ROOT)


def test_diagnostic_cannot_overwrite_reserved_baseline_even_outside_repo(matrix, tmp_path):
    target = tmp_path / "optimizer_quality_matrix_baseline.json"
    target.write_text("preserve-existing-baseline", encoding="utf-8")
    with pytest.raises(ValueError, match="reserved"):
        write_diagnostic(target, matrix, REPO_ROOT)
    assert target.read_text(encoding="utf-8") == "preserve-existing-baseline"


def test_operation_boolean_sequence_is_not_integer_identity(matrix):
    actual = copy.deepcopy(matrix)
    actual["cases"][0]["improved"]["schedule"][0]["seq"] = True
    assert compare_quality_matrices(matrix, actual)["status"] == "failed"


@pytest.mark.parametrize("field", ("source_sha256", "head"))
@pytest.mark.parametrize("side", ("baseline", "actual"))
def test_measurement_source_drift_is_diagnostic_only(matrix, tmp_path, field, side):
    mixed = copy.deepcopy(matrix)
    value = mixed["source_before"][field]
    mixed["source_after"][field] = ("0" if value[0] != "0" else "1") + value[1:]
    mixed["proof_binding"] = proof_binding(mixed["source_before"], mixed["source_after"])
    assert mixed["proof_binding"] == "unbound_source_changed"
    path = tmp_path / "mixed-diagnostic.json"
    write_diagnostic(path, mixed, REPO_ROOT)
    saved = read_snapshot(path)
    assert saved == mixed
    message = "measured " + field + " changed during run"
    with pytest.raises(ValueError, match=message):
        validate_snapshot(saved)
    operands = {"baseline": matrix, "actual": matrix}
    operands[side] = saved
    result = compare_quality_matrices(**operands)
    assert result["status"] == "failed"
    assert any(failure.startswith(side + ": " + message) for failure in result["failures"])
    assert main(["compare", "--baseline", str(path), "--actual", str(path)]) == 1
    target = tmp_path / "optimizer_quality_matrix_baseline.json"
    with pytest.raises(ValueError, match=message):
        update_baseline(saved, target, REPO_ROOT)
    assert not target.exists()


@pytest.mark.parametrize("changed", ("status", "diff", "status_and_diff"))
def test_unrelated_worktree_drift_remains_comparable(matrix, changed):
    actual = copy.deepcopy(matrix)
    actual["source_after"] = copy.deepcopy(actual["source_before"])
    if changed in {"status", "status_and_diff"}:
        actual["source_after"]["status_porcelain"].append(" M web/static/unrelated.css")
        actual["source_after"]["worktree_clean"] = False
    if changed in {"diff", "status_and_diff"}:
        value = actual["source_before"]["diff_sha256"]
        actual["source_after"]["diff_sha256"] = ("0" if value[0] != "0" else "1") + value[1:]
    actual["proof_binding"] = proof_binding(actual["source_before"], actual["source_after"])
    assert actual["proof_binding"] == "unbound_source_changed"
    validate_snapshot(actual)
    assert compare_quality_matrices(matrix, actual)["status"] == "passed"


@pytest.mark.parametrize("field", ("source_sha256", "head"))
def test_different_stable_revisions_across_measurements_remain_comparable(matrix, field):
    actual = copy.deepcopy(matrix)
    value = actual["source_before"][field]
    for key in ("source_before", "source_after"):
        actual[key][field] = ("0" if value[0] != "0" else "1") + value[1:]
    actual["proof_binding"] = proof_binding(actual["source_before"], actual["source_after"])
    validate_snapshot(actual)
    assert compare_quality_matrices(matrix, actual)["status"] == "passed"
