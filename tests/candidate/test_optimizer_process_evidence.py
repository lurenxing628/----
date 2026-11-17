"""Solver process evidence retains late work and separates adoption from improvement."""

from copy import deepcopy
from dataclasses import replace
from functools import partial
from types import SimpleNamespace

from core.algorithm_contracts.resource_pool import DISABLED_RESOURCE_POOL
from core.algorithm_contracts.types import ScheduleSummary
from core.algorithms.evaluation import ScheduleMetrics, objective_score
from core.algorithms.evaluation_completion import BatchCompletion
from core.algorithms.greedy.scheduler import GreedyScheduler
from core.models.enums import SortStrategy
from core.models.objective import target_objectives_for
from core.models.schedule_config_runtime_fields import default_snapshot_values
from core.models.schedule_config_runtime_snapshot import snapshot_from_values
from core.services.scheduler.run.optimizer.candidate_fingerprint import CandidateFingerprint
from core.services.scheduler.run.optimizer.graph.candidates import (
    PreparedDecisionFeatures,
    evaluate_graph_ready_candidate,
)
from core.services.scheduler.run.optimizer.graph.iterated_greedy import IteratedGreedySearch
from core.services.scheduler.run.optimizer.graph.iterated_greedy_contract import (
    IteratedGreedyLimits,
    new_iterated_greedy_report,
)
from core.services.scheduler.run.optimizer.graph.iterated_greedy_moves import parent_from_candidate
from core.services.scheduler.run.optimizer.graph.repair_decisions import (
    prepare_repair_parent,
    prepare_repair_scope,
)
from core.services.scheduler.run.optimizer.graph.stages import _candidate_should_replace_best
from core.services.scheduler.run.optimizer.graph.v2_features import enrich_graph_ready_v2_metrics
from core.services.scheduler.run.optimizer.graph.v2_ranks import build_v2_common_rank_cache
from core.services.scheduler.run.optimizer.graph_ready_profiles import resolve_v2_profiles
from core.services.scheduler.run.optimizer.multi_start import _evaluate_multi_start_candidate
from core.services.scheduler.run.optimizer.process_evidence import sample_elapsed_points
from core.services.scheduler.run.optimizer.shared_archive import SharedScheduleArchive
from core.services.scheduler.run.optimizer.shared_process import build_shared_process
from core.services.scheduler.run.schedule_shared_search import open_shared_search
from tests._support.algo_operations import make_batch
from tests._support.optimizer_graph_ready_benchmark import (
    START_DT,
    ContinuousCalendar,
    graph_ready_benchmark_batches,
    graph_ready_benchmark_context,
    graph_ready_benchmark_operations,
)
from tests._support.schedule_decode import NO_END_DATE, required_hours_by_op_id, unbounded_search_budget
from tests._support.shared_schedule_archive import _register_decode, detached_report


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
            "strategy": SortStrategy.PRIORITY_FIRST, "params": None, "graph_ready_profile": None,
            "repair_decision": None, "algo_stats": {},
            "dispatch_mode": "sgs", "dispatch_rule": "cr", "order": ["B1", "B2"]}
    archive = SharedScheduleArchive(objective, target_objectives_for(objective), (1, 2, 3), ("B1", "B2"))
    return _register_decode(archive, candidate)


class _Clock:
    def __init__(self):
        self.value, self.reads = 0.0, 0

    def __call__(self):
        self.reads += 1
        return self.value


def _identity(name):
    return CandidateFingerprint(
        output_key=(name,),
        same_as_parent=False,
        same_as_seen=False,
        fingerprint_changed=True,
    )


def test_candidate_contents_define_duplicates_and_diagnostic_sequences_preserve_legacy_reports():
    report = detached_report("min_tardiness")
    baseline = _candidate(20.0)
    first = report.mark_candidate_evaluated(baseline, origin="baseline")
    report.mark_candidate_accepted(baseline, origin="baseline", fingerprint=first)
    duplicate = _candidate(20.0)
    duplicate.update(strategy=SortStrategy.DUE_DATE_FIRST, order=["B2", "B1"], params={"different": True})
    repeated = report.mark_candidate_evaluated(duplicate, origin="multi_start")
    assert repeated.same_as_seen and repeated.same_as_parent and not repeated.fingerprint_changed
    assert len(report.candidate_fingerprints) == 1
    # The saved content remains immutable when the mutable source metrics change.
    baseline["metrics"].total_tardiness_hours = 999.0
    changed = report.mark_candidate_evaluated(_candidate(8.0), origin="local_search")
    assert changed.output_key != first.output_key and not changed.same_as_seen
    report.mark_candidate_accepted(_candidate(8.0), origin="local_search", fingerprint=changed)
    assert report.best_fingerprint_changed()
    assert report.initial_fingerprint == first.output_key
    assert report.best_fingerprint == changed.output_key


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

    immediate = [{"elapsed_ms": 0, "flags": ["first_valid", "first_expected_complete", "final"]}]
    merged, zero_sampling = sample_elapsed_points(immediate, elapsed_ms=0)
    assert len(merged) == 1
    assert merged[0]["elapsed_ms"] == 0
    assert {"first_valid", "first_expected_complete", "final"} <= set(merged[0]["flags"])
    assert zero_sampling["bucket_width_ms"] == 0.0


def test_adoption_is_separate_from_strict_improvement_and_revisited_stages_do_not_connect():
    recorded_clock = _Clock()
    observed = []
    reporter = detached_report("min_tardiness", clock=recorded_clock,
                               candidate_observer=lambda **kw: observed.append(kw))
    profile = next(p for p in resolve_v2_profiles(seed=0, objective_name="min_overdue") if p.slug == "balanced")
    incumbent = _candidate(20.0)
    incumbent["runtime_ms"] = 20
    recorded_clock.value = 0.125
    identity = _identity("first")
    assert _candidate_should_replace_best(incumbent, profile=profile, best=None,
        search_report_state=reporter, fingerprint=identity)
    reporter.mark_candidate_accepted(incumbent, origin=profile.candidate_origin, fingerprint=identity)
    tied = _candidate(20.0)
    tied["runtime_ms"] = 10
    recorded_clock.value = 0.25
    assert _candidate_should_replace_best(tied, profile=profile, best=incumbent,
        search_report_state=reporter, fingerprint=_identity("tie"))
    assert recorded_clock.reads == 2
    assert [row["elapsed_ms"] for row in observed] == [125, 250]
    partial_reference, partial_candidate = _candidate(20.0, complete=False), _candidate(10.0, complete=False)
    partial_candidate["metrics"].completion = replace(partial_candidate["metrics"].completion,
        incomplete_batch_ids=("B2",), partial_batch_ids=("B2",), failure_batch_ids=("B2",))
    recorded_clock.value = 0.5
    assert _candidate_should_replace_best(partial_candidate, profile=profile, best=partial_reference,
        search_report_state=reporter, fingerprint=_identity("partial"))
    assert recorded_clock.reads == 3
    assert observed[-1]["elapsed_ms"] == 500


def test_unknown_and_unverified_results_do_not_claim_valid_or_complete_milestones():
    from tests._support.shared_schedule_archive import (
        BATCHES,
        _result,
        arrangement_search,
        observation_events,
        observe_arrangement,
    )

    rows = [_result(1, 0), _result(2, 2), _result(3, 4)]
    # A run batch without an operation to schedule leaves every decode's scope unknown: no milestone at all.
    unknown_search = arrangement_search(batches=dict(BATCHES, B4=make_batch(batch_id="B4", due_date="2026-10-13")))
    unknown_search.phase = "graph_ig"
    observe_arrangement(unknown_search, "min_tardiness", rows, order=("B1", "B2", "B3", "B4"), origin="graph_ig",
                        elapsed_ms=100)
    unknown = build_shared_process(unknown_search, runtime_ms=200, stop_reason="completed", decode_stats={},
                                   budget_stats=unknown_search.budget.summary(finished_at=0.2))
    unknown_points = unknown["targets"]["min_tardiness"]["points"]
    assert unknown_points[0]["score"] == [0.0, None, None, None, None, None]
    assert all(not {"first_valid", "first_expected_complete"} & set(point["flags"]) for point in unknown_points)
    assert all(not scope["components_known"] and not scope["is_complete"] for scope in unknown["scopes"].values())
    assert unknown["scopes"][unknown_points[0]["scope_ref"]]["objective_scope"] == "unknown"

    clock = _Clock()
    search = arrangement_search(clock=clock, deadline=2.0)
    budget, archive = search.budget, search.archive
    search.phase = "graph_ig"
    clock.value = 0.2
    trial = observe_arrangement(search, "min_tardiness", rows, order=("B2", "B1", "B3"), origin="graph_ig",
                                elapsed_ms=200, trial=True)
    assert not trial["decode_receipt"]["verified"] and trial["archive_ref"].entry_id not in archive
    before_verified = build_shared_process(search, runtime_ms=200, stop_reason="completed", decode_stats={},
                                           budget_stats=budget.summary(finished_at=0.2))
    assert all(not {"first_valid", "first_expected_complete"} & set(point["flags"])
               for point in before_verified["targets"]["min_tardiness"]["points"])
    clock.value = 0.3
    observe_arrangement(search, "min_tardiness", rows, order=("B1", "B2", "B3"), origin="graph_ig", elapsed_ms=300)
    evidence = build_shared_process(search, runtime_ms=400, stop_reason="completed", decode_stats={},
                                     budget_stats=budget.summary(finished_at=0.4))
    trial_event, verified_event = observation_events(search)
    assert trial_event["verified"] is False and trial_event["entry_id"] == trial["archive_ref"].entry_id
    assert verified_event["verified"] is True
    points = evidence["targets"]["min_tardiness"]["points"]
    assert all(point.get("source_event_id") != trial_event["event_id"] for point in points)
    milestones = [point for point in points if "first_valid" in point["flags"]]
    assert len(milestones) == 1 and milestones[0]["source_event_id"] == verified_event["event_id"]
    assert "first_expected_complete" in milestones[0]["flags"]
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
    recorder = detached_report("min_tardiness", clock=clock)
    limits = IteratedGreedyLimits()
    report = new_iterated_greedy_report(objective_name="min_tardiness")
    profile = next(p for p in resolve_v2_profiles(seed=0, objective_name="min_overdue") if p.slug == "balanced")
    cfg_values = default_snapshot_values()
    cfg_values.update(auto_assign_enabled="no")
    scheduler = GreedyScheduler(calendar_service=ContinuousCalendar(), config_service=snapshot_from_values(cfg_values))
    operations, batches = graph_ready_benchmark_operations(), graph_ready_benchmark_batches()
    context = graph_ready_benchmark_context()
    session = open_shared_search(
        objective_name="min_tardiness", scheduler=scheduler, operations=operations, batches=batches,
        required_hours_by_op_id=required_hours_by_op_id(operations, batches), seed_results=[], downtime_map={},
        resource_pool=DISABLED_RESOURCE_POOL, graph_ready_context=context, start_dt=START_DT, end_date=NO_END_DATE,
        readiness_gate_enabled=False, clock=clock, started_at=0.0, deadline=2.0, configured_seconds=2).decode_session
    baseline = _evaluate_multi_start_candidate(
        strategy=SortStrategy.PRIORITY_FIRST, params=None, order=list(batches), dispatch_mode="sgs",
        dispatch_rule="slack", objective_name="min_tardiness", graph_ready_context=None, decode_session=session)
    parent = parent_from_candidate(baseline,
                                   prepared=prepare_repair_parent(
                                       baseline,
                                       scope=prepare_repair_scope(
                                           operations, session.native_preparation.graph_topology(),
                                           resource_pairs_for=session.native_preparation.qualified_resource_pairs)))
    assert parent is not None
    graph_metrics = enrich_graph_ready_v2_metrics(context["node_metrics_by_op_id"], operations=operations,
                                                  batches=batches, start_dt=START_DT, graph_ready_context=context,
                                                  calendar_service=scheduler.calendar, downtime_map={}, seed_results=[],
                                                  budget=unbounded_search_budget(),
                                                  native_preparation=session.native_preparation)
    assert graph_metrics is not None
    decision_features = PreparedDecisionFeatures(
        graph_metrics, build_v2_common_rank_cache(graph_metrics),
        schedulable_ids=session.native_preparation.graph_topology().schedulable_ids)
    evaluate = partial(evaluate_graph_ready_candidate,
        prepared_decision_features=decision_features, strategy=SortStrategy.PRIORITY_FIRST, params=None,
        dispatch_rule="slack", objective_name="min_tardiness", version=0, decode_session=session)
    search = IteratedGreedySearch(limits=limits, parent=parent, profile=profile, pool=pool, evaluate=evaluate,
        metrics_by_op_id=graph_metrics, seed=0, report_state=recorder, report=report, decode_session=session)
    tracker = search.incumbent
    original, capture, improved = _candidate(20.0), _candidate(20.0), _candidate(8.0)
    identity_by_id.update({id(original): _identity("original"), id(capture): _identity("original"),
                          id(improved): _identity("improved")})
    tracker.adopt_best(original)
    clock.value = 0.5
    search._consider_for_incumbent(capture, capture_of=original)
    assert tracker.best is original and report["improvements"] == 0 and not report["accepted"]
    clock.value = 0.75
    search._consider_for_incumbent(improved, capture_of=None)
    assert tracker.best is improved and search.improved_incumbent is True
    assert report["improvements"] == 1


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
    report = detached_report("min_tardiness")
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
    sub_micro_hours = 1.0 / 3_600_000_000.0
    sub_micro_evaluation = dict(
        candidate,
        metrics=replace(
            candidate["metrics"],
            total_tardiness_hours=candidate["metrics"].total_tardiness_hours - sub_micro_hours,
        ),
        score=(candidate["score"][0], candidate["score"][1] - sub_micro_hours) + candidate["score"][2:],
    )
    sub_micro_changed = report.mark_candidate_evaluated(sub_micro_evaluation, origin="sub_micro_evidence")
    assert sub_micro_changed.output_key != initial.output_key
    from core.services.scheduler.run.optimizer.candidate_fingerprint import score_strictly_better
    assert score_strictly_better(sub_micro_evaluation["score"], candidate["score"])
    other_objective = detached_report("min_changeover")
    alternative = other_objective.mark_candidate_evaluated(candidate, origin="shared_reference")
    assert alternative.output_key != initial.output_key
    trial_rows = archive_candidate([_result(1, 7), _result(2, 9), _result(3, 11)])
    _register_decode(archive, trial_rows, verified=False)
    previous = set(report.candidate_fingerprints)
    report.mark_candidate_evaluated(trial_rows, origin="checkpoint_trial", remember_fingerprint=False)
    assert report.candidate_fingerprints == previous
    assert trial_rows["archive_ref"].entry_id not in archive
