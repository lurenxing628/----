from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Set, Tuple, cast

from core.algorithm_contracts.dispatch_rules import dispatch_rule_search_pool

from .acceptance import ACCEPTANCE_IMPROVE_ONLY
from .local_search_limits import (
    LocalSearchCounters,
    LocalSearchLimits,
    derive_local_search_limits,
    local_search_stop_reason,
)
from .local_search_restart import RestartOutcome, _evaluate_restart_candidate, restart_after_stall
from .local_search_round import LocalSearchRoundResult, run_local_search_candidate_round
from .local_search_state import LocalSearchState, resolve_current_strategy_state
from .neighborhood_moves import (
    BUSINESS_NEIGHBORHOODS,
    DEFAULT_SGS_DISPATCH_RULES,
    SGS_DISPATCH_RULE,
    pick_sgs_dispatch_rule,
)
from .search_stage import SearchStage
from .vns import VnsState

if TYPE_CHECKING:
    from .search_report import OptimizationSearchReportState
    from .shared_decode import SharedDecodeSession

__all__ = ["LocalSearchStage"]


def _local_search_skip_reason(*, best: Optional[Dict[str, Any]]) -> Optional[str]:
    if best is None:
        return "best_missing"
    if len(best["order"]) < 2:
        return "order_too_short"
    return None


def _active_neighborhoods(
    *,
    neighborhoods: Optional[Tuple[str, ...]],
    cur_dispatch_mode: str,
) -> Tuple[str, ...]:
    configured = tuple(neighborhoods or BUSINESS_NEIGHBORHOODS)
    return (SGS_DISPATCH_RULE,) if cur_dispatch_mode == "sgs" else configured


def _resolve_sgs_dispatch_rules(valid_dispatch_rules: Optional[List[str]], current_dispatch_rule: str) -> List[str]:
    # The rule neighborhood searches the registry rules plus the ATC k ladder; the
    # current rule may already be a ladder token adopted by an earlier phase.
    out = list(dispatch_rule_search_pool(valid_dispatch_rules or DEFAULT_SGS_DISPATCH_RULES))
    current = current_dispatch_rule.strip().lower()
    if current and current not in out:
        out.insert(0, current)
    return out


class _LocalSearchRun:
    """One local search over the incumbent: the decode inputs shared by every round and restart."""

    def __init__(self, **decode_inputs: Any) -> None:
        self.valid_dispatch_rules: List[str] = decode_inputs.pop("valid_dispatch_rules")
        self.inputs = decode_inputs

    def round(self, *, local_state: LocalSearchState, vns_state: VnsState, strategy_state: Tuple[Any, Any, str, str],
              counters: LocalSearchCounters, limits: LocalSearchLimits, iteration: int,
              tried_sgs_rules: Optional[Set[str]] = None) -> LocalSearchRoundResult:
        cur_strat, cur_params, cur_dispatch_mode, cur_dispatch_rule = strategy_state
        valid_dispatch_rules = self.valid_dispatch_rules
        if cur_dispatch_mode == "sgs" and tried_sgs_rules is not None:
            picked = pick_sgs_dispatch_rule(
                cur_dispatch_rule, valid_dispatch_rules, self.inputs["rnd"], tried_rules=tried_sgs_rules,
            )
            valid_dispatch_rules = [picked] if picked is not None else []
        return run_local_search_candidate_round(
            local_state=local_state, vns_state=vns_state, cur_strat=cur_strat, cur_params=cur_params,
            cur_dispatch_mode=cur_dispatch_mode, cur_dispatch_rule=cur_dispatch_rule,
            no_improve=counters.no_improve, iteration=iteration, iteration_limit=limits.decode_limit,
            valid_dispatch_rules=valid_dispatch_rules,
            **self.inputs,
        )

    def restart(self, *, local_state: LocalSearchState,
                dispatch_mode_cfg: str, dispatch_rule_cfg: str) -> RestartOutcome:
        inputs = self.inputs

        def _evaluate(shaken_order: List[str], strategy: Any, params: Dict[str, Any],
                      dispatch_mode: str, dispatch_rule: str) -> Optional[Dict[str, Any]]:
            return _evaluate_restart_candidate(
                shaken_order=shaken_order, local_state=local_state, strategy=strategy, params=params,
                dispatch_mode=dispatch_mode, dispatch_rule=dispatch_rule,
                strict_mode=inputs["strict_mode"], start_dt=inputs["start_dt"], end_date=inputs["end_date"],
                resource_pool=inputs["resource_pool"], objective_name=inputs["objective_name"],
                optimizer_algo_stats=inputs["optimizer_algo_stats"],
                readiness_gate_enabled=inputs["readiness_gate_enabled"],
                attempts=inputs["attempts"], search_report_state=inputs["search_report_state"],
                decode_session=inputs["decode_session"],
            )

        return restart_after_stall(
            local_state=local_state, rnd=inputs["rnd"], dispatch_mode_cfg=dispatch_mode_cfg,
            dispatch_rule_cfg=dispatch_rule_cfg,
            evaluate_shaken_order=_evaluate, decode_session=inputs["decode_session"],
        )


class LocalSearchStage(SearchStage):
    """The local incumbent and exploration state, paused between single decode actions."""

    name = "local_search"

    def __init__(
        self,
        *,
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
        search_report_state: OptimizationSearchReportState,
        neighborhoods: Optional[Tuple[str, ...]] = None,
        valid_dispatch_rules: Optional[List[str]] = None,
        acceptance: str = ACCEPTANCE_IMPROVE_ONLY,
        decode_session: SharedDecodeSession,
    ) -> None:
        self._initial_best = best
        self.local_state: Optional[LocalSearchState] = None
        self.clock = clock
        self.deadline = deadline
        self.dispatch_mode_cfg = dispatch_mode_cfg
        self.dispatch_rule_cfg = dispatch_rule_cfg
        self._neighborhoods = neighborhoods
        self._unaffordable_modes: Set[str] = set()
        self.stop_reason: Optional[str] = None
        self._skip_reason: Optional[str] = None
        self.pending_restart = False
        self.finished = False
        self.rounds = 0
        self._current_stall_rounds = 0
        self._tried_sgs_rules: Set[str] = set()
        self._skip_reason = _local_search_skip_reason(best=best)
        if self._skip_reason:
            return
        best = cast(Dict[str, Any], best)
        local_state = LocalSearchState.from_best(best, resource_pool=resource_pool)
        strategy_state = resolve_current_strategy_state(best, dispatch_mode_cfg=dispatch_mode_cfg, dispatch_rule_cfg=dispatch_rule_cfg)
        active_neighborhoods = _active_neighborhoods(
            neighborhoods=neighborhoods, cur_dispatch_mode=strategy_state[2],
        )
        # Size limits once; each task measures only its own work after the queue resumes it.
        limits = derive_local_search_limits(neighborhood_count=len(active_neighborhoods))
        vns_state = VnsState(active_neighborhoods)
        counters = LocalSearchCounters()
        run = _LocalSearchRun(
            attempts=attempts, improvement_trace=improvement_trace, rnd=rng_factory(int(version)),
            search_report_state=search_report_state, acceptance=acceptance,
            strict_mode=strict_mode, batches=batches, start_dt=start_dt,
            end_date=end_date, resource_pool=resource_pool,
            objective_name=objective_name, optimizer_algo_stats=optimizer_algo_stats,
            readiness_gate_enabled=readiness_gate_enabled,
            valid_dispatch_rules=_resolve_sgs_dispatch_rules(valid_dispatch_rules, strategy_state[3]),
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
        prev_best = self.local_state.best
        if candidate is prev_best:
            return
        self.local_state.best = candidate
        if (candidate["archive_ref"].entry_id != prev_best["archive_ref"].entry_id
                or candidate.get("order") != prev_best.get("order")):
            self._tried_sgs_rules.clear()
        if (self.stop_reason == "estimated_decode_cost"
                and self._best_dispatch_mode(self.local_state) not in self._unaffordable_modes):
            self.stop_reason = None
            self.pending_restart = True

    def _best_dispatch_mode(self, local_state: LocalSearchState) -> str:
        return resolve_current_strategy_state(
            local_state.best, dispatch_mode_cfg=self.dispatch_mode_cfg, dispatch_rule_cfg=self.dispatch_rule_cfg,
        )[2]

    def _sync_strategy_and_neighborhoods(self, strategy_state: Tuple[Any, Any, str, str]) -> None:
        if strategy_state[2] != self.strategy_state[2]:
            self.vns_state = VnsState(
                _active_neighborhoods(neighborhoods=self._neighborhoods, cur_dispatch_mode=strategy_state[2]),
            )
            self._current_stall_rounds = 0
            self._tried_sgs_rules.clear()
        self.strategy_state = strategy_state

    def _handle_budget_skip(self, local_state: LocalSearchState, *, stop_reason: Optional[str],
                            rejected_mode: Optional[str]) -> None:
        if stop_reason == "time_budget":
            self.stop_reason = "time_budget"
            return
        if stop_reason != "estimated_decode_cost":
            return
        if rejected_mode is not None:
            self._unaffordable_modes.add(rejected_mode)
        cur_mode = self.strategy_state[2]
        best_mode = self._best_dispatch_mode(local_state)
        if cur_mode in self._unaffordable_modes and best_mode not in self._unaffordable_modes:
            self.pending_restart = True
            return
        if cur_mode in self._unaffordable_modes and best_mode in self._unaffordable_modes:
            self.stop_reason = "estimated_decode_cost"

    def available(self) -> bool:
        if self.finished or self._skip_reason is not None or self.stop_reason is not None:
            return False
        self.stop_reason = local_search_stop_reason(
            now_value=self.clock(), deadline=self.deadline,
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

    def run_task(self) -> None:
        """Run one ordinary round or one pending restart, with at most one decoder call."""
        if not self.available():
            return
        local_state = cast(LocalSearchState, self.local_state)
        self.rounds += 1
        if self.pending_restart:
            self.pending_restart = False
            self.counters.no_improve = 0
            self._current_stall_rounds = 0
            self._tried_sgs_rules.clear()
            restart = self._run.restart(
                local_state=local_state,
                dispatch_mode_cfg=self.dispatch_mode_cfg, dispatch_rule_cfg=self.dispatch_rule_cfg,
            )
            self.counters.record_round(decode_attempted=restart.decode_attempted)
            self._sync_strategy_and_neighborhoods(
                (restart.strategy, restart.params, restart.dispatch_mode, restart.dispatch_rule),
            )
            self._handle_budget_skip(
                local_state, stop_reason=restart.stop_reason, rejected_mode=restart.rejected_mode,
            )
            return
        prev_current = local_state.current
        outcome = self._run.round(
            local_state=local_state, vns_state=self.vns_state, strategy_state=self.strategy_state,
            counters=self.counters, limits=self.limits,
            iteration=self.rounds - 1, tried_sgs_rules=self._tried_sgs_rules,
        )
        self.counters.record_round(decode_attempted=outcome.decode_attempted)
        self.counters.no_improve = outcome.no_improve
        if local_state.current is prev_current:
            self._current_stall_rounds += 1
        else:
            self._current_stall_rounds = 0
            self._tried_sgs_rules.clear()
        self._sync_strategy_and_neighborhoods(
            resolve_current_strategy_state(
                local_state.current, dispatch_mode_cfg=self.dispatch_mode_cfg, dispatch_rule_cfg=self.dispatch_rule_cfg,
            ),
        )
        self.vns_state.record_round(best_improved=outcome.best_improved)
        self._handle_budget_skip(
            local_state, stop_reason=outcome.stop_reason, rejected_mode=outcome.rejected_mode,
        )
        cycle_length = (
            max(len(self._run.valid_dispatch_rules) - 1, 1)
            if self.strategy_state[2] == "sgs"
            else len(self.vns_state.neighborhoods)
        )
        deterministic_cycle_exhausted = self._current_stall_rounds >= cycle_length
        if (self.stop_reason is None and not self.pending_restart
                and (self.counters.no_improve >= self.limits.restart_after or deterministic_cycle_exhausted)):
            self.pending_restart = True

    def finish(self) -> None:
        if self.finished:
            return
        if self.local_state is not None:
            self.available()
        self.finished = True
