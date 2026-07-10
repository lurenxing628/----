from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from tests._support.benchmark_parallel import DEFAULT_BENCHMARK_WORKERS
from tests._support.optimizer_compare_algorithms import (
    POSTHOC_UPPER_BOUND_SEMANTICS,
    SAME_BUDGET_SEMANTICS,
    build_algorithm_comparison,
)

GRAPH_READY_V2_LONG_RUN_SCHEMA_VERSION = 1
GRAPH_READY_V2_NO_REPAIR_PROFILE = "graph_ready_v2_no_repair"
PORTFOLIO_ALL_PROFILE = "portfolio_all"
PORTFOLIO_ALL_WIN_LOSS_STATUS = "not_comparable"
DEFAULT_GRAPH_READY_V2_LONG_RUN_PROFILES = (
    "greedy",
    "local_search",
    "grasp_ig",
    "graph_ready_v1",
    GRAPH_READY_V2_NO_REPAIR_PROFILE,
    PORTFOLIO_ALL_PROFILE,
)


def build_graph_ready_v2_long_run(
    *,
    seeds: int = 10,
    profiles: Sequence[str] = DEFAULT_GRAPH_READY_V2_LONG_RUN_PROFILES,
    workers: int = DEFAULT_BENCHMARK_WORKERS,
) -> Dict[str, Any]:
    seed_count = int(seeds)
    if seed_count < 10:
        raise ValueError("GraphReady v2 long-run requires at least 10 seeds.")
    comparison = build_algorithm_comparison(profiles=profiles, seeds=seed_count, workers=workers)
    summary = _v2_summary(comparison)
    return {
        "schema_version": GRAPH_READY_V2_LONG_RUN_SCHEMA_VERSION,
        "status": comparison.get("status") or "failed",
        "generated_at": comparison.get("generated_at"),
        "git_commit": comparison.get("git_commit"),
        "dirty_worktree": bool(comparison.get("dirty_worktree")),
        "proof_binding_status": comparison.get("proof_binding_status"),
        "command": "build_graph_ready_v2_long_run",
        "command_args": {
            "profiles": list(comparison.get("algorithm_profiles") or list(profiles)),
            "seeds": seed_count,
            "workers": int((comparison.get("command_args") or {}).get("workers") or workers),
        },
        "case_group": comparison.get("case_group"),
        "case_slug": comparison.get("case_slug"),
        "seed_count": seed_count,
        "algorithm_profiles": list(comparison.get("algorithm_profiles") or list(profiles)),
        "ratchet_key_fields": list(comparison.get("ratchet_key_fields") or []),
        "comparison": comparison,
        "v2_summary": summary,
    }


def _v2_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    rows = [dict(row) for row in list(payload.get("rows") or [])]
    portfolio = _profile_rows(rows, PORTFOLIO_ALL_PROFILE)
    summary = {
        "algorithm_profile": GRAPH_READY_V2_NO_REPAIR_PROFILE,
        "seed_count": int(payload.get("seed_count") or 0),
        "mean_duplicate_candidate_rate": _mean_duplicate_candidate_rate(rows),
        "mean_candidate_rejection_rate": _mean_candidate_rejection_rate(rows),
        "portfolio_all_comparison_semantics": _portfolio_semantics(portfolio),
        "portfolio_all_win_loss_status": PORTFOLIO_ALL_WIN_LOSS_STATUS,
        "proof_binding_status": payload.get("proof_binding_status"),
    }
    for reference in ("greedy", "local_search", "grasp_ig", "graph_ready_v1"):
        counts = _pairwise_counts(rows, reference=reference)
        suffix = _reference_suffix(reference)
        summary["wins_vs_" + suffix] = counts["wins"]
        summary["ties_vs_" + suffix] = counts["ties"]
        summary["losses_vs_" + suffix] = counts["losses"]
        summary["not_comparable_vs_" + suffix] = counts["not_comparable"]
    return summary


def _reference_suffix(reference: str) -> str:
    return "graph_ready_v1" if reference == "graph_ready_v1" else reference


def _pairwise_counts(rows: Sequence[Dict[str, Any]], *, reference: str) -> Dict[str, int]:
    counts = {"wins": 0, "ties": 0, "losses": 0, "not_comparable": 0}
    by_seed = _rows_by_seed(rows)
    for seed_rows in by_seed.values():
        subject = seed_rows.get(GRAPH_READY_V2_NO_REPAIR_PROFILE)
        baseline = seed_rows.get(reference)
        status = _pairwise_status(subject, baseline)
        if status == "improved":
            counts["wins"] += 1
        elif status == "same":
            counts["ties"] += 1
        elif status == "degraded":
            counts["losses"] += 1
        else:
            counts["not_comparable"] += 1
    return counts


def _rows_by_seed(rows: Sequence[Dict[str, Any]]) -> Dict[int, Dict[str, Dict[str, Any]]]:
    out: Dict[int, Dict[str, Dict[str, Any]]] = {}
    for row in rows:
        seed = _int_seed(row.get("seed"))
        if seed is None:
            continue
        out.setdefault(seed, {})[str(row.get("algorithm_profile") or "")] = dict(row)
    return out


def _pairwise_status(subject: Any, reference: Any) -> str:
    if not isinstance(subject, dict) or not isinstance(reference, dict):
        return "not_comparable"
    if subject.get("status") != "passed" or reference.get("status") != "passed":
        return "not_comparable"
    if subject.get("comparison_semantics") != SAME_BUDGET_SEMANTICS:
        return "not_comparable"
    if reference.get("comparison_semantics") != SAME_BUDGET_SEMANTICS:
        return "not_comparable"
    subject_score = _score_tuple(subject.get("objective_score"))
    reference_score = _score_tuple(reference.get("objective_score"))
    if subject_score is None or reference_score is None or len(subject_score) != len(reference_score):
        return "not_comparable"
    if _time_budget(subject) != _time_budget(reference):
        return "not_comparable"
    if subject_score < reference_score:
        return "improved"
    if subject_score > reference_score:
        return "degraded"
    return "same"


def _mean_duplicate_candidate_rate(rows: Sequence[Dict[str, Any]]) -> float:
    return _mean_rate(rows, numerator_fn=lambda row: int((row.get("candidate_rejections") or {}).get("same_fingerprint") or 0))


def _mean_candidate_rejection_rate(rows: Sequence[Dict[str, Any]]) -> float:
    return _mean_rate(rows, numerator_fn=lambda row: sum(int(value or 0) for value in (row.get("candidate_rejections") or {}).values()))


def _mean_rate(rows: Sequence[Dict[str, Any]], *, numerator_fn: Callable[[Dict[str, Any]], int]) -> float:
    rates: List[float] = []
    for row in _profile_rows(rows, GRAPH_READY_V2_NO_REPAIR_PROFILE):
        evaluated = int(row.get("evaluated_candidates") or 0)
        if evaluated <= 0:
            continue
        rates.append(float(numerator_fn(row)) / float(evaluated))
    if not rates:
        return 0.0
    return float(round(sum(rates) / len(rates), 6))


def _profile_rows(rows: Sequence[Dict[str, Any]], profile: str) -> List[Dict[str, Any]]:
    return [dict(row) for row in rows if row.get("algorithm_profile") == profile]


def _portfolio_semantics(portfolio_rows: Sequence[Dict[str, Any]]) -> str:
    if not portfolio_rows:
        return "missing"
    values = {str(row.get("comparison_semantics") or "") for row in portfolio_rows}
    if values == {POSTHOC_UPPER_BOUND_SEMANTICS}:
        return POSTHOC_UPPER_BOUND_SEMANTICS
    return "mixed_or_invalid"


def _score_tuple(value: Any) -> Optional[Tuple[float, ...]]:
    if not isinstance(value, (list, tuple)) or not value:
        return None
    out: List[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return None
        number = float(item)
        if not math.isfinite(number):
            return None
        out.append(number)
    return tuple(out)


def _time_budget(row: Dict[str, Any]) -> int:
    value = row.get("time_budget_seconds")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return -1
    number = float(value)
    if not math.isfinite(number) or int(number) != number:
        return -1
    return int(number)


def _int_seed(value: Any) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number) or int(number) != number:
        return None
    return int(number)


__all__ = [
    "DEFAULT_GRAPH_READY_V2_LONG_RUN_PROFILES",
    "GRAPH_READY_V2_NO_REPAIR_PROFILE",
    "build_graph_ready_v2_long_run",
]
