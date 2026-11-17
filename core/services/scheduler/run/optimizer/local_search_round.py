from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from .candidate_fingerprint import score_strictly_better
from .local_search_candidate_eval import evaluate_local_search_candidate
from .local_search_state import LocalSearchState, StrategyState, candidate_can_update_best
from .neighborhood_registry import build_neighborhood_move
from .shared_budget import SharedSearchSkip
from .vns import VnsState

if TYPE_CHECKING:
    from .candidate_fingerprint import CandidateFingerprint
    from .search_report import OptimizationSearchReportState
    from .shared_decode import SharedDecodeSession


@dataclass(frozen=True)
class LocalSearchRoundResult:
    """``decode_attempted`` reflects actual common-session decoder calls for this round."""

    no_improve: int
    best_improved: bool
    decode_attempted: bool = False
    stop_reason: Optional[str] = None
    rejected_mode: Optional[str] = None


def stamp_decode_runtime(candidate: Dict[str, Any]) -> None:
    """Every decoded candidate carries its measured decode time so later phases can budget on it.

    A first decode also records that time as its own ``runtime_ms``; a reused decision keeps the source's.
    """
    receipt = candidate["decode_receipt"]
    source_cost = receipt.get("source_initial_decode_runtime_ms")
    if source_cost is None:
        source_cost = receipt.get("source_runtime_ms")
    if source_cost is None:
        source_cost = receipt["original_decode_ms"]
    candidate["initial_decode_runtime_ms"] = max(float(source_cost), 0.0)
    if receipt["execution_kind"] != "decision_reused":
        candidate["runtime_ms"] = int(candidate["initial_decode_runtime_ms"])


def _apply_accepted_candidate(
    *,
    candidate: Dict[str, Any],
    local_state: LocalSearchState,
    candidate_fingerprint: CandidateFingerprint,
    accepted: bool,
    no_improve: int,
    incumbent_origin: str,
    incumbent_fingerprint_changed: bool,
) -> Tuple[bool, bool, int]:
    if accepted and candidate_can_update_best(
        candidate=candidate,
        best=local_state.best,
        fingerprint=candidate_fingerprint,
        candidate_origin="local_search",
        incumbent_origin=incumbent_origin,
        incumbent_fingerprint_changed=incumbent_fingerprint_changed,
    ):
        local_state.improve_best(candidate)
        return True, True, 0
    if accepted:
        local_state.accept_current(candidate)
        return True, False, no_improve + 1
    return False, False, no_improve + 1


def run_local_search_candidate_round(
    *,
    local_state: LocalSearchState,
    vns_state: VnsState,
    strategy_state: StrategyState,
    rnd: Any,
    search_report_state: OptimizationSearchReportState,
    no_improve: int,
    objective_name: str,
    valid_dispatch_rules: List[str],
    decode_session: SharedDecodeSession,
) -> LocalSearchRoundResult:
    move = build_neighborhood_move(
        vns_state.current_neighborhood(),
        order=local_state.current_order,
        resource_pool=decode_session.native_preparation.resource_pool.with_pair_rank(
            local_state.current_resource_pair_rank),
        rnd=rnd,
        current_dispatch_rule=strategy_state.dispatch_rule,
        valid_dispatch_rules=valid_dispatch_rules,
        result_facts=local_state.current_facts,
    )
    if move.noop:
        return LocalSearchRoundResult(no_improve + 1, False)
    cand_order = list(move.batch_order or local_state.current_order)
    # The move's overrides apply on top of current's.
    candidate_pair_rank = {**local_state.current_resource_pair_rank, **move.resource_pair_rank}
    candidate_mode = str(move.dispatch_mode or strategy_state.dispatch_mode)
    candidate_rule = str(move.dispatch_rule or strategy_state.dispatch_rule)
    calls_before = decode_session.actual_decoder_calls
    try:
        candidate = evaluate_local_search_candidate(
            inherited=strategy_state,
            order=cand_order,
            dispatch_mode=candidate_mode,
            dispatch_rule=candidate_rule,
            resource_pair_rank=candidate_pair_rank,
            objective_name=objective_name,
            decode_session=decode_session,
        )
    except SharedSearchSkip as exc:
        stop_reason = exc.reason if exc.reason in ("estimated_decode_cost", "time_budget") else None
        rejected_mode = candidate_mode if stop_reason == "estimated_decode_cost" else None
        return LocalSearchRoundResult(
            no_improve + 1, False, stop_reason=stop_reason, rejected_mode=rejected_mode,
        )
    decode_attempted = decode_session.actual_decoder_calls > calls_before
    stamp_decode_runtime(candidate)
    candidate_fingerprint = search_report_state.mark_candidate_evaluated(candidate, origin="local_search")
    accepted = score_strictly_better(candidate["score"], local_state.current["score"])
    accepted_current, best_improved, no_improve = _apply_accepted_candidate(
        candidate=candidate,
        local_state=local_state,
        candidate_fingerprint=candidate_fingerprint,
        accepted=accepted,
        no_improve=no_improve,
        incumbent_origin=str(search_report_state.best_origin or "baseline"),
        incumbent_fingerprint_changed=search_report_state.best_fingerprint_changed(),
    )
    _record_acceptance_result(
        best_improved=best_improved,
        accepted_current=accepted_current,
        candidate_fingerprint=candidate_fingerprint,
        search_report_state=search_report_state,
        candidate=candidate,
    )
    return LocalSearchRoundResult(
        no_improve, best_improved,
        decode_attempted=decode_attempted,
    )


def _record_acceptance_result(
    *,
    best_improved: bool,
    accepted_current: bool,
    candidate_fingerprint: Any,
    search_report_state: OptimizationSearchReportState,
    candidate: Dict[str, Any],
) -> None:
    if best_improved:
        search_report_state.mark_candidate_accepted(
            candidate,
            origin="local_search",
            fingerprint=candidate_fingerprint,
        )
    elif accepted_current:
        search_report_state.mark_current_candidate_accepted(
            candidate,
            origin="local_search",
            fingerprint=candidate_fingerprint,
        )


__all__ = ["LocalSearchRoundResult", "run_local_search_candidate_round", "stamp_decode_runtime"]
