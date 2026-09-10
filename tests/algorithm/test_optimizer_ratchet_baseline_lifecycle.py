"""Baseline updates require real proof; malformed or regressed rows fail closed."""
from __future__ import annotations

import json
from copy import deepcopy

import pytest

from tests._scripts_e2e import benchmark_optimizer_ratchet as cli
from tests._support.optimizer_benchmark_ratchet import compare_to_baseline, write_baseline


def snapshot():
    return {
        "schema_version": 1, "status": "passed", "dirty_worktree": False,
        "git_commit": "a" * 40, "case_count": 1,
        "cases": [{"case_group": "tiny", "case_slug": "lifecycle-proof", "failed_ops": 0,
                   "gap_to_oracle_pct": 0.0, "objective_score_matched": True,
                   "objective_name": "min_overdue", "seed": 0, "time_budget_seconds": 1}],
    }


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
