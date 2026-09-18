"""The iterated greedy stage: start, bounded trial tasks, finish and publish."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from .optimizer_graph_ready_iterated_greedy import (
    _BudgetExhausted,
    _IteratedGreedySearch,
    _parent_from_candidate,
    _publish,
    _stage_deadline,
    admit_parent_decode,
)
from .optimizer_graph_ready_iterated_greedy_contract import IteratedGreedyLimits, new_iterated_greedy_report
from .optimizer_graph_ready_iterated_greedy_iteration import IGIteration
from .optimizer_graph_ready_iterated_greedy_large import iteration_for, search_type_for
from .optimizer_graph_ready_iterated_greedy_local import LOCAL_BUDGET_REASON
from .optimizer_graph_ready_profiles import GraphReadyWeightProfile


class IteratedGreedyRun:
    """Yield between trials while retaining an iteration's parent context and partial reinsertion."""

    def __init__(self, *, limits: IteratedGreedyLimits, state: Any,
                 parent_profile: Callable[[Optional[Dict[str, Any]]], Optional[GraphReadyWeightProfile]],
                 pool: Any, evaluate: Callable[..., Dict[str, Any]], operations: List[Any], graph_context: Dict[str, Any],
                 metrics_by_op_id: Dict[int, Dict[str, Any]], objective_name: str, start_dt: Any, seed: int, deadline: float,
                 clock: Callable[[], float], t_begin: float, attempts: List[Dict[str, Any]],
                 improvement_trace: List[Dict[str, Any]], report_state: Any, strict_mode: bool) -> None:
        self.limits = limits
        self.state = state
        self.parent_profile = parent_profile
        self.pool = pool
        self.evaluate = evaluate
        self.operations = operations
        self.graph_context = graph_context
        self.metrics_by_op_id = metrics_by_op_id
        self.start_dt = start_dt
        self.seed = int(seed)
        self.deadline = deadline
        self.clock = clock
        self.t_begin = t_begin
        self.attempts = attempts
        self.improvement_trace = improvement_trace
        self.report_state = report_state
        self.strict_mode = strict_mode
        self.report = new_iterated_greedy_report(limits, objective_name=objective_name)
        self.search: Optional[_IteratedGreedySearch] = None
        self.stopped = not limits.enabled
        self.started_at: Optional[float] = None
        self.last_task_end: Optional[float] = None
        self.task_seconds = 0.0
        self.finished = False
        self.iteration: Optional[IGIteration] = None
        self.pending_adoption: Optional[Dict[str, Any]] = None

    def available(self) -> bool:
        if self.stopped or self.state.best is None:
            return False
        deadline = self.deadline if self.search is None else self.search.deadline
        return self.clock() < deadline

    def step(self) -> None:
        started = self.clock()
        try:
            if self.search is None:
                self._start(started)
            else:
                self._advance()
        except _BudgetExhausted as exc:
            if exc.reason == LOCAL_BUDGET_REASON:
                self.report["local_search"]["local_timeouts"] += 1
                self.iteration = None
            else:
                self.report["stop_reason"] = exc.reason
                self.stopped = True
        finally:
            if self.search is not None:
                self.state.best = self.search.best
            finished = self.clock()
            self.task_seconds += max(finished - started, 0.0)
            self.last_task_end = finished

    def _start(self, started: float) -> None:
        self.started_at = started
        best = self.state.best
        parent = _parent_from_candidate(best, operations=self.operations, graph_context=self.graph_context)
        profile = self.parent_profile(best)
        if parent is None or profile is None:
            self.report["status"] = "skipped_no_parent"
            self.stopped = True
            return
        self.report["parent_origin"] = str((best or {}).get("candidate_origin") or "baseline")
        self.report["parent_score"] = list((best or {}).get("score") or [])
        self.search = search_type_for(parent)(
            limits=self.limits, parent=parent, profile=profile, pool=self.pool, evaluate=self.evaluate,
            metrics_by_op_id=self.metrics_by_op_id, start_dt=self.start_dt, seed=self.seed,
            deadline=_stage_deadline(self.limits, started=started, deadline=self.deadline), clock=self.clock,
            t_begin=self.t_begin, attempts=self.attempts, improvement_trace=self.improvement_trace,
            report_state=self.report_state, strict_mode=self.strict_mode, report=self.report,
            operations=self.operations, graph_context=self.graph_context)
        self.search.best = best
        admit_parent_decode(best, clock=self.clock, deadline=self.search.deadline, report=self.report)
        self.search._start_reference()

    def _advance(self) -> None:
        search = self.search
        if search is None:
            raise RuntimeError("Iterated greedy trial advanced before its search was created.")
        if self.state.best is not search.best:
            # Share the improved incumbent immediately, but finish the trial's fixed decode context.
            self.pending_adoption = self.state.best
            search.best = self.state.best
        if self.iteration is None:
            if self.report["iterations"] >= self.limits.max_iterations:
                self.report["stop_reason"] = "max_iterations"
                self.stopped = True
                return
            if self.pending_adoption is self.state.best and self.pending_adoption is not None:
                search.adopt_incumbent(self.state.best, self.parent_profile(self.state.best))
            self.pending_adoption = None
            self.iteration = iteration_for(search, IGIteration)
        if not self.iteration.step():
            self.iteration = None

    def finish(self) -> None:
        if self.finished:
            return
        self.finished = True
        report = self.report
        if self.iteration is not None:
            self.iteration.close()
            self.iteration = None
        self._finish_status(report)
        report["runtime_ms"] = int(self.task_seconds * 1000)
        last = self.last_task_end if self.last_task_end is not None else self.clock()
        stage_deadline = self.search.deadline if self.search is not None else self.deadline
        report["deadline_overrun_ms"] = max(int((last - stage_deadline) * 1000), 0) if self.started_at is not None else 0
        report["best_score"] = list((self.state.best or {}).get("score") or [])
        _publish(report, report_state=self.report_state, attempts=self.attempts)
        if self.report_state is not None and last >= self.deadline:
            self.report_state.mark_deadline_reached()

    def _finish_status(self, report: Dict[str, Any]) -> None:
        if self.search is not None:
            if report["stop_reason"] is None:
                report["stop_reason"] = "time_budget" if self.clock() >= self.search.deadline else "rotation_ended"
            self.search._finish_report()
        elif self.limits.enabled and report["status"] == "not_run":
            if self.clock() >= self.deadline:
                report["status"], report["stop_reason"] = "skipped_by_budget", "time_budget"
            elif self.state.best is None:
                report["status"] = "skipped_no_parent"


class _BestHolder:
    def __init__(self, best: Optional[Dict[str, Any]]) -> None:
        self.best = best


def run_graph_ready_iterated_greedy(
    *, limits: IteratedGreedyLimits, best: Optional[Dict[str, Any]], parent_profile: Optional[GraphReadyWeightProfile],
    pool: Any, evaluate: Callable[..., Dict[str, Any]], operations: List[Any], graph_context: Dict[str, Any],
    metrics_by_op_id: Dict[int, Dict[str, Any]], objective_name: str, start_dt: Any, seed: int, deadline: float,
    clock: Callable[[], float], t_begin: float, attempts: List[Dict[str, Any]], improvement_trace: List[Dict[str, Any]],
    report_state: Any, strict_mode: bool,
) -> Optional[Dict[str, Any]]:
    """One-shot form of the stage: run it alone until it stops (tests and direct callers)."""
    state = _BestHolder(best)
    run = IteratedGreedyRun(
        limits=limits, state=state, parent_profile=lambda _best: parent_profile, pool=pool, evaluate=evaluate,
        operations=operations, graph_context=graph_context, metrics_by_op_id=metrics_by_op_id,
        objective_name=objective_name, start_dt=start_dt, seed=seed, deadline=deadline, clock=clock, t_begin=t_begin,
        attempts=attempts, improvement_trace=improvement_trace, report_state=report_state, strict_mode=strict_mode)
    while run.available():
        run.step()
    run.finish()
    return state.best


__all__ = ["IteratedGreedyRun", "run_graph_ready_iterated_greedy"]
