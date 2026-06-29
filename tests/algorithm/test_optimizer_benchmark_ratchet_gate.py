"""回归测试：优化器 benchmark ratchet 轻门禁和长跑输出口径。"""

from __future__ import annotations

import subprocess
from pathlib import Path

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


def test_light_benchmark_ratchet_matches_tracked_baseline() -> None:
    repo_root = _repo_root()
    baseline = load_baseline(repo_root / DEFAULT_BASELINE)
    assert baseline is not None
    snapshot = build_light_ratchet_snapshot(repo_root=repo_root)
    comparison = compare_to_baseline(snapshot, baseline)
    assert snapshot["status"] == "passed"
    assert comparison["status"] == "passed"


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
    assert "evidence/QualityGate/long_gate/" in (repo_root / ".gitignore").read_text(encoding="utf-8")


def test_medium_gate_declares_three_benchmark_families_and_ignored_reports() -> None:
    plan = command_plan()
    ids = {str(item["id"]) for item in plan}
    command_text = " ".join(" ".join(str(arg) for arg in item["args"]) for item in plan)
    assert ids == {"fjsp_graph_ready_smoke", "smtwt_local_search", "sgs_large_resource_pool"}
    assert "benchmark_fjsp.py" in command_text
    assert "benchmark_smtwt_localsearch.py" in command_text
    assert "benchmark_sgs_large_resource_pool.py" in command_text
    assert "evidence/Benchmark" not in command_text
