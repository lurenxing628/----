from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from functools import partial
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from .acceptance import AcceptanceDecision, decide_acceptance
from .attempt_records import (
    append_rejected_reason_attempt,
    attempt_decision_evidence,
    evaluate_optional_local_candidate,
)
from .local_search_candidate_eval import evaluate_local_search_candidate
from .local_search_fingerprints import LocalSearchFingerprintTracker, local_candidate_fingerprint
from .local_search_state import LocalSearchState, candidate_can_update_best
from .neighborhood_moves import NeighborhoodMove
from .neighborhood_registry import choose_neighborhood_move
from .shared_budget import SharedSearchSkip
from .vns import VnsState

if TYPE_CHECKING:
    from .search_report import OptimizationSearchReportState
    from .shared_decode import SharedDecodeSession


@dataclass(frozen=True)
class LocalSearchRoundResult:
    """``decode_attempted`` reflects actual common-session decoder calls for this round."""

    no_improve: int
    accepted_current: bool
    best_improved: bool
    move: NeighborhoodMove
    decode_attempted: bool = False
    skip_reason: Optional[str] = None
    request_id: Optional[int] = None
    decode_receipt: Optional[Dict[str, Any]] = None


def stamp_decode_runtime(candidate: Optional[Dict[str, Any]], *, started_at: float, clock: Callable[[], float]) -> None:
    """Every decoded candidate carries its measured decode time so later phases can budget on it."""
    if candidate is not None:
        receipt = candidate.get("decode_receipt")
        if receipt is not None:
            source_cost = receipt.get("source_initial_decode_runtime_ms")
            if source_cost is None:
                source_cost = receipt.get("source_runtime_ms")
            if source_cost is None:
                source_cost = receipt["original_decode_ms"]
            candidate["initial_decode_runtime_ms"] = max(float(source_cost), 0.0)
            return
        candidate["initial_decode_runtime_ms"] = max((clock() - started_at) * 1000.0, 0.0)


def _record_improvement(
    *,
    candidate: Dict[str, Any],
    move: NeighborhoodMove,
    attempts: List[Dict[str, Any]],
    improvement_trace: List[Dict[str, Any]],
    clock: Callable[[], float],
    t_begin: float,
    reference: Optional[Dict[str, Any]] = None,
    search_report_state: Optional[OptimizationSearchReportState] = None,
) -> None:
    metrics = candidate["metrics"]
    score = candidate["score"]
    used_strat = candidate["strategy"]
    used_params = candidate["params"]
    dispatch_mode = str(candidate.get("dispatch_mode") or "")
    dispatch_rule = str(candidate.get("dispatch_rule") or "")
    move_tag = f"local:{move.neighborhood_name}"
    improvement_trace.append(
        {
            "elapsed_ms": int((clock() - t_begin) * 1000),
            "tag": move_tag,
            "strategy": used_strat.value,
            "dispatch_mode": dispatch_mode,
            "dispatch_rule": dispatch_rule,
            "score": list(score),
            "metrics": metrics.to_dict(),
        }
    )
    # Every best improvement is recorded; the final compaction keeps the best per dispatch mode,
    # so a cap here could drop the adopted plan's own attempt from the report.
    attempt = {
        "tag": move_tag,
        "source": "local_search",
        "strategy": used_strat.value,
        "dispatch_mode": dispatch_mode,
        "dispatch_rule": dispatch_rule,
        "used_params": dict(used_params or {}),
        "score": list(score),
        "failed_ops": int(candidate["summary"].failed_ops),
        "algo_stats": candidate["algo_stats"],
        "metrics": metrics.to_dict(),
    }
    attempt.update(attempt_decision_evidence(
        candidate=candidate, reference=reference, accepted=True,
        search_report_state=search_report_state, clock=clock, t_begin=t_begin,
    ))
    attempts.append(attempt)


def _record_noop_neighbor(
    *,
    attempts: List[Dict[str, Any]],
    search_report_state: Optional[OptimizationSearchReportState],
    strategy: Any,
    dispatch_mode: str,
    dispatch_rule: str,
    move: NeighborhoodMove,
) -> None:
    if search_report_state is None:
        return
    reason = str(move.candidate_rejected or "noop_neighbor")
    append_rejected_reason_attempt(
        attempts=attempts,
        tag=f"local:{move.neighborhood_name}",
        strategy=strategy.value,
        dispatch_mode=dispatch_mode,
        dispatch_rule=dispatch_rule,
        reason=reason,
        message=f"业务邻域 {move.neighborhood_name} 未产生有效候选：{reason}",
    )
    search_report_state.mark_candidate_rejected(reason=reason)


def mark_neighborhood_move(
    search_report_state: Optional[OptimizationSearchReportState],
    move: NeighborhoodMove,
) -> None:
    if search_report_state is not None:
        search_report_state.mark_neighborhood_move(move.to_report_dict())


def _apply_accepted_candidate(
    *,
    candidate: Dict[str, Any],
    local_state: LocalSearchState,
    candidate_fingerprint: Any,
    acceptance_decision: AcceptanceDecision,
    no_improve: int,
    move: NeighborhoodMove,
    attempts: List[Dict[str, Any]],
    improvement_trace: List[Dict[str, Any]],
    clock: Callable[[], float],
    t_begin: float,
    incumbent_origin: str,
    incumbent_fingerprint_changed: bool,
    search_report_state: Optional[OptimizationSearchReportState] = None,
) -> Tuple[bool, bool, int]:
    if acceptance_decision.accepted and candidate_can_update_best(
        candidate=candidate,
        best=local_state.best,
        fingerprint=candidate_fingerprint,
        candidate_origin="local_search",
        incumbent_origin=incumbent_origin,
        incumbent_fingerprint_changed=incumbent_fingerprint_changed,
    ):
        _record_improvement(
            candidate=candidate,
            move=move,
            attempts=attempts,
            improvement_trace=improvement_trace,
            clock=clock,
            t_begin=t_begin,
            reference=local_state.best,
            search_report_state=search_report_state,
        )
        local_state.improve_best(candidate)
        return True, True, 0
    if acceptance_decision.accepted:
        local_state.accept_current(candidate)
        return True, False, no_improve + 1
    return False, False, no_improve + 1


def run_local_search_candidate_round(
    *,
    local_state: LocalSearchState,
    vns_state: VnsState,
    cur_strat: Any,
    cur_params: Dict[str, Any],
    cur_dispatch_mode: str,
    cur_dispatch_rule: str,
    rnd: Any,
    attempts: List[Dict[str, Any]],
    improvement_trace: List[Dict[str, Any]],
    search_report_state: Optional[OptimizationSearchReportState],
    no_improve: int,
    acceptance: str,
    version: int,
    iteration: int,
    iteration_limit: int,
    strict_mode: bool,
    batches: Dict[str, Any],
    start_dt: datetime,
    end_date: Optional[date],
    resource_pool: Optional[Dict[str, Any]],
    objective_name: str,
    optimizer_algo_stats: Optional[Dict[str, Any]],
    readiness_gate_enabled: bool,
    valid_dispatch_rules: List[str],
    fingerprint_tracker: LocalSearchFingerprintTracker,
    clock: Callable[[], float],
    t_begin: float,
    started_at: float,
    decode_session: SharedDecodeSession,
) -> LocalSearchRoundResult:
    move = choose_neighborhood_move(
        order=local_state.current_order,
        neighborhoods=vns_state.current_choice(),
        results=local_state.current.get("results") or [],
        batches=batches,
        resource_pool=local_state.current_resource_pool or resource_pool,
        rnd=rnd,
        current_dispatch_rule=cur_dispatch_rule,
        valid_dispatch_rules=valid_dispatch_rules,
    )
    mark_neighborhood_move(search_report_state, move)
    if move.noop:
        _record_noop_neighbor(
            attempts=attempts,
            search_report_state=search_report_state,
            strategy=cur_strat,
            dispatch_mode=cur_dispatch_mode,
            dispatch_rule=cur_dispatch_rule,
            move=move,
        )
        return LocalSearchRoundResult(no_improve + 1, False, False, move)
    cand_order = list(move.batch_order or local_state.current_order)
    candidate_resource_pool = local_state.current_resource_pool or resource_pool
    candidate_pair_rank = local_state.current_resource_pair_rank
    if move.resource_pair_rank:
        candidate_pair_rank = dict(candidate_pair_rank)
        candidate_pair_rank.update(move.resource_pair_rank)
        ranks = dict((candidate_resource_pool or {}).get("pair_rank") or {})
        ranks.update(move.resource_pair_rank)
        candidate_resource_pool = dict(candidate_resource_pool or {}, pair_rank=ranks)
    candidate_mode = str(move.dispatch_mode or cur_dispatch_mode)
    candidate_rule = str(move.dispatch_rule or cur_dispatch_rule)
    # ``started_at`` is the loop's reading taken just before this round; choosing the move costs
    # microseconds, so the decode time is measured from it without another clock call.
    evaluate = partial(
        evaluate_local_search_candidate,
        strict_mode=bool(strict_mode),
        strategy=cur_strat,
        params=cur_params,
        start_dt=start_dt,
        end_date=end_date,
        order=cand_order,
        dispatch_mode=candidate_mode,
        dispatch_rule=candidate_rule,
        resource_pool=candidate_resource_pool,
        resource_pair_rank=candidate_pair_rank,
        objective_name=objective_name,
        optimizer_algo_stats=optimizer_algo_stats,
        readiness_gate_enabled=bool(readiness_gate_enabled),
        neighborhood_move=move,
        decode_session=decode_session,
    )
    calls_before = decode_session.actual_decoder_calls
    try:
        candidate = evaluate_optional_local_candidate(
            evaluate=evaluate,
            attempts=attempts,
            move=move.neighborhood_name,
            strategy=cur_strat,
            dispatch_mode=candidate_mode,
            dispatch_rule=candidate_rule,
            strict_mode=bool(strict_mode),
            search_report_state=search_report_state,
        )
    except SharedSearchSkip as exc:
        return LocalSearchRoundResult(
            no_improve + 1, False, False, move, skip_reason=exc.reason,
            request_id=exc.request_id, decode_receipt=exc.receipt,
        )
    decode_attempted = decode_session.actual_decoder_calls > calls_before
    stamp_decode_runtime(candidate, started_at=started_at, clock=clock)
    candidate_fingerprint = local_candidate_fingerprint(
        search_report_state=search_report_state,
        fingerprint_tracker=fingerprint_tracker,
        candidate=candidate,
    )
    if candidate is None:
        return LocalSearchRoundResult(
            no_improve + 1, False, False, move,
            decode_attempted=decode_attempted,
        )
    acceptance_decision = decide_acceptance(
        acceptance_name=acceptance,
        candidate_score=candidate.get("score"),
        current_score=local_state.current.get("score"),
        best_score=local_state.best.get("score"),
        iteration=iteration,
        max_iterations=iteration_limit,
        random_seed=int(version),
        rnd=rnd,
    )
    accepted_current, best_improved, no_improve = _apply_accepted_candidate(
        candidate=candidate,
        local_state=local_state,
        candidate_fingerprint=candidate_fingerprint,
        acceptance_decision=acceptance_decision,
        no_improve=no_improve,
        move=move,
        attempts=attempts,
        improvement_trace=improvement_trace,
        clock=clock,
        t_begin=t_begin,
        incumbent_origin=_incumbent_origin(local_state.best, search_report_state),
        incumbent_fingerprint_changed=bool(search_report_state and search_report_state.best_fingerprint_changed()),
        search_report_state=search_report_state,
    )
    _record_acceptance_result(
        best_improved=best_improved,
        accepted_current=accepted_current,
        candidate_fingerprint=candidate_fingerprint,
        fingerprint_tracker=fingerprint_tracker,
        search_report_state=search_report_state,
        candidate=candidate,
        acceptance_decision=acceptance_decision,
    )
    receipt = candidate.get("decode_receipt")
    return LocalSearchRoundResult(
        no_improve, accepted_current, best_improved, move,
        decode_attempted=decode_attempted,
        request_id=receipt["request_id"] if receipt is not None else None,
        decode_receipt=receipt,
    )


def _incumbent_origin(
    best: Dict[str, Any],
    search_report_state: Optional[OptimizationSearchReportState],
) -> str:
    if search_report_state is not None:
        return str(search_report_state.best_origin or "baseline")
    return str((best or {}).get("candidate_origin") or "baseline")


def _record_acceptance_result(
    *,
    best_improved: bool,
    accepted_current: bool,
    candidate_fingerprint: Any,
    fingerprint_tracker: LocalSearchFingerprintTracker,
    search_report_state: Optional[OptimizationSearchReportState],
    candidate: Dict[str, Any],
    acceptance_decision: AcceptanceDecision,
) -> None:
    if best_improved and candidate_fingerprint is not None:
        fingerprint_tracker.mark_best(candidate_fingerprint)
    if search_report_state is None:
        return
    if best_improved:
        search_report_state.local_search_improved = True
        search_report_state.mark_candidate_accepted(
            candidate,
            origin="local_search",
            acceptance_event=acceptance_decision.to_report_dict(),
            fingerprint=candidate_fingerprint,
        )
    elif accepted_current:
        search_report_state.mark_current_candidate_accepted(
            candidate,
            origin="local_search",
            acceptance_event=acceptance_decision.to_report_dict(),
            fingerprint=candidate_fingerprint,
        )
    else:
        search_report_state.mark_acceptance_event(
            acceptance_decision.to_report_dict(),
            best_improved=False,
            current_accepted=False,
        )


__all__ = ["LocalSearchRoundResult", "mark_neighborhood_move", "run_local_search_candidate_round", "stamp_decode_runtime"]
