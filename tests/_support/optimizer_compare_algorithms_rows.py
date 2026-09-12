"""Candidate rows and pairwise quality summaries for algorithm comparisons."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.services.scheduler.run.optimizer_candidate_fingerprint import build_candidate_fingerprint
from tests._support.optimizer_compare_algorithms_provenance import COMPARE_SCHEMA_VERSION
from tests._support.optimizer_graph_ready_benchmark import OBJECTIVE_NAME, _result_order, _score_list

COMPARE_CASE_GROUP = "graph_ready"
COMPARE_CASE_SLUG = "graph-ready-weight-grid-real-sgs"
POSTHOC_UPPER_BOUND_SEMANTICS = "posthoc_upper_bound"
SAME_BUDGET_SEMANTICS = "same_budget_algorithm"


def _row_from_candidate(
    *,
    candidate: Dict[str, Any],
    profile: str,
    version: str,
    seed: int,
    evaluated_candidates: int,
    distinct_candidates: int,
    accepted_candidates: int,
    candidate_rejections: Dict[str, Any],
    status: str,
    runtime_ms: float,
    candidate_output_fingerprints: Optional[Sequence[str]] = None,
    accepted_output_fingerprints: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    summary = candidate.get("summary")
    best_output_fingerprint = _candidate_output_fingerprint(candidate)
    candidate_fingerprints = _fingerprints_or_default(candidate_output_fingerprints, best_output_fingerprint)
    accepted_fingerprints = _fingerprints_or_default(accepted_output_fingerprints, best_output_fingerprint)
    return {
        "schema_version": COMPARE_SCHEMA_VERSION,
        "case_group": COMPARE_CASE_GROUP,
        "case_slug": COMPARE_CASE_SLUG,
        "algorithm_profile": profile,
        "algorithm_version": version,
        "seed": int(seed),
        "time_budget_seconds": 1,
        "comparison_semantics": SAME_BUDGET_SEMANTICS,
        "objective_name": OBJECTIVE_NAME,
        "objective_score": _score_list(candidate.get("score")),
        "failed_ops": int(getattr(summary, "failed_ops", 0) or 0),
        "runtime_ms": float(runtime_ms),
        "evaluated_candidates": int(evaluated_candidates),
        "distinct_candidates": len(candidate_fingerprints),
        "accepted_candidates": int(accepted_candidates),
        "accepted_distinct_candidates": len(accepted_fingerprints),
        "candidate_rejections": dict(candidate_rejections or {}),
        "best_origin": str(candidate.get("candidate_origin") or profile),
        "candidate_origin": str(candidate.get("candidate_origin") or profile),
        "best_order": _result_order(candidate.get("results")),
        "best_output_fingerprint": best_output_fingerprint,
        "candidate_output_fingerprints": candidate_fingerprints,
        "accepted_output_fingerprints": accepted_fingerprints,
        "comparison_reference_status": "reference_diagnostics_attached",
        "status": status if int(getattr(summary, "failed_ops", 0) or 0) == 0 and getattr(summary, "success", True) else "failed",
    }


def _fingerprints_or_default(values: Optional[Sequence[str]], default: str) -> List[str]:
    out = sorted({str(item) for item in list(values or []) if str(item)})
    return out or [str(default)]


def _portfolio_row(rows: Sequence[Dict[str, Any]], *, seed: int) -> Dict[str, Any]:
    if not rows:
        raise ValueError("portfolio_all requires at least one source row")
    invalid_sources = _invalid_score_sources(rows)
    failed_sources = _failed_sources(rows)
    shape_mismatch_sources = _shape_mismatch_sources(rows)
    invalid_time_budget_sources = _invalid_time_budget_sources(rows)
    eligible_rows = _eligible_portfolio_rows(rows)
    best = min(eligible_rows, key=lambda row: _score_tuple(row.get("objective_score"))) if eligible_rows else {}
    candidate_fingerprints = _output_fingerprint_union(rows, field="candidate_output_fingerprints")
    accepted_fingerprints = _output_fingerprint_union(rows, field="accepted_output_fingerprints")
    source_profiles = [str(row.get("algorithm_profile") or "") for row in rows]
    source_time_budgets = {
        str(row.get("algorithm_profile") or ""): _valid_time_budget_seconds(row)
        for row in rows
    }
    total_time_budget = sum(value for value in source_time_budgets.values() if value is not None)
    return {
        "schema_version": COMPARE_SCHEMA_VERSION,
        "case_group": COMPARE_CASE_GROUP,
        "case_slug": COMPARE_CASE_SLUG,
        "algorithm_profile": "portfolio_all",
        "algorithm_version": "posthoc_same_seed_v1",
        "seed": int(seed),
        "time_budget_seconds": int(total_time_budget),
        "comparison_semantics": POSTHOC_UPPER_BOUND_SEMANTICS,
        "source_algorithm_profiles": source_profiles,
        "source_time_budget_seconds_by_profile": source_time_budgets,
        "source_time_budget_seconds_total": int(total_time_budget),
        "objective_name": OBJECTIVE_NAME,
        "objective_score": list(best.get("objective_score") or []),
        "failed_ops": int(best.get("failed_ops") or 0),
        "runtime_ms": sum(float(row.get("runtime_ms") or 0) for row in rows),
        "evaluated_candidates": sum(int(row.get("evaluated_candidates") or 0) for row in rows),
        "distinct_candidates": len(candidate_fingerprints),
        "accepted_candidates": len(accepted_fingerprints),
        "accepted_distinct_candidates": len(accepted_fingerprints),
        "candidate_rejections": _merge_rejections(rows),
        "best_origin": f"{best.get('algorithm_profile')}:{best.get('best_origin')}" if best else "",
        "candidate_origin": f"portfolio_all:{best.get('algorithm_profile')}" if best else "portfolio_all:no_eligible_source",
        "best_order": list(best.get("best_order") or []),
        "best_output_fingerprint": str(best.get("best_output_fingerprint") or ""),
        "candidate_output_fingerprints": candidate_fingerprints,
        "accepted_output_fingerprints": accepted_fingerprints,
        "comparison_reference_status": "reference_diagnostics_attached",
        "invalid_objective_score_sources": invalid_sources,
        "failed_source_profiles": failed_sources,
        "objective_score_shape_mismatch_sources": shape_mismatch_sources,
        "invalid_time_budget_sources": invalid_time_budget_sources,
        "status": "failed"
        if invalid_sources or failed_sources or shape_mismatch_sources or invalid_time_budget_sources or not eligible_rows
        else "passed",
    }


def _merge_rejections(rows: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    merged: Dict[str, int] = {}
    for row in rows:
        for key, value in (row.get("candidate_rejections") or {}).items():
            merged[str(key)] = merged.get(str(key), 0) + int(value or 0)
    return merged


def _attach_comparisons(rows: List[Dict[str, Any]]) -> None:
    baseline = _find_profile(rows, "greedy")
    graph_ready_v1 = _find_profile(rows, "graph_ready_v1")
    portfolio = _find_profile(rows, "portfolio_all")
    for row in rows:
        row["comparison_to_current_baseline"] = _comparison(row, baseline, label="current_baseline")
        row["comparison_to_graph_ready_v1"] = _comparison(row, graph_ready_v1, label="graph_ready_v1")
        row["comparison_to_portfolio_best"] = _comparison(row, portfolio, label="portfolio_best")


def _find_profile(rows: Sequence[Dict[str, Any]], profile: str) -> Optional[Dict[str, Any]]:
    for row in rows:
        if row.get("algorithm_profile") == profile:
            return dict(row)
    return None


def _comparison(row: Dict[str, Any], reference: Optional[Dict[str, Any]], *, label: str) -> Dict[str, Any]:
    if reference is None:
        actual = _valid_score_tuple(row.get("objective_score"))
        return {
            "reference": label,
            "baseline_algorithm_profile": None,
            "baseline_value": [],
            "actual_value": list(actual or ()),
            "primary_delta": None,
            "status": "not_comparable",
            "reason": "missing_reference_algorithm",
        }
    if row.get("status") != "passed":
        return {
            "reference": label,
            "baseline_algorithm_profile": reference.get("algorithm_profile"),
            "baseline_value": list(_valid_score_tuple(reference.get("objective_score")) or ()),
            "actual_value": list(_valid_score_tuple(row.get("objective_score")) or ()),
            "primary_delta": None,
            "status": "not_comparable",
            "reason": "actual_status_not_passed",
        }
    if row.get("comparison_semantics") == POSTHOC_UPPER_BOUND_SEMANTICS:
        actual = _valid_score_tuple(row.get("objective_score"))
        baseline = _valid_score_tuple(reference.get("objective_score"))
        return {
            "reference": label,
            "baseline_algorithm_profile": reference.get("algorithm_profile"),
            "baseline_value": list(baseline or ()),
            "actual_value": list(actual or ()),
            "primary_delta": None,
            "status": "not_comparable",
            "reason": "actual_is_posthoc_upper_bound",
        }
    if reference.get("comparison_semantics") == POSTHOC_UPPER_BOUND_SEMANTICS:
        actual = _valid_score_tuple(row.get("objective_score"))
        baseline = _valid_score_tuple(reference.get("objective_score"))
        return {
            "reference": label,
            "baseline_algorithm_profile": reference.get("algorithm_profile"),
            "baseline_value": list(baseline or ()),
            "actual_value": list(actual or ()),
            "primary_delta": None,
            "status": "not_comparable",
            "reason": "reference_is_posthoc_upper_bound",
        }
    if reference.get("status") != "passed":
        return {
            "reference": label,
            "baseline_algorithm_profile": reference.get("algorithm_profile"),
            "baseline_value": list(_valid_score_tuple(reference.get("objective_score")) or ()),
            "actual_value": list(_valid_score_tuple(row.get("objective_score")) or ()),
            "primary_delta": None,
            "status": "not_comparable",
            "reason": "reference_status_not_passed",
        }
    actual = _valid_score_tuple(row.get("objective_score"))
    baseline = _valid_score_tuple(reference.get("objective_score"))
    if actual is None:
        return {
            "reference": label,
            "baseline_algorithm_profile": reference.get("algorithm_profile"),
            "baseline_value": list(baseline or ()),
            "actual_value": [],
            "primary_delta": None,
            "status": "not_comparable",
            "reason": "invalid_actual_objective_score",
        }
    if baseline is None:
        return {
            "reference": label,
            "baseline_algorithm_profile": reference.get("algorithm_profile"),
            "baseline_value": [],
            "actual_value": list(actual),
            "primary_delta": None,
            "status": "not_comparable",
            "reason": "invalid_reference_objective_score",
        }
    if len(actual) != len(baseline):
        return {
            "reference": label,
            "baseline_algorithm_profile": reference.get("algorithm_profile"),
            "baseline_value": list(baseline),
            "actual_value": list(actual),
            "primary_delta": None,
            "status": "not_comparable",
            "reason": "objective_score_shape_mismatch",
        }
    budget_mismatch = _time_budget_mismatch(row, reference)
    if budget_mismatch is not None:
        reason, actual_budget, baseline_budget = budget_mismatch
        return {
            "reference": label,
            "baseline_algorithm_profile": reference.get("algorithm_profile"),
            "baseline_value": list(baseline),
            "actual_value": list(actual),
            "primary_delta": None,
            "status": "not_comparable",
            "reason": reason,
            "actual_time_budget_seconds": actual_budget,
            "baseline_time_budget_seconds": baseline_budget,
        }
    status = "same"
    if actual < baseline:
        status = "improved"
    elif actual > baseline:
        status = "degraded"
    return {
        "reference": label,
        "baseline_algorithm_profile": reference.get("algorithm_profile"),
        "baseline_value": list(baseline),
        "actual_value": list(actual),
        "primary_delta": _first_changed_delta(actual, baseline),
        "status": status,
    }


def _score_tuple(value: Any) -> Tuple[float, ...]:
    score = _valid_score_tuple(value)
    return score if score is not None else (float("inf"),)


def _valid_score_tuple(value: Any) -> Optional[Tuple[float, ...]]:
    if not isinstance(value, (list, tuple)):
        return None
    if not value:
        return None
    score: List[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return None
        number = float(item)
        if not math.isfinite(number):
            return None
        score.append(number)
    return tuple(score)


def _valid_time_budget_seconds(row: Dict[str, Any]) -> Optional[int]:
    value = row.get("time_budget_seconds")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number) or number < 0 or int(number) != number:
        return None
    return int(number)


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


def _eligible_portfolio_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    expected_len = _expected_score_length(rows)
    if expected_len is None:
        return []
    return [
        row
        for row in rows
        if row.get("status") == "passed"
        and (score := _valid_score_tuple(row.get("objective_score"))) is not None
        and len(score) == expected_len
    ]


def _expected_score_length(rows: Sequence[Dict[str, Any]]) -> Optional[int]:
    lengths = [
        len(score)
        for row in rows
        if row.get("status") == "passed" and (score := _valid_score_tuple(row.get("objective_score"))) is not None
    ]
    return max(lengths) if lengths else None


def _invalid_score_sources(rows: Sequence[Dict[str, Any]]) -> List[str]:
    return [
        str(row.get("algorithm_profile") or "")
        for row in rows
        if _valid_score_tuple(row.get("objective_score")) is None
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
        if (score := _valid_score_tuple(row.get("objective_score"))) is not None
        and len(score) != expected_len
    ]


def _invalid_time_budget_sources(rows: Sequence[Dict[str, Any]]) -> List[str]:
    return [
        str(row.get("algorithm_profile") or "")
        for row in rows
        if _valid_time_budget_seconds(row) is None
    ]


def _first_changed_delta(actual: Tuple[float, ...], baseline: Tuple[float, ...]) -> float:
    for actual_item, baseline_item in zip(actual, baseline):
        delta = float(actual_item) - float(baseline_item)
        if abs(delta) > 1e-9:
            return delta
    return 0.0


def _candidate_output_fingerprint(candidate: Dict[str, Any]) -> str:
    return build_candidate_fingerprint(
        candidate,
        objective_name=OBJECTIVE_NAME,
        parent_fingerprint=None,
        seen_output_fingerprints=set(),
    ).output_fingerprint


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
