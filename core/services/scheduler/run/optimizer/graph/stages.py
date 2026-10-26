"""The three graph phase stages as rotation units: weight profiles, elite repair, iterated greedy."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from core.algorithm_contracts.sort_strategies import SortStrategy
from core.errors import ValidationError
from core.services.scheduler.run.optimizer.candidate_comparison import candidate_is_preferred
from core.services.scheduler.run.optimizer.graph_ready_profiles import GraphReadyWeightProfile
from core.services.scheduler.run.optimizer.search_stage import SearchStage

from .context import reason_from_validation
from .iterated_greedy_run import IteratedGreedyRun
from .predecode import GraphReadyProfileSearch
from .repair import EliteRepairPool, EliteRepairRun
from .reporting import append_graph_attempt, append_graph_trace, record_rejected_attempt
from .v2_contract import is_graph_ready_v2_contract_error

if TYPE_CHECKING:
    from core.services.scheduler.run.optimizer.candidate_fingerprint import CandidateFingerprint
    from core.services.scheduler.run.optimizer.search_report import OptimizationSearchReportState


class GraphSearchState:
    """The incumbent shared by all stages of one graph phase run."""

    def __init__(self, best: Optional[Dict[str, Any]]) -> None:
        self.best = best


class ProfileStage(SearchStage):
    name = "profiles"

    def __init__(self, *, profiles: List[GraphReadyWeightProfile], search: GraphReadyProfileSearch, pool: EliteRepairPool,
                 state: GraphSearchState, order: List[str], strict_mode: bool, base_strategy: SortStrategy,
                 dispatch_rule_cfg: str, attempts: List[Dict[str, Any]], improvement_trace: List[Dict[str, Any]],
                 search_report_state: OptimizationSearchReportState, clock: Callable[[], float],
                 t_begin: float) -> None:
        self.profiles = list(profiles)
        self.search = search
        self.pool = pool
        self.state = state
        self.order = order
        self.strict_mode = bool(strict_mode)
        self.base_strategy = base_strategy
        self.dispatch_rule_cfg = dispatch_rule_cfg
        self.attempts = attempts
        self.improvement_trace = improvement_trace
        self.search_report_state = search_report_state
        self.clock = clock
        self.t_begin = t_begin
        self.index = 0
        self.finished = False

    def available(self) -> bool:
        return self.index < len(self.profiles) and self.search.can_start()

    def unavailable_reason(self) -> Optional[str]:
        if not self.search.can_start():
            return self.search.budget.stop_reason
        if self.index >= len(self.profiles):
            return "profiles_exhausted"
        return None

    def run_task(self) -> None:
        profile = self.profiles[self.index]
        self.index += 1
        candidate = _evaluate_profile(evaluate=self.search.evaluate, profile=profile, order=self.order, strict_mode=self.strict_mode,
                                      base_strategy=self.base_strategy, dispatch_rule_cfg=self.dispatch_rule_cfg,
                                      attempts=self.attempts)
        if candidate is None:
            return
        fingerprint = self.pool.observe(candidate, profile)
        if not _candidate_should_replace_best(candidate, profile=profile, best=self.state.best, attempts=self.attempts,
                                              search_report_state=self.search_report_state, fingerprint=fingerprint,
                                              clock=self.clock, t_begin=self.t_begin):
            return
        self.search_report_state.mark_candidate_accepted(candidate, origin=profile.candidate_origin,
                                                         fingerprint=fingerprint)
        append_graph_trace(improvement_trace=self.improvement_trace, candidate=candidate, profile=profile, clock=self.clock,
                           t_begin=self.t_begin)
        self.state.best = candidate

    def finish(self) -> None:
        if self.finished:
            return
        self.finished = True
        self.search.publish(attempts=self.attempts)


class RepairStage(SearchStage):
    name = "elite_repair"

    def __init__(self, run: EliteRepairRun) -> None:
        self.run = run

    def available(self) -> bool:
        return self.run.available()

    def unavailable_reason(self) -> Optional[str]:
        if self.run.clock() >= self.run.repair_deadline:
            return "time_budget"
        if self.run.report["repair_stop_reason"] in ("time_budget", "estimated_decode_cost"):
            return self.run.report["repair_stop_reason"]
        if self.run.exhausted:
            return self.run.report["repair_stop_reason"] or "search_exhausted"
        if not self.run.pool.elites and self.run.budget.stop_reason in ("time_budget", "estimated_decode_cost"):
            return self.run.budget.stop_reason
        return None if self.run.pool.elites else "no_elite"

    def run_task(self) -> None:
        self.run.step()

    def finish(self) -> None:
        self.run.finish()


class IteratedGreedyStage(SearchStage):
    name = "iterated_greedy"

    def __init__(self, run: IteratedGreedyRun, *, startup_ready: Callable[[], bool]) -> None:
        self.run = run
        self.startup_ready = startup_ready

    def available(self) -> bool:
        return self.run.available() and (self.run.started_at is not None or self.startup_ready())

    def unavailable_reason(self) -> Optional[str]:
        if self.run.state.best is None:
            return "no_incumbent"
        deadline = self.run.deadline if self.run.search is None else self.run.search.deadline
        if self.run.clock() >= deadline:
            return "time_budget"
        if self.run.stopped:
            return self.run.report["stop_reason"] or self.run.report["status"]
        if self.run.started_at is None and not self.startup_ready():
            return "waiting_for_repair_parent"
        return None

    def run_task(self) -> None:
        self.run.step()

    def finish(self) -> None:
        self.run.finish()


def iterated_greedy_parent_profile(best: Optional[Dict[str, Any]], *, pool: EliteRepairPool,
                                   profiles: List[GraphReadyWeightProfile]) -> Optional[GraphReadyWeightProfile]:
    """The incumbent's own v2 profile when it is a graph elite, else the first v2 profile."""
    if best is None:
        return None
    elite = pool.parents_by_fingerprint.get(pool.fingerprint(best).output_key)
    if elite is not None:
        return elite["profile"]
    return next((profile for profile in profiles if profile.formula_version.startswith("graph_ready_v2")), None)


def _evaluate_profile(
    *,
    evaluate: Callable[..., Optional[Dict[str, Any]]],
    profile: GraphReadyWeightProfile,
    strict_mode: bool,
    base_strategy: SortStrategy,
    order: List[str],
    dispatch_rule_cfg: str,
    attempts: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    try:
        return evaluate(profile=profile, order=order)
    except ValidationError as exc:
        if strict_mode or is_graph_ready_v2_contract_error(exc):
            raise
        _record_profile_rejection(exc, profile=profile, attempts=attempts, base_strategy=base_strategy,
                                  dispatch_rule_cfg=dispatch_rule_cfg)
        return None


def _record_profile_rejection(
    exc: ValidationError,
    *,
    profile: GraphReadyWeightProfile,
    attempts: List[Dict[str, Any]],
    base_strategy: SortStrategy,
    dispatch_rule_cfg: str,
) -> None:
    reason = reason_from_validation(exc)
    record_rejected_attempt(attempts=attempts, strategy=base_strategy, dispatch_rule=dispatch_rule_cfg, reason=reason,
                            message=str(exc), profile_slug=profile.slug)


def _candidate_should_replace_best(
    candidate: Dict[str, Any],
    *,
    profile: GraphReadyWeightProfile,
    best: Optional[Dict[str, Any]],
    attempts: List[Dict[str, Any]],
    search_report_state: OptimizationSearchReportState,
    fingerprint: CandidateFingerprint,
    clock: Callable[[], float],
    t_begin: float,
) -> bool:
    fingerprint = search_report_state.mark_candidate_evaluated(candidate, origin=profile.candidate_origin,
                                                               fingerprint=fingerprint)
    duplicate = fingerprint.same_as_parent or fingerprint.same_as_seen
    accepted = not duplicate and candidate_is_preferred(
        candidate=candidate,
        incumbent=best,
        candidate_origin=profile.candidate_origin,
        incumbent_origin=str(search_report_state.best_origin or "baseline"),
        candidate_fingerprint=fingerprint,
        incumbent_fingerprint_changed=search_report_state.best_fingerprint_changed(),
    )
    append_graph_attempt(attempts=attempts, candidate=candidate, profile=profile, reference=best, accepted=accepted,
                         search_report_state=search_report_state, clock=clock, t_begin=t_begin)
    return accepted


__all__ = ["GraphSearchState", "IteratedGreedyStage", "ProfileStage", "RepairStage", "iterated_greedy_parent_profile"]
