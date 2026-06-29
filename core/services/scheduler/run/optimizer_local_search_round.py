from __future__ import annotations

from datetime import date, datetime
from functools import partial
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from core.algorithms import ScheduleResult

from .optimizer_acceptance import AcceptanceDecision, decide_acceptance
from .optimizer_attempt_records import append_rejected_reason_attempt, evaluate_optional_local_candidate
from .optimizer_local_search_candidate_eval import evaluate_local_search_candidate
from .optimizer_local_search_fingerprints import (
    LocalSearchFingerprintTracker,
    local_candidate_fingerprint,
    should_skip_seen,
)
from .optimizer_local_search_report_hooks import (
    mark_acceptance_rejected,
    mark_best_candidate_accepted,
    mark_current_candidate_accepted,
)
from .optimizer_local_search_state import LocalSearchState, candidate_can_update_best
from .optimizer_neighborhood_moves import NeighborhoodMove
from .optimizer_neighborhood_registry import choose_neighborhood_move
from .optimizer_vns import VnsState

if TYPE_CHECKING:
    from .optimizer_search_report import OptimizationSearchReportState


def _record_improvement(
    *,
    candidate: Dict[str, Any],
    move: NeighborhoodMove,
    attempts: List[Dict[str, Any]],
    improvement_trace: List[Dict[str, Any]],
    clock: Callable[[], float],
    t_begin: float,
) -> None:
    metrics = candidate["metrics"]
    score = candidate["score"]
    used_strat = candidate["strategy"]
    used_params = candidate["params"]
    dispatch_mode = str(candidate.get("dispatch_mode") or "")
    dispatch_rule = str(candidate.get("dispatch_rule") or "")
    move_tag = f"local:{move.neighborhood_name}"
    if len(improvement_trace) < 200:
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
    if len(attempts) < 12:
        attempts.append(
            {
                "tag": move_tag,
                "strategy": used_strat.value,
                "dispatch_mode": dispatch_mode,
                "dispatch_rule": dispatch_rule,
                "used_params": dict(used_params or {}),
                "score": list(score),
                "failed_ops": int(candidate["summary"].failed_ops),
                "algo_stats": candidate["algo_stats"],
                "metrics": metrics.to_dict(),
            }
        )


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


def _mark_neighborhood_move(
    search_report_state: Optional[OptimizationSearchReportState],
    move: NeighborhoodMove,
    *,
    noop: Optional[bool] = None,
    candidate_rejected: str = "",
    reason: str = "",
) -> None:
    if search_report_state is None:
        return
    row = move.to_report_dict()
    if noop is not None:
        row["noop"] = bool(noop)
    if candidate_rejected:
        row["candidate_rejected"] = str(candidate_rejected)
    if reason:
        diagnostics = dict(row.get("diagnostics") or {})
        diagnostics["reason"] = str(reason)
        row["diagnostics"] = diagnostics
    search_report_state.mark_neighborhood_move(row)


def _apply_accepted_candidate(
    *,
    candidate: Optional[Dict[str, Any]],
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
) -> Tuple[bool, bool, int]:
    if candidate is None:
        return False, False, no_improve + 1
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
    seen_hashes: Optional[set],
    rnd: Any,
    attempts: List[Dict[str, Any]],
    improvement_trace: List[Dict[str, Any]],
    search_report_state: Optional[OptimizationSearchReportState],
    no_improve: int,
    acceptance: str,
    version: int,
    iteration: int,
    iteration_limit: int,
    scheduler: Any,
    strict_mode: bool,
    algo_ops_to_schedule: List[Any],
    batches: Dict[str, Any],
    start_dt: datetime,
    end_date: Optional[date],
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]],
    seed_sr_list: List[ScheduleResult],
    resource_pool: Optional[Dict[str, Any]],
    objective_name: str,
    optimizer_algo_stats: Optional[Dict[str, Any]],
    schedule_fn: Callable[..., Any],
    readiness_gate_enabled: bool,
    graph_ready_context: Optional[Any],
    valid_dispatch_rules: List[str],
    fingerprint_tracker: LocalSearchFingerprintTracker,
    clock: Callable[[], float],
    t_begin: float,
) -> Tuple[int, bool, bool, NeighborhoodMove]:
    move = choose_neighborhood_move(
        order=local_state.current_order,
        neighborhoods=vns_state.current_choice(),
        results=list(local_state.current.get("results") or []),
        batches=batches,
        resource_pool=local_state.current_resource_pool or resource_pool,
        rnd=rnd,
        current_dispatch_rule=cur_dispatch_rule,
        valid_dispatch_rules=valid_dispatch_rules,
    )
    if move.noop:
        _mark_neighborhood_move(search_report_state, move)
        _record_noop_neighbor(
            attempts=attempts,
            search_report_state=search_report_state,
            strategy=cur_strat,
            dispatch_mode=cur_dispatch_mode,
            dispatch_rule=cur_dispatch_rule,
            move=move,
        )
        return no_improve + 1, False, False, move
    if should_skip_seen(move, seen_hashes):
        _mark_neighborhood_move(
            search_report_state,
            move,
            noop=True,
            candidate_rejected="noop_neighbor",
            reason="duplicate_decision",
        )
        _record_noop_neighbor(
            attempts=attempts,
            search_report_state=search_report_state,
            strategy=cur_strat,
            dispatch_mode=cur_dispatch_mode,
            dispatch_rule=cur_dispatch_rule,
            move=move,
        )
        return no_improve + 1, False, False, move

    _mark_neighborhood_move(search_report_state, move)
    cand_order = list(move.batch_order or local_state.current_order)
    candidate_resource_pool = move.resource_pool if move.resource_pool is not None else (local_state.current_resource_pool or resource_pool)
    candidate_mode = str(move.dispatch_mode or cur_dispatch_mode)
    candidate_rule = str(move.dispatch_rule or cur_dispatch_rule)
    candidate = evaluate_optional_local_candidate(
        evaluate=partial(
            evaluate_local_search_candidate,
            scheduler=scheduler,
            strict_mode=bool(strict_mode),
            algo_ops_to_schedule=algo_ops_to_schedule,
            batches=batches,
            strategy=cur_strat,
            params=cur_params,
            start_dt=start_dt,
            end_date=end_date,
            downtime_map=downtime_map,
            order=cand_order,
            seed_sr_list=seed_sr_list,
            dispatch_mode=candidate_mode,
            dispatch_rule=candidate_rule,
            resource_pool=candidate_resource_pool,
            objective_name=objective_name,
            optimizer_algo_stats=optimizer_algo_stats,
            schedule_fn=schedule_fn,
            readiness_gate_enabled=bool(readiness_gate_enabled),
            graph_ready_context=graph_ready_context,
            neighborhood_move=move,
        ),
        attempts=attempts,
        move=move.neighborhood_name,
        strategy=cur_strat,
        dispatch_mode=candidate_mode,
        dispatch_rule=candidate_rule,
        strict_mode=bool(strict_mode),
        search_report_state=search_report_state,
    )
    candidate_fingerprint = local_candidate_fingerprint(
        search_report_state=search_report_state,
        fingerprint_tracker=fingerprint_tracker,
        candidate=candidate,
    )
    if candidate is None:
        return no_improve + 1, False, False, move
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
    return no_improve, accepted_current, best_improved, move


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
    if best_improved:
        if candidate_fingerprint is not None:
            fingerprint_tracker.mark_best(candidate_fingerprint)
        mark_best_candidate_accepted(
            search_report_state=search_report_state,
            candidate=candidate,
            acceptance_decision=acceptance_decision,
        )
        return
    if accepted_current:
        mark_current_candidate_accepted(
            search_report_state=search_report_state,
            candidate=candidate,
            acceptance_decision=acceptance_decision,
        )
        return
    mark_acceptance_rejected(
        search_report_state=search_report_state,
        acceptance_decision=acceptance_decision,
    )


__all__ = ["run_local_search_candidate_round"]
