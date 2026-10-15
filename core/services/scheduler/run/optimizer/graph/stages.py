"""The three graph phase stages as rotation units: weight profiles, elite repair, iterated greedy."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from core.algorithms import SortStrategy
from core.errors import ValidationError
from core.services.scheduler.run.optimizer.candidate_comparison import candidate_is_preferred
from core.services.scheduler.run.optimizer.candidate_fingerprint import score_strictly_better
from core.services.scheduler.run.optimizer.graph_ready_profiles import GraphReadyWeightProfile
from core.services.scheduler.run.optimizer.search_stage import SearchStage

from .acceptance import build_graph_ready_improve_only_acceptance_event
from .context import reason_from_validation
from .iterated_greedy_incumbent import incumbent_events
from .iterated_greedy_run import IteratedGreedyRun
from .predecode import GraphReadyProfileSearch
from .repair import EliteRepairPool, EliteRepairRun
from .reporting import append_graph_attempt, append_graph_trace, record_rejected_attempt
from .v2_contract import is_graph_ready_v2_contract_error

if TYPE_CHECKING:
    from core.services.scheduler.run.optimizer.shared_decode import SharedDecodeSession

class GraphSearchState:
    """The incumbent shared by all stages of one graph phase run."""

    def __init__(self, best: Optional[Dict[str, Any]]) -> None:
        self.best = best


class ProfileStage(SearchStage):
    name = "profiles"

    def __init__(self, *, profiles: List[GraphReadyWeightProfile], search: GraphReadyProfileSearch, pool: EliteRepairPool,
                 state: GraphSearchState, order: List[str], strict_mode: bool, base_strategy: SortStrategy,
                 dispatch_rule_cfg: str, version: int, attempts: List[Dict[str, Any]], improvement_trace: List[Dict[str, Any]],
                 search_report_state: Any, clock: Callable[[], float], t_begin: float,
                 extra_summary: Optional[Callable[[], Dict[str, Any]]] = None,
                 decode_session: SharedDecodeSession) -> None:
        self.profiles = list(profiles)
        self.search = search
        self.pool = pool
        self.state = state
        self.order = order
        self.strict_mode = bool(strict_mode)
        self.base_strategy = base_strategy
        self.dispatch_rule_cfg = dispatch_rule_cfg
        self.version = int(version)
        self.attempts = attempts
        self.improvement_trace = improvement_trace
        self.search_report_state = search_report_state
        self.clock = clock
        self.t_begin = t_begin
        self.extra_summary = extra_summary
        self.decode_session = decode_session
        self.index = 0
        self.finished = False

    def available(self) -> bool:
        return self.index < len(self.profiles) and self.search.can_start()

    def unavailable_reason(self) -> Optional[str]:
        if self.index >= len(self.profiles):
            return "profiles_exhausted"
        return None if self.search.can_start() else self.search.budget.stop_reason

    def run_task(self) -> int:
        profile = self.profiles[self.index]
        self.index += 1
        candidate = _evaluate_profile(evaluate=self.search.evaluate, profile=profile, order=self.order, strict_mode=self.strict_mode,
                                      base_strategy=self.base_strategy, dispatch_rule_cfg=self.dispatch_rule_cfg,
                                      attempts=self.attempts, search_report_state=self.search_report_state)
        if candidate is None:
            return 0
        fingerprint = self.pool.observe(candidate, profile)
        if not _candidate_should_replace_best(candidate, profile=profile, best=self.state.best, attempts=self.attempts,
                                              search_report_state=self.search_report_state, fingerprint=fingerprint,
                                              clock=self.clock, t_begin=self.t_begin):
            return 0
        improved = score_strictly_better(candidate.get("score"), (self.state.best or {}).get("score"))
        _accept_candidate(candidate, profile=profile, incumbent=self.state.best, version=self.version,
                          search_report_state=self.search_report_state, fingerprint=fingerprint)
        append_graph_trace(improvement_trace=self.improvement_trace, candidate=candidate, profile=profile, clock=self.clock,
                           t_begin=self.t_begin)
        self.state.best = candidate
        return int(improved)

    def finish(self) -> None:
        if self.finished:
            return
        self.finished = True
        if self.extra_summary is not None:
            self.search.report.update(self.extra_summary())
        self.search.publish(attempts=self.attempts, report_state=self.search_report_state)


class RepairStage(SearchStage):
    name = "elite_repair"

    def __init__(self, run: EliteRepairRun) -> None:
        self.run = run

    def available(self) -> bool:
        return self.run.available()

    def unavailable_reason(self) -> Optional[str]:
        if not self.run.pool.limits.enabled:
            return "disabled"
        if self.run.clock() >= self.run.repair_deadline:
            return "time_budget"
        if self.run.exhausted:
            return self.run.report["repair_stop_reason"] or "search_exhausted"
        return None if self.run.pool.elites else "no_elite"

    def run_task(self) -> int:
        before = (self.run.state.best or {}).get("score")
        self.run.step()
        return int(score_strictly_better((self.run.state.best or {}).get("score"), before))

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
        if not self.run.limits.enabled:
            return "disabled"
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

    def run_task(self) -> int:
        before = incumbent_events(self.run.report)
        self.run.step()
        return incumbent_events(self.run.report) - before

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
    return next((profile for profile in profiles if str(profile.formula_version or "").startswith("graph_ready_v2")), None)


def _evaluate_profile(
    *,
    evaluate: Callable[..., Optional[Dict[str, Any]]],
    profile: GraphReadyWeightProfile,
    strict_mode: bool,
    base_strategy: SortStrategy,
    order: List[str],
    dispatch_rule_cfg: str,
    attempts: List[Dict[str, Any]],
    search_report_state: Any,
) -> Optional[Dict[str, Any]]:
    try:
        return evaluate(profile=profile, order=order)
    except ValidationError as exc:
        if strict_mode or is_graph_ready_v2_contract_error(exc):
            raise
        _record_profile_rejection(exc, profile=profile, attempts=attempts, base_strategy=base_strategy,
                                  dispatch_rule_cfg=dispatch_rule_cfg, search_report_state=search_report_state)
        return None


def _record_profile_rejection(
    exc: ValidationError,
    *,
    profile: GraphReadyWeightProfile,
    attempts: List[Dict[str, Any]],
    base_strategy: SortStrategy,
    dispatch_rule_cfg: str,
    search_report_state: Any,
) -> None:
    reason = reason_from_validation(exc)
    record_rejected_attempt(attempts=attempts, strategy=base_strategy, dispatch_rule=dispatch_rule_cfg, reason=reason,
                            message=str(exc), profile_slug=profile.slug)
    if search_report_state is not None:
        search_report_state.mark_candidate_rejected(reason=reason)


def _candidate_should_replace_best(
    candidate: Dict[str, Any],
    *,
    profile: GraphReadyWeightProfile,
    best: Optional[Dict[str, Any]],
    attempts: List[Dict[str, Any]],
    search_report_state: Any,
    fingerprint: Any = None,
    clock: Optional[Callable[[], float]] = None,
    t_begin: Optional[float] = None,
) -> bool:
    if search_report_state is not None:
        fingerprint = search_report_state.mark_candidate_evaluated(candidate, origin=profile.candidate_origin,
                                                                   fingerprint=fingerprint)
    else:
        fingerprint = None
    duplicate = fingerprint is not None and (fingerprint.same_as_parent or fingerprint.same_as_seen)
    accepted = not duplicate and candidate_is_preferred(
        candidate=candidate,
        incumbent=best,
        candidate_origin=profile.candidate_origin,
        incumbent_origin=_incumbent_origin(best, search_report_state),
        candidate_fingerprint=fingerprint,
        incumbent_fingerprint_changed=bool(search_report_state and search_report_state.best_fingerprint_changed()),
    )
    append_graph_attempt(attempts=attempts, candidate=candidate, profile=profile, reference=best, accepted=accepted,
                         search_report_state=search_report_state, clock=clock, t_begin=t_begin)
    return accepted


def _incumbent_origin(best: Optional[Dict[str, Any]], search_report_state: Any) -> str:
    if search_report_state is not None:
        return str(search_report_state.best_origin or "baseline")
    return str((best or {}).get("candidate_origin") or "baseline")


def _accept_candidate(
    candidate: Dict[str, Any],
    *,
    profile: GraphReadyWeightProfile,
    incumbent: Optional[Dict[str, Any]],
    version: int,
    search_report_state: Any,
    fingerprint: Any = None,
) -> None:
    if search_report_state is not None:
        event = None
        if incumbent is not None:
            event = build_graph_ready_improve_only_acceptance_event(
                candidate_score=candidate.get("score"), incumbent_score=incumbent.get("score"), seed=int(version))
        search_report_state.mark_candidate_accepted(candidate, origin=profile.candidate_origin,
                                                     acceptance_event=event, fingerprint=fingerprint)


__all__ = ["GraphSearchState", "IteratedGreedyStage", "ProfileStage", "RepairStage", "iterated_greedy_parent_profile"]
