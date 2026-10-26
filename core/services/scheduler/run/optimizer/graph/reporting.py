from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from core.algorithm_contracts.sort_strategies import SortStrategy
from core.services.scheduler.run.optimizer.attempt_records import (
    append_rejected_reason_attempt,
    attempt_decision_evidence,
)
from core.services.scheduler.run.optimizer.graph_ready_profiles import GraphReadyWeightProfile

if TYPE_CHECKING:
    from core.services.scheduler.run.optimizer.search_report import OptimizationSearchReportState


def append_graph_attempt(
    *, attempts: List[Dict[str, Any]], candidate: Dict[str, Any], profile: GraphReadyWeightProfile,
    reference: Optional[Dict[str, Any]], accepted: bool, search_report_state: OptimizationSearchReportState,
    clock: Callable[[], float], t_begin: float, verified: bool = True, comparison_kind: str = "incumbent",
) -> None:
    metrics = candidate["metrics"]
    attempts.append(
        {
            "tag": _tag(candidate, profile),
            "strategy": candidate["strategy"].value,
            "dispatch_mode": "sgs",
            "dispatch_rule": candidate["dispatch_rule"],
            "used_params": dict(candidate["params"]),
            "score": list(candidate["score"]),
            "failed_ops": candidate["summary"].failed_ops,
            "metrics": metrics.to_dict(),
            "candidate_status": "evaluated",
            "candidate_origin": profile.candidate_origin,
            "weight_profile_slug": profile.slug,
            **attempt_decision_evidence(candidate=candidate, reference=reference, accepted=accepted,
                                        search_report_state=search_report_state, clock=clock, t_begin=t_begin,
                                        verified=verified, comparison_kind=comparison_kind),
        }
    )


def append_graph_trace(
    *,
    improvement_trace: List[Dict[str, Any]],
    candidate: Dict[str, Any],
    profile: GraphReadyWeightProfile,
    clock: Callable[[], float],
    t_begin: float,
) -> None:
    metrics = candidate["metrics"]
    improvement_trace.append(
        {
            "elapsed_ms": int((clock() - t_begin) * 1000),
            "tag": _tag(candidate, profile),
            "strategy": candidate["strategy"].value,
            "dispatch_mode": "sgs",
            "dispatch_rule": candidate["dispatch_rule"],
            "score": list(candidate["score"]),
            "metrics": metrics.to_dict(),
        }
    )


def record_rejected_attempt(
    *,
    attempts: List[Dict[str, Any]],
    strategy: SortStrategy,
    dispatch_rule: str,
    reason: str,
    message: str,
    profile_slug: str,
) -> None:
    append_rejected_reason_attempt(
        attempts=attempts,
        tag=f"graph_ready:{profile_slug}|sgs:{dispatch_rule}",
        strategy=strategy.value,
        dispatch_mode="sgs",
        dispatch_rule=dispatch_rule,
        reason=reason,
        message=message,
    )


def public_params(params: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(params)
    # The weighted strategy rebuilds its parameters, so only other strategies carry the profile.
    profile = out.get("graph_ready_profile")
    if profile is not None:
        out["graph_ready_profile"] = _public_profile(profile)
    return out


def _public_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    return {key: profile[key] for key in (
        "schema_version", "candidate_origin", "weight_profile_slug", "candidate_policy", "max_weight_profiles")}


def _tag(candidate: Dict[str, Any], profile: GraphReadyWeightProfile) -> str:
    return f"graph_ready:{profile.slug}|sgs:{candidate['dispatch_rule']}"
