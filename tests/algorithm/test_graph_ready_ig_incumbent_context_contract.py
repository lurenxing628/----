"""IG context handoff and verified-incumbent boundaries through real four-operation SGS decodes."""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from functools import partial

import pytest

from core.algorithms import SortStrategy
from core.infrastructure.errors import ValidationError
from core.services.scheduler.run.optimizer_graph_ready_candidates import evaluate_graph_ready_candidate
from core.services.scheduler.run.optimizer_graph_ready_iterated_greedy import (
    IG_CANDIDATE_POLICY,
    IG_PROFILE_SLUG,
    _BudgetExhausted,
    _IteratedGreedySearch,
    _parent_from_candidate,
)
from core.services.scheduler.run.optimizer_graph_ready_iterated_greedy_acceptance import profile_identity
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


class _UncertifiedCalendar(ContinuousCalendar):
    """Same valid full-decode behaviour, deliberately without a checkpoint certificate."""


def _ig_profile(profile):
    return replace(profile, slug=IG_PROFILE_SLUG, candidate_origin=GRAPH_READY_V2_ITERATED_GREEDY_ORIGIN,
                   candidate_policy=IG_CANDIDATE_POLICY)


class _Harness:
    def __init__(self, *, flexible=False, uncertified_calendar=False, strict_mode=True):
        self.now = 0.0
        self.scheduler = _scheduler()
        if uncertified_calendar:
            self.scheduler.calendar = _UncertifiedCalendar()
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
        self.profile = _ig_profile(next(item for item in profiles if item.slug == "v2_edd"))
        self.other_profile = next(item for item in profiles if item.formula_slug != self.profile.formula_slug)
        self.evaluations, self.schedule_calls = [], []
        self.before_evaluate = self.after_evaluate = None
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
        self.search = _IteratedGreedySearch(
            limits=limits, parent=_parent_from_candidate(self.baseline, operations=self.operations, graph_context=self.context),
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


def test_adoption_uses_new_batch_resources_and_profile_and_does_not_reuse_old_context_caches():
    harness = _Harness(flexible=True)
    reference = harness.start()
    old_trial = (1, 2, 4, 3)  # Equal-length final jobs: changed output, equal score, leaving a pending digest.
    assert harness.search._score_trial(old_trial, reference)[0] == reference.score
    assert old_trial in harness.search.scores and old_trial in harness.search.digests
    new_batch_order = tuple(reversed(BASE_BATCH_ORDER))
    new_overrides = harness.overrides("M2", "P2")
    new_profile = _ig_profile(harness.other_profile)
    incoming = harness.candidate((4, 3, 2, 1), overrides=new_overrides, batch_order=new_batch_order, profile=new_profile)
    harness.state.mark_candidate_accepted(incoming, origin="graph_ready_v2_repaired")
    harness.search.adopt_incumbent(incoming, harness.other_profile)
    assert harness.search.parent.batch_order == new_batch_order
    assert harness.search.parent.inherited == new_overrides
    assert profile_identity(harness.search.profile) == profile_identity(new_profile)
    decision = harness.evaluations[-1][0]["repair_decision"]
    assert decision.batch_order == new_batch_order and decision.resource_overrides == new_overrides
    assert old_trial not in harness.search.digests
    previous_calls = len(harness.schedule_calls)
    assert harness.search._score_trial(old_trial, harness.search.reference) is not None
    assert len(harness.schedule_calls) > previous_calls, "old-context score must not answer the new-resource trial"
    decoded = harness.search._decode_entry(reference.order)
    assert decoded is not None and decoded.resource_overrides == new_overrides
    assert all((row.machine_id, row.operator_id) == ("M2", "P2") for row in decoded.candidate["results"])
    assert all((operation.machine_id, operation.operator_id) == ("M2", "P2")
               for operation in harness.schedule_calls[-1]["operations"])
    actual_input = harness.schedule_calls[-1]
    assert actual_input["batch_order_override"] == list(new_batch_order)
    actual_profile = actual_input["strategy_params"]["graph_ready_profile"]
    assert actual_profile["formula_slug"] == new_profile.formula_slug
    assert actual_profile["formula_version"] == new_profile.formula_version
    assert actual_profile["feature_basis"] == new_profile.feature_basis


def test_resumed_improvement_is_published_only_after_the_formal_full_decode_matches():
    harness = _Harness()
    reference = harness.start()
    observed_validation = []

    def inspect(kwargs):
        if kwargs.get("decode_resume") is None:
            harness.assert_initial_incumbent()
            observed_validation.append(True)

    harness.before_evaluate = inspect
    score, feasible = harness.search._score_trial((1, 3, 4, 2), reference)
    assert feasible and score < reference.score
    assert [call.get("decode_resume") is not None for call in harness.schedule_calls] == [True, False]
    assert observed_validation == [True] and harness.report["validation_decodes"] == 1
    assert harness.search.best is harness.evaluations[-1][1]
    assert harness.state.accepted_candidates == 2 and harness.report["improvements"] == 1
    assert harness.report["accepted"] is True and len(harness.trace) == 1


@pytest.mark.parametrize("budget", ["decode", "time"])
def test_budget_exhausted_after_resumed_improvement_keeps_the_verified_incumbent(budget):
    harness = _Harness()
    reference = harness.start()
    if budget == "decode":
        harness.search.limits = replace(harness.search.limits, max_decodes=harness.report["decodes"] + 1)

    def exhaust(kwargs, candidate):
        if budget == "time" and kwargs.get("decode_resume") is not None:
            harness.now = harness.search.deadline
        return candidate

    harness.after_evaluate = exhaust
    with pytest.raises(_BudgetExhausted) as excinfo:
        harness.search._score_trial((1, 3, 4, 2), reference)
    assert excinfo.value.reason == ("decode_budget" if budget == "decode" else "time_budget")
    assert len(harness.schedule_calls) == 1 and harness.schedule_calls[0].get("decode_resume") is not None
    assert tuple(harness.evaluations[0][1]["score"]) < reference.score
    harness.assert_initial_incumbent()
    fingerprint = harness.pool.fingerprint(harness.evaluations[0][1]).output_fingerprint
    assert fingerprint not in harness.pool.seen_outputs and fingerprint not in harness.state.candidate_fingerprints


@pytest.mark.parametrize("corruption", ["digest", "score"])
def test_mismatching_full_validation_fails_loud_before_any_incumbent_publication(corruption):
    harness = _Harness(strict_mode=False)
    reference = harness.start()

    def corrupt(kwargs, candidate):
        if kwargs.get("decode_resume") is not None:
            return candidate
        damaged = dict(candidate)
        if corruption == "digest":
            rows = list(candidate["results"])
            rows[-1] = replace(rows[-1], end_time=rows[-1].end_time + timedelta(minutes=1))
            damaged["results"] = rows
        else:
            score = tuple(candidate["score"])
            damaged["score"] = score[:1] + (score[1] + 0.25,) + score[2:]
        return damaged

    harness.after_evaluate = corrupt
    with pytest.raises(ValidationError) as excinfo:
        harness.search._score_trial((1, 3, 4, 2), reference)
    assert excinfo.value.field == "graph_ready_iterated_greedy"
    assert excinfo.value.details["reason"] == "decode_checkpoint_equivalence_violation"
    assert [call.get("decode_resume") is not None for call in harness.schedule_calls] == [True, False]
    assert harness.search.checkpoints.equivalence_checks == 1
    harness.assert_initial_incumbent()
    assert len(harness.state.accepted_fingerprints) == 1
    assert len(harness.state.candidate_fingerprints) == len(harness.pool.seen_outputs) == 1


def test_unsupported_calendar_capture_reports_reason_and_continues_with_real_full_decodes():
    harness = _Harness(uncertified_calendar=True)
    harness.schedule_calls.clear()
    harness.search._start_reference()
    checkpoints = harness.search.checkpoints.summary()
    assert checkpoints["disabled_reason"] == "decode_checkpoint_unsupported_calendar"
    assert harness.report["checkpoint_capture_rejections"] == 1
    assert [call.get("decode_checkpoints") is not None for call in harness.schedule_calls] == [True, False]
    harness.schedule_calls.clear()
    assert harness.search._score_trial((1, 3, 4, 2), harness.search.reference) is not None
    assert len(harness.schedule_calls) == 1
    assert harness.schedule_calls[0].get("decode_resume") is None and harness.schedule_calls[0].get("decode_checkpoints") is None
    assert harness.search.checkpoints.resumed_decodes == 0
    assert harness.report["decodes"] == harness.search.checkpoints.full_decodes == 2


@pytest.mark.parametrize("failure", ["unsupported_input", "signature_mismatch"])
def test_other_checkpoint_failures_are_not_silently_retried_as_full_decodes(failure):
    harness = _Harness(strict_mode=False)
    if failure == "unsupported_input":
        harness.batches[BASE_BATCH_ORDER[0]].unsupported_value = object()
        action = harness.search._start_reference
    else:
        reference = harness.start()
        harness.batches[BASE_BATCH_ORDER[0]].quantity = 2
        action = lambda: harness.search._score_trial((1, 3, 4, 2), reference)
    harness.schedule_calls.clear()
    with pytest.raises(ValidationError) as excinfo:
        action()
    assert excinfo.value.field == "decode_checkpoint"
    assert excinfo.value.details["reason"] == "decode_checkpoint_" + failure
    assert len(harness.schedule_calls) == 1
    assert harness.search.checkpoints.disabled_reason is None
    assert harness.report["checkpoint_capture_rejections"] == 0
    harness.assert_initial_incumbent()


def test_stagnation_restarts_the_complete_resource_context_and_reuses_its_checkpoint(monkeypatch):
    from core.services.scheduler.run.optimizer_graph_ready_iterated_greedy_acceptance import SolutionPool

    harness = _Harness(flexible=True)
    first = harness.start()
    search = harness.search
    first_context = first.decision_key()
    second_overrides = harness.overrides("M2", "P2")
    search._set_parent(replace(search.parent, inherited=second_overrides), first.profile)
    second = search._decode_entry(first.order)
    assert second is not None and first.decoded_order and second.decoded_order
    assert first.order == second.order and first.checkpoints and second.checkpoints
    assert second.decision_key() != first_context

    # Only two complete contexts are eligible; choosing the other one is independent of pool RNG.
    search.solution_pool = SolutionPool(2)
    search.solution_pool.refresh(first)
    search.solution_pool.refresh(second)
    search._activate_entry(first)
    search.reference = first
    search.limits = replace(search.limits, stagnation_iterations=len(search.generators), pool_size=2)
    harness.report["pool"].update(size=2, stagnation_iterations=search.limits.stagnation_iterations)
    initial_sizes = {generator.name: generator.size() for generator in search.generators}
    for generator in search.generators:
        # A no-move neighbourhood produces a completed, non-improving iteration.
        monkeypatch.setattr(generator, "select", lambda *args, **kwargs: ())

    for completed in range(1, search.limits.stagnation_iterations + 1):
        search.iterate_once()
        assert search.reference.decision_key() == first_context
        assert search.non_improving == completed
        assert harness.report["pool"]["restarts"] == 0
    calls_before_restart = {generator.name: generator.calls for generator in search.generators}
    assert all(calls_before_restart.values())
    assert all(generator.size() > initial_sizes[generator.name] for generator in search.generators)
    assert harness.report["iterations"] == search.limits.stagnation_iterations

    primary_rng_before_restart = search.rnd.getstate()
    restarted = search._reference_for_iteration()
    assert search.rnd.getstate() == primary_rng_before_restart
    assert restarted.decision_key() == second.decision_key()
    assert search.reference is restarted
    assert search.parent.batch_order == second.batch_order
    assert search.parent.inherited == second_overrides
    assert profile_identity(search.profile) == profile_identity(second.profile)
    assert search.non_improving == search.idle_iterations == search.rejected_iterations == 0
    assert harness.report["pool"]["restarts"] == 1
    assert {generator.name: generator.calls for generator in search.generators} == calls_before_restart
    assert {generator.name: generator.size() for generator in search.generators} == initial_sizes

    trial = second.order[:-2] + tuple(reversed(second.order[-2:]))
    harness.schedule_calls.clear()
    harness.evaluations.clear()
    scored = search._score_trial(trial, restarted)
    assert scored is not None and scored[1]
    trial_call = harness.schedule_calls[0]
    resumed_from = trial_call.get("decode_resume")
    assert resumed_from is not None and any(resumed_from is item for item in restarted.checkpoints)
    assert trial_call["batch_order_override"] == list(second.batch_order)
    assert all((operation.machine_id, operation.operator_id) == ("M2", "P2")
               for operation in trial_call["operations"])
    assert all((row.machine_id, row.operator_id) == ("M2", "P2")
               for row in harness.evaluations[0][1]["results"])
    verified = search._decode_entry(trial)
    assert verified is not None and verified.score == scored[0]
    assert verified.resource_overrides == second_overrides
    assert [call.get("decode_resume") is not None for call in harness.schedule_calls] == [True, False]
    assert harness.search.checkpoints.equivalence_checks >= 1


def test_initial_pool_selection_uses_the_best_score_layer_without_consuming_search_rng():
    from types import SimpleNamespace

    harness = _Harness(flexible=True)
    good_order = (1, 3, 4, 2)
    first_overrides = harness.overrides("M1", "P1")
    second_overrides = harness.overrides("M2", "P2")
    starting = dict(harness.candidate(good_order, overrides=first_overrides),
                    candidate_origin="graph_ready_v2_generated")
    equally_good_elite = dict(harness.candidate(good_order, overrides=second_overrides),
                              candidate_origin="graph_ready_v2_repaired")
    worse_elite = harness.baseline
    assert tuple(starting["score"]) == tuple(equally_good_elite["score"]) < tuple(worse_elite["score"])
    harness.search.best = starting
    harness.state.mark_candidate_accepted(starting, origin=starting["candidate_origin"])
    harness.pool.elites = [{"candidate": worse_elite, "profile": harness.profile},
                          {"candidate": equally_good_elite, "profile": harness.profile}]
    offered_layers = []

    def choose_last(entries):
        offered_layers.append(tuple(entry.score for entry in entries))
        return entries[-1]

    # Deterministic pool selection chooses the other top-quality source; no random seed is assumed.
    harness.search.pool_rnd = SimpleNamespace(choice=choose_last)
    primary_rng_before = harness.search.rnd.getstate()
    harness.search._start_reference()

    assert harness.search.rnd.getstate() == primary_rng_before
    assert offered_layers == [(tuple(starting["score"]), tuple(equally_good_elite["score"]))]
    assert harness.search.reference.resource_overrides == second_overrides
    assert harness.search.parent.inherited == second_overrides
    assert harness.search.reference.score == tuple(equally_good_elite["score"])
    assert harness.report["parent_origin"] == equally_good_elite["candidate_origin"]
    assert harness.report["parent_score"] == list(equally_good_elite["score"])
    assert harness.report["parent_order_score"] == list(harness.search.reference.score)
    assert harness.report["parent_order_consistent"] is True
    assert harness.report["starting_incumbent_origin"] == starting["candidate_origin"]
    assert harness.report["starting_incumbent_score"] == list(starting["score"])
    assert harness.search.best is starting
