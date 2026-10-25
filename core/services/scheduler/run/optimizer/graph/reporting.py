from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from core.algorithms import SortStrategy
from core.services.scheduler.run.optimizer.attempt_records import (
    append_rejected_reason_attempt,
    attempt_decision_evidence,
)
from core.services.scheduler.run.optimizer.graph_ready_profiles import GraphReadyWeightProfile

if TYPE_CHECKING:
    from core.services.scheduler.run.optimizer.search_report import OptimizationSearchReportState


def append_graph_attempt(
    *, attempts: List[Dict[str, Any]], candidate: Dict[str, Any], profile: GraphReadyWeightProfile,
    reference: Optional[Dict[str, Any]] = None, accepted: Optional[bool] = None,
    search_report_state: Optional[OptimizationSearchReportState] = None,
    clock: Optional[Callable[[], float]] = None, t_begin: Optional[float] = None,
    verified: bool = True, comparison_kind: str = "incumbent",
) -> None:
    metrics = candidate["metrics"]
    attempts.append(
        {
            "tag": _tag(candidate, profile),
            "strategy": _strategy_value(candidate.get("strategy")),
            "dispatch_mode": "sgs",
            "dispatch_rule": candidate["dispatch_rule"],
            "used_params": dict(candidate["params"]),
            "score": list(candidate["score"]),
            "failed_ops": int(candidate["summary"].failed_ops),
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
            "strategy": _strategy_value(candidate.get("strategy")),
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
    profile_slug: str = "",
) -> None:
    append_rejected_reason_attempt(
        attempts=attempts,
        tag=f"graph_ready:{profile_slug or 'profile'}|sgs:{dispatch_rule}",
        strategy=str(getattr(strategy, "value", strategy) or ""),
        dispatch_mode="sgs",
        dispatch_rule=str(dispatch_rule or ""),
        reason=str(reason or "graph_ready_candidate_rejected"),
        message=str(message or ""),
    )


def public_params(params: Any) -> Dict[str, Any]:
    if not isinstance(params, dict):
        return {}
    out = dict(params)
    profile = out.get("graph_ready_profile")
    if isinstance(profile, dict):
        out["graph_ready_profile"] = _public_profile(profile)
    return out


def _public_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema_version": int(profile.get("schema_version") or 1),
        "candidate_origin": str(profile.get("candidate_origin") or ""),
        "weight_profile_slug": str(profile.get("weight_profile_slug") or ""),
        "candidate_policy": str(profile.get("candidate_policy") or ""),
        "max_weight_profiles": int(profile.get("max_weight_profiles") or 0),
    }


def _tag(candidate: Dict[str, Any], profile: GraphReadyWeightProfile) -> str:
    return f"graph_ready:{profile.slug}|sgs:{candidate.get('dispatch_rule')}"


def _strategy_value(strategy: Any) -> str:
    return str(getattr(strategy, "value", strategy) or "")
