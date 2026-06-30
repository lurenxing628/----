"""回归测试：优化器 benchmark ratchet 轻门禁和长跑输出口径。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests._scripts_e2e import benchmark_optimizer_long_run, benchmark_optimizer_ratchet, benchmark_smtwt_localsearch
from tests._scripts_e2e.benchmark_optimizer_medium_gate import command_plan
from tests._support.optimizer_benchmark_ratchet import (
    DEFAULT_BASELINE,
    build_light_ratchet_snapshot,
    compare_to_baseline,
    load_baseline,
)
from tests._support.optimizer_graph_ready_benchmark import run_graph_ready_flexible_machine_metric_case


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _minimal_ratchet_snapshot(*, dirty_worktree: bool = False) -> dict:
    return {
        "status": "passed",
        "dirty_worktree": dirty_worktree,
        "case_count": 1,
        "cases": [
            {
                "case_group": "tiny",
                "case_slug": "tiny-sgs-single-machine",
                "failed_ops": 0,
                "gap_to_oracle_pct": 0.0,
                "objective_score_matched": True,
            }
        ],
    }


def test_light_benchmark_ratchet_rejects_tracked_dirty_baseline() -> None:
    repo_root = _repo_root()
    baseline = load_baseline(repo_root / DEFAULT_BASELINE)
    assert baseline is not None
    snapshot = build_light_ratchet_snapshot(repo_root=repo_root)
    comparison = compare_to_baseline(snapshot, baseline)
    assert snapshot["status"] == "passed"
    assert comparison["status"] == "failed"
    assert comparison["proof_binding_status"] == "unbound_dirty_worktree"
    assert any(item.get("reason") == "dirty_baseline_worktree" for item in comparison["failures"])


def test_benchmark_ratchet_blocks_dirty_actual_worktree_proof() -> None:
    baseline = _minimal_ratchet_snapshot(dirty_worktree=False)
    actual = _minimal_ratchet_snapshot(dirty_worktree=True)

    result = compare_to_baseline(actual, baseline)

    assert result["status"] == "failed"
    assert result["proof_binding_status"] == "unbound_dirty_worktree"
    assert result["failures"] == [{"reason": "dirty_actual_worktree"}]


def test_benchmark_ratchet_blocks_dirty_baseline_worktree_proof() -> None:
    baseline = _minimal_ratchet_snapshot(dirty_worktree=True)
    actual = _minimal_ratchet_snapshot(dirty_worktree=False)

    result = compare_to_baseline(actual, baseline)

    assert result["status"] == "failed"
    assert result["proof_binding_status"] == "unbound_dirty_worktree"
    assert result["failures"] == [{"reason": "dirty_baseline_worktree"}]


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
    assert payload["baseline_check"]["failures"] == [{"reason": "dirty_baseline_worktree"}]


def test_benchmark_ratchet_rejects_empty_actual_cases() -> None:
    baseline = {
        "status": "passed",
        "case_count": 1,
        "cases": [
            {
                "case_group": "graph_ready",
                "case_slug": "graph-ready-weight-grid-real-sgs",
                "status": "passed",
                "objective_score": [0.0],
                "failed_ops": 0,
                "objective_score_matched": True,
                "candidate_profile_count": 9,
                "evaluated_candidates": 10,
                "distinct_candidates": 3,
                "accepted_distinct_candidates": 2,
                "same_fingerprint_rejections": 4,
                "best_origin": "graph_ready_weight_grid",
            }
        ],
    }
    result = compare_to_baseline({"status": "passed", "case_count": 0, "cases": []}, baseline)

    assert result["status"] == "failed"
    assert any(item.get("reason") == "empty_actual_cases" for item in result["failures"])
    assert any(item.get("reason") == "missing_actual_case" for item in result["failures"])


def test_benchmark_ratchet_rejects_missing_baseline_case_from_actual() -> None:
    baseline = {
        "status": "passed",
        "case_count": 2,
        "cases": [
            {"case_group": "tiny", "case_slug": "tiny-sgs-single-machine", "failed_ops": 0, "objective_score_matched": True},
            {
                "case_group": "graph_ready",
                "case_slug": "graph-ready-weight-grid-real-sgs",
                "status": "passed",
                "objective_score": [0.0],
                "failed_ops": 0,
                "objective_score_matched": True,
                "candidate_profile_count": 9,
                "evaluated_candidates": 10,
                "distinct_candidates": 3,
                "accepted_distinct_candidates": 2,
                "same_fingerprint_rejections": 4,
                "best_origin": "graph_ready_weight_grid",
            },
        ],
    }
    actual = {"status": "passed", "case_count": 1, "cases": [baseline["cases"][0]]}

    result = compare_to_baseline(actual, baseline)

    assert result["status"] == "failed"
    assert any(item.get("reason") == "missing_actual_case" for item in result["failures"])


def _graph_ready_real_sgs_ratchet_row() -> dict:
    return {
        "case_group": "graph_ready",
        "case_slug": "graph-ready-weight-grid-real-sgs",
        "status": "passed",
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
    baseline = {"status": "passed", "dirty_worktree": False, "case_count": 1, "cases": [_graph_ready_real_sgs_ratchet_row()]}
    actual_row = _graph_ready_real_sgs_ratchet_row()
    actual_row.pop("evaluated_candidates")
    actual = {"status": "passed", "dirty_worktree": False, "case_count": 1, "cases": [actual_row]}

    result = compare_to_baseline(actual, baseline)

    assert result["status"] == "failed"
    assert any(
        item.get("reason") == "missing_or_invalid_actual_evaluated_candidates"
        for item in result["failures"]
    )


def test_benchmark_ratchet_rejects_flexible_machine_metric_collapsing_to_busy_machine() -> None:
    base_row = run_graph_ready_flexible_machine_metric_case()
    baseline = {"status": "passed", "case_count": 1, "cases": [base_row]}
    actual_row = dict(base_row)
    actual_row["bottleneck_scores"] = dict(base_row["bottleneck_scores"])
    actual_row["bottleneck_scores"]["flex"] = actual_row["bottleneck_scores"]["busy"]

    result = compare_to_baseline({"status": "passed", "case_count": 1, "cases": [actual_row]}, baseline)

    assert result["status"] == "failed"
    assert any(
        item.get("metric") in {"bottleneck_scores.flex", "bottleneck_score_order"}
        for item in result["failures"]
    )


def test_long_run_benchmark_defaults_to_ignored_quality_gate_dir() -> None:
    repo_root = _repo_root()
    script = repo_root / "tests" / "_scripts_e2e" / "benchmark_optimizer_long_run.py"
    out = subprocess.check_output(
        [str(repo_root / ".venv" / "bin" / "python"), str(script), "--seeds", "10", "--no-write"],
        cwd=str(repo_root),
        text=True,
    )
    assert '"tier": "long_run"' in out
    assert '"workers": 10' in out
    assert "evidence/QualityGate/long_gate/" in (repo_root / ".gitignore").read_text(encoding="utf-8")


def test_long_run_benchmark_returns_nonzero_when_payload_failed(monkeypatch, capsys) -> None:
    def fake_run_seed(seed: int) -> dict:
        return {
            "status": "failed" if seed == 3 else "passed",
            "objective_score": [0.0],
            "duplicate_candidate_rate": 0.0,
            "candidate_rejection_rate": 0.0,
            "distinct_candidates": 1,
            "accepted_distinct_candidates": 1,
        }

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
