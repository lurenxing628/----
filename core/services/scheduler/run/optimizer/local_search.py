from __future__ import annotations

from random import Random
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple, cast

from core.algorithm_contracts.dispatch_rules import dispatch_rule_search_pool

from .local_search_limits import (
    LocalSearchCounters,
    derive_local_search_limits,
    local_search_stop_reason,
)
from .local_search_restart import RestartOutcome, evaluate_restart_candidate, restart_after_stall
from .local_search_round import LocalSearchRoundResult, run_local_search_candidate_round
from .local_search_state import LocalSearchState, StrategyState, resolve_current_strategy_state
from .neighborhood_moves import SGS_DISPATCH_RULE, pick_sgs_dispatch_rule
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
    neighborhoods: Tuple[str, ...],
    cur_dispatch_mode: str,
) -> Tuple[str, ...]:
    return (SGS_DISPATCH_RULE,) if cur_dispatch_mode == "sgs" else neighborhoods


def _resolve_sgs_dispatch_rules(valid_dispatch_rules: List[str], current_dispatch_rule: str) -> List[str]:
    # The rule neighborhood searches the registry rules plus the ATC k ladder; the
    # current rule may already be a ladder token adopted by an earlier phase.
    out = list(dispatch_rule_search_pool(valid_dispatch_rules))
    current = current_dispatch_rule.strip().lower()
    if current and current not in out:
        out.insert(0, current)
    return out


class _LocalSearchRun:
    """One local search over the incumbent: the inputs shared by every round and restart."""

    def __init__(self, *, rnd: Random, search_report_state: OptimizationSearchReportState, objective_name: str,
                 valid_dispatch_rules: List[str], decode_session: SharedDecodeSession) -> None:
        self.rnd = rnd
        self.search_report_state = search_report_state
        self.objective_name = objective_name
        self.valid_dispatch_rules = valid_dispatch_rules
        self.decode_session = decode_session

    def round(self, *, local_state: LocalSearchState, vns_state: VnsState, strategy_state: StrategyState,
              counters: LocalSearchCounters,
              tried_sgs_rules: Optional[Set[str]] = None) -> LocalSearchRoundResult:
        valid_dispatch_rules = self.valid_dispatch_rules
        if strategy_state.dispatch_mode == "sgs" and tried_sgs_rules is not None:
            picked = pick_sgs_dispatch_rule(
                strategy_state.dispatch_rule, valid_dispatch_rules, self.rnd, tried_rules=tried_sgs_rules,
            )
            valid_dispatch_rules = [picked] if picked is not None else []
        return run_local_search_candidate_round(
            local_state=local_state, vns_state=vns_state, strategy_state=strategy_state,
            rnd=self.rnd, search_report_state=self.search_report_state, no_improve=counters.no_improve,
            objective_name=self.objective_name, valid_dispatch_rules=valid_dispatch_rules,
            decode_session=self.decode_session,
        )

    def restart(self, *, local_state: LocalSearchState) -> RestartOutcome:
        def _evaluate(shaken_order: List[str], inherited: StrategyState) -> Dict[str, Any]:
            return evaluate_restart_candidate(
                shaken_order=shaken_order, local_state=local_state, inherited=inherited,
                objective_name=self.objective_name, search_report_state=self.search_report_state,
                decode_session=self.decode_session,
            )

        return restart_after_stall(
            local_state=local_state, rnd=self.rnd,
            evaluate_shaken_order=_evaluate, decode_session=self.decode_session,
        )


class LocalSearchStage(SearchStage):
    """The local incumbent and exploration state, paused between single decode actions."""

    name = "local_search"

    def __init__(
        self,
        *,
        best: Optional[Dict[str, Any]],
        version: int,
        objective_name: str,
        search_report_state: OptimizationSearchReportState,
        neighborhoods: Tuple[str, ...],
        valid_dispatch_rules: List[str],
        decode_session: SharedDecodeSession,
    ) -> None:
        self._initial_best = best
        self.local_state: Optional[LocalSearchState] = None
        self.budget = decode_session.budget
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
        local_state = LocalSearchState.from_best(best, due_batches=decode_session.evaluation_context.due_batches)
        strategy_state = resolve_current_strategy_state(best)
        active_neighborhoods = _active_neighborhoods(
            neighborhoods=neighborhoods, cur_dispatch_mode=strategy_state.dispatch_mode,
        )
        # Size limits once; each task measures only its own work after the queue resumes it.
        limits = derive_local_search_limits(neighborhood_count=len(active_neighborhoods))
        vns_state = VnsState(active_neighborhoods)
        counters = LocalSearchCounters()
        run = _LocalSearchRun(
            rnd=Random(int(version)),
            search_report_state=search_report_state,
            objective_name=objective_name,
            valid_dispatch_rules=_resolve_sgs_dispatch_rules(valid_dispatch_rules, strategy_state.dispatch_rule),
            decode_session=decode_session,
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
        self.local_state.set_best(candidate)
        if (candidate["archive_ref"].entry_id != prev_best["archive_ref"].entry_id
                # Producers keep their own sequence type (read-only tuple or list); compare by content.
                or tuple(candidate["order"]) != tuple(prev_best["order"])):
            self._tried_sgs_rules.clear()
        if (self.stop_reason == "estimated_decode_cost"
                and self._best_dispatch_mode(self.local_state) not in self._unaffordable_modes):
            self.stop_reason = None
            self.pending_restart = True

    def _best_dispatch_mode(self, local_state: LocalSearchState) -> str:
        return str(local_state.best["dispatch_mode"])

    def _sync_strategy_and_neighborhoods(self, strategy_state: StrategyState) -> None:
        if strategy_state.dispatch_mode != self.strategy_state.dispatch_mode:
            self.vns_state = VnsState(
                _active_neighborhoods(neighborhoods=self._neighborhoods,
                                      cur_dispatch_mode=strategy_state.dispatch_mode),
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
        cur_mode = self.strategy_state.dispatch_mode
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
            now_value=self.budget.clock(), deadline=self.budget.deadline,
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
            restart = self._run.restart(local_state=local_state)
            self.counters.record_round(decode_attempted=restart.decode_attempted)
            self._sync_strategy_and_neighborhoods(restart.strategy_state)
            self._handle_budget_skip(
                local_state, stop_reason=restart.stop_reason, rejected_mode=restart.rejected_mode,
            )
            return
        prev_current = local_state.current
        outcome = self._run.round(
            local_state=local_state, vns_state=self.vns_state, strategy_state=self.strategy_state,
            counters=self.counters,
            tried_sgs_rules=self._tried_sgs_rules,
        )
        self.counters.record_round(decode_attempted=outcome.decode_attempted)
        self.counters.no_improve = outcome.no_improve
        if local_state.current is prev_current:
            self._current_stall_rounds += 1
        else:
            self._current_stall_rounds = 0
            self._tried_sgs_rules.clear()
        self._sync_strategy_and_neighborhoods(
            resolve_current_strategy_state(local_state.current),
        )
        self.vns_state.record_round(best_improved=outcome.best_improved)
        self._handle_budget_skip(
            local_state, stop_reason=outcome.stop_reason, rejected_mode=outcome.rejected_mode,
        )
        cycle_length = (
            max(len(self._run.valid_dispatch_rules) - 1, 1)
            if self.strategy_state.dispatch_mode == "sgs"
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
