"""回归测试：优化器 benchmark ratchet 轻门禁和长跑输出口径。"""

from __future__ import annotations

import json
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest

from tests._scripts_e2e import benchmark_optimizer_long_run, benchmark_optimizer_ratchet, benchmark_smtwt_localsearch
from tests._scripts_e2e.benchmark_optimizer_medium_gate import command_plan
from tests._support.optimizer_benchmark_ratchet import compare_to_baseline
from tests._support.optimizer_graph_ready_benchmark import run_graph_ready_flexible_machine_metric_case


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _source_receipt(*, dirty_worktree: bool = False) -> dict:
    return {
        "repo_root": str(_repo_root()), "head": "a" * 40, "branch": "main",
        "status_porcelain": [" M scratch.txt"] if dirty_worktree else [],
        "worktree_clean": not dirty_worktree,
        "diff_sha256": "b" * 64, "source_sha256": "c" * 64,
    }


def _minimal_ratchet_snapshot(*, dirty_worktree: bool = False, rows=None) -> dict:
    source = _source_receipt(dirty_worktree=dirty_worktree)
    cases = rows if rows is not None else [
        {
            "case_group": "tiny", "case_slug": "tiny-sgs-single-machine",
            "objective_name": "min_overdue", "seed": 0, "time_budget_seconds": 0,
            "runtime_ms": None, "runtime_scope": "shared_proof_harness",
            "failed_ops": 0, "gap_to_oracle_pct": 0.0, "objective_score_matched": True,
        }
    ]
    return {
        "schema_version": 2,
        "status": "passed",
        "tier": "light",
        "dirty_worktree": dirty_worktree,
        "git_commit": source["head"], "git_commit_before": source["head"],
        "source_before": deepcopy(source), "source_after": deepcopy(source),
        "proof_binding_status": "unbound_dirty_worktree" if dirty_worktree else "clean_worktree",
        "measurement": {
            "clock": "time.perf_counter", "scope": "whole_light_ratchet_including_oracle_and_all_cases",
            "execution": "serial_single_worker",
        },
        "machine": {"node": "fixture", "python_version": "3.8.10"},
        "runtime_ms": 10.0,
        "case_count": len(cases),
        "cases": cases,
    }


@pytest.mark.parametrize("action", ["--check-baseline", "--update-baseline"])
def test_light_benchmark_ratchet_reports_current_proof_binding(monkeypatch, capsys, action) -> None:
    legacy = _minimal_ratchet_snapshot()
    legacy["schema_version"] = 1
    monkeypatch.setattr(benchmark_optimizer_ratchet, "load_baseline", lambda path: legacy)

    def unexpected_benchmark(**kwargs):
        pytest.fail("a legacy baseline must require migration before starting the benchmark")

    monkeypatch.setattr(benchmark_optimizer_ratchet, "build_light_ratchet_snapshot", unexpected_benchmark)
    assert benchmark_optimizer_ratchet.main([action]) == 1
    payload = json.loads(capsys.readouterr().out)
    checked = payload["baseline_check" if action == "--check-baseline" else "baseline_update"]
    assert checked["status"] == "failed"
    assert checked.get("reason") == "baseline_migration_required" or any(
        item.get("reason") == "baseline_migration_required" for item in checked.get("failures", [])
    )


def test_clean_light_benchmark_receipts_are_bound() -> None:
    snapshot = _minimal_ratchet_snapshot()
    result = compare_to_baseline(snapshot, deepcopy(snapshot))
    assert result["status"] == "passed", result
    assert result["proof_binding_status"] == "clean_worktree"


def test_benchmark_ratchet_blocks_dirty_actual_worktree_proof() -> None:
    baseline = _minimal_ratchet_snapshot(dirty_worktree=False)
    actual = _minimal_ratchet_snapshot(dirty_worktree=True)

    result = compare_to_baseline(actual, baseline)

    assert result["status"] == "failed"
    assert result["proof_binding_status"] == "unbound_dirty_worktree"
    assert {"reason": "dirty_actual_worktree"} in result["failures"]


def test_benchmark_ratchet_blocks_dirty_baseline_worktree_proof() -> None:
    baseline = _minimal_ratchet_snapshot(dirty_worktree=True)
    actual = _minimal_ratchet_snapshot(dirty_worktree=False)

    result = compare_to_baseline(actual, baseline)

    assert result["status"] == "failed"
    assert result["proof_binding_status"] == "unbound_dirty_worktree"
    assert {"reason": "dirty_baseline_worktree"} in result["failures"]


def test_benchmark_ratchet_rejects_missing_oracle_gap_for_tiny_proof() -> None:
    baseline = _minimal_ratchet_snapshot(dirty_worktree=False)
    actual = _minimal_ratchet_snapshot(dirty_worktree=False)
    actual["cases"][0].pop("gap_to_oracle_pct")

    result = compare_to_baseline(actual, baseline)

    assert result["status"] == "failed"
    assert any(
        item.get("reason") == "missing_or_invalid_actual_gap_to_oracle_pct"
        for item in result["failures"]
    )


def test_light_ratchet_cli_exits_nonzero_for_dirty_baseline(monkeypatch, capsys) -> None:
    monkeypatch.setattr(benchmark_optimizer_ratchet, "build_light_ratchet_snapshot", lambda *, repo_root: _minimal_ratchet_snapshot())
    monkeypatch.setattr(benchmark_optimizer_ratchet, "load_baseline", lambda path: _minimal_ratchet_snapshot(dirty_worktree=True))

    exit_code = benchmark_optimizer_ratchet.main(["--check-baseline", "--baseline", "unused-baseline.json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["baseline_check"]["status"] == "failed"
    assert payload["baseline_check"]["proof_binding_status"] == "unbound_dirty_worktree"
    assert {"reason": "dirty_baseline_worktree"} in payload["baseline_check"]["failures"]


def test_benchmark_ratchet_rejects_empty_actual_cases() -> None:
    baseline = _minimal_ratchet_snapshot(rows=[_graph_ready_real_sgs_ratchet_row()])
    result = compare_to_baseline(_minimal_ratchet_snapshot(rows=[]), baseline)

    assert result["status"] == "failed"
    assert any(item.get("reason") == "empty_actual_cases" for item in result["failures"])
    assert any(item.get("reason") == "missing_actual_case" for item in result["failures"])


def test_benchmark_ratchet_rejects_missing_baseline_case_from_actual() -> None:
    actual = _minimal_ratchet_snapshot()
    baseline = _minimal_ratchet_snapshot(rows=deepcopy(actual["cases"]) + [_graph_ready_real_sgs_ratchet_row()])

    result = compare_to_baseline(actual, baseline)

    assert result["status"] == "failed"
    assert any(item.get("reason") == "missing_actual_case" for item in result["failures"])


def _graph_ready_real_sgs_ratchet_row() -> dict:
    return {
        "case_group": "graph_ready",
        "case_slug": "graph-ready-weight-grid-real-sgs",
        "status": "passed",
        "objective_name": "min_overdue", "seed": 0, "time_budget_seconds": 2,
        "runtime_ms": 5.0,
        "objective_score": [0.0],
        "failed_ops": 0,
        "objective_score_matched": True,
        "candidate_profile_count": 9,
        "evaluated_candidates": 10,
        "distinct_candidates": 6,
        "accepted_distinct_candidates": 3,
        "same_fingerprint_rejections": 4,
        "best_origin": "graph_ready_weight_grid",
    }


def test_benchmark_ratchet_rejects_missing_int_count_metric_in_actual() -> None:
    # 候选计数类基准字段(evaluated_candidates 等)缺失不能被当成 0 静默放行,
    # 必须像 gap_to_oracle_pct 一样报 missing_or_invalid,守住基准比较合同。
    baseline = _minimal_ratchet_snapshot(rows=[_graph_ready_real_sgs_ratchet_row()])
    actual_row = _graph_ready_real_sgs_ratchet_row()
    actual_row.pop("evaluated_candidates")
    actual = _minimal_ratchet_snapshot(rows=[actual_row])

    result = compare_to_baseline(actual, baseline)

    assert result["status"] == "failed"
    assert any(
        item.get("reason") == "missing_or_invalid_actual_evaluated_candidates"
        for item in result["failures"]
    )


def test_benchmark_ratchet_rejects_flexible_machine_metric_collapsing_to_busy_machine() -> None:
    base_row = run_graph_ready_flexible_machine_metric_case()
    baseline = _minimal_ratchet_snapshot(rows=[base_row])
    actual_row = dict(base_row)
    actual_row["bottleneck_scores"] = dict(base_row["bottleneck_scores"])
    actual_row["bottleneck_scores"]["flex"] = actual_row["bottleneck_scores"]["busy"]

    result = compare_to_baseline(_minimal_ratchet_snapshot(rows=[actual_row]), baseline)

    assert result["status"] == "failed"
    assert any(
        item.get("metric") in {"bottleneck_scores.flex", "bottleneck_score_order"}
        for item in result["failures"]
    )


def _long_run_seed_row(seed: int, *, status: str = "passed") -> dict:
    return {
        "seed": seed, "status": status, "runtime_ms": float(seed + 1),
        "objective_score": [0.0], "duplicate_candidate_rate": 0.0,
        "candidate_rejection_rate": 0.0, "distinct_candidates": 1, "accepted_distinct_candidates": 1,
    }


def _mock_long_run_provenance(monkeypatch) -> None:
    monkeypatch.setattr(benchmark_optimizer_long_run, "capture_source", lambda root: _source_receipt())
    monkeypatch.setattr(benchmark_optimizer_long_run, "machine_metadata", lambda: {"node": "fixture"})


def test_long_run_benchmark_defaults_to_ignored_quality_gate_dir() -> None:
    repo_root = _repo_root()
    script = repo_root / "tests" / "_scripts_e2e" / "benchmark_optimizer_long_run.py"
    output = subprocess.check_output(
        [str(repo_root / ".venv" / "bin" / "python"), str(script), "--seeds", "10", "--no-write"],
        cwd=str(repo_root), text=True,
    )
    payload = json.loads(output)
    assert payload["tier"] == "long_run"
    assert payload["workers"] == 1
    assert payload["schema_version"] == 2
    assert payload["measurement"]["clock"] == "time.perf_counter"
    assert payload["measurement"]["execution"] == "serial_single_worker"
    assert len(payload["cases"]) == 10
    assert all(row["clock_scope"] == "time.perf_counter" and row["runtime_ms"] > 0 for row in payload["cases"])
    assert "evidence/QualityGate/long_gate/" in (repo_root / ".gitignore").read_text(encoding="utf-8")


def test_long_run_benchmark_serial_execution_and_runtime_aggregation(monkeypatch, capsys) -> None:
    repo_root = _repo_root()
    seeds = []

    def fake_run_seed(seed: int) -> dict:
        seeds.append(seed)
        return _long_run_seed_row(seed)

    _mock_long_run_provenance(monkeypatch)
    monkeypatch.setattr(benchmark_optimizer_long_run, "run_seed", fake_run_seed)
    assert benchmark_optimizer_long_run.main(["--seeds", "10", "--no-write"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["tier"] == "long_run"
    assert payload["workers"] == 1
    assert seeds == list(range(10))
    assert payload["aggregate"]["mean_runtime_ms"] == 5.5
    assert payload["aggregate"]["worst_runtime_ms"] == 10.0
    assert benchmark_optimizer_long_run.build_arg_parser().parse_args([]).output_dir == "evidence/QualityGate/long_gate/optimizer_benchmark"
    assert "evidence/QualityGate/long_gate/" in (repo_root / ".gitignore").read_text(encoding="utf-8")


def test_long_run_benchmark_returns_nonzero_when_payload_failed(monkeypatch, capsys) -> None:
    def fake_run_seed(seed: int) -> dict:
        return _long_run_seed_row(seed, status="failed" if seed == 3 else "passed")

    _mock_long_run_provenance(monkeypatch)
    monkeypatch.setattr(benchmark_optimizer_long_run, "run_seed", fake_run_seed)

    assert benchmark_optimizer_long_run.main(["--seeds", "10", "--workers", "1", "--no-write"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"


def test_smtwt_localsearch_returns_nonzero_when_any_sample_fails(monkeypatch) -> None:
    def fake_run(size: int, mode: str, workers: int) -> tuple:
        return 1, 0, 1, 1, [("wt-sample", "boom")] if size == 40 and mode == "sgs" else []

    monkeypatch.setattr(benchmark_smtwt_localsearch, "_run", fake_run)

    assert benchmark_smtwt_localsearch.main(["--workers", "1"]) == 1


def test_medium_gate_declares_three_benchmark_families_and_ignored_reports() -> None:
    plan = command_plan()
    ids = {str(item["id"]) for item in plan}
    command_text = " ".join(" ".join(str(arg) for arg in item["args"]) for item in plan)
    assert ids == {"fjsp_graph_ready_smoke", "smtwt_local_search", "sgs_large_resource_pool"}
    assert "benchmark_fjsp.py" in command_text
    assert "benchmark_smtwt_localsearch.py" in command_text
    assert "benchmark_sgs_large_resource_pool.py" in command_text
    for item in plan:
        args = [str(arg) for arg in item["args"]]
        assert "--workers" in args
        assert args[args.index("--workers") + 1] == "10"
    assert "evidence/Benchmark" not in command_text
