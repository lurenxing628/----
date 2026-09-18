"""Four-operation real-SGS harness for iterated greedy context, capture and reference contracts."""
from __future__ import annotations

from dataclasses import replace
from functools import partial
from typing import Any, Callable, Optional

from core.algorithms import SortStrategy
from core.services.scheduler.run.optimizer_graph_ready_candidates import evaluate_graph_ready_candidate
from core.services.scheduler.run.optimizer_graph_ready_iterated_greedy import (
    IG_CANDIDATE_POLICY,
    IG_PROFILE_SLUG,
    _IteratedGreedySearch,
    _parent_from_candidate,
)
from core.services.scheduler.run.optimizer_graph_ready_iterated_greedy_contract import (
    IteratedGreedyLimits,
    new_iterated_greedy_report,
)
from core.services.scheduler.run.optimizer_graph_ready_profiles import (
    GRAPH_READY_V2_ITERATED_GREEDY_ORIGIN,
    graph_ready_v2_profiles,
)
from core.services.scheduler.run.optimizer_graph_ready_repair import EliteRepairPool
from core.services.scheduler.run.optimizer_graph_ready_repair_contract import EliteRepairLimits
from core.services.scheduler.run.optimizer_graph_ready_repair_decisions import RepairDecision
from core.services.scheduler.run.optimizer_graph_ready_v2_features import enrich_graph_ready_v2_metrics
from core.services.scheduler.run.optimizer_search_report import OptimizationSearchReportState
from tests._support.optimizer_graph_ready_benchmark import (
    BASE_BATCH_ORDER,
    OBJECTIVE_NAME,
    START_DT,
    ContinuousCalendar,
    _scheduler,
    graph_ready_benchmark_batches,
    graph_ready_benchmark_context,
    graph_ready_benchmark_operations,
)


class UncertifiedCalendar(ContinuousCalendar):
    """Same valid full-decode behaviour, deliberately without a checkpoint certificate."""


def ig_profile(profile):
    return replace(profile, slug=IG_PROFILE_SLUG, candidate_origin=GRAPH_READY_V2_ITERATED_GREEDY_ORIGIN,
                   candidate_policy=IG_CANDIDATE_POLICY)


class IGHarness:
    def __init__(self, *, flexible=False, uncertified_calendar=False, strict_mode=True):
        self.now = 0.0
        self.scheduler = _scheduler()
        if uncertified_calendar:
            self.scheduler.calendar = UncertifiedCalendar()
        self.operations = graph_ready_benchmark_operations()
        self.batches = graph_ready_benchmark_batches()
        self.context = graph_ready_benchmark_context()
        self.resource_pool = None
        if flexible:
            for operation in self.operations:
                operation.machine_id = operation.operator_id = None
            self.resource_pool = {"machines_by_op_type": {"OT-BENCH": ["M1", "M2"]},
                                  "operators_by_machine": {"M1": ["P1"], "M2": ["P2"]},
                                  "machines_by_operator": {"P1": ["M1"], "P2": ["M2"]}, "pair_rank": {}}
        self.metrics = enrich_graph_ready_v2_metrics(self.context["node_metrics_by_op_id"], operations=self.operations,
                                                     batches=self.batches, start_dt=START_DT, seed_results=[])
        profiles = graph_ready_v2_profiles(max_candidate_profiles=60)[0]
        self.profile = ig_profile(next(item for item in profiles if item.slug == "v2_edd"))
        self.other_profile = next(item for item in profiles if item.formula_slug != self.profile.formula_slug)
        self.evaluations, self.schedule_calls = [], []
        self.before_evaluate: Optional[Callable[..., Any]] = None
        self.after_evaluate: Optional[Callable[..., Any]] = None
        self.formal_evaluate = partial(
            evaluate_graph_ready_candidate, graph_ready_context=self.context, metrics_by_op_id=self.metrics,
            scheduler=self.scheduler, strict_mode=strict_mode, algo_ops_to_schedule=self.operations, batches=self.batches,
            strategy=SortStrategy.PRIORITY_FIRST, params={}, start_dt=START_DT, end_date=None, downtime_map={},
            seed_sr_list=[], dispatch_rule="slack", resource_pool=self.resource_pool, objective_name=OBJECTIVE_NAME,
            optimizer_algo_stats=None, schedule_fn=self.schedule, readiness_gate_enabled=False, version=0, clock=lambda: self.now)
        overrides = self.overrides("M1", "P1") if flexible else ()
        self.baseline = self.candidate((1, 2, 3, 4), overrides=overrides)
        self.state = OptimizationSearchReportState(algorithm_profile="graph_ready_v2_with_repair", seed=0,
                                                  time_budget_seconds=100, objective_name=OBJECTIVE_NAME,
                                                  started_at=0.0, strict_mode=strict_mode)
        self.state.mark_candidate_accepted(self.baseline, origin="baseline")
        self.pool = EliteRepairPool(limits=EliteRepairLimits(enabled=False), objective_name=OBJECTIVE_NAME,
                                   operations=self.operations, metrics_by_op_id=self.metrics, start_dt=START_DT, seed=0,
                                   best=self.baseline, report_state=self.state, graph_context=self.context,
                                   resource_pool=self.resource_pool)
        # Context/verification contracts keep a controlled incumbent; constructive starts are tested separately.
        limits = IteratedGreedyLimits(max_decodes=30, checkpoint_count=3, due_date_seed=False)
        self.report, self.attempts, self.trace = new_iterated_greedy_report(limits, objective_name=OBJECTIVE_NAME), [], []
        parent = _parent_from_candidate(self.baseline, operations=self.operations, graph_context=self.context)
        assert parent is not None
        self.search = _IteratedGreedySearch(
            limits=limits, parent=parent,
            profile=self.profile, pool=self.pool, evaluate=self.evaluate, metrics_by_op_id=self.metrics,
            start_dt=START_DT, seed=0, deadline=100.0, clock=lambda: self.now, t_begin=0.0, attempts=self.attempts,
            improvement_trace=self.trace, report_state=self.state, strict_mode=strict_mode, report=self.report,
            operations=self.operations, graph_context=self.context)
        self.search.best = self.baseline

    def overrides(self, machine, operator):
        return tuple((operation.id, machine, operator) for operation in self.operations)

    def schedule(self, scheduler, **kwargs):
        self.schedule_calls.append(kwargs)
        return scheduler.schedule(**kwargs)

    def evaluate(self, **kwargs):
        if self.before_evaluate is not None:
            self.before_evaluate(kwargs)
        candidate = self.formal_evaluate(**kwargs)
        if self.after_evaluate is not None:
            candidate = self.after_evaluate(kwargs, candidate)
        self.evaluations.append((kwargs, candidate))
        return candidate

    def candidate(self, order, *, overrides=(), batch_order=tuple(BASE_BATCH_ORDER), profile=None):
        return self.formal_evaluate(profile=profile or self.profile, order=list(batch_order), repair_order=list(batch_order),
                                    repair_decision=RepairDecision(batch_order, tuple(order), overrides))

    def start(self):
        self.search._start_reference()
        assert self.search.reference is not None
        self.evaluations.clear()
        self.schedule_calls.clear()
        return self.search.reference

    def assert_initial_incumbent(self):
        assert self.search.best is self.baseline
        assert self.state.accepted_candidates == 1 and self.report["improvements"] == 0
        assert self.report["accepted"] is False and self.trace == []


__all__ = ["IGHarness", "UncertifiedCalendar", "ig_profile"]
