"""Baseline updates require real proof; malformed or regressed rows fail closed."""
from __future__ import annotations

import json
from copy import deepcopy

import pytest

from tests._scripts_e2e import benchmark_optimizer_ratchet as cli
from tests._support import optimizer_benchmark_ratchet as ratchet
from tests._support import optimizer_benchmark_ratchet_io as ratchet_io
from tests._support.optimizer_benchmark_ratchet import compare_to_baseline, write_baseline


def snapshot():
    source = {
        "repo_root": str(cli.REPO_ROOT), "head": "a" * 40, "branch": "main",
        "status_porcelain": [], "worktree_clean": True,
        "diff_sha256": "b" * 64, "source_sha256": "c" * 64,
    }
    return {
        "schema_version": 2, "status": "passed", "dirty_worktree": False,
        "measurement": dict(ratchet_io.RATCHET_MEASUREMENT), "machine": {"node": "fixture"},
        "source_before": deepcopy(source), "source_after": deepcopy(source),
        "proof_binding_status": "clean_worktree", "runtime_ms": 5.0,
        "git_commit": "a" * 40, "case_count": 1,
        "cases": [{"case_group": "tiny", "case_slug": "lifecycle-proof", "failed_ops": 0,
                   "gap_to_oracle_pct": 0.0, "objective_score_matched": True,
                   "objective_name": "min_overdue", "seed": 0, "time_budget_seconds": 1,
                   "runtime_ms": None, "runtime_scope": "shared_proof_harness"}],
    }


@pytest.fixture(autouse=True)
def measured_source(monkeypatch):
    monkeypatch.setattr(ratchet_io, "capture_source", lambda root: snapshot()["source_after"])
    monkeypatch.setattr(ratchet_io, "machine_metadata", lambda: snapshot()["machine"])


@pytest.mark.parametrize("field,value", [
    ("dirty_worktree", True), ("dirty_worktree", None), ("status", "failed"),
    ("git_commit", "unknown"), ("cases", []), ("case_count", 9),
])
def test_invalid_baseline_cannot_overwrite_existing_file(tmp_path, field, value):
    path = tmp_path / "baseline.json"
    write_baseline(path, snapshot())
    original = path.read_bytes()
    invalid = snapshot()
    invalid[field] = value
    with pytest.raises(ValueError, match="invalid benchmark baseline"):
        write_baseline(path, invalid)
    assert path.read_bytes() == original


def test_clean_passed_baseline_round_trips(tmp_path):
    path = tmp_path / "nested" / "baseline.json"
    write_baseline(path, snapshot())
    assert json.loads(path.read_text(encoding="utf-8")) == snapshot()
    assert compare_to_baseline(snapshot(), snapshot())["status"] == "passed"


@pytest.mark.parametrize("metric,value", [("gap_to_oracle_pct", 1.0), ("failed_ops", 1)])
def test_quality_regression_is_rejected(metric, value):
    actual = snapshot()
    actual["cases"][0][metric] = value
    assert compare_to_baseline(actual, snapshot())["status"] == "failed"


@pytest.mark.parametrize("field,value", [("seed", 2), ("objective_name", "min_changeover"), ("time_budget_seconds", 10)])
def test_changed_case_contract_cannot_pass(field, value):
    actual = snapshot()
    actual["cases"][0][field] = value
    result = compare_to_baseline(actual, snapshot())
    assert any(row.get("reason") == "case_contract_mismatch" for row in result["failures"])


def test_duplicate_cases_are_not_silently_collapsed():
    actual = snapshot()
    actual["cases"].append(deepcopy(actual["cases"][0]))
    actual["case_count"] = 2
    result = compare_to_baseline(actual, snapshot())
    assert any(row.get("reason") == "duplicate_actual_case" for row in result["failures"])


def test_missing_worktree_state_is_not_clean_proof():
    actual = snapshot()
    actual.pop("dirty_worktree")
    result = compare_to_baseline(actual, snapshot())
    assert result["status"] == "failed"
    assert result["proof_binding_status"] == "unknown_worktree_state"


def test_baseline_update_cli_refuses_dirty_snapshot_without_writing(monkeypatch, tmp_path, capsys):
    invalid = snapshot()
    invalid["dirty_worktree"] = True
    monkeypatch.setattr(cli, "build_light_ratchet_snapshot", lambda **kwargs: invalid)
    path = tmp_path / "baseline.json"
    assert cli.main(["--update-baseline", "--baseline", str(path)]) == 1
    assert not path.exists()
    assert json.loads(capsys.readouterr().out)["baseline_update"]["status"] == "failed"


def test_baseline_cli_update_and_check_are_mutually_exclusive():
    with pytest.raises(SystemExit):
        cli.build_arg_parser().parse_args(["--update-baseline", "--check-baseline"])


@pytest.mark.parametrize("mutation", ["source", "head", "dirty", "machine"])
def test_formal_write_rechecks_current_source_and_machine(tmp_path, monkeypatch, mutation):
    path = tmp_path / "baseline.json"
    write_baseline(path, snapshot())
    original = path.read_bytes()
    current = snapshot()["source_after"]
    if mutation == "source":
        current["source_sha256"] = "d" * 64
    elif mutation == "head":
        current["head"] = "d" * 40
    elif mutation == "dirty":
        current.update(worktree_clean=False, status_porcelain=[" M scratch.txt"])
    else:
        monkeypatch.setattr(ratchet_io, "machine_metadata", lambda: {"node": "another-machine"})
    monkeypatch.setattr(ratchet_io, "capture_source", lambda root: current)
    with pytest.raises(ValueError, match="formal baseline"):
        write_baseline(path, snapshot())
    assert path.read_bytes() == original


def test_legacy_baseline_is_never_overwritten(tmp_path):
    path = tmp_path / "legacy.json"
    legacy = snapshot()
    legacy["schema_version"] = 1
    path.write_text(json.dumps(legacy), encoding="utf-8")
    original = path.read_bytes()
    with pytest.raises(ValueError, match="baseline_migration_required"):
        write_baseline(path, snapshot())
    assert path.read_bytes() == original
    compared = compare_to_baseline(snapshot(), legacy)
    assert compared["status"] == "failed"
    assert compared["proof_binding_status"] != "clean_worktree"


@pytest.mark.parametrize("field,value", [("gap_to_oracle_pct", 1.0), ("runtime_ms", 1000.0)])
def test_update_cannot_bless_quality_or_total_runtime_regression(tmp_path, field, value):
    path = tmp_path / "baseline.json"
    write_baseline(path, snapshot())
    original = path.read_bytes()
    actual = snapshot()
    target = actual if field == "runtime_ms" else actual["cases"][0]
    target[field] = value
    with pytest.raises(ValueError, match="invalid benchmark baseline"):
        write_baseline(path, actual)
    assert path.read_bytes() == original


def test_source_change_during_measurement_is_not_promotable(tmp_path):
    actual = snapshot()
    actual["source_after"]["source_sha256"] = "d" * 64
    with pytest.raises(ValueError, match="source_changed_during_run"):
        write_baseline(tmp_path / "baseline.json", actual)
    assert not (tmp_path / "baseline.json").exists()


def test_atomic_failure_preserves_existing_baseline_and_removes_temporary_file(tmp_path, monkeypatch):
    path = tmp_path / "baseline.json"
    write_baseline(path, snapshot())
    original = path.read_bytes()

    def fail_replace(*args):
        raise OSError("replacement failed")

    monkeypatch.setattr(ratchet_io.os, "replace", fail_replace)
    with pytest.raises(OSError, match="replacement failed"):
        write_baseline(path, snapshot())
    assert path.read_bytes() == original
    assert list(tmp_path.iterdir()) == [path]


def test_duplicate_json_keys_cannot_be_loaded_as_a_baseline(tmp_path):
    path = tmp_path / "baseline.json"
    path.write_text('{"schema_version": 2, "schema_version": 1}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON key"):
        ratchet.load_baseline(path)


def test_light_measurement_includes_oracle_and_every_case_without_fake_tiny_runtime(monkeypatch):
    now = [100.0]
    source = snapshot()["source_before"]
    monkeypatch.setattr(ratchet, "time", type("Clock", (), {"perf_counter": staticmethod(lambda: now[0])}))
    monkeypatch.setattr(ratchet, "capture_source", lambda root: deepcopy(source))
    monkeypatch.setattr(ratchet, "machine_metadata", lambda: snapshot()["machine"])

    def proof(**kwargs):
        now[0] += 0.2
        return {"public": {"status": "passed", "cases": [{"case_slug": "controlled-tiny",
                 "gap_to_oracle_pct": 0.0, "objective_score_matched": True, "aggregate_counts": {"failed_ops": 0}}]}}

    def graph(**kwargs):
        now[0] += 0.3
        return {"case_group": "stub", "case_slug": "controlled-graph", "failed_ops": 0, "objective_score_matched": True}

    def metric():
        now[0] += 0.1
        return {"case_group": "stub", "case_slug": "controlled-metric", "failed_ops": 0, "objective_score_matched": True}

    monkeypatch.setattr(ratchet, "run_optimizer_proof_harness", proof)
    monkeypatch.setattr(ratchet, "run_graph_ready_real_sgs_case", graph)
    monkeypatch.setattr(ratchet, "run_graph_ready_flexible_machine_metric_case", metric)
    result = ratchet.build_light_ratchet_snapshot(repo_root=cli.REPO_ROOT)
    assert result["runtime_ms"] == pytest.approx(600.0)
    assert result["proof_harness_runtime_ms"] == pytest.approx(200.0)
    assert result["cases"][0]["runtime_ms"] is None
    assert result["cases"][0]["runtime_scope"] == "shared_proof_harness"
    assert result["cases"][2]["runtime_ms"] == pytest.approx(100.0)
    assert result["schema_version"] == 2
