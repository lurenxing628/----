from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from .optimizer_candidate_fingerprint import CandidateFingerprint, build_candidate_fingerprint

CANDIDATE_ORIGIN_ORDER = (
    "baseline",
    "ortools_warmstart",
    "multi_start",
    "grasp",
    "ig",
    "vns",
    "sa",
    "local_search",
    "graph_ready_base",
    "graph_ready_weight_grid",
    "graph_ready_local_search",
    "alns",
)


def candidate_origin_rank(origin: str) -> int:
    text = str(origin or "").strip()
    try:
        return CANDIDATE_ORIGIN_ORDER.index(text)
    except ValueError:
        return len(CANDIDATE_ORIGIN_ORDER)


def candidate_score_tuple(candidate: Optional[Dict[str, Any]]) -> Tuple[float, ...]:
    if not isinstance(candidate, dict):
        return ()
    score = candidate.get("score")
    if not isinstance(score, (list, tuple)):
        return ()
    out = []
    for item in score:
        out.append(float(item))
    return tuple(out)


def candidate_runtime_ms(candidate: Optional[Dict[str, Any]]) -> int:
    if not isinstance(candidate, dict):
        return 1_000_000_000
    try:
        value = int(candidate.get("runtime_ms", 1_000_000_000) or 0)
    except (TypeError, ValueError, OverflowError):
        return 1_000_000_000
    return max(value, 0)


def candidate_fingerprint_for_comparison(
    candidate: Dict[str, Any],
    *,
    objective_name: str,
    parent_fingerprint: Optional[str],
    seen_output_fingerprints: Any,
) -> CandidateFingerprint:
    return build_candidate_fingerprint(
        candidate,
        objective_name=objective_name,
        parent_fingerprint=parent_fingerprint,
        seen_output_fingerprints=seen_output_fingerprints,
    )


def candidate_is_preferred(
    *,
    candidate: Dict[str, Any],
    incumbent: Optional[Dict[str, Any]],
    candidate_origin: str,
    incumbent_origin: str,
    candidate_fingerprint: Optional[CandidateFingerprint],
    incumbent_fingerprint_changed: bool,
) -> bool:
    if incumbent is None:
        return True

    candidate_score = candidate_score_tuple(candidate)
    incumbent_score = candidate_score_tuple(incumbent)
    if candidate_score and incumbent_score and candidate_score != incumbent_score:
        return candidate_score < incumbent_score
    if candidate_score and not incumbent_score:
        return True
    if incumbent_score and not candidate_score:
        return False

    candidate_changed = bool(candidate_fingerprint and candidate_fingerprint.fingerprint_changed)
    if candidate_changed != bool(incumbent_fingerprint_changed):
        return candidate_changed

    candidate_runtime = candidate_runtime_ms(candidate)
    incumbent_runtime = candidate_runtime_ms(incumbent)
    if candidate_runtime != incumbent_runtime:
        return candidate_runtime < incumbent_runtime

    return candidate_origin_rank(candidate_origin) < candidate_origin_rank(incumbent_origin)


__all__ = [
    "CANDIDATE_ORIGIN_ORDER",
    "candidate_fingerprint_for_comparison",
    "candidate_is_preferred",
    "candidate_origin_rank",
    "candidate_runtime_ms",
    "candidate_score_tuple",
]
