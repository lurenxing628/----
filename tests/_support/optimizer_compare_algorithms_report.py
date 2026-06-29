from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

COMPARE_SCHEMA_VERSION = 1


def summarize_comparison_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_profile: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        by_profile.setdefault(str(row.get("algorithm_profile") or ""), []).append(dict(row))
    summary: List[Dict[str, Any]] = []
    for profile in sorted(by_profile):
        profile_rows = by_profile[profile]
        passed_rows = [row for row in profile_rows if row.get("status") == "passed"]
        wins = len([row for row in passed_rows if _comparison_status(row, "comparison_to_current_baseline") == "improved"])
        ties = len([row for row in passed_rows if _comparison_status(row, "comparison_to_current_baseline") == "same"])
        losses = len([row for row in passed_rows if _comparison_status(row, "comparison_to_current_baseline") == "degraded"])
        deltas = [_primary_delta(row, "comparison_to_current_baseline") for row in passed_rows]
        runtimes = [float(row.get("runtime_ms") or 0.0) for row in profile_rows]
        summary.append(
            {
                "algorithm_profile": profile,
                "case_count": len(profile_rows),
                "wins_vs_current_baseline": wins,
                "ties_vs_current_baseline": ties,
                "losses_vs_current_baseline": losses,
                "mean_primary_delta_vs_current_baseline": round(sum(deltas) / len(deltas), 6) if deltas else 0.0,
                "worst_primary_delta_vs_current_baseline": max(deltas) if deltas else 0.0,
                "runtime_ms": round(sum(runtimes) / len(runtimes), 3) if runtimes else 0.0,
            }
        )
    return summary


def compare_to_algorithm_baseline(
    actual: Dict[str, Any],
    baseline: Dict[str, Any],
    *,
    require_clean_proof: bool = True,
) -> Dict[str, Any]:
    actual_rows = _rows_by_key(actual.get("rows") or [])
    baseline_rows = _rows_by_key(baseline.get("rows") or [])
    failures: List[Dict[str, Any]] = []
    proof_binding_status = _proof_binding_status(actual, baseline)
    if require_clean_proof:
        failures.extend(_worktree_proof_failures(actual, baseline))
    if not actual_rows:
        failures.append({"reason": "empty_actual_rows"})
    if not baseline_rows:
        failures.append({"reason": "empty_baseline_rows"})
    for key in sorted(set(baseline_rows) - set(actual_rows)):
        failures.append({"reason": "missing_actual_row", "key": list(key)})
    allowed_new = []
    for key in sorted(set(actual_rows) - set(baseline_rows)):
        failures.append({"reason": "missing_baseline_row", "key": list(key)})
    for key in sorted(set(actual_rows).intersection(baseline_rows)):
        actual_score = _score_tuple(actual_rows[key].get("objective_score"))
        baseline_score = _score_tuple(baseline_rows[key].get("objective_score"))
        if actual_score is None:
            failures.append({"reason": "invalid_actual_objective_score", "key": list(key)})
            continue
        if baseline_score is None:
            failures.append({"reason": "invalid_baseline_objective_score", "key": list(key)})
            continue
        if len(actual_score) != len(baseline_score):
            failures.append(
                {
                    "reason": "objective_score_shape_mismatch",
                    "key": list(key),
                    "baseline": list(baseline_score),
                    "actual": list(actual_score),
                }
            )
            continue
        if actual_score > baseline_score:
            failures.append(
                {
                    "reason": "objective_score_regressed",
                    "key": list(key),
                    "baseline": list(baseline_score),
                    "actual": list(actual_score),
                }
            )
    status = "passed" if not failures and actual.get("status") == "passed" else "failed"
    return {
        "schema_version": COMPARE_SCHEMA_VERSION,
        "status": status,
        "failure_count": len(failures),
        "failures": failures,
        "allowed_new_algorithm_rows": allowed_new,
        "proof_binding_status": proof_binding_status,
        "require_clean_proof": bool(require_clean_proof),
    }


def _comparison_status(row: Dict[str, Any], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, dict):
        return ""
    return str(value.get("status") or "")


def _primary_delta(row: Dict[str, Any], field: str) -> float:
    value = row.get(field)
    if not isinstance(value, dict):
        return 0.0
    return float(value.get("primary_delta") or 0.0)


def _score_tuple(value: Any) -> Optional[Tuple[float, ...]]:
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


def _proof_binding_status(actual: Dict[str, Any], baseline: Dict[str, Any]) -> str:
    actual_state = _clean_worktree_state(actual)
    baseline_state = _clean_worktree_state(baseline)
    if actual_state is True and baseline_state is True:
        return "clean_worktree"
    if actual_state is False or baseline_state is False:
        return "unbound_dirty_worktree"
    return "unknown_worktree_state"


def _worktree_proof_failures(actual: Dict[str, Any], baseline: Dict[str, Any]) -> List[Dict[str, str]]:
    failures: List[Dict[str, str]] = []
    actual_state = _clean_worktree_state(actual)
    baseline_state = _clean_worktree_state(baseline)
    if actual_state is False:
        failures.append({"reason": "dirty_actual_worktree"})
    elif actual_state is None:
        failures.append({"reason": "unknown_actual_worktree_state"})
    if baseline_state is False:
        failures.append({"reason": "dirty_baseline_worktree"})
    elif baseline_state is None:
        failures.append({"reason": "unknown_baseline_worktree_state"})
    return failures


def _clean_worktree_state(payload: Dict[str, Any]) -> Optional[bool]:
    value = payload.get("dirty_worktree")
    if value is False:
        return True
    if value is True:
        return False
    return None


def _rows_by_key(rows: Sequence[Dict[str, Any]]) -> Dict[Tuple[str, str, str, str, int], Dict[str, Any]]:
    out: Dict[Tuple[str, str, str, str, int], Dict[str, Any]] = {}
    for row in rows:
        key = (
            str(row.get("case_group") or ""),
            str(row.get("case_slug") or ""),
            str(row.get("algorithm_profile") or ""),
            str(row.get("algorithm_version") or ""),
            int(row.get("seed") or 0),
        )
        out[key] = dict(row)
    return out

__all__ = ["compare_to_algorithm_baseline", "summarize_comparison_rows"]
