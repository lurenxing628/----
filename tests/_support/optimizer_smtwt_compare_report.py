"""Reporting helpers for SMTWT optimizer comparison."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from tests._support.optimizer_smtwt_compare_common import (
    SMTWT_COMPARE_SCHEMA_VERSION,
    SMTWT_OBJECTIVE_NAME,
    first_changed_delta,
    mean,
    row_key,
    score_tuple,
    valid_score_tuple,
)


def portfolio_row(rows: Sequence[Dict[str, Any]], *, seed: int, optimum: int) -> Dict[str, Any]:
    if not rows:
        raise ValueError("portfolio_all requires at least one source row")
    invalid_sources = _invalid_score_sources(rows)
    failed_sources = _failed_sources(rows)
    shape_mismatch_sources = _shape_mismatch_sources(rows)
    eligible_rows = _eligible_portfolio_rows(rows)
    accepted_fingerprints = _output_fingerprint_union(rows, field="accepted_output_fingerprints")
    best = min(eligible_rows, key=lambda row: score_tuple(row.get("objective_score"))) if eligible_rows else {}
    row = _portfolio_base(best=best, seed=seed, optimum=optimum)
    row.update(_portfolio_totals(rows, accepted_fingerprints=accepted_fingerprints))
    row.update(
        {
            "candidate_rejections": merge_rejections(rows),
            "best_origin": f"{best.get('algorithm_profile')}:{best.get('best_origin')}" if best else "",
            "candidate_origin": f"portfolio_all:{best.get('algorithm_profile')}" if best else "portfolio_all:no_eligible_source",
            "best_output_fingerprint": str(best.get("best_output_fingerprint") or ""),
            "candidate_output_fingerprints": _output_fingerprint_union(rows, field="candidate_output_fingerprints"),
            "accepted_output_fingerprints": accepted_fingerprints,
            "best_order": list(best.get("best_order") or []),
            "invalid_objective_score_sources": invalid_sources,
            "failed_source_profiles": failed_sources,
            "objective_score_shape_mismatch_sources": shape_mismatch_sources,
            "status": "failed" if invalid_sources or failed_sources or shape_mismatch_sources or not eligible_rows else "passed",
        }
    )
    return row


def attach_case_comparisons(rows: List[Dict[str, Any]]) -> None:
    refs = {
        "greedy": _find_profile(rows, "greedy"),
        "local_search": _find_profile(rows, "local_search"),
        "grasp_ig": _find_profile(rows, "grasp_ig"),
        "graph_ready_v1": _find_profile(rows, "graph_ready_v1"),
        "portfolio_all": _find_profile(rows, "portfolio_all"),
    }
    for row in rows:
        row["comparison_to_greedy"] = comparison(row, refs["greedy"], label="greedy")
        row["comparison_to_local_search"] = comparison(row, refs["local_search"], label="local_search")
        row["comparison_to_grasp_ig"] = comparison(row, refs["grasp_ig"], label="grasp_ig")
        row["comparison_to_graph_ready_v1"] = comparison(row, refs["graph_ready_v1"], label="graph_ready_v1")
        row["comparison_to_portfolio_best"] = comparison(row, refs["portfolio_all"], label="portfolio_all")


def summarize_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [_summary_for_profile(rows, profile) for profile in sorted(_profiles(rows))]


def pairwise_vs(rows: Sequence[Dict[str, Any]], *, subject: str) -> List[Dict[str, Any]]:
    references = [profile for profile in sorted(_profiles(rows)) if profile != subject]
    return [_pairwise_row(rows, subject=subject, reference=reference) for reference in references]


def comparison(row: Dict[str, Any], reference: Optional[Dict[str, Any]], *, label: str) -> Dict[str, Any]:
    if reference is None:
        return {"reference": label, "status": "not_comparable", "primary_delta": None, "reason": "missing_reference_algorithm"}
    if row.get("status") != "passed":
        return {"reference": label, "status": "not_comparable", "primary_delta": None, "reason": "actual_status_not_passed"}
    if reference.get("status") != "passed":
        return {"reference": label, "status": "not_comparable", "primary_delta": None, "reason": "reference_status_not_passed"}
    actual = valid_score_tuple(row.get("objective_score"))
    baseline = valid_score_tuple(reference.get("objective_score"))
    if actual is None:
        return {"reference": label, "status": "not_comparable", "primary_delta": None, "reason": "invalid_actual_objective_score"}
    if baseline is None:
        return {"reference": label, "status": "not_comparable", "primary_delta": None, "reason": "invalid_reference_objective_score"}
    if len(actual) != len(baseline):
        return {"reference": label, "status": "not_comparable", "primary_delta": None, "reason": "objective_score_shape_mismatch"}
    status = "same"
    if actual < baseline:
        status = "improved"
    elif actual > baseline:
        status = "degraded"
    return {"reference": label, "status": status, "primary_delta": first_changed_delta(actual, baseline)}


def merge_rejections(rows: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    merged: Dict[str, int] = {}
    for row in rows:
        for key, value in (row.get("candidate_rejections") or {}).items():
            merged[str(key)] = merged.get(str(key), 0) + int(value or 0)
    return merged


def _portfolio_base(*, best: Dict[str, Any], seed: int, optimum: int) -> Dict[str, Any]:
    return {
        "schema_version": SMTWT_COMPARE_SCHEMA_VERSION,
        "case_group": "smtwt_overdue",
        "case_slug": str(best.get("case_slug") or ""),
        "algorithm_profile": "portfolio_all",
        "algorithm_version": "posthoc_same_seed_v1",
        "seed": int(seed),
        "time_budget_seconds": int(best.get("time_budget_seconds") or 1),
        "objective_name": SMTWT_OBJECTIVE_NAME,
        "objective_score": list(best.get("objective_score") or []),
        "overdue_count": int(best.get("overdue_count") or 0),
        "optimal_overdue_count": int(optimum),
        "overdue_gap_to_opt": int(best.get("overdue_gap_to_opt") or 0),
        "failed_ops": int(best.get("failed_ops") or 0),
    }


def _portfolio_totals(rows: Sequence[Dict[str, Any]], *, accepted_fingerprints: Sequence[str]) -> Dict[str, int]:
    return {
        "runtime_ms": sum(int(row.get("runtime_ms") or 0) for row in rows),
        "evaluated_candidates": sum(int(row.get("evaluated_candidates") or 0) for row in rows),
        "distinct_candidates": len(_output_fingerprint_union(rows, field="candidate_output_fingerprints")),
        "accepted_candidates": len(accepted_fingerprints),
        "accepted_distinct_candidates": len(accepted_fingerprints),
    }


def _summary_for_profile(rows: Sequence[Dict[str, Any]], profile: str) -> Dict[str, Any]:
    profile_rows = [row for row in rows if row.get("algorithm_profile") == profile]
    return {
        "algorithm_profile": profile,
        "case_count": len(profile_rows),
        "mean_overdue_gap_to_opt": mean(row.get("overdue_gap_to_opt") for row in profile_rows),
        "mean_overdue_count": mean(row.get("overdue_count") for row in profile_rows),
        "optimal_case_count": sum(
            1
            for row in profile_rows
            if row.get("status") == "passed" and int(row.get("overdue_gap_to_opt") or 0) == 0
        ),
        "wins_vs_greedy": _count_status(profile_rows, "comparison_to_greedy", "improved"),
        "ties_vs_greedy": _count_status(profile_rows, "comparison_to_greedy", "same"),
        "losses_vs_greedy": _count_status(profile_rows, "comparison_to_greedy", "degraded"),
        "wins_vs_portfolio": _count_status(profile_rows, "comparison_to_portfolio_best", "improved"),
        "ties_vs_portfolio": _count_status(profile_rows, "comparison_to_portfolio_best", "same"),
        "losses_vs_portfolio": _count_status(profile_rows, "comparison_to_portfolio_best", "degraded"),
    }


def _pairwise_row(rows: Sequence[Dict[str, Any]], *, subject: str, reference: str) -> Dict[str, Any]:
    paired = _paired_rows(rows, subject=subject, reference=reference)
    statuses = [_pairwise_status(row, ref) for row, ref in paired]
    return {
        "subject": subject,
        "reference": reference,
        "case_count": len(paired),
        "wins": statuses.count("improved"),
        "ties": statuses.count("same"),
        "losses": statuses.count("degraded"),
        "not_comparable": statuses.count("not_comparable"),
        "mean_overdue_gap_delta": mean((row.get("overdue_gap_to_opt") or 0) - (ref.get("overdue_gap_to_opt") or 0) for row, ref in paired),
    }


def _paired_rows(rows: Sequence[Dict[str, Any]], *, subject: str, reference: str) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    subject_rows = [row for row in rows if row.get("algorithm_profile") == subject]
    ref_by_key = {row_key(row): row for row in rows if row.get("algorithm_profile") == reference}
    return [(row, ref_by_key[row_key(row)]) for row in subject_rows if row_key(row) in ref_by_key]


def _profiles(rows: Sequence[Dict[str, Any]]) -> set:
    return {str(row.get("algorithm_profile") or "") for row in rows}


def _find_profile(rows: Sequence[Dict[str, Any]], profile: str) -> Optional[Dict[str, Any]]:
    for row in rows:
        if row.get("algorithm_profile") == profile:
            return dict(row)
    return None


def _pairwise_status(row: Dict[str, Any], ref: Dict[str, Any]) -> str:
    if row.get("status") != "passed" or ref.get("status") != "passed":
        return "not_comparable"
    actual = valid_score_tuple(row.get("objective_score"))
    baseline = valid_score_tuple(ref.get("objective_score"))
    if actual is None or baseline is None:
        return "not_comparable"
    if len(actual) != len(baseline):
        return "not_comparable"
    if actual < baseline:
        return "improved"
    if actual > baseline:
        return "degraded"
    return "same"


def _invalid_score_sources(rows: Sequence[Dict[str, Any]]) -> List[str]:
    return [
        str(row.get("algorithm_profile") or "")
        for row in rows
        if valid_score_tuple(row.get("objective_score")) is None
    ]


def _failed_sources(rows: Sequence[Dict[str, Any]]) -> List[str]:
    return [
        str(row.get("algorithm_profile") or "")
        for row in rows
        if row.get("status") != "passed"
    ]


def _shape_mismatch_sources(rows: Sequence[Dict[str, Any]]) -> List[str]:
    expected_len = _expected_score_length(rows)
    if expected_len is None:
        return []
    return [
        str(row.get("algorithm_profile") or "")
        for row in rows
        if (score := valid_score_tuple(row.get("objective_score"))) is not None
        and len(score) != expected_len
    ]


def _eligible_portfolio_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    expected_len = _expected_score_length(rows)
    if expected_len is None:
        return []
    return [
        row
        for row in rows
        if row.get("status") == "passed"
        and (score := valid_score_tuple(row.get("objective_score"))) is not None
        and len(score) == expected_len
    ]


def _expected_score_length(rows: Sequence[Dict[str, Any]]) -> Optional[int]:
    lengths = [
        len(score)
        for row in rows
        if row.get("status") == "passed" and (score := valid_score_tuple(row.get("objective_score"))) is not None
    ]
    return max(lengths) if lengths else None


def _count_status(rows: Sequence[Dict[str, Any]], field: str, status: str) -> int:
    return sum(
        1
        for row in rows
        if row.get("status") == "passed" and (row.get(field) or {}).get("status") == status
    )


def _output_fingerprint_union(rows: Sequence[Dict[str, Any]], *, field: str) -> List[str]:
    fingerprints = set()
    for row in rows:
        added = False
        for item in list(row.get(field) or []):
            text = str(item or "").strip()
            if text:
                fingerprints.add(text)
                added = True
        if not added and row.get("best_output_fingerprint"):
            fingerprints.add(str(row["best_output_fingerprint"]))
    return sorted(fingerprints)
