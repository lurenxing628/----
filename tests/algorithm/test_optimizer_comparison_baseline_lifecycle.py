"""CLI promotion preserves prior baselines unless clean measured evidence passes."""
from __future__ import annotations

import json
from copy import deepcopy

import pytest

from tests._scripts_e2e import benchmark_optimizer_compare_algorithms as comparison_cli
from tests._scripts_e2e import benchmark_optimizer_graph_ready_v2_long_run as long_run_cli
from tests._support.optimizer_compare_algorithms_provenance import COMPARE_SCHEMA_VERSION, MEASUREMENT
from tests._support.optimizer_compare_algorithms_report import compare_to_algorithm_baseline


def _snapshot(*, long_run=False, dirty=False):
    source = {
        "repo_root": str(comparison_cli.REPO_ROOT), "head": "a" * 40, "branch": "main",
        "status_porcelain": [" M scratch.txt"] if dirty else [], "worktree_clean": not dirty,
        "diff_sha256": "b" * 64, "source_sha256": "c" * 64,
    }
    payload = {
        "schema_version": COMPARE_SCHEMA_VERSION, "status": "passed", "git_commit": source["head"],
        "dirty_worktree": dirty, "proof_binding_status": "unbound_dirty_worktree" if dirty else "clean_worktree",
        "source_before": deepcopy(source), "source_after": deepcopy(source),
        "measurement": deepcopy(MEASUREMENT), "machine": {"node": "fixture", "python_version": "3.8.10"},
        "seed_count": 1, "algorithm_profiles": ["greedy"],
        "command_args": {"profiles": ["greedy"], "seeds": 1, "workers": 1},
        "rows": [{"case_group": "graph_ready", "case_slug": "lifecycle-case", "algorithm_profile": "greedy",
                  "algorithm_version": "baseline_v1", "seed": 0, "status": "passed", "objective_name": "min_overdue",
                  "objective_score": [0, 0, 1], "time_budget_seconds": 1, "runtime_ms": 5.0,
                  "comparison_semantics": "same_budget_algorithm"}],
    }
    if long_run:
        wrapper = deepcopy(payload)
        wrapper.pop("rows")
        wrapper["comparison"] = payload
        return wrapper
    return payload


@pytest.fixture(params=[comparison_cli, long_run_cli], ids=["comparison", "long_run"])
def cli_case(request, monkeypatch):
    cli = request.param
    payload = _snapshot(long_run=cli is long_run_cli)
    builder = "build_algorithm_comparison" if cli is comparison_cli else "build_graph_ready_v2_long_run"
    monkeypatch.setattr(cli, builder, lambda **kwargs: deepcopy(payload))
    monkeypatch.setattr(comparison_cli, "capture_source", lambda root: deepcopy(payload["source_after"]))
    monkeypatch.setattr(comparison_cli, "machine_metadata", lambda: deepcopy(payload["machine"]))
    return cli, payload


def _run(cli, path, *args):
    return cli.main(["--baseline", str(path), "--no-write"] + list(args))


def test_clean_current_passed_source_can_create_and_update_baseline(cli_case, tmp_path, capsys):
    cli, payload = cli_case
    path = tmp_path / "new" / "baseline-v2.json"
    assert _run(cli, path, "--update-baseline") == 0
    assert json.loads(path.read_text(encoding="utf-8")) == payload
    assert _run(cli, path, "--update-baseline") == 0
    assert json.loads(capsys.readouterr().out.split("\n{", 1)[0])["baseline_write"]["status"] == "passed"


@pytest.mark.parametrize("arguments", [
    ["--update-baseline", "--check-baseline"],
    ["--update-baseline", "--allow-dirty-proof"],
    ["--workers", "2"],
])
def test_invalid_actions_are_rejected_before_running_benchmark(cli_case, monkeypatch, arguments):
    cli, _payload = cli_case
    builder = "build_algorithm_comparison" if cli is comparison_cli else "build_graph_ready_v2_long_run"

    def unexpected_run(**kwargs):
        pytest.fail("invalid command must not start a benchmark")

    monkeypatch.setattr(cli, builder, unexpected_run)
    with pytest.raises(SystemExit) as error:
        cli.main(arguments)
    assert error.value.code == 2
    assert cli.build_arg_parser().parse_args([]).workers == 1


@pytest.mark.parametrize("mutation", ["failed", "missing_dirty", "dirty", "head", "changed_source", "missing_receipt"])
def test_invalid_snapshot_never_overwrites_prior_baseline(cli_case, tmp_path, mutation):
    cli, payload = cli_case
    path = tmp_path / "baseline.json"
    original = json.dumps(payload).encode()
    path.write_bytes(original)
    if mutation == "failed":
        payload["status"] = "failed"
    elif mutation == "missing_dirty":
        payload.pop("dirty_worktree")
    elif mutation == "dirty":
        payload["dirty_worktree"] = True
    elif mutation == "head":
        payload["git_commit"] = "d" * 40
    elif mutation == "changed_source":
        payload["source_after"]["source_sha256"] = "d" * 64
    else:
        payload.pop("source_before")
    assert _run(cli, path, "--update-baseline") == 1
    assert path.read_bytes() == original


@pytest.mark.parametrize("current_change", ["dirty", "source", "head", "machine"])
def test_update_rechecks_actual_source_and_runtime(cli_case, tmp_path, monkeypatch, current_change):
    cli, payload = cli_case
    path = tmp_path / "baseline.json"
    original = json.dumps(payload).encode()
    path.write_bytes(original)
    current = deepcopy(payload["source_after"])
    if current_change == "dirty":
        current["worktree_clean"] = False
        current["status_porcelain"] = [" M scratch.txt"]
    elif current_change in {"source", "head"}:
        current["source_sha256" if current_change == "source" else "head"] = "d" * (64 if current_change == "source" else 40)
    else:
        monkeypatch.setattr(comparison_cli, "machine_metadata", lambda: {"node": "other-machine"})
    monkeypatch.setattr(comparison_cli, "capture_source", lambda root: current)
    assert _run(cli, path, "--update-baseline") == 1
    assert path.read_bytes() == original


@pytest.mark.parametrize("arguments", [["--update-baseline"], ["--check-baseline"], ["--check-baseline", "--allow-dirty-proof"]])
def test_legacy_baseline_requires_explicit_migration_without_overwrite(cli_case, tmp_path, capsys, arguments):
    cli, payload = cli_case
    legacy = deepcopy(payload)
    legacy["schema_version"] = 1
    legacy.pop("source_before")
    legacy.pop("source_after")
    path = tmp_path / "legacy.json"
    original = json.dumps(legacy).encode()
    path.write_bytes(original)
    assert _run(cli, path, *arguments) == 1
    result = json.loads(capsys.readouterr().out)
    checked = result["baseline_write"] if "--update-baseline" in arguments else result["baseline_check"]
    assert checked["reason"] == "baseline_migration_required"
    assert path.read_bytes() == original


def test_quality_regression_cannot_be_blessed_by_update(cli_case, tmp_path):
    cli, payload = cli_case
    path = tmp_path / "baseline.json"
    original = json.dumps(payload).encode()
    path.write_bytes(original)
    measured = payload.get("comparison", payload)
    measured["rows"][0]["objective_score"][0] = 1
    assert _run(cli, path, "--update-baseline") == 1
    assert path.read_bytes() == original


def test_atomic_replace_failure_preserves_previous_baseline(cli_case, tmp_path, monkeypatch):
    cli, payload = cli_case
    path = tmp_path / "baseline.json"
    original = json.dumps(payload).encode()
    path.write_bytes(original)

    def fail_replace(*args):
        raise OSError("replacement failed")

    monkeypatch.setattr(comparison_cli.os, "replace", fail_replace)
    assert _run(cli, path, "--update-baseline") == 1
    assert path.read_bytes() == original
    assert list(tmp_path.iterdir()) == [path]


def test_invalid_existing_json_is_preserved(cli_case, tmp_path, capsys):
    cli, _payload = cli_case
    path = tmp_path / "baseline.json"
    path.write_bytes(b'{"status": "passed", "status": "failed"}')
    original = path.read_bytes()
    assert _run(cli, path, "--update-baseline") == 1
    assert json.loads(capsys.readouterr().out)["baseline_write"]["reason"] == "invalid_baseline"
    assert path.read_bytes() == original


def test_diagnostic_output_cannot_overwrite_selected_baseline(cli_case, tmp_path):
    cli, payload = cli_case
    path = tmp_path / "baseline.json"
    original = json.dumps(payload).encode()
    path.write_bytes(original)
    assert cli.main(["--baseline", str(path), "--output", str(path), "--allow-dirty-proof"]) == 1
    assert path.read_bytes() == original


def test_dirty_same_protocol_check_is_diagnostic_only(cli_case, tmp_path, capsys):
    cli, payload = cli_case
    payload.clear()
    payload.update(_snapshot(long_run=cli is long_run_cli, dirty=True))
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert _run(cli, path, "--check-baseline", "--allow-dirty-proof") == 0
    checked = json.loads(capsys.readouterr().out)["baseline_check"]
    assert checked["require_clean_proof"] is False
    assert checked["proof_binding_status"] == "unbound_dirty_worktree"
    assert _run(cli, path, "--check-baseline") == 1


def test_diagnostic_accepts_unrelated_status_changes_but_rejects_measured_source_changes(cli_case, tmp_path):
    cli, payload = cli_case
    payload.clear()
    payload.update(_snapshot(long_run=cli is long_run_cli, dirty=True))
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    for item in (payload, payload.get("comparison", payload)):
        item["source_after"]["status_porcelain"] = [" M other-note.txt"]
        item["source_after"]["diff_sha256"] = "d" * 64
    assert _run(cli, path, "--check-baseline", "--allow-dirty-proof") == 0
    for item in (payload, payload.get("comparison", payload)):
        item["source_after"]["source_sha256"] = "d" * 64
    assert _run(cli, path, "--check-baseline", "--allow-dirty-proof") == 1


@pytest.mark.parametrize("legacy", [False, True])
def test_unusable_baseline_is_rejected_before_spending_search_budget(cli_case, tmp_path, monkeypatch, legacy):
    cli, payload = cli_case
    path = tmp_path / "baseline.json"
    if legacy:
        payload["schema_version"] = 1
        path.write_text(json.dumps(payload), encoding="utf-8")
    builder = "build_algorithm_comparison" if cli is comparison_cli else "build_graph_ready_v2_long_run"

    def unexpected_run(**kwargs):
        raise AssertionError("unusable reference must be rejected before running the benchmark")

    monkeypatch.setattr(cli, builder, unexpected_run)
    assert _run(cli, path, "--check-baseline") == 1


@pytest.mark.parametrize("mutation,reason", [
    ("runtime", "runtime_regressed"), ("zero_runtime", "actual_runtime_unknown"),
    ("legacy", "actual_migration_required"), ("clock", "actual_measurement_mismatch"),
    ("source", "actual_source_changed_during_run"), ("machine", "machine_mismatch"),
    ("binding", "actual_proof_binding_mismatch"),
])
def test_comparator_rejects_incomparable_or_corrupted_timing_evidence(mutation, reason):
    baseline = _snapshot()
    actual = deepcopy(baseline)
    if mutation in {"runtime", "zero_runtime"}:
        actual["rows"][0]["runtime_ms"] = 1_000_000.0 if mutation == "runtime" else 0.0
    elif mutation == "legacy":
        actual["schema_version"] = 1
    elif mutation == "clock":
        actual["measurement"]["clock"] = "BenchmarkClock"
    elif mutation == "source":
        actual["source_after"]["source_sha256"] = "d" * 64
    elif mutation == "machine":
        actual["machine"]["node"] = "other-machine"
    else:
        actual["proof_binding_status"] = "unbound_dirty_worktree"
    result = compare_to_algorithm_baseline(actual, baseline, require_clean_proof=False)
    assert result["status"] == "failed"
    assert reason in {item["reason"] for item in result["failures"]}
