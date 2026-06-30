"""Reporting helpers for SMTWT optimizer comparison."""

from __future__ import annotations

import math
from collections import Counter
from typing import Any, Dict, List, Optional, Sequence, Tuple

from tests._support.optimizer_smtwt_compare_common import (
    POSTHOC_UPPER_BOUND_SEMANTICS,
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
    invalid_time_budget_sources = _invalid_time_budget_sources(rows)
    eligible_rows = _eligible_portfolio_rows(rows)
    accepted_fingerprints = _output_fingerprint_union(rows, field="accepted_output_fingerprints")
    best = min(eligible_rows, key=lambda row: score_tuple(row.get("objective_score"))) if eligible_rows else {}
    row = _portfolio_base(best=best, seed=seed, optimum=optimum)
    row.update(_portfolio_totals(rows, accepted_fingerprints=accepted_fingerprints))
    row.update(_portfolio_source_metadata(rows))
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
            "invalid_time_budget_sources": invalid_time_budget_sources,
            "status": "failed"
            if invalid_sources or failed_sources or shape_mismatch_sources or invalid_time_budget_sources or not eligible_rows
            else "passed",
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
    if row.get("comparison_semantics") == POSTHOC_UPPER_BOUND_SEMANTICS:
        return {"reference": label, "status": "not_comparable", "primary_delta": None, "reason": "actual_is_posthoc_upper_bound"}
    if reference.get("comparison_semantics") == POSTHOC_UPPER_BOUND_SEMANTICS:
        return {"reference": label, "status": "not_comparable", "primary_delta": None, "reason": "reference_is_posthoc_upper_bound"}
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
    budget_mismatch = _time_budget_mismatch(row, reference)
    if budget_mismatch is not None:
        reason, actual_budget, baseline_budget = budget_mismatch
        return {
            "reference": label,
            "status": "not_comparable",
            "primary_delta": None,
            "reason": reason,
            "actual_time_budget_seconds": actual_budget,
            "baseline_time_budget_seconds": baseline_budget,
        }
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
        "time_budget_seconds": 0,
        "comparison_semantics": POSTHOC_UPPER_BOUND_SEMANTICS,
        "objective_name": SMTWT_OBJECTIVE_NAME,
        "objective_score": list(best.get("objective_score") or []),
        "overdue_count": int(best.get("overdue_count") or 0),
        "optimal_overdue_count": int(optimum),
        "overdue_gap_to_opt": _valid_int(best.get("overdue_gap_to_opt")),
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


def _portfolio_source_metadata(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    source_profiles = [str(row.get("algorithm_profile") or "") for row in rows]
    source_time_budgets = {
        str(row.get("algorithm_profile") or ""): _valid_time_budget_seconds(row)
        for row in rows
    }
    total_time_budget = sum(value for value in source_time_budgets.values() if value is not None)
    return {
        "time_budget_seconds": int(total_time_budget),
        "comparison_semantics": POSTHOC_UPPER_BOUND_SEMANTICS,
        "source_algorithm_profiles": source_profiles,
        "source_time_budget_seconds_by_profile": source_time_budgets,
        "source_time_budget_seconds_total": int(total_time_budget),
    }


def _summary_for_profile(rows: Sequence[Dict[str, Any]], profile: str) -> Dict[str, Any]:
    profile_rows = [row for row in rows if row.get("algorithm_profile") == profile]
    valid_gap_rows = [
        row
        for row in profile_rows
        if row.get("status") == "passed" and _valid_int(row.get("overdue_gap_to_opt")) is not None
    ]
    valid_overdue_count_rows = [
        row for row in profile_rows if _valid_int(row.get("overdue_count")) is not None
    ]
    return {
        "algorithm_profile": profile,
        "case_count": len(profile_rows),
        "mean_overdue_gap_to_opt": mean(row.get("overdue_gap_to_opt") for row in valid_gap_rows)
        if valid_gap_rows
        else None,
        "mean_overdue_count": mean(row.get("overdue_count") for row in valid_overdue_count_rows)
        if valid_overdue_count_rows
        else None,
        "optimal_case_count": sum(
            1
            for row in valid_gap_rows
            if _valid_int(row.get("overdue_gap_to_opt")) == 0
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
    comparable_pairs = [
        (row, ref)
        for (row, ref), status in zip(paired, statuses)
        if status != "not_comparable" and ref is not None
    ]
    comparable_gap_deltas = _comparable_overdue_gap_deltas(comparable_pairs)
    return {
        "subject": subject,
        "reference": reference,
        "case_count": len(paired),
        "wins": statuses.count("improved"),
        "ties": statuses.count("same"),
        "losses": statuses.count("degraded"),
        "not_comparable": statuses.count("not_comparable"),
        "mean_overdue_gap_delta": mean(comparable_gap_deltas) if comparable_gap_deltas else None,
    }


def _paired_rows(rows: Sequence[Dict[str, Any]], *, subject: str, reference: str) -> List[Tuple[Dict[str, Any], Optional[Dict[str, Any]]]]:
    subject_rows = [row for row in rows if row.get("algorithm_profile") == subject]
    reference_rows = [row for row in rows if row.get("algorithm_profile") == reference]
    ref_by_key, duplicate_ref_keys = _unique_rows_by_key(reference_rows)
    subject_key_counts = Counter(key for row in subject_rows if (key := row_key(row)) is not None)
    pairs: List[Tuple[Dict[str, Any], Optional[Dict[str, Any]]]] = []
    for row in subject_rows:
        key = row_key(row)
        if key is None or subject_key_counts[key] > 1 or key in duplicate_ref_keys:
            pairs.append((row, None))
            continue
        pairs.append((row, ref_by_key.get(key)))
    return pairs


def _unique_rows_by_key(rows: Sequence[Dict[str, Any]]) -> Tuple[Dict[Tuple[str, int], Dict[str, Any]], set]:
    out: Dict[Tuple[str, int], Dict[str, Any]] = {}
    duplicate_keys = set()
    for row in rows:
        key = row_key(row)
        if key is None:
            continue
        if key in out:
            duplicate_keys.add(key)
            out.pop(key, None)
            continue
        out[key] = row
    return out, duplicate_keys


def _overdue_gap_delta(row: Dict[str, Any], ref: Dict[str, Any]) -> Optional[float]:
    actual = _valid_number(row.get("overdue_gap_to_opt"))
    baseline = _valid_number(ref.get("overdue_gap_to_opt"))
    if actual is None or baseline is None:
        return None
    return actual - baseline


def _comparable_overdue_gap_deltas(pairs: Sequence[Tuple[Dict[str, Any], Dict[str, Any]]]) -> List[float]:
    deltas: List[float] = []
    for row, ref in pairs:
        delta = _overdue_gap_delta(row, ref)
        if delta is not None:
            deltas.append(delta)
    return deltas


def _profiles(rows: Sequence[Dict[str, Any]]) -> set:
    return {str(row.get("algorithm_profile") or "") for row in rows}


def _find_profile(rows: Sequence[Dict[str, Any]], profile: str) -> Optional[Dict[str, Any]]:
    for row in rows:
        if row.get("algorithm_profile") == profile:
            return dict(row)
    return None


def _pairwise_status(row: Dict[str, Any], ref: Optional[Dict[str, Any]]) -> str:
    if ref is None:
        return "not_comparable"
    if row.get("status") != "passed" or ref.get("status") != "passed":
        return "not_comparable"
    if row.get("comparison_semantics") == POSTHOC_UPPER_BOUND_SEMANTICS:
        return "not_comparable"
    if ref.get("comparison_semantics") == POSTHOC_UPPER_BOUND_SEMANTICS:
        return "not_comparable"
    actual = valid_score_tuple(row.get("objective_score"))
    baseline = valid_score_tuple(ref.get("objective_score"))
    if actual is None or baseline is None:
        return "not_comparable"
    if len(actual) != len(baseline):
        return "not_comparable"
    if _time_budget_mismatch(row, ref) is not None:
        return "not_comparable"
    if actual < baseline:
        return "improved"
    if actual > baseline:
        return "degraded"
    return "same"


def _valid_time_budget_seconds(row: Dict[str, Any]) -> Optional[int]:
    value = row.get("time_budget_seconds")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number) or number < 0 or int(number) != number:
        return None
    return int(number)


def _valid_int(value: Any) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number) or int(number) != number:
        return None
    return int(number)


def _valid_number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _time_budget_mismatch(row: Dict[str, Any], reference: Dict[str, Any]) -> Optional[Tuple[str, Optional[int], Optional[int]]]:
    actual_budget = _valid_time_budget_seconds(row)
    baseline_budget = _valid_time_budget_seconds(reference)
    if actual_budget is None:
        return "missing_actual_time_budget_seconds", actual_budget, baseline_budget
    if baseline_budget is None:
        return "missing_reference_time_budget_seconds", actual_budget, baseline_budget
    if actual_budget != baseline_budget:
        return "time_budget_mismatch", actual_budget, baseline_budget
    return None


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


def _invalid_time_budget_sources(rows: Sequence[Dict[str, Any]]) -> List[str]:
    return [
        str(row.get("algorithm_profile") or "")
        for row in rows
        if _valid_time_budget_seconds(row) is None
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
