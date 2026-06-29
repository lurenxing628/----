"""回归测试：GraphReady v2 前的多算法比较矩阵。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests._scripts_e2e.benchmark_optimizer_compare_algorithms import _proof_check
from tests._support.optimizer_compare_algorithms import (
    _comparison,
    _portfolio_row,
    build_algorithm_comparison,
    compare_to_algorithm_baseline,
)
from tests._support.optimizer_compare_algorithms_report import summarize_comparison_rows


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _minimal_compare_payload(*, dirty_worktree: bool) -> dict:
    return {
        "status": "passed",
        "dirty_worktree": bool(dirty_worktree),
        "rows": [
            {
                "case_group": "graph_ready",
                "case_slug": "graph-ready-weight-grid-real-sgs",
                "algorithm_profile": "greedy",
                "algorithm_version": "baseline_v1",
                "seed": 0,
                "objective_score": [0.0, 1.0],
            }
        ],
    }


def test_algorithm_comparison_matrix_consumes_reference_diagnostics_and_uses_full_key() -> None:
    payload = build_algorithm_comparison(
        profiles=["greedy", "local_search", "grasp_ig", "graph_ready_v1", "portfolio_all"],
        seeds=1,
    )
    rows = payload["rows"]
    by_profile = {str(row["algorithm_profile"]): row for row in rows}

    assert payload["status"] == "passed"
    assert payload["ratchet_key_fields"] == [
        "case_group",
        "case_slug",
        "algorithm_profile",
        "algorithm_version",
        "seed",
    ]
    assert payload["reference_diagnostics"]["summary"]["not_comparable_reference_count"] >= 1
    assert set(by_profile) == {"greedy", "local_search", "grasp_ig", "graph_ready_v1", "portfolio_all"}
    assert by_profile["graph_ready_v1"]["comparison_to_current_baseline"]["status"] == "improved"
    assert by_profile["portfolio_all"]["best_origin"].startswith("grasp_ig:")
    assert by_profile["portfolio_all"]["candidate_origin"] == "portfolio_all:grasp_ig"
    assert payload["dirty_worktree"] in {True, False}
    assert payload["git_commit"]
    assert payload["generated_at"]
    for row in rows:
        assert row["comparison_reference_status"] == "reference_diagnostics_attached"
        assert "comparison_to_graph_ready_v1" in row
        assert "comparison_to_portfolio_best" in row
        assert row["distinct_candidates"] == len(row["candidate_output_fingerprints"])
        assert row["accepted_distinct_candidates"] == len(row["accepted_output_fingerprints"])


def test_algorithm_comparison_real_grasp_ig_candidate_counts_match_output_fingerprints() -> None:
    payload = build_algorithm_comparison(profiles=["grasp_ig"], seeds=1)
    row = payload["rows"][0]

    assert row["algorithm_profile"] == "grasp_ig"
    assert row["distinct_candidates"] == len(row["candidate_output_fingerprints"])
    assert row["accepted_distinct_candidates"] == len(row["accepted_output_fingerprints"])
    assert row["accepted_candidates"] >= row["accepted_distinct_candidates"]


def test_algorithm_comparison_missing_reference_is_not_comparable_instead_of_self_compare() -> None:
    payload = build_algorithm_comparison(profiles=["graph_ready_v2_no_repair"], seeds=1)
    row = payload["rows"][0]

    assert row["comparison_to_current_baseline"]["status"] == "not_comparable"
    assert row["comparison_to_current_baseline"]["reason"] == "missing_reference_algorithm"
    assert row["comparison_to_graph_ready_v1"]["status"] == "not_comparable"
    assert row["comparison_to_portfolio_best"]["status"] == "not_comparable"


def test_algorithm_comparison_invalid_actual_score_is_not_improvement() -> None:
    result = _comparison(
        {"algorithm_profile": "graph_ready_v2_no_repair", "objective_score": [], "status": "passed"},
        {"algorithm_profile": "graph_ready_v1", "objective_score": [0.0, 2.0], "status": "passed"},
        label="graph_ready_v1",
    )

    assert result["status"] == "not_comparable"
    assert result["reason"] == "invalid_actual_objective_score"


def test_algorithm_comparison_short_actual_score_is_not_improvement() -> None:
    result = _comparison(
        {"algorithm_profile": "graph_ready_v2_no_repair", "objective_score": [0.0], "status": "passed"},
        {"algorithm_profile": "graph_ready_v1", "objective_score": [0.0, 2.0], "status": "passed"},
        label="graph_ready_v1",
    )

    assert result["status"] == "not_comparable"
    assert result["reason"] == "objective_score_shape_mismatch"


def test_algorithm_comparison_failed_actual_score_is_not_improvement() -> None:
    result = _comparison(
        {"algorithm_profile": "graph_ready_v2_no_repair", "objective_score": [0.0, 1.0], "status": "failed"},
        {"algorithm_profile": "graph_ready_v1", "objective_score": [0.0, 2.0], "status": "passed"},
        label="graph_ready_v1",
    )

    assert result["status"] == "not_comparable"
    assert result["reason"] == "actual_status_not_passed"


def test_algorithm_portfolio_distinct_candidates_deduplicate_output_fingerprint() -> None:
    rows = [
        {
            "algorithm_profile": "a",
            "objective_score": [0.0, 1.0],
            "failed_ops": 0,
            "runtime_ms": 1,
            "evaluated_candidates": 2,
            "distinct_candidates": 1,
            "accepted_candidates": 1,
            "accepted_distinct_candidates": 1,
            "candidate_rejections": {},
            "best_origin": "a",
            "best_order": [1, 2],
            "best_output_fingerprint": "same-output",
            "candidate_output_fingerprints": ["same-output"],
            "accepted_output_fingerprints": ["same-output"],
            "status": "passed",
        },
        {
            "algorithm_profile": "b",
            "objective_score": [0.0, 1.0],
            "failed_ops": 0,
            "runtime_ms": 1,
            "evaluated_candidates": 3,
            "distinct_candidates": 1,
            "accepted_candidates": 1,
            "accepted_distinct_candidates": 1,
            "candidate_rejections": {},
            "best_origin": "b",
            "best_order": [1, 2],
            "best_output_fingerprint": "same-output",
            "candidate_output_fingerprints": ["same-output"],
            "accepted_output_fingerprints": ["same-output"],
            "status": "passed",
        },
    ]

    row = _portfolio_row(rows, seed=0)

    assert row["evaluated_candidates"] == 5
    assert row["distinct_candidates"] == 1
    assert row["accepted_distinct_candidates"] == 1


def test_algorithm_portfolio_rejects_failed_source_and_uses_passed_candidate() -> None:
    rows = [
        {
            "algorithm_profile": "bad",
            "objective_score": [0.0, 0.0],
            "failed_ops": 0,
            "runtime_ms": 1,
            "evaluated_candidates": 1,
            "distinct_candidates": 1,
            "accepted_candidates": 1,
            "accepted_distinct_candidates": 1,
            "candidate_rejections": {},
            "best_origin": "bad",
            "best_order": [1],
            "best_output_fingerprint": "bad-output",
            "candidate_output_fingerprints": ["bad-output"],
            "accepted_output_fingerprints": ["bad-output"],
            "status": "failed",
        },
        {
            "algorithm_profile": "good",
            "objective_score": [0.0, 2.0],
            "failed_ops": 0,
            "runtime_ms": 1,
            "evaluated_candidates": 1,
            "distinct_candidates": 1,
            "accepted_candidates": 1,
            "accepted_distinct_candidates": 1,
            "candidate_rejections": {},
            "best_origin": "good",
            "best_order": [2],
            "best_output_fingerprint": "good-output",
            "candidate_output_fingerprints": ["good-output"],
            "accepted_output_fingerprints": ["good-output"],
            "status": "passed",
        },
    ]

    row = _portfolio_row(rows, seed=0)

    assert row["status"] == "failed"
    assert row["best_origin"] == "good:good"
    assert row["failed_source_profiles"] == ["bad"]


def test_algorithm_portfolio_has_no_best_when_all_sources_fail() -> None:
    rows = [
        {
            "algorithm_profile": "bad",
            "objective_score": [0.0, 0.0],
            "failed_ops": 0,
            "runtime_ms": 1,
            "evaluated_candidates": 1,
            "distinct_candidates": 1,
            "accepted_candidates": 1,
            "accepted_distinct_candidates": 1,
            "candidate_rejections": {},
            "best_origin": "bad",
            "best_order": [1],
            "best_output_fingerprint": "bad-output",
            "candidate_output_fingerprints": ["bad-output"],
            "accepted_output_fingerprints": ["bad-output"],
            "status": "failed",
        }
    ]

    row = _portfolio_row(rows, seed=0)

    assert row["status"] == "failed"
    assert row["best_origin"] == ""
    assert row["candidate_origin"] == "portfolio_all:no_eligible_source"
    assert row["objective_score"] == []


def test_algorithm_summary_does_not_count_failed_row_as_win() -> None:
    summary = summarize_comparison_rows(
        [
            {
                "algorithm_profile": "bad",
                "status": "failed",
                "runtime_ms": 1,
                "comparison_to_current_baseline": {"status": "improved", "primary_delta": -1},
            }
        ]
    )

    assert summary[0]["wins_vs_current_baseline"] == 0
    assert summary[0]["mean_primary_delta_vs_current_baseline"] == 0.0


def test_algorithm_comparison_baseline_rejects_profile_regression() -> None:
    baseline = build_algorithm_comparison(profiles=["greedy"], seeds=1)
    actual = build_algorithm_comparison(profiles=["greedy"], seeds=1)
    actual["rows"][0]["objective_score"] = [99.0 for _item in actual["rows"][0]["objective_score"]]

    result = compare_to_algorithm_baseline(actual, baseline)

    assert result["status"] == "failed"
    assert any(failure["reason"] == "objective_score_regressed" for failure in result["failures"])


def test_algorithm_comparison_baseline_rejects_invalid_actual_score() -> None:
    baseline = _minimal_compare_payload(dirty_worktree=False)
    actual = _minimal_compare_payload(dirty_worktree=False)
    actual["rows"][0]["objective_score"] = []

    result = compare_to_algorithm_baseline(actual, baseline)

    assert result["status"] == "failed"
    assert result["failures"] == [
        {
            "reason": "invalid_actual_objective_score",
            "key": ["graph_ready", "graph-ready-weight-grid-real-sgs", "greedy", "baseline_v1", 0],
        }
    ]
    assert result["proof_binding_status"] == "clean_worktree"


def test_algorithm_comparison_baseline_rejects_score_shape_mismatch() -> None:
    baseline = _minimal_compare_payload(dirty_worktree=False)
    actual = _minimal_compare_payload(dirty_worktree=False)
    actual["rows"][0]["objective_score"] = [0.0]

    result = compare_to_algorithm_baseline(actual, baseline)

    assert result["status"] == "failed"
    assert result["failures"] == [
        {
            "reason": "objective_score_shape_mismatch",
            "key": ["graph_ready", "graph-ready-weight-grid-real-sgs", "greedy", "baseline_v1", 0],
            "baseline": [0.0, 1.0],
            "actual": [0.0],
        }
    ]


def test_algorithm_comparison_baseline_blocks_dirty_clean_proof_by_default() -> None:
    baseline = _minimal_compare_payload(dirty_worktree=True)
    actual = _minimal_compare_payload(dirty_worktree=True)

    result = compare_to_algorithm_baseline(actual, baseline)

    assert result["status"] == "failed"
    assert result["proof_binding_status"] == "unbound_dirty_worktree"
    assert {failure["reason"] for failure in result["failures"]} == {
        "dirty_actual_worktree",
        "dirty_baseline_worktree",
    }


def test_algorithm_comparison_baseline_can_report_dirty_functional_check_as_unbound() -> None:
    baseline = _minimal_compare_payload(dirty_worktree=True)
    actual = _minimal_compare_payload(dirty_worktree=True)

    result = compare_to_algorithm_baseline(actual, baseline, require_clean_proof=False)

    assert result["status"] == "passed"
    assert result["proof_binding_status"] == "unbound_dirty_worktree"
    assert result["require_clean_proof"] is False


def test_algorithm_comparison_proof_check_keeps_dirty_output_unbound() -> None:
    strict = _proof_check({"dirty_worktree": True, "proof_binding_status": "unbound_dirty_worktree"}, allow_dirty=False)
    allowed = _proof_check({"dirty_worktree": True, "proof_binding_status": "unbound_dirty_worktree"}, allow_dirty=True)

    assert strict == {
        "status": "failed",
        "reason": "dirty_actual_worktree",
        "proof_binding_status": "unbound_dirty_worktree",
    }
    assert allowed == {
        "status": "passed",
        "proof_binding_status": "unbound_dirty_worktree",
        "require_clean_proof": False,
    }


def test_algorithm_comparison_baseline_rejects_missing_v2_rows() -> None:
    baseline = build_algorithm_comparison(profiles=["greedy", "graph_ready_v1"], seeds=1)
    actual = build_algorithm_comparison(
        profiles=["greedy", "graph_ready_v1", "graph_ready_v2_no_repair", "graph_ready_v2_with_repair"],
        seeds=1,
    )

    result = compare_to_algorithm_baseline(actual, baseline)

    assert result["status"] == "failed"
    assert result["allowed_new_algorithm_rows"] == []
    missing_profiles = {failure["key"][2] for failure in result["failures"] if failure["reason"] == "missing_baseline_row"}
    assert missing_profiles == {"graph_ready_v2_no_repair", "graph_ready_v2_with_repair"}


def test_algorithm_comparison_script_no_write_runs_requested_profiles() -> None:
    repo_root = _repo_root()
    script = repo_root / "tests" / "_scripts_e2e" / "benchmark_optimizer_compare_algorithms.py"

    out = subprocess.check_output(
        [
            str(repo_root / ".venv" / "bin" / "python"),
            str(script),
            "--profiles",
            "greedy,graph_ready_v1,graph_ready_v2_no_repair,graph_ready_v2_with_repair,portfolio_all",
            "--seeds",
            "1",
            "--no-write",
            "--allow-dirty-proof",
        ],
        cwd=str(repo_root),
        text=True,
    )

    payload = json.loads(out)
    assert payload["comparison"]["status"] == "passed"
    assert payload["comparison"]["proof_binding_status"] in {"clean_worktree", "unbound_dirty_worktree"}
    assert payload["proof_check"]["status"] == "passed"
    assert "graph_ready_v1" in out
    assert "graph_ready_v2_no_repair" in out
    assert "graph_ready_v2_with_repair" in out
    assert "reference_diagnostics" in out
