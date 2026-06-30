"""回归测试：SMTWT 全量算法对比脚本合同。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from tests._scripts_e2e.benchmark_optimizer_smtwt_compare_algorithms import _proof_check
from tests._support.optimizer_smtwt_compare_algorithms import build_smtwt_algorithm_comparison
from tests._support.optimizer_smtwt_compare_common import POSTHOC_UPPER_BOUND_SEMANTICS, make_report_state
from tests._support.optimizer_smtwt_compare_context import row_from_candidate
from tests._support.optimizer_smtwt_compare_graph import GRAPH_READY_V2_REPAIRED_ORIGIN
from tests._support.optimizer_smtwt_compare_report import comparison, pairwise_vs, portfolio_row, summarize_rows


def test_smtwt_algorithm_comparison_reports_v2_pairwise_summary() -> None:
    payload = build_smtwt_algorithm_comparison(
        profiles=["greedy", "graph_ready_v2_no_repair", "portfolio_all"],
        sizes=[40],
        seeds=1,
        limit_per_size=1,
        time_budget_seconds=1,
        workers=1,
    )

    assert payload["status"] == "passed"
    assert payload["summary"]
    assert payload["pairwise_vs_graph_ready_v2"]
    assert payload["dirty_worktree"] in {True, False}
    assert payload["git_commit"]
    assert payload["generated_at"]
    assert payload["proof_binding_status"] in {"clean_worktree", "unbound_dirty_worktree"}
    assert "full objective_score" in payload["comparison_scope"]
    assert "not an APS graph/multi-machine optimum proof" in payload["comparison_scope"]
    assert "must not be reported as APS min_overdue global optimum proof" in payload["degenerate_benchmark_notice"]
    assert len(payload["rows"]) == 3
    by_profile = {str(row["algorithm_profile"]): row for row in payload["rows"]}
    assert by_profile["portfolio_all"]["comparison_semantics"] == POSTHOC_UPPER_BOUND_SEMANTICS
    assert by_profile["portfolio_all"]["time_budget_seconds"] == 2
    assert by_profile["portfolio_all"]["comparison_to_greedy"]["status"] == "not_comparable"
    assert by_profile["portfolio_all"]["comparison_to_greedy"]["reason"] == "actual_is_posthoc_upper_bound"
    assert by_profile["graph_ready_v2_no_repair"]["comparison_to_portfolio_best"]["status"] == "not_comparable"
    assert by_profile["graph_ready_v2_no_repair"]["comparison_to_portfolio_best"]["reason"] == "reference_is_posthoc_upper_bound"
    portfolio_pairwise = [
        item for item in payload["pairwise_vs_graph_ready_v2"] if item["reference"] == "portfolio_all"
    ][0]
    assert portfolio_pairwise["not_comparable"] == 1


def test_smtwt_missing_reference_is_not_comparable_instead_of_self_compare() -> None:
    payload = build_smtwt_algorithm_comparison(
        profiles=["graph_ready_v2_no_repair"],
        sizes=[40],
        seeds=1,
        limit_per_size=1,
        time_budget_seconds=1,
        workers=1,
    )
    row = payload["rows"][0]

    assert row["comparison_to_greedy"]["status"] == "not_comparable"
    assert row["comparison_to_greedy"]["reason"] == "missing_reference_algorithm"
    assert row["comparison_to_portfolio_best"]["status"] == "not_comparable"


def test_smtwt_invalid_actual_score_is_not_improvement() -> None:
    result = comparison(
        {"algorithm_profile": "graph_ready_v2_no_repair", "objective_score": [], "status": "passed"},
        {"algorithm_profile": "graph_ready_v1", "objective_score": [0.0, 2.0], "status": "passed"},
        label="graph_ready_v1",
    )

    assert result["status"] == "not_comparable"
    assert result["reason"] == "invalid_actual_objective_score"


def test_smtwt_short_actual_score_is_not_improvement() -> None:
    result = comparison(
        {"algorithm_profile": "graph_ready_v2_no_repair", "objective_score": [0.0], "status": "passed"},
        {"algorithm_profile": "graph_ready_v1", "objective_score": [0.0, 2.0], "status": "passed"},
        label="graph_ready_v1",
    )

    assert result["status"] == "not_comparable"
    assert result["reason"] == "objective_score_shape_mismatch"


def test_smtwt_failed_actual_score_is_not_improvement() -> None:
    result = comparison(
        {"algorithm_profile": "graph_ready_v2_no_repair", "objective_score": [0.0, 1.0], "status": "failed"},
        {"algorithm_profile": "graph_ready_v1", "objective_score": [0.0, 2.0], "status": "passed"},
        label="graph_ready_v1",
    )

    assert result["status"] == "not_comparable"
    assert result["reason"] == "actual_status_not_passed"


def test_smtwt_time_budget_mismatch_is_not_comparable() -> None:
    result = comparison(
        {
            "algorithm_profile": "graph_ready_v2_no_repair",
            "time_budget_seconds": 10,
            "objective_score": [0.0, 1.0],
            "status": "passed",
        },
        {
            "algorithm_profile": "graph_ready_v1",
            "time_budget_seconds": 1,
            "objective_score": [0.0, 2.0],
            "status": "passed",
        },
        label="graph_ready_v1",
    )

    assert result["status"] == "not_comparable"
    assert result["reason"] == "time_budget_mismatch"
    assert result["actual_time_budget_seconds"] == 10
    assert result["baseline_time_budget_seconds"] == 1


def test_smtwt_pairwise_time_budget_mismatch_is_not_win() -> None:
    rows = [
        {
            "case_slug": "case",
            "algorithm_profile": "graph_ready_v2_no_repair",
            "seed": 0,
            "time_budget_seconds": 10,
            "objective_score": [0.0, 1.0],
            "overdue_gap_to_opt": 0,
            "status": "passed",
        },
        {
            "case_slug": "case",
            "algorithm_profile": "graph_ready_v1",
            "seed": 0,
            "time_budget_seconds": 1,
            "objective_score": [0.0, 2.0],
            "overdue_gap_to_opt": 1,
            "status": "passed",
        },
    ]

    result = pairwise_vs(rows, subject="graph_ready_v2_no_repair")

    assert result == [
        {
            "subject": "graph_ready_v2_no_repair",
            "reference": "graph_ready_v1",
            "case_count": 1,
            "wins": 0,
            "ties": 0,
            "losses": 0,
            "not_comparable": 1,
            "mean_overdue_gap_delta": None,
        }
    ]


def test_smtwt_pairwise_missing_seed_is_not_win() -> None:
    rows = [
        {
            "case_slug": "case",
            "algorithm_profile": "graph_ready_v2_no_repair",
            "time_budget_seconds": 1,
            "objective_score": [0.0, 1.0],
            "overdue_gap_to_opt": 0,
            "status": "passed",
        },
        {
            "case_slug": "case",
            "algorithm_profile": "greedy",
            "seed": 0,
            "time_budget_seconds": 1,
            "objective_score": [0.0, 2.0],
            "overdue_gap_to_opt": 1,
            "status": "passed",
        },
    ]

    result = pairwise_vs(rows, subject="graph_ready_v2_no_repair")

    assert result == [
        {
            "subject": "graph_ready_v2_no_repair",
            "reference": "greedy",
            "case_count": 1,
            "wins": 0,
            "ties": 0,
            "losses": 0,
            "not_comparable": 1,
            "mean_overdue_gap_delta": None,
        }
    ]


def test_smtwt_pairwise_subject_duplicate_key_is_not_win() -> None:
    rows = [
        {
            "case_slug": "case",
            "algorithm_profile": "graph_ready_v2_no_repair",
            "seed": 0,
            "time_budget_seconds": 1,
            "objective_score": [0.0, 1.0],
            "overdue_gap_to_opt": 0,
            "status": "passed",
        },
        {
            "case_slug": "case",
            "algorithm_profile": "graph_ready_v2_no_repair",
            "seed": 0,
            "time_budget_seconds": 1,
            "objective_score": [0.0, 1.5],
            "overdue_gap_to_opt": 0,
            "status": "passed",
        },
        {
            "case_slug": "case",
            "algorithm_profile": "greedy",
            "seed": 0,
            "time_budget_seconds": 1,
            "objective_score": [0.0, 2.0],
            "overdue_gap_to_opt": 1,
            "status": "passed",
        },
    ]

    result = pairwise_vs(rows, subject="graph_ready_v2_no_repair")

    assert result == [
        {
            "subject": "graph_ready_v2_no_repair",
            "reference": "greedy",
            "case_count": 2,
            "wins": 0,
            "ties": 0,
            "losses": 0,
            "not_comparable": 2,
            "mean_overdue_gap_delta": None,
        }
    ]


def test_smtwt_pairwise_duplicate_reference_key_is_not_win() -> None:
    rows = [
        {
            "case_slug": "case",
            "algorithm_profile": "graph_ready_v2_no_repair",
            "seed": 0,
            "time_budget_seconds": 1,
            "objective_score": [0.0, 1.0],
            "overdue_gap_to_opt": 0,
            "status": "passed",
        },
        {
            "case_slug": "case",
            "algorithm_profile": "greedy",
            "seed": 0,
            "time_budget_seconds": 1,
            "objective_score": [0.0, 2.0],
            "overdue_gap_to_opt": 1,
            "status": "passed",
        },
        {
            "case_slug": "case",
            "algorithm_profile": "greedy",
            "seed": 0,
            "time_budget_seconds": 1,
            "objective_score": [0.0, 3.0],
            "overdue_gap_to_opt": 2,
            "status": "passed",
        },
    ]

    result = pairwise_vs(rows, subject="graph_ready_v2_no_repair")

    assert result == [
        {
            "subject": "graph_ready_v2_no_repair",
            "reference": "greedy",
            "case_count": 1,
            "wins": 0,
            "ties": 0,
            "losses": 0,
            "not_comparable": 1,
            "mean_overdue_gap_delta": None,
        }
    ]


def test_smtwt_pairwise_missing_reference_key_is_not_win() -> None:
    rows = [
        {
            "case_slug": "case-a",
            "algorithm_profile": "graph_ready_v2_no_repair",
            "seed": 0,
            "time_budget_seconds": 1,
            "objective_score": [0.0, 1.0],
            "overdue_gap_to_opt": 0,
            "status": "passed",
        },
        {
            "case_slug": "case-b",
            "algorithm_profile": "greedy",
            "seed": 0,
            "time_budget_seconds": 1,
            "objective_score": [0.0, 2.0],
            "overdue_gap_to_opt": 1,
            "status": "passed",
        },
    ]

    result = pairwise_vs(rows, subject="graph_ready_v2_no_repair")

    assert result == [
        {
            "subject": "graph_ready_v2_no_repair",
            "reference": "greedy",
            "case_count": 1,
            "wins": 0,
            "ties": 0,
            "losses": 0,
            "not_comparable": 1,
            "mean_overdue_gap_delta": None,
        }
    ]


def test_smtwt_portfolio_distinct_candidates_deduplicate_output_fingerprint() -> None:
    rows = [
        {
            "case_slug": "case",
            "algorithm_profile": "a",
            "time_budget_seconds": 1,
            "objective_score": [0.0, 1.0],
            "overdue_count": 1,
            "overdue_gap_to_opt": 0,
            "failed_ops": 0,
            "runtime_ms": 1,
            "evaluated_candidates": 2,
            "distinct_candidates": 1,
            "accepted_candidates": 1,
            "candidate_rejections": {},
            "best_origin": "a",
            "best_order": [1, 2],
            "best_output_fingerprint": "same-output",
            "candidate_output_fingerprints": ["same-output"],
            "accepted_output_fingerprints": ["same-output"],
            "status": "passed",
        },
        {
            "case_slug": "case",
            "algorithm_profile": "b",
            "time_budget_seconds": 1,
            "objective_score": [0.0, 1.0],
            "overdue_count": 1,
            "overdue_gap_to_opt": 0,
            "failed_ops": 0,
            "runtime_ms": 1,
            "evaluated_candidates": 3,
            "distinct_candidates": 1,
            "accepted_candidates": 1,
            "candidate_rejections": {},
            "best_origin": "b",
            "best_order": [1, 2],
            "best_output_fingerprint": "same-output",
            "candidate_output_fingerprints": ["same-output"],
            "accepted_output_fingerprints": ["same-output"],
            "status": "passed",
        },
    ]

    row = portfolio_row(rows, seed=0, optimum=1)

    assert row["evaluated_candidates"] == 5
    assert row["time_budget_seconds"] == 2
    assert row["comparison_semantics"] == POSTHOC_UPPER_BOUND_SEMANTICS
    assert row["distinct_candidates"] == 1
    assert row["accepted_candidates"] == 1
    assert row["accepted_distinct_candidates"] == len(row["accepted_output_fingerprints"])


def test_smtwt_portfolio_rejects_invalid_source_score() -> None:
    rows = [
        {
            "case_slug": "case",
            "algorithm_profile": "bad",
            "time_budget_seconds": 1,
            "objective_score": [],
            "overdue_count": 0,
            "overdue_gap_to_opt": 0,
            "failed_ops": 0,
            "runtime_ms": 1,
            "evaluated_candidates": 1,
            "distinct_candidates": 1,
            "accepted_candidates": 1,
            "candidate_rejections": {},
            "best_origin": "bad",
            "best_order": [1],
            "best_output_fingerprint": "bad-output",
            "candidate_output_fingerprints": ["bad-output"],
            "accepted_output_fingerprints": ["bad-output"],
            "status": "passed",
        },
        {
            "case_slug": "case",
            "algorithm_profile": "good",
            "time_budget_seconds": 1,
            "objective_score": [0.0, 2.0],
            "overdue_count": 2,
            "overdue_gap_to_opt": 1,
            "failed_ops": 0,
            "runtime_ms": 1,
            "evaluated_candidates": 1,
            "distinct_candidates": 1,
            "accepted_candidates": 1,
            "candidate_rejections": {},
            "best_origin": "good",
            "best_order": [2],
            "best_output_fingerprint": "good-output",
            "candidate_output_fingerprints": ["good-output"],
            "accepted_output_fingerprints": ["good-output"],
            "status": "passed",
        },
    ]

    row = portfolio_row(rows, seed=0, optimum=1)

    assert row["status"] == "failed"
    assert row["best_origin"] == "good:good"
    assert row["invalid_objective_score_sources"] == ["bad"]


def test_smtwt_portfolio_rejects_missing_source_time_budget() -> None:
    rows = [
        {
            "case_slug": "case",
            "algorithm_profile": "missing-budget",
            "objective_score": [0.0, 1.0],
            "overdue_count": 1,
            "overdue_gap_to_opt": 0,
            "failed_ops": 0,
            "runtime_ms": 1,
            "evaluated_candidates": 1,
            "distinct_candidates": 1,
            "accepted_candidates": 1,
            "candidate_rejections": {},
            "best_origin": "source",
            "best_order": [1],
            "best_output_fingerprint": "source-output",
            "candidate_output_fingerprints": ["source-output"],
            "accepted_output_fingerprints": ["source-output"],
            "status": "passed",
        }
    ]

    row = portfolio_row(rows, seed=0, optimum=1)

    assert row["status"] == "failed"
    assert row["invalid_time_budget_sources"] == ["missing-budget"]
    assert row["source_time_budget_seconds_by_profile"] == {"missing-budget": None}


def test_smtwt_portfolio_rejects_failed_source_and_uses_passed_candidate() -> None:
    rows = [
        {
            "case_slug": "case",
            "algorithm_profile": "bad",
            "time_budget_seconds": 1,
            "objective_score": [0.0, 0.0],
            "overdue_count": 0,
            "overdue_gap_to_opt": 0,
            "failed_ops": 0,
            "runtime_ms": 1,
            "evaluated_candidates": 1,
            "distinct_candidates": 1,
            "accepted_candidates": 1,
            "candidate_rejections": {},
            "best_origin": "bad",
            "best_order": [1],
            "best_output_fingerprint": "bad-output",
            "candidate_output_fingerprints": ["bad-output"],
            "accepted_output_fingerprints": ["bad-output"],
            "status": "failed",
        },
        {
            "case_slug": "case",
            "algorithm_profile": "good",
            "time_budget_seconds": 1,
            "objective_score": [0.0, 2.0],
            "overdue_count": 2,
            "overdue_gap_to_opt": 1,
            "failed_ops": 0,
            "runtime_ms": 1,
            "evaluated_candidates": 1,
            "distinct_candidates": 1,
            "accepted_candidates": 1,
            "candidate_rejections": {},
            "best_origin": "good",
            "best_order": [2],
            "best_output_fingerprint": "good-output",
            "candidate_output_fingerprints": ["good-output"],
            "accepted_output_fingerprints": ["good-output"],
            "status": "passed",
        },
    ]

    row = portfolio_row(rows, seed=0, optimum=1)

    assert row["status"] == "failed"
    assert row["best_origin"] == "good:good"
    assert row["failed_source_profiles"] == ["bad"]


def test_smtwt_portfolio_has_no_best_when_all_sources_fail() -> None:
    rows = [
        {
            "case_slug": "case",
            "algorithm_profile": "bad",
            "time_budget_seconds": 1,
            "objective_score": [0.0, 0.0],
            "overdue_count": 0,
            "overdue_gap_to_opt": 0,
            "failed_ops": 0,
            "runtime_ms": 1,
            "evaluated_candidates": 1,
            "distinct_candidates": 1,
            "accepted_candidates": 1,
            "candidate_rejections": {},
            "best_origin": "bad",
            "best_order": [1],
            "best_output_fingerprint": "bad-output",
            "candidate_output_fingerprints": ["bad-output"],
            "accepted_output_fingerprints": ["bad-output"],
            "status": "failed",
        }
    ]

    row = portfolio_row(rows, seed=0, optimum=1)

    assert row["status"] == "failed"
    assert row["best_origin"] == ""
    assert row["candidate_origin"] == "portfolio_all:no_eligible_source"
    assert row["objective_score"] == []


def test_smtwt_summary_does_not_count_failed_row_as_win_or_optimal() -> None:
    summary = summarize_rows(
        [
            {
                "algorithm_profile": "bad",
                "status": "failed",
                "overdue_gap_to_opt": 0,
                "overdue_count": 0,
                "comparison_to_greedy": {"status": "improved"},
                "comparison_to_portfolio_best": {"status": "improved"},
            }
        ]
    )

    assert summary[0]["wins_vs_greedy"] == 0
    assert summary[0]["wins_vs_portfolio"] == 0
    assert summary[0]["optimal_case_count"] == 0


def test_smtwt_summary_does_not_turn_missing_gap_into_optimal_zero() -> None:
    summary = summarize_rows(
        [
            {
                "algorithm_profile": "bad-gap",
                "status": "passed",
                "overdue_count": 1,
                "comparison_to_greedy": {"status": "same"},
                "comparison_to_portfolio_best": {"status": "not_comparable"},
            }
        ]
    )

    assert summary[0]["mean_overdue_gap_to_opt"] is None
    assert summary[0]["optimal_case_count"] == 0


def test_smtwt_summary_does_not_turn_missing_overdue_count_into_zero() -> None:
    # 缺 overdue_count 的 passed 行不能把"没记录超期数"显示成平均超期 0.0,
    # 应与 mean_overdue_gap_to_opt 口径对齐,无有效样本时返回 None。
    summary = summarize_rows(
        [
            {
                "algorithm_profile": "no-count",
                "status": "passed",
                "overdue_gap_to_opt": 2,
                "comparison_to_greedy": {"status": "same"},
                "comparison_to_portfolio_best": {"status": "not_comparable"},
            }
        ]
    )

    assert summary[0]["mean_overdue_count"] is None
    assert summary[0]["mean_overdue_gap_to_opt"] == 2.0


def test_smtwt_repaired_candidate_state_keeps_origin_and_fingerprint_aligned() -> None:
    context = {"case": SimpleNamespace(slug="case", objective_name="min_overdue"), "time_budget_seconds": 1}
    candidate = {
        "results": [SimpleNamespace(op_id=1, batch_id="B1", seq=1)],
        "summary": SimpleNamespace(success=True, total_ops=1, scheduled_ops=1, failed_ops=0),
        "metrics": SimpleNamespace(
            overdue_count=1,
            weighted_tardiness_hours=0.0,
            total_tardiness_hours=0.0,
            makespan_hours=1.0,
            changeover_count=0,
        ),
        "score": [0.0, 1.0, 0.0, 0.0, 1.0, 0.0],
        "candidate_origin": GRAPH_READY_V2_REPAIRED_ORIGIN,
        "strategy": "priority_first",
        "params": {},
        "dispatch_mode": "sgs",
        "dispatch_rule": "slack",
        "order": [1],
        "runtime_ms": 0,
    }
    state = make_report_state(profile="graph_ready_v2_with_repair", seed=0, context=context)
    state.mark_candidate_accepted(candidate, origin=GRAPH_READY_V2_REPAIRED_ORIGIN)

    row = row_from_candidate(
        candidate,
        profile="graph_ready_v2_with_repair",
        version="graph_ready_v2_objective_features_v2",
        context=context,
        optimum=1,
        seed=0,
        state=state,
    )

    assert row["candidate_origin"] == GRAPH_READY_V2_REPAIRED_ORIGIN
    assert row["best_origin"] == GRAPH_READY_V2_REPAIRED_ORIGIN
    assert row["best_output_fingerprint"] in row["accepted_output_fingerprints"]
    assert row["accepted_distinct_candidates"] == len(row["accepted_output_fingerprints"])


def test_smtwt_proof_check_keeps_dirty_result_unbound() -> None:
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


def test_smtwt_compare_script_summary_only_omits_rows() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "tests" / "_scripts_e2e" / "benchmark_optimizer_smtwt_compare_algorithms.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--profiles",
            "greedy,graph_ready_v2_no_repair,portfolio_all",
            "--sizes",
            "40",
            "--limit-per-size",
            "1",
            "--seeds",
            "1",
            "--no-write",
            "--summary-only",
            "--workers",
            "1",
            "--allow-dirty-proof",
        ],
        cwd=str(repo_root),
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    payload = json.loads(result.stdout)

    comparison = payload["comparison"]
    assert comparison["status"] == "passed"
    assert comparison["proof_binding_status"] in {"clean_worktree", "unbound_dirty_worktree"}
    assert payload["proof_check"]["status"] == "passed"
    assert comparison["rows"]["omitted"] is True
    assert comparison["rows"]["row_count"] == 3
