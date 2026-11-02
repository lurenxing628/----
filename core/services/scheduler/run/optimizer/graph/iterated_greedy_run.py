"""The iterated greedy stage: start, bounded trial tasks, finish."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from core.services.scheduler.run.optimizer.graph_ready_profiles import GraphReadyWeightProfile
from core.services.scheduler.run.optimizer.shared_budget import SharedSearchSkip
from core.services.scheduler.run.optimizer.shared_decode import SharedDecodeSession

from .iterated_greedy import _IteratedGreedySearch
from .iterated_greedy_contract import IteratedGreedyLimits, _BudgetExhausted, new_iterated_greedy_report
from .iterated_greedy_iteration import IGIteration
from .iterated_greedy_large import iteration_for, search_type_for
from .iterated_greedy_moves import _parent_from_candidate

if TYPE_CHECKING:
    from core.services.scheduler.run.optimizer.search_report import OptimizationSearchReportState


class IteratedGreedyRun:
    """Yield between trials while retaining an iteration's parent context and partial reinsertion."""

    def __init__(self, *, limits: IteratedGreedyLimits, state: Any,
                 parent_profile: Callable[[Optional[Dict[str, Any]]], Optional[GraphReadyWeightProfile]],
                 pool: Any, evaluate: Callable[..., Dict[str, Any]],
                 metrics_by_op_id: Dict[int, Dict[str, Any]], objective_name: str, start_dt: Any, seed: int, deadline: float,
                 clock: Callable[[], float], report_state: OptimizationSearchReportState,
                 decode_session: SharedDecodeSession) -> None:
        self.limits = limits
        self.state = state
        self.parent_profile = parent_profile
        self.pool = pool
        self.evaluate = evaluate
        self.decode_session = decode_session
        self.metrics_by_op_id = metrics_by_op_id
        self.start_dt = start_dt
        self.seed = int(seed)
        self.deadline = deadline
        self.clock = clock
        self.report_state = report_state
        self.report = new_iterated_greedy_report(objective_name=objective_name)
        self.search: Optional[_IteratedGreedySearch] = None
        self.stopped = False
        self.started_at: Optional[float] = None
        self.finished = False
        self.iteration: Optional[IGIteration] = None
        self.pending_adoption: Optional[Dict[str, Any]] = None

    def available(self) -> bool:
        if self.stopped or self.state.best is None:
            return False
        return self.clock() < self.deadline

    def step(self) -> None:
        started = self.clock()
        try:
            if self.search is None:
                self._start(started)
            elif self.search.reference is None:
                self.search._start_reference()
            else:
                self._advance()
        except SharedSearchSkip:
            # A rejected request ends only this cooperative action; the stage and its
            # remaining insertion tasks remain available to the common rotation.
            pass
        except _BudgetExhausted as exc:
            self.report["stop_reason"] = exc.reason
            self.stopped = True
        finally:
            if self.search is not None:
                self.state.best = self.search.best

    def _start(self, started: float) -> None:
        self.started_at = started
        best = self.state.best
        self.pool.sync_ig_candidates(best)
        parent = _parent_from_candidate(best, prepared=self.pool.prepare_parent(best))
        profile = self.parent_profile(best)
        if parent is None or profile is None:
            self.pool.sync_ig_candidates()
            self.report["status"] = "skipped_no_parent"
            self.stopped = True
            return
        self.search = search_type_for(parent)(
            limits=self.limits, parent=parent, profile=profile, pool=self.pool, evaluate=self.evaluate,
            metrics_by_op_id=self.metrics_by_op_id, start_dt=self.start_dt, seed=self.seed,
            deadline=self.deadline, clock=self.clock,
            report_state=self.report_state, report=self.report, decode_session=self.decode_session)
        self.search.best = best
        self.search._start_reference()

    def _advance(self) -> None:
        search = self.search
        assert search is not None
        if self.state.best is not search.best:
            # Share the improved incumbent immediately, but finish the trial's fixed decode context.
            self.pending_adoption = self.state.best
            search.best = self.state.best
        if self.iteration is None:
            if self.report["iterations"] >= self.limits.max_iterations:
                self.report["stop_reason"] = "max_iterations"
                self.stopped = True
                return
            pending = self.pending_adoption
            self.pending_adoption = None
            if pending is self.state.best:
                search.adopt_incumbent(self.state.best, self.parent_profile(self.state.best))
            self.iteration = iteration_for(search)
        if not self.iteration.step():
            self.iteration = None

    def finish(self) -> None:
        if self.finished:
            return
        self.finished = True
        if self.iteration is not None:
            self.iteration.close()
            self.iteration = None
        self.pool.sync_ig_candidates(self.state.best)
        self._finish_status(self.report)

    def _finish_status(self, report: Dict[str, Any]) -> None:
        if self.search is not None:
            if report["stop_reason"] is None:
                report["stop_reason"] = "time_budget" if self.clock() >= self.deadline else "rotation_ended"
            self.search._finish_report()
        elif report["status"] == "not_run":
            if self.clock() >= self.deadline:
                report["status"], report["stop_reason"] = "skipped_by_budget", "time_budget"
            elif self.state.best is None:
                report["status"] = "skipped_no_parent"


__all__ = ["IteratedGreedyRun"]
