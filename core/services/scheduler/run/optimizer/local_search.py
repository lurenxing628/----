from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple, cast

from core.algorithm_contracts.dispatch_rules import dispatch_rule_search_pool

from .acceptance import ACCEPTANCE_IMPROVE_ONLY
from .candidate_fingerprint import score_strictly_better
from .local_search_fingerprints import LocalSearchFingerprintTracker
from .local_search_limits import (
    STOP_ITERATION_LIMIT,
    STOP_SEARCH_EXHAUSTED,
    STOP_TIME_BUDGET,
    LocalSearchCounters,
    LocalSearchLimits,
    derive_local_search_limits,
    local_search_stop_reason,
)
from .local_search_restart import RestartOutcome, _evaluate_restart_candidate, restart_after_stall
from .local_search_round import LocalSearchRoundResult, run_local_search_candidate_round
from .local_search_state import LocalSearchState, resolve_current_strategy_state
from .neighborhood_moves import BUSINESS_NEIGHBORHOODS, DEFAULT_SGS_DISPATCH_RULES, SGS_DISPATCH_RULE
from .search_stage import SearchStage
from .vns import VnsState

if TYPE_CHECKING:
    from .search_report import OptimizationSearchReportState
    from .shared_decode import SharedDecodeSession

__all__ = ["LocalSearchStage"]


def _local_search_skip_reason(
    *,
    algo_mode: str,
    best: Optional[Dict[str, Any]],
) -> Tuple[Optional[str], Dict[str, Any]]:
    if algo_mode != "improve":
        return "algo_mode_not_improve", {}
    if best is None:
        return "best_missing", {}
    order_length = len(best.get("order") or [])
    if order_length < 2:
        return "order_too_short", {"order_length": order_length}
    return None, {}


def _mark_local_search_skipped(search_report_state: Optional[OptimizationSearchReportState], reason: str, extra: Dict[str, Any]) -> None:
    if search_report_state is not None:
        search_report_state.mark_phase_skipped("local_search", reason, **extra)


def _mark_local_search_stop(
    search_report_state: Optional[OptimizationSearchReportState],
    reason: str,
    *,
    counters: LocalSearchCounters,
    limits: LocalSearchLimits,
    rounds: int,
) -> None:
    if search_report_state is None:
        return
    if reason == STOP_TIME_BUDGET:
        search_report_state.mark_deadline_reached()
    elif reason == STOP_ITERATION_LIMIT:
        search_report_state.mark_iteration_limit_reached()
    elif reason == STOP_SEARCH_EXHAUSTED:
        search_report_state.mark_search_exhausted()
    stop = dict(counters.to_report_dict(), reason=str(reason), limits=limits.to_report_dict(), rounds=rounds)
    search_report_state.update_candidate_profile(local_search_stop=stop)


def _mark_local_search_entered(search_report_state: Optional[OptimizationSearchReportState], limits: LocalSearchLimits) -> None:
    if search_report_state is not None:
        search_report_state.local_search_entered = True
        search_report_state.update_candidate_profile(local_search_limits=limits.to_report_dict())


def _active_neighborhoods(
    *,
    neighborhoods: Optional[Tuple[str, ...]],
    cur_dispatch_mode: str,
    search_report_state: Optional[OptimizationSearchReportState],
) -> Tuple[str, ...]:
    configured = tuple(neighborhoods or BUSINESS_NEIGHBORHOODS)
    active = (SGS_DISPATCH_RULE,) if cur_dispatch_mode == "sgs" else configured
    if search_report_state is not None:
        search_report_state.set_effective_neighborhoods(
            configured=configured,
            effective=active,
            reason="sgs_dispatch_rule_only" if cur_dispatch_mode == "sgs" else "configured_neighborhoods",
            dispatch_mode=cur_dispatch_mode,
        )
    return active


def _mark_vns_round(
    search_report_state: Optional[OptimizationSearchReportState],
    vns_state: VnsState,
    *,
    best_improved: bool,
    move: Any,
) -> None:
    vns_event = vns_state.record_round(
        best_improved=best_improved,
        noop=bool(move.noop),
        fallback_used=bool(move.fallback_used),
    )
    if search_report_state is not None:
        search_report_state.mark_vns_event(vns_event)


def _resolve_sgs_dispatch_rules(valid_dispatch_rules: Optional[List[str]], current_dispatch_rule: str) -> List[str]:
    # The rule neighborhood searches the registry rules plus the ATC k ladder; the
    # current rule may already be a ladder token adopted by an earlier phase.
    out = list(dispatch_rule_search_pool(valid_dispatch_rules or DEFAULT_SGS_DISPATCH_RULES))
    current = str(current_dispatch_rule or "").strip().lower()
    if current and current not in out:
        out.insert(0, current)
    return out


class _LocalSearchRun:
    """One local search over the incumbent: the decode inputs shared by every round and restart."""

    def __init__(self, **decode_inputs: Any) -> None:
        self.inputs = decode_inputs

    def round(self, *, local_state: LocalSearchState, vns_state: VnsState, strategy_state: Tuple[Any, Any, str, str],
              counters: LocalSearchCounters, limits: LocalSearchLimits, started_at: float, iteration: int) -> LocalSearchRoundResult:
        cur_strat, cur_params, cur_dispatch_mode, cur_dispatch_rule = strategy_state
        return run_local_search_candidate_round(
            local_state=local_state, vns_state=vns_state, cur_strat=cur_strat, cur_params=cur_params,
            cur_dispatch_mode=cur_dispatch_mode, cur_dispatch_rule=cur_dispatch_rule,
            no_improve=counters.no_improve, iteration=iteration, iteration_limit=limits.decode_limit,
            started_at=started_at, **self.inputs,
        )

    def restart(self, *, local_state: LocalSearchState, vns_state: VnsState,
                dispatch_mode_cfg: str, dispatch_rule_cfg: str) -> RestartOutcome:
        inputs = self.inputs

        def _evaluate(shaken_order: List[str], move: Any, strategy: Any, params: Dict[str, Any],
                      dispatch_mode: str, dispatch_rule: str) -> Optional[Dict[str, Any]]:
            return _evaluate_restart_candidate(
                shaken_order=shaken_order, move=move, local_state=local_state, strategy=strategy, params=params,
                dispatch_mode=dispatch_mode, dispatch_rule=dispatch_rule,
                strict_mode=inputs["strict_mode"], start_dt=inputs["start_dt"], end_date=inputs["end_date"],
                resource_pool=inputs["resource_pool"], objective_name=inputs["objective_name"],
                optimizer_algo_stats=inputs["optimizer_algo_stats"],
                readiness_gate_enabled=inputs["readiness_gate_enabled"],
                attempts=inputs["attempts"], search_report_state=inputs["search_report_state"], clock=inputs["clock"],
                decode_session=inputs["decode_session"],
            )

        return restart_after_stall(
            local_state=local_state, rnd=inputs["rnd"], dispatch_mode_cfg=dispatch_mode_cfg,
            dispatch_rule_cfg=dispatch_rule_cfg, vns_state=vns_state,
            evaluate_shaken_order=_evaluate, decode_session=inputs["decode_session"],
        )


class LocalSearchStage(SearchStage):
    """The local incumbent and exploration state, paused between single decode actions."""

    name = "local_search"

    def __init__(
        self,
        *,
        algo_mode: str,
        best: Optional[Dict[str, Any]],
        version: int,
        deadline: float,
        batches: Dict[str, Any],
        start_dt: datetime,
        end_date: Optional[date],
        dispatch_mode_cfg: str,
        dispatch_rule_cfg: str,
        resource_pool: Optional[Dict[str, Any]],
        objective_name: str,
        attempts: List[Dict[str, Any]],
        improvement_trace: List[Dict[str, Any]],
        optimizer_algo_stats: Optional[Dict[str, Any]],
        t_begin: float,
        readiness_gate_enabled: bool,
        strict_mode: bool,
        clock: Callable[[], float],
        rng_factory: Callable[[int], Any],
        search_report_state: Optional[OptimizationSearchReportState] = None,
        neighborhoods: Optional[Tuple[str, ...]] = None,
        valid_dispatch_rules: Optional[List[str]] = None,
        acceptance: str = ACCEPTANCE_IMPROVE_ONLY,
        decode_session: SharedDecodeSession,
    ) -> None:
        self._initial_best = best
        self.local_state: Optional[LocalSearchState] = None
        self.clock = clock
        self.deadline = deadline
        self.search_report_state = search_report_state
        self.dispatch_mode_cfg = dispatch_mode_cfg
        self.dispatch_rule_cfg = dispatch_rule_cfg
        self.stop_reason: Optional[str] = None
        self._skip_reason: Optional[str] = None
        self.pending_restart = False
        self.finished = False
        self.rounds = 0
        skip_reason, skip_extra = _local_search_skip_reason(algo_mode=algo_mode, best=best)
        self._skip_reason = skip_reason
        if skip_reason:
            _mark_local_search_skipped(search_report_state, skip_reason, skip_extra)
            return
        best = cast(Dict[str, Any], best)
        local_state = LocalSearchState.from_best(best, resource_pool=resource_pool)
        strategy_state = resolve_current_strategy_state(best, dispatch_mode_cfg=dispatch_mode_cfg, dispatch_rule_cfg=dispatch_rule_cfg)
        active_neighborhoods = _active_neighborhoods(
            neighborhoods=neighborhoods, cur_dispatch_mode=strategy_state[2], search_report_state=search_report_state,
        )
        # Size limits once; each task measures only its own work after the queue resumes it.
        limits = derive_local_search_limits(neighborhood_count=len(active_neighborhoods))
        self._now_value: Optional[float] = None
        _mark_local_search_entered(search_report_state, limits)
        vns_state = VnsState(active_neighborhoods)
        counters = LocalSearchCounters()
        run = _LocalSearchRun(
            attempts=attempts, improvement_trace=improvement_trace, rnd=rng_factory(int(version)),
            search_report_state=search_report_state, acceptance=acceptance, version=version,
            strict_mode=strict_mode, batches=batches, start_dt=start_dt,
            end_date=end_date, resource_pool=resource_pool,
            objective_name=objective_name, optimizer_algo_stats=optimizer_algo_stats,
            readiness_gate_enabled=readiness_gate_enabled,
            valid_dispatch_rules=_resolve_sgs_dispatch_rules(valid_dispatch_rules, strategy_state[3]),
            fingerprint_tracker=LocalSearchFingerprintTracker(
                objective_name=objective_name, initial_best=best,
                initial_fingerprint=search_report_state.fingerprint_identity(best) if search_report_state is not None else None),
            clock=clock, t_begin=t_begin, decode_session=decode_session,
        )
        self.local_state = local_state
        self._run = run
        self.vns_state = vns_state
        self.counters = counters
        self.limits = limits
        self.strategy_state = strategy_state

    @property
    def best(self) -> Optional[Dict[str, Any]]:
        return self.local_state.best if self.local_state is not None else self._initial_best

    @best.setter
    def best(self, candidate: Dict[str, Any]) -> None:
        if self.local_state is None:
            self._initial_best = candidate
            return
        if candidate is self.local_state.best:
            return
        self.local_state.best = candidate
        tracker = self._run.inputs["fingerprint_tracker"]
        tracker.mark_best(tracker.mark_evaluated(candidate))
        if self.search_report_state is not None:
            self.search_report_state.sync_best_reference(
                candidate, origin=str(candidate.get("candidate_origin") or "shared_archive_reference"),
            )

    def available(self) -> bool:
        if self.finished or self._skip_reason is not None or self.stop_reason is not None:
            return False
        now_value = self.clock()
        self._now_value = now_value
        self.stop_reason = local_search_stop_reason(
            now_value=now_value, deadline=self.deadline,
            decodes=self.rounds,
            decode_limit=self.limits.decode_limit,
            idle_rounds=self.counters.idle_rounds, idle_round_limit=self.limits.idle_round_limit,
        )
        return self.stop_reason is None

    def unavailable_reason(self) -> Optional[str]:
        if self._skip_reason is not None:
            return self._skip_reason
        if self.finished:
            return self.stop_reason or "local_search_finished"
        return None if self.available() else self.stop_reason

    def run_task(self) -> int:
        """Run one ordinary round or one pending restart, with at most one decoder call."""
        if not self.available():
            return 0
        local_state = cast(LocalSearchState, self.local_state)
        self.rounds += 1
        if self.pending_restart:
            self.pending_restart = False
            self.counters.no_improve = 0
            restart = self._run.restart(
                local_state=local_state, vns_state=self.vns_state,
                dispatch_mode_cfg=self.dispatch_mode_cfg, dispatch_rule_cfg=self.dispatch_rule_cfg,
            )
            self._now_value = None
            self.counters.record_round(decode_attempted=restart.decode_attempted)
            self.strategy_state = (restart.strategy, restart.params, restart.dispatch_mode, restart.dispatch_rule)
            self._publish_iterations()
            return 0
        before_score = local_state.best.get("score")
        outcome = self._run.round(
            local_state=local_state, vns_state=self.vns_state, strategy_state=self.strategy_state,
            counters=self.counters, limits=self.limits,
            started_at=cast(float, self._now_value),
            iteration=self.rounds - 1,
        )
        self._now_value = None
        self.counters.record_round(
            decode_attempted=outcome.decode_attempted, noop=bool(outcome.move.noop),
        )
        self.counters.no_improve = outcome.no_improve
        self._publish_iterations()
        self.strategy_state = resolve_current_strategy_state(
            local_state.current, dispatch_mode_cfg=self.dispatch_mode_cfg, dispatch_rule_cfg=self.dispatch_rule_cfg,
        )
        _mark_vns_round(self.search_report_state, self.vns_state, best_improved=outcome.best_improved, move=outcome.move)
        if self.stop_reason is None and self.counters.no_improve >= self.limits.restart_after:
            self.pending_restart = True
        return int(score_strictly_better(local_state.best.get("score"), before_score))

    def _publish_iterations(self) -> None:
        if self.search_report_state is not None:
            self.search_report_state.set_iterations(self.rounds)

    def finish(self) -> None:
        if self.finished:
            return
        if self.local_state is not None:
            self.available()
            if self.search_report_state is not None and self.search_report_state.vns_summary:
                self.search_report_state.vns_summary["shake_count"] = int(self.vns_state.shake_count)
            if self.stop_reason is not None:
                _mark_local_search_stop(
                    self.search_report_state, self.stop_reason,
                    counters=self.counters, limits=self.limits,
                    rounds=self.rounds,
                )
        self.finished = True
