"""Solver process evidence retains late work and separates adoption from improvement."""

from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest

from core.algorithm_contracts.types import ScheduleSummary
from core.algorithms import GreedyScheduler, SortStrategy
from core.algorithms.evaluation import ScheduleMetrics, objective_score
from core.algorithms.evaluation_completion import BatchCompletion
from core.errors import ValidationError
from core.models.objective import target_objectives_for
from core.models.schedule_config_runtime import default_snapshot_values
from core.models.schedule_config_runtime_snapshot import snapshot_from_values
from core.models.workbench_run_compute import CandidateRunComputation
from core.services.scheduler.contracts.optimizer_public_search_report import project_search_report
from core.services.scheduler.run import schedule_optimizer_steps
from core.services.scheduler.run.optimizer.candidate_fingerprint import CandidateFingerprint
from core.services.scheduler.run.optimizer.graph.iterated_greedy import _IteratedGreedySearch
from core.services.scheduler.run.optimizer.graph.iterated_greedy_incumbent import IGIncumbentTracker
from core.services.scheduler.run.optimizer.graph.reporting import append_graph_trace
from core.services.scheduler.run.optimizer.graph.stages import _accept_candidate, _candidate_should_replace_best
from core.services.scheduler.run.optimizer.graph_ready_profiles import default_weight_profiles
from core.services.scheduler.run.optimizer.grasp_ig_candidates import _append_trace
from core.services.scheduler.run.optimizer.local_search_round import _record_improvement
from core.services.scheduler.run.optimizer.neighborhood_moves import NeighborhoodMove
from core.services.scheduler.run.optimizer.process_evidence import sample_elapsed_points
from core.services.scheduler.run.optimizer.search_report import OptimizationSearchReportState
from core.services.scheduler.run.optimizer.search_state import OptimizerSearchState
from core.services.scheduler.run.optimizer.shared_archive import SharedScheduleArchive
from core.services.scheduler.run.optimizer.shared_budget import SharedSearchBudget
from core.services.scheduler.run.optimizer.shared_decode import SharedDecodeSession
from core.services.scheduler.run.optimizer.shared_process import build_shared_process
from core.services.scheduler.run.optimizer.signature_support import schedule_with_optional_strict_mode
from core.services.scheduler.run.optimizer.step_report_hooks import _append_multi_start_trace, _append_ortools_trace
from core.services.scheduler.run.schedule_candidate_plan import CandidateComparisonOutcome, CandidatePlan
from core.services.scheduler.run.schedule_payload_contract import ValidatedSchedulePayload
from core.services.scheduler.run.schedule_shared_optimizer import _GoalView, _SharedSearch, _WarmStartStage
from core.services.workbench.run.result_preparation import _prepare_result_artifacts
from tests._support.optimizer_graph_ready_benchmark import (
    START_DT,
    BenchmarkClock,
    ContinuousCalendar,
    graph_ready_benchmark_batches,
    graph_ready_benchmark_operations,
)
from tests._support.shared_schedule_archive import _observe_decoded, _register_decode
from tests.workbench.legacy_run_archive_support import load_legacy_process_evidence


def _candidate(primary, *, complete=True, objective="min_tardiness"):
    completion = BatchCompletion(
        expected_operation_count=3,
        missing_operation_count=0 if complete else 1,
        unexpected_result_count=0,
        complete_batch_count=2 if complete else 1,
        incomplete_batch_ids=() if complete else ("B1",),
        partial_batch_ids=() if complete else ("B1",),
        failure_detail_count=0 if complete else 1,
        failure_batch_ids=() if complete else ("B1",),
        explained=not complete,
    )
    metrics = ScheduleMetrics(
        overdue_count=int(primary > 0),
        total_tardiness_hours=float(primary),
        weighted_tardiness_hours=float(primary),
        makespan_hours=10.0,
        changeover_count=0,
        completion=completion,
    )
    failed = 0 if complete else 1
    candidate = {"results": [], "summary": ScheduleSummary(failed_ops=failed, success=complete, total_ops=3,
                                                      scheduled_ops=3 - failed, warnings=[], errors=[], duration_seconds=0.0),
            "score": (float(failed),) + objective_score(objective, metrics), "metrics": metrics,
            "strategy": SortStrategy.PRIORITY_FIRST, "params": {}, "algo_stats": {},
            "dispatch_mode": "sgs", "dispatch_rule": "cr", "order": ["B1", "B2"]}
    archive = SharedScheduleArchive(objective, target_objectives_for(objective), (1, 2, 3), ("B1", "B2"))
    return _register_decode(archive, candidate)


def test_warmstart_keeps_optional_solver_failure_but_propagates_real_candidate_observer(monkeypatch):
    values = default_snapshot_values()
    values.update(sort_strategy="fifo", dispatch_mode="batch_order", ortools_enabled="yes", auto_assign_enabled="no")
    cfg = snapshot_from_values(values)
    operations, batches = graph_ready_benchmark_operations(), graph_ready_benchmark_batches()
    scheduler = GreedyScheduler(calendar_service=ContinuousCalendar(), config_service=cfg)
    clock = BenchmarkClock()
    started_at = clock()
    deadline = started_at + 10.0
    targets = target_objectives_for("min_overdue")
    archive = SharedScheduleArchive("min_overdue", targets, (op.id for op in operations), batches)
    budget = SharedSearchBudget(clock=clock, started_at=started_at, deadline=deadline,
                                target_objectives=targets, configured_seconds=10)
    shared = _SharedSearch(archive=archive, clock=clock, started_at=started_at, budget=budget)
    seed_results, downtime_map = [], {}
    session = SharedDecodeSession(
        archive=archive, budget=budget, scheduler=scheduler, operations=operations, batches=batches,
        seed_results=seed_results, downtime_map=downtime_map, resource_pool=None,
        clock=clock, started_at=started_at, deadline=deadline, event_sink=shared.record_event,
        schedule_fn=schedule_with_optional_strict_mode, start_dt=START_DT,
    )
    shared.decode_session = session
    decode_inputs = dict(
        scheduler=scheduler, strict_mode=True, algo_ops_to_schedule=operations, batches=batches,
        start_dt=START_DT, end_date=None, downtime_map=downtime_map, seed_sr_list=seed_results, dispatch_mode_cfg="batch_order",
        dispatch_rule_cfg="slack", resource_pool=None, objective_name="min_overdue", optimizer_algo_stats={},
        readiness_gate_enabled=False, graph_ready_context=None, decode_session=session,
    )
    best = schedule_optimizer_steps._evaluate_ortools_candidate(
        **decode_inputs, strategy=SortStrategy.FIFO, params={}, ort_order=list(batches),
    )
    shared.observe("min_overdue", candidate=best, origin="initial", verified=True, elapsed_ms=0)
    assert best["summary"].success and scheduler._decode_invocations == 1
    solver_failure, observer_failure = RuntimeError("optional order unavailable"), RuntimeError("archive observer failed")
    solver_results = [solver_failure, list(reversed(batches))]
    solver_calls = []
    solver_finished_at = None

    def solve_order(**kwargs):
        solver_calls.append(kwargs)
        result = solver_results.pop(0)
        if isinstance(result, Exception):
            raise result
        if solver_finished_at is not None:
            clock.now = solver_finished_at
        return result

    monkeypatch.setattr(schedule_optimizer_steps, "_solve_ortools_order", solve_order)
    warmstart_inputs = dict(**decode_inputs, algo_mode="improve", cfg=cfg, strategy_enum=SortStrategy.FIFO,
                           deadline=deadline, best=best, t_begin=started_at, logger=None, clock=clock)
    optional_report = OptimizationSearchReportState(
        algorithm_profile="improve", seed=0, time_budget_seconds=10, objective_name="min_overdue", started_at=0.0,
    )
    optional_attempts = []
    assert schedule_optimizer_steps._run_ortools_warmstart(
        **warmstart_inputs, attempts=optional_attempts, improvement_trace=[], search_report_state=optional_report,
    ) is best
    assert scheduler._decode_invocations == 1
    assert optional_report.optional_warmstart_failed
    assert optional_report.rejection_summary == {"optional_warmstart_failed": 1}
    assert optional_attempts[0]["origin"]["message"] == str(solver_failure)

    observed = []

    def observe(candidate, **kwargs):
        assert candidate["summary"].success and candidate["summary"].failed_ops == 0
        assert {row.op_id for row in candidate["results"]} == {op.id for op in operations}
        observed.append(candidate)
        raise observer_failure

    report = OptimizationSearchReportState(
        algorithm_profile="improve", seed=0, time_budget_seconds=10, objective_name="min_overdue", started_at=0.0,
        candidate_observer=observe, candidate_clock=lambda: 0.0,
    )
    attempts = []
    with pytest.raises(RuntimeError) as raised:
        schedule_optimizer_steps._run_ortools_warmstart(
            **warmstart_inputs, attempts=attempts, improvement_trace=[], search_report_state=report,
        )
    assert raised.value is observer_failure
    assert scheduler._decode_invocations == 2 and len(observed) == 1
    assert not report.optional_warmstart_failed and report.rejection_summary == {} and attempts == []
    shared.observe("min_overdue", candidate=observed[0], origin="validated_warmstart", verified=True, elapsed_ms=0)

    # Shared ordering admission records one real action, before a decode request exists.
    shared_best = schedule_optimizer_steps._evaluate_ortools_candidate(
        **decode_inputs, strategy=SortStrategy.FIFO, params={}, ort_order=list(batches),
    )
    assert shared_best["decode_receipt"]["execution_kind"] == "decision_reused"
    assert session.actual_decoder_calls == scheduler._decode_invocations == 2
    original_best = (tuple(shared_best["results"]), shared_best["summary"], tuple(shared_best["score"]))
    shared_report = OptimizationSearchReportState(
        algorithm_profile="unified_schedule_optimizer", seed=0, time_budget_seconds=10,
        objective_name="min_overdue", started_at=started_at, candidate_clock=clock,
    )
    view = _GoalView("min_overdue", OptimizerSearchState(shared_archive=archive), shared_report)
    shared.views[view.objective] = view
    shared_inputs = dict(warmstart_inputs, deadline=deadline, clock=clock, t_begin=started_at,
                         best=shared_best, decode_session=session)
    for remaining, reason, solver_finishes in ((1.03, "estimated_decode_cost", False),
                                               (0.5, "time_budget", False), (5.0, "time_budget", True)):
        shared_attempts = []
        before_budget = budget.summary()
        before_session = session.stats()
        before_events, before_solver, before_scheduler = len(shared.events), len(solver_calls), scheduler._decode_invocations
        if solver_finishes:
            solver_results.append(list(batches))
            solver_finished_at = deadline
        clock.now = deadline - remaining
        stage = _WarmStartStage(
            run=lambda: schedule_optimizer_steps._run_ortools_warmstart(
                **shared_inputs, attempts=shared_attempts, improvement_trace=[], search_report_state=shared_report,
            ), clock=clock, deadline=deadline,
        )
        assert not shared.run_action(view, stage)
        assert len(solver_calls) == before_solver + int(solver_finishes)
        assert scheduler._decode_invocations == before_scheduler
        assert (tuple(shared_best["results"]), shared_best["summary"], tuple(shared_best["score"])) == original_best
        assert session.stats() == before_session and len(shared.events) == before_events
        assert len(shared_attempts) == 1 and shared_attempts[0]["reason"] == reason
        assert shared_attempts[0]["request_id"] is None and shared_attempts[0]["decode_receipt"] is None
        action = shared.actions[-1]
        assert action["skip_reason"] == reason and action["new_decisions"] == action["reused_decisions"] == 0
        assert action["evaluation_count"] == action["verified_evaluation_count"] == 0
        after_budget = budget.summary()
        assert after_budget["admission_skips"] == dict(
            before_budget["admission_skips"], **{reason: before_budget["admission_skips"].get(reason, 0) + 1})
        assert after_budget["actual_decoder_count"] == before_budget["actual_decoder_count"]
        if solver_finishes:
            assert shared_report.deadline_reached

def test_all_trace_producers_preserve_improvement_after_two_hundred_points():
    candidate = _candidate(0.0)
    profile = default_weight_profiles(max_weight_profiles=1)[0][0]
    move = NeighborhoodMove(schema_version=1, neighborhood_name="tardy_window", move_kind="swap",
                            input_scope="batch_order", batch_order=("B1", "B2"), changed_decision_count=2,
                            expected_effect="减少拖期")
    def clock():
        return 5.0
    writers = (
        lambda trace: _append_ortools_trace(improvement_trace=trace, candidate=candidate, now=clock, t_begin=0.0),
        lambda trace: _append_multi_start_trace(improvement_trace=trace, candidate=candidate, strategy_key="priority_first",
                                               dispatch_mode="sgs", dispatch_rule="cr", now=clock, t_begin=0.0),
        lambda trace: append_graph_trace(improvement_trace=trace, candidate=candidate, profile=profile, clock=clock,
                                        t_begin=0.0),
        lambda trace: _record_improvement(candidate=candidate, move=move, attempts=[], improvement_trace=trace,
                                          clock=clock, t_begin=0.0),
        lambda trace: _append_trace(improvement_trace=trace, candidate=candidate, origin="grasp", index=210,
                                    now=clock, t_begin=0.0),
    )
    for write in writers:
        trace = [{"elapsed_ms": index, "score": [0.0, 100.0]} for index in range(201)]
        write(trace)
        assert len(trace) == 202
        assert trace[-1]["elapsed_ms"] == 5000
        assert trace[-1]["score"] == list(candidate["score"])
        assert trace[-1]["metrics"]["total_tardiness_hours"] == 0.0


class _Clock:
    def __init__(self):
        self.value, self.reads = 0.0, 0

    def __call__(self):
        self.reads += 1
        return self.value


def _identity(name):
    return CandidateFingerprint(schema_version=2, fingerprint_scope="decoded_output", objective_name="min_tardiness",
        candidate_id=0, output_key=(name,), parent_candidate_id=None,
        same_as_parent=False, same_as_seen=False, fingerprint_changed=True)


def test_candidate_contents_define_duplicates_and_diagnostic_sequences_preserve_legacy_reports():
    report = OptimizationSearchReportState(algorithm_profile="graph", seed=0, time_budget_seconds=2,
        objective_name="min_tardiness", started_at=0.0)
    baseline = _candidate(20.0)
    first = report.mark_candidate_evaluated(baseline, origin="baseline")
    report.mark_candidate_accepted(baseline, origin="baseline", fingerprint=first)
    duplicate = _candidate(20.0)
    duplicate.update(strategy=SortStrategy.DUE_DATE_FIRST, order=["B2", "B1"], params={"different": True})
    repeated = report.mark_candidate_evaluated(duplicate, origin="multi_start")
    assert repeated.candidate_id != first.candidate_id
    assert repeated.same_as_seen and repeated.same_as_parent
    assert repeated.parent_candidate_id == first.candidate_id
    assert len(report.candidate_fingerprints) == 1
    # The saved content remains immutable when the mutable source metrics change.
    baseline["metrics"].total_tardiness_hours = 999.0
    changed = report.mark_candidate_evaluated(_candidate(8.0), origin="local_search")
    assert changed.output_key != first.output_key and not changed.same_as_seen
    event = {"acceptance_name": "improve_only", "accepted": True}
    report.mark_candidate_accepted(_candidate(8.0), origin="local_search", acceptance_event=event, fingerprint=changed)
    payload = report.finalize(runtime_ms=1, attempts=[], improvement_trace=[])
    assert payload["schema_version"] == 2 and payload["best_output_changed"] and payload["improved"]
    assert payload["initial_candidate_id"] == first.candidate_id and payload["best_candidate_id"] == changed.candidate_id
    assert "fingerprint_events" not in payload and "output_key" not in payload["candidate_events"][0]
    public, diagnostics = project_search_report(payload)
    assert public["distinct_candidates"] == 2 and public["best_output_changed"]
    assert diagnostics["best_candidate_id"] == changed.candidate_id
    legacy = {"schema_version": 1, "best_fingerprint_changed": True, "initial_fingerprint": "saved-before-P8",
              "fingerprint_events": [{"output_fingerprint": "saved-before-P8"}]}
    old_public, old_diagnostics = project_search_report(legacy)
    assert old_public["best_fingerprint_changed"] is True
    assert old_diagnostics["initial_fingerprint"] == "saved-before-P8"
    assert old_diagnostics["fingerprint_events"] == legacy["fingerprint_events"]
    invalid = _candidate(1.0)
    invalid["score"] = (False, 1.0)
    with pytest.raises(ValidationError):
        report.mark_candidate_evaluated(invalid, origin="local_search")


def test_equal_elapsed_buckets_retain_late_best_and_all_three_milestones():
    # Explicit progress events exercise the production sampler, independently of a writer.
    raw_points, raw_times = [], []
    for index in range(321):
        candidate = _candidate(400 - index, complete=index >= 210)
        flags = ["first_valid"] if index == 0 else ["first_expected_complete"] if index == 210 else ["strict_improvement"]
        raw_points.append({
            "event_index": index + 1, "elapsed_ms": (index + 1) * 1000,
            "score": list(candidate["score"]), "primary_value": float(400 - index), "flags": flags,
            "completion": {"missing_operation_count": 0 if index >= 210 else 1}, "segment": int(index >= 210),
        })
        raw_times.append((index + 1, (index + 1) * 1000))
    raw_points.append({**deepcopy(raw_points[-1]), "event_index": 322, "elapsed_ms": 400000, "flags": ["final"]})
    original = deepcopy(raw_points)
    points, sampling = sample_elapsed_points(raw_points, elapsed_ms=400000)
    assert sampling["event_total_count"] == 322
    assert sampling["retained_point_count"] == len(points) <= 200
    assert sampling["policy"] == "elapsed_equal_width_bucket_end_best_v1"
    milestones = {flag: point for point in points for flag in point["flags"]
                  if flag in ("first_valid", "first_expected_complete", "final")}
    assert milestones["first_valid"]["event_index"] == 1
    assert milestones["first_valid"]["completion"]["missing_operation_count"] == 1
    assert milestones["first_expected_complete"]["event_index"] == 211
    assert milestones["first_expected_complete"]["completion"]["missing_operation_count"] == 0
    assert milestones["first_valid"]["segment"] != milestones["first_expected_complete"]["segment"]
    assert milestones["final"]["event_index"] == 322
    assert milestones["final"]["elapsed_ms"] == 400000
    assert milestones["final"]["score"] == list(candidate["score"])
    assert milestones["final"]["primary_value"] == 80.0
    assert any(point["event_index"] == 321 and point["primary_value"] == 80.0 for point in points)

    # Independent bucket oracle: each slot retains the last actual incumbent event.
    slots = 197
    bucket_ends = {}
    for event_index, elapsed in raw_times + [(322, 400000)]:
        bucket_ends[min(elapsed * slots // 400000, slots - 1)] = event_index
    assert {point["event_index"] for point in points} == {1, 211, 322} | set(bucket_ends.values())
    assert [point["elapsed_ms"] for point in points] == sorted(point["elapsed_ms"] for point in points)
    assert raw_points == original
    points[-1]["score"][1] = -999.0
    points[-1]["flags"].append("changed-output")
    assert raw_points == original
    raw_points[-1]["score"][1] = -888.0
    assert points[-1]["score"][1] == -999.0 and original[-1]["score"][1] == 80.0

    immediate = [{"elapsed_ms": 0, "flags": ["first_valid", "first_expected_complete", "final"]}]
    merged, zero_sampling = sample_elapsed_points(immediate, elapsed_ms=0)
    assert len(merged) == 1
    assert merged[0]["elapsed_ms"] == 0
    assert {"first_valid", "first_expected_complete", "final"} <= set(merged[0]["flags"])
    assert zero_sampling["bucket_width_ms"] == 0.0


def test_adoption_is_separate_from_strict_improvement_and_revisited_stages_do_not_connect():
    # Use the actual GraphReady decision recorder: accepting a tie keeps a zero change,
    # and an incumbent snapshot stays intact after its original metrics change.
    recorded_clock = _Clock()
    reporter = OptimizationSearchReportState(algorithm_profile="graph", seed=0, time_budget_seconds=2,
        objective_name="min_tardiness", started_at=0.0, candidate_clock=recorded_clock)
    profile = default_weight_profiles(max_weight_profiles=1)[0][0]
    attempts = []
    incumbent = _candidate(20.0)
    incumbent["runtime_ms"] = 20
    recorded_clock.value = 0.125
    identity = _identity("first")
    assert _candidate_should_replace_best(incumbent, profile=profile, best=None, attempts=attempts,
        search_report_state=reporter, fingerprint=identity, clock=recorded_clock, t_begin=0.0)
    _accept_candidate(incumbent, profile=profile, incumbent=None, version=0,
                      search_report_state=reporter, fingerprint=identity)
    assert attempts[0]["elapsed_ms"] == 125 and attempts[0]["event_index"] is None
    assert attempts[0]["accepted"] is True and attempts[0]["strict_improved"] is None
    assert attempts[0]["comparison"]["state"] == "no_reference"
    assert attempts[0]["comparison"]["metric_deltas"] is None
    tied = _candidate(20.0)
    tied["runtime_ms"] = 10
    recorded_clock.value = 0.25
    assert _candidate_should_replace_best(tied, profile=profile, best=incumbent, attempts=attempts,
        search_report_state=reporter, fingerprint=_identity("tie"), clock=recorded_clock, t_begin=0.0)
    assert attempts[-1]["accepted"] is True and attempts[-1]["strict_improved"] is False
    assert attempts[-1]["elapsed_ms"] == 250 and attempts[-1]["event_index"] is None
    assert attempts[-1]["comparison"]["reference_score"] == list(incumbent["score"])
    assert attempts[-1]["comparison"]["metric_deltas"]["total_tardiness_hours"] == 0.0
    assert recorded_clock.reads == 2  # Each actual attempt reads its explicit clock once.
    incumbent["metrics"].total_tardiness_hours = 999.0
    assert attempts[-1]["comparison"]["reference_metrics"]["total_tardiness_hours"] == 20.0
    partial_reference, partial_candidate = _candidate(20.0, complete=False), _candidate(10.0, complete=False)
    partial_candidate["metrics"].completion = replace(partial_candidate["metrics"].completion,
        incomplete_batch_ids=("B2",), partial_batch_ids=("B2",), failure_batch_ids=("B2",))
    recorded_clock.value = 0.5
    assert _candidate_should_replace_best(partial_candidate, profile=profile, best=partial_reference, attempts=attempts,
        search_report_state=reporter, fingerprint=_identity("partial"), clock=recorded_clock, t_begin=0.0)
    assert attempts[-1]["elapsed_ms"] == 500 and attempts[-1]["event_index"] is None
    assert attempts[-1]["comparison"]["state"] == "different_coverage"
    assert attempts[-1]["strict_improved"] is None and attempts[-1]["comparison"]["metric_deltas"] is None


def test_unknown_and_unverified_results_do_not_claim_valid_or_complete_milestones():
    from tests._support.shared_schedule_archive import _archive, _result
    from tests._support.shared_schedule_archive import _candidate as archive_candidate

    clock = _Clock()
    archive = _archive()
    budget = SharedSearchBudget(clock=clock, started_at=0.0, deadline=2.0,
                                target_objectives=archive.target_objectives, configured_seconds=2)
    search = _SharedSearch(archive=archive, clock=clock, started_at=0.0, budget=budget)
    search.phase = "graph_ig"
    unknown = archive_candidate([_result(1, 0), _result(2, 2)])
    clock.value = 0.1
    _observe_decoded(search, "min_tardiness", candidate=unknown, origin="graph_ig", verified=True, elapsed_ms=100)
    trial = archive_candidate([_result(1, 0), _result(2, 2), _result(3, 4)])
    clock.value = 0.2
    _observe_decoded(search, "min_tardiness", candidate=trial, origin="graph_ig", verified=False, elapsed_ms=200)
    assert trial["_shared_entry_id"] not in archive.retained_entry_ids
    before_verified = build_shared_process(search, runtime_ms=200, stop_reason="completed", decode_stats={},
                                           budget_stats=budget.summary(finished_at=0.2))
    pending_points = before_verified["targets"]["min_tardiness"]["points"]
    assert all(not {"first_valid", "first_expected_complete"} & set(point["flags"]) for point in pending_points)
    assert all(not scope["components_known"] and not scope["is_complete"]
               for scope in before_verified["scopes"].values())
    verified = archive_candidate([_result(1, 0), _result(2, 2), _result(3, 4)])
    clock.value = 0.3
    _observe_decoded(search, "min_tardiness", candidate=verified, origin="graph_ig", verified=True, elapsed_ms=300)
    evidence = build_shared_process(search, runtime_ms=400, stop_reason="completed", decode_stats={},
                                     budget_stats=budget.summary(finished_at=0.4))
    assert len(evidence["events"]) == 3 and sum(event["verified"] is False for event in evidence["events"]) == 1
    points = evidence["targets"]["min_tardiness"]["points"]
    first = points[0]
    first_scope = evidence["scopes"][first["scope_ref"]]
    assert first_scope["objective_scope"] == "unknown" and first["score"][1] is None
    assert first_scope["components_known"] is False and first_scope["is_complete"] is False
    assert first["score"] == [1.0, None, None, None, None, None]
    assert "first_valid" not in first["flags"] and "first_expected_complete" not in first["flags"]
    assert evidence["events"][1]["entry_id"] == trial["_shared_entry_id"]
    assert evidence["events"][1]["verified"] is False
    assert all(point.get("source_event_id") != 2 for point in points)
    milestones = [point for point in points if "first_valid" in point["flags"]]
    assert len(milestones) == 1 and milestones[0]["source_event_id"] == 3
    milestone_event = evidence["events"][milestones[0]["source_event_id"] - 1]
    assert milestone_event["verified"] is True and "first_expected_complete" in milestones[0]["flags"]
    complete_scope = evidence["scopes"][milestones[0]["scope_ref"]]
    assert complete_scope["components_known"] is True and complete_scope["is_complete"] is True
    assert complete_scope["scheduled_operation_ids"] == [1, 2, 3]
    assert complete_scope["complete_batch_ids"] == ["B1", "B2", "B3"]
    assert points[-1]["flags"] == ["final"]

    # Reference re-capture and a subsequent full decode use the actual IG return points.
    identity_by_id = {}
    def fingerprint(candidate, parent=None):
        identity = identity_by_id[id(candidate)]
        return identity.with_context(parent_fingerprint=parent, seen_output_fingerprints=())
    pool = SimpleNamespace(fingerprint=fingerprint, seen_outputs=set())
    recorder = OptimizationSearchReportState(algorithm_profile="graph", seed=0, time_budget_seconds=2,
        objective_name="min_tardiness", started_at=0.0, candidate_clock=clock)
    report = {"reference_captures": 0, "reference_capture_divergences": 0, "reference_capture_improvements": 0,
              "improvements": 0, "accepted": False, "rejected_by_reason": {}, "unverified_trial_decodes": 0}
    profile = default_weight_profiles(max_weight_profiles=1)[0][0]
    tracker = IGIncumbentTracker(pool=pool, report_state=recorder, report=report, seed=0,
                                clock=clock, t_begin=0.0, improvement_trace=[])
    original, capture, improved = _candidate(20.0), _candidate(20.0), _candidate(8.0)
    identity_by_id.update({id(original): _identity("original"), id(capture): _identity("original"),
                          id(improved): _identity("improved")})
    tracker.adopt_best(original)
    search = SimpleNamespace(incumbent=tracker, profile=profile, clock=clock, t_begin=0.0,
                             attempts=[], capturing=original, improved_incumbent=False)
    clock.value = 0.5
    _IteratedGreedySearch._consider_for_incumbent(search, capture)
    assert report["reference_captures"] == 1 and tracker.best is original
    row = search.attempts[-1]
    assert row["comparison"]["kind"] == "reference_capture" and row["accepted"] is False
    assert row["strict_improved"] is False and row["comparison"]["metric_deltas"]["total_tardiness_hours"] == 0.0
    search.capturing = None
    clock.value = 0.75
    _IteratedGreedySearch._consider_for_incumbent(search, improved)
    row = search.attempts[-1]
    assert tracker.best is improved and search.improved_incumbent is True
    assert row["elapsed_ms"] == 750 and row["accepted"] is True and row["strict_improved"] is True
    assert row["comparison"]["kind"] == "incumbent"
    assert row["comparison"]["reference_score"] == list(original["score"])
    assert row["comparison"]["metric_deltas"]["total_tardiness_hours"] == -12.0


def test_reuse_failure_skip_counts_and_persisted_source_reference_have_distinct_meanings():
    empty = _candidate(0.0)
    empty["metrics"].completion = BatchCompletion(expected_operation_count=0, missing_operation_count=0,
        unexpected_result_count=0, complete_batch_count=0, incomplete_batch_ids=(), partial_batch_ids=(),
        failure_detail_count=0, failure_batch_ids=())
    empty["summary"] = ScheduleSummary(success=True, total_ops=0, scheduled_ops=0, failed_ops=0,
                                      warnings=[], errors=[], duration_seconds=0.0)
    empty["metrics"].makespan_hours = 0.0
    empty["score"] = (0.0,) + objective_score("min_tardiness", empty["metrics"])
    # Frozen legacy saved records keep zero work distinct from unavailable runtime history.
    own = load_legacy_process_evidence("min_tardiness_own_empty")
    reused = load_legacy_process_evidence("min_tardiness_reused", source_candidate_key="graph-source")
    skipped = load_legacy_process_evidence("min_tardiness_not_started")
    budget_stopped = load_legacy_process_evidence("min_tardiness_budget_skipped_11")
    failed = load_legacy_process_evidence("min_tardiness_failed_17")
    original_evidence = deepcopy((own, reused, skipped, budget_stopped, failed))
    assert reused["state"] == skipped["state"] == "complete"
    assert reused["elapsed_ms"] == skipped["elapsed_ms"] == 0
    assert all(value == 0 for value in reused["counts"].values())
    assert all(value == 0 for value in skipped["counts"].values())
    assert budget_stopped["state"] == "unavailable" and budget_stopped["elapsed_ms"] == 11
    assert all(value is None for value in budget_stopped["counts"].values())
    assert budget_stopped["sampling"]["event_total_count"] is None
    assert failed["state"] == "unavailable" and failed["elapsed_ms"] == 17
    assert all(value is None for value in failed["counts"].values())
    assert failed["sampling"]["event_total_count"] is None and failed["rejection_summary"] is None
    assert reused["points"] == skipped["points"] == budget_stopped["points"] == failed["points"] == []

    source_plan = CandidatePlan(sequence=1, candidate_key="graph-source", kind="critical_chain", label="来源方案",
        status="completed", score=empty["score"], graph_critical_weight=500, graph_impact_weight=10,
        graph_downstream_weight=1, metrics=empty["metrics"], summary=empty["summary"], objective="min_tardiness",
        objective_name="min_tardiness", process_evidence=own)
    reused_plan = replace(source_plan, sequence=2, candidate_key="graph-reused", label="复用方案",
                          reused_from_candidate_key=source_plan.candidate_key, process_evidence=reused)
    failed_plan = replace(source_plan, sequence=3, candidate_key="graph-failed", label="失败方案", status="failed",
                          score=None, metrics=None, summary=None, process_evidence=failed)
    skipped_plan = replace(source_plan, sequence=4, candidate_key="graph-skipped", label="跳过方案", status="skipped",
                           score=None, metrics=None, summary=None, process_evidence=skipped)
    plans = [source_plan, reused_plan, failed_plan, skipped_plan]
    # Explicit saved legacy selection: historical projection never runs the retired selector.
    saved_selection = {
        "selected_candidate_key": "graph-source", "selected_kind": "critical_chain",
        "selection_policy": "score_only", "reason_code": "score_only_raw_score_best",
        "raw_score_best_key": "graph-source", "baseline_best_key": None,
        "critical_best_key": "graph-source", "critical_health_best_key": None,
        "selected_score": list(source_plan.score), "selection_policy_version": "candidate-selection-v1",
        "tolerance_overdue_jobs": None, "tolerance_weighted_tardiness_pct": None,
        "tolerance_makespan_pct": None, "tolerance_changeover_pct": None,
    }
    selection = SimpleNamespace(selected_plan=source_plan, selected_candidate_key="graph-source",
                                to_dict=lambda: dict(saved_selection))
    comparison = CandidateComparisonOutcome(candidates=plans, selection=selection,
        planned_count=4, completed_count=2, failed_count=1, skipped_count=1, time_budget_reached=True,
        selection_policy="score_only", run_time_budget_seconds=1.0, skipped_candidate_labels=["跳过方案"],
        baseline_missing_or_failed=True, reused_count=1)
    payload = ValidatedSchedulePayload(schedule_rows=[], scheduled_op_ids=set(), assigned_by_op_id={})
    computation = CandidateRunComputation(schedule_input=SimpleNamespace(frozen_op_ids=set()),
        orchestration=SimpleNamespace(candidate_comparison=comparison, result_summary_obj={}),
        candidate_payloads={source_plan.candidate_key: payload, reused_plan.candidate_key: payload}, dispositions=[], state="partial")
    saved, receipt = _prepare_result_artifacts(computation, {})
    rows = {row["key"]: row for row in saved}
    source_ref = rows[source_plan.candidate_key]["candidate_ref"]
    mapped = rows[reused_plan.candidate_key]["artifact"]["process_evidence"]
    assert mapped["source"]["reused_from_candidate_ref"] == source_ref
    assert "reused_from_candidate_key" not in mapped["source"]
    assert receipt["selection"]["selected_candidate_ref"] == source_ref
    assert reused["source"]["reused_from_candidate_key"] == source_plan.candidate_key
    assert rows[failed_plan.candidate_key]["artifact"]["process_evidence"]["counts"]["evaluated"] is None
    assert rows[skipped_plan.candidate_key]["artifact"]["process_evidence"]["counts"]["evaluated"] == 0
    assert (own, reused, skipped, budget_stopped, failed) == original_evidence


def test_report_uses_archive_identity_and_evaluation_without_scanning_schedule_rows():
    from tests._support.shared_schedule_archive import _archive, _result
    from tests._support.shared_schedule_archive import _candidate as archive_candidate

    class RegisteredRows(list):
        def __iter__(self):
            raise AssertionError("the report must consume the archive identity, not walk the schedule")

    archive = _archive()
    candidate = archive_candidate([_result(1, 0), _result(2, 2), _result(3, 4)])
    _register_decode(archive, candidate)
    candidate["results"] = RegisteredRows(candidate["results"])
    report = OptimizationSearchReportState(algorithm_profile="shared", seed=0, time_budget_seconds=1,
        objective_name="min_tardiness", started_at=0.0)
    initial = report.mark_candidate_evaluated(candidate, origin="baseline")
    report.mark_candidate_accepted(candidate, origin="baseline", fingerprint=initial)
    duplicate = dict(candidate, order=["B3", "B2", "B1"], params={"other_decision": True})
    repeated = report.mark_candidate_evaluated(duplicate, origin="multi_start")
    assert repeated.same_as_seen and repeated.same_as_parent
    assert len(report.candidate_fingerprints) == 1
    # Arrangement identity stays fixed while real completion and objective values remain comparison inputs.
    different_evaluation = dict(candidate, metrics=replace(candidate["metrics"], total_tardiness_hours=5.0))
    changed = report.mark_candidate_evaluated(different_evaluation, origin="validated_evidence")
    assert changed.output_key != initial.output_key
    other_objective = OptimizationSearchReportState(algorithm_profile="shared", seed=0, time_budget_seconds=1,
        objective_name="min_changeover", started_at=0.0)
    alternative = other_objective.mark_candidate_evaluated(candidate, origin="shared_reference")
    assert alternative.output_key != initial.output_key
    trial_rows = archive_candidate([_result(1, 7), _result(2, 9), _result(3, 11)])
    _register_decode(archive, trial_rows, verified=False)
    previous = set(report.candidate_fingerprints)
    report.mark_candidate_evaluated(trial_rows, origin="checkpoint_trial", remember_fingerprint=False)
    assert report.candidate_fingerprints == previous
    assert trial_rows["_shared_entry_id"] not in archive.retained_entry_ids
