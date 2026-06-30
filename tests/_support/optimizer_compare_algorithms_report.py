from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

COMPARE_SCHEMA_VERSION = 1
_KEY_TEXT_FIELDS = ("case_group", "case_slug", "algorithm_profile", "algorithm_version")
_Key = Tuple[str, str, str, str, int]


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
        deltas = [
            delta
            for row in passed_rows
            if _comparison_status(row, "comparison_to_current_baseline") in {"improved", "same", "degraded"}
            for delta in [_primary_delta(row, "comparison_to_current_baseline")]
            if delta is not None
        ]
        runtimes = [float(row.get("runtime_ms") or 0.0) for row in profile_rows]
        summary.append(
            {
                "algorithm_profile": profile,
                "case_count": len(profile_rows),
                "wins_vs_current_baseline": wins,
                "ties_vs_current_baseline": ties,
                "losses_vs_current_baseline": losses,
                "mean_primary_delta_vs_current_baseline": round(sum(deltas) / len(deltas), 6)
                if deltas
                else None,
                "worst_primary_delta_vs_current_baseline": max(deltas)
                if deltas
                else None,
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
    actual_raw_rows = actual.get("rows") or []
    baseline_raw_rows = baseline.get("rows") or []
    actual_rows, actual_key_failures = _rows_by_key(actual_raw_rows, label="actual")
    baseline_rows, baseline_key_failures = _rows_by_key(baseline_raw_rows, label="baseline")
    failures: List[Dict[str, Any]] = []
    failures.extend(actual_key_failures)
    failures.extend(baseline_key_failures)
    proof_binding_status = _proof_binding_status(actual, baseline)
    if require_clean_proof:
        failures.extend(_worktree_proof_failures(actual, baseline))
    if not actual_raw_rows:
        failures.append({"reason": "empty_actual_rows"})
    if not baseline_raw_rows:
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
        budget_failure = _time_budget_failure(key=key, actual=actual_rows[key], baseline=baseline_rows[key])
        if budget_failure is not None:
            failures.append(budget_failure)
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


def _primary_delta(row: Dict[str, Any], field: str) -> Optional[float]:
    value = row.get(field)
    if not isinstance(value, dict):
        return None
    delta = value.get("primary_delta")
    if isinstance(delta, bool) or not isinstance(delta, (int, float)):
        return None
    number = float(delta)
    return number if math.isfinite(number) else None


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


def _valid_time_budget_seconds(row: Dict[str, Any]) -> Optional[int]:
    value = row.get("time_budget_seconds")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number) or number < 0 or int(number) != number:
        return None
    return int(number)


def _time_budget_failure(
    *,
    key: _Key,
    actual: Dict[str, Any],
    baseline: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    actual_budget = _valid_time_budget_seconds(actual)
    baseline_budget = _valid_time_budget_seconds(baseline)
    if actual_budget is None:
        return {"reason": "missing_actual_time_budget_seconds", "key": list(key)}
    if baseline_budget is None:
        return {"reason": "missing_baseline_time_budget_seconds", "key": list(key)}
    if actual_budget != baseline_budget:
        return {
            "reason": "time_budget_mismatch",
            "key": list(key),
            "baseline_time_budget_seconds": baseline_budget,
            "actual_time_budget_seconds": actual_budget,
        }
    return None


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


def _rows_by_key(rows: Sequence[Dict[str, Any]], *, label: str) -> Tuple[Dict[_Key, Dict[str, Any]], List[Dict[str, Any]]]:
    out: Dict[_Key, Dict[str, Any]] = {}
    first_seen: Dict[_Key, int] = {}
    failures: List[Dict[str, Any]] = []
    for index, row in enumerate(rows):
        key, failure = _ratchet_key(row, label=label, row_index=index)
        if failure is not None:
            failures.append(failure)
            continue
        assert key is not None
        if key in out:
            failures.append(
                {
                    "reason": f"duplicate_{label}_ratchet_key",
                    "key": list(key),
                    "first_row_index": first_seen[key],
                    "row_index": index,
                }
            )
            continue
        out[key] = dict(row)
        first_seen[key] = index
    return out, failures


def _ratchet_key(row: Dict[str, Any], *, label: str, row_index: int) -> Tuple[Optional[_Key], Optional[Dict[str, Any]]]:
    text_values: List[str] = []
    for field in _KEY_TEXT_FIELDS:
        value = row.get(field)
        text = str(value).strip() if value is not None else ""
        if not text:
            return None, {"reason": f"missing_{label}_{field}", "row_index": row_index}
        text_values.append(text)
    seed = _valid_seed(row.get("seed"))
    if seed is None:
        reason = f"missing_{label}_seed" if "seed" not in row or row.get("seed") is None else f"invalid_{label}_seed"
        return None, {"reason": reason, "row_index": row_index}
    return (text_values[0], text_values[1], text_values[2], text_values[3], seed), None


def _valid_seed(value: Any) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number) or number < 0 or int(number) != number:
        return None
    return int(number)

__all__ = ["compare_to_algorithm_baseline", "summarize_comparison_rows"]
