"""Solver process evidence retains late work and separates adoption from improvement."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from core.algorithm_contracts.types import ScheduleSummary
from core.algorithms import SortStrategy
from core.algorithms.evaluation import ScheduleMetrics, objective_score
from core.algorithms.evaluation_completion import BatchCompletion
from core.errors import ValidationError
from core.models.workbench_run_compute import CandidateRunComputation
from core.services.scheduler.contracts.optimizer_public_search_report import project_search_report
from core.services.scheduler.run.optimizer.candidate_fingerprint import CandidateFingerprint
from core.services.scheduler.run.optimizer.graph.iterated_greedy import _IteratedGreedySearch
from core.services.scheduler.run.optimizer.graph.iterated_greedy_incumbent import IGIncumbentTracker
from core.services.scheduler.run.optimizer.graph.reporting import append_graph_trace
from core.services.scheduler.run.optimizer.graph.stages import _accept_candidate, _candidate_should_replace_best
from core.services.scheduler.run.optimizer.graph_ready_profiles import default_weight_profiles
from core.services.scheduler.run.optimizer.grasp_ig_candidates import _append_trace
from core.services.scheduler.run.optimizer.local_search_round import _record_improvement
from core.services.scheduler.run.optimizer.neighborhood_moves import NeighborhoodMove
from core.services.scheduler.run.optimizer.process_evidence import OptimizationProcessEvidence, non_search_evidence
from core.services.scheduler.run.optimizer.search_report import OptimizationSearchReportState
from core.services.scheduler.run.optimizer.step_report_hooks import _append_multi_start_trace, _append_ortools_trace
from core.services.scheduler.run.schedule_candidate_plan import CandidateComparisonOutcome, CandidatePlan
from core.services.scheduler.run.schedule_candidate_selection import select_candidate_plan
from core.services.scheduler.run.schedule_payload_contract import ValidatedSchedulePayload
from data.repositories.workbench_run_result_repo import prepare_run_result


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
    return {"results": [], "summary": ScheduleSummary(failed_ops=failed, success=complete, total_ops=3,
                                                      scheduled_ops=3 - failed, warnings=[], errors=[], duration_seconds=0.0),
            "score": (float(failed),) + objective_score(objective, metrics), "metrics": metrics,
            "strategy": SortStrategy.PRIORITY_FIRST, "params": {}, "algo_stats": {},
            "dispatch_mode": "sgs", "dispatch_rule": "cr", "order": ["B1", "B2"]}


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
    clock = _Clock()
    collector = OptimizationProcessEvidence(objective_name="min_tardiness", clock=clock, started_at=0.0)
    collector.begin_phase("multi_start", at=0.0)
    raw_times = []
    for index in range(321):
        clock.value = float(index + 1)
        candidate = _candidate(400 - index, complete=index >= 210)
        collector.evaluated(candidate, origin="multi_start")
        collector.accepted(candidate, origin="multi_start")
        raw_times.append((index + 1, (index + 1) * 1000))
    collector.end_phase(at=400.0)
    evidence = collector.finalize(candidate, elapsed_ms=400000, stop_reason="time_budget", decoder_invocations=321)
    points, sampling = evidence["points"], evidence["sampling"]
    assert evidence["version"] == "optimization-process-v1"
    assert evidence["objective"]["primary_metric_key"] == "total_tardiness_hours"
    assert evidence["objective"]["unit"] == "小时"
    assert evidence["counts"]["evaluated"] == evidence["counts"]["accepted"] == 321
    assert evidence["counts"]["strict_improvements"] == 319
    assert evidence["counts"]["decoder_invocations"] == 321
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
    points[-1]["score"][1] = -999.0
    assert collector.finalize(candidate, elapsed_ms=400000, stop_reason="time_budget")["points"][-1]["score"][1] == 80.0

    immediate = OptimizationProcessEvidence(objective_name="min_tardiness", clock=lambda: 0.0, started_at=0.0)
    complete = _candidate(0.0)
    immediate.evaluated(complete, origin="baseline")
    immediate.accepted(complete, origin="baseline")
    merged = immediate.finalize(complete, elapsed_ms=0, stop_reason="completed")
    assert len(merged["points"]) == 1
    assert merged["points"][0]["elapsed_ms"] == 0
    assert {"first_valid", "first_expected_complete", "final"} <= set(merged["points"][0]["flags"])


def test_adoption_is_separate_from_strict_improvement_and_revisited_stages_do_not_connect():
    clock = _Clock()
    collector = OptimizationProcessEvidence(objective_name="min_tardiness", clock=clock, started_at=0.0)
    collector.begin_phase("profiles", at=0.0)
    assert clock.reads == 0
    first = _candidate(20.0)
    clock.value = 0.25
    collector.evaluated(first, origin="graph_ready_base")
    collector.accepted(first, origin="graph_ready_base")
    clock.value = 0.5
    tied = _candidate(20.0)
    collector.evaluated(tied, origin="graph_ready_generated")
    collector.accepted(tied, origin="graph_ready_generated")
    reads = clock.reads
    collector.end_phase(at=0.75)
    collector.begin_phase("repair", at=0.75)
    assert clock.reads == reads
    lower = _candidate(10.0)
    clock.value = 1.0
    collector.evaluated(lower, origin="graph_ready_repaired")
    collector.accepted(lower, origin="graph_ready_repaired")
    collector.end_phase(at=1.25)
    collector.begin_phase("profiles", at=1.25)
    current = _candidate(25.0)
    clock.value = 1.35
    collector.evaluated(current, origin="local_search")
    collector.accepted(current, origin="local_search", current_only=True)
    final = _candidate(8.0)
    clock.value = 1.5
    collector.evaluated(final, origin="graph_ready_generated")
    collector.accepted(final, origin="graph_ready_generated")
    collector.rejected(reason="fixture_rejected")
    collector.end_phase(at=1.75)
    collector.skipped_phase("ortools", "disabled")
    evidence = collector.finalize(final, elapsed_ms=1750, stop_reason="stages_exhausted")
    assert evidence["counts"]["evaluated"] == evidence["counts"]["accepted"] == 5
    assert evidence["counts"]["current_accepted"] == 1
    assert evidence["counts"]["strict_improvements"] == 2
    assert evidence["counts"]["rejected"] == 1
    assert evidence["rejection_summary"] == {"fixture_rejected": 1}
    profiles = [point for point in evidence["points"] if point["phase"] == "profiles" and "final" not in point["flags"]]
    assert [point["primary_value"] for point in profiles] == [20.0, 8.0]
    assert len({point["segment"] for point in profiles}) == len({point["phase_visit"] for point in profiles}) == 2
    assert all(point["evaluation_scope"] == {"incomplete_batch_ids": []} for point in evidence["points"])
    assert not any(point["primary_value"] == 25.0 for point in evidence["points"])
    stages = {stage["phase"]: stage for stage in evidence["stages"]}
    assert stages["profiles"]["visits"] == 2 and stages["profiles"]["elapsed_ms"] == 1250
    assert stages["profiles"]["strict_improvements"] == 1
    assert stages["repair"]["elapsed_ms"] == 500 and stages["repair"]["strict_improvements"] == 1
    assert stages["ortools"]["status"] == "skipped" and stages["ortools"]["stop_reason"] == "disabled"

    # Use the actual GraphReady decision recorder: accepting a tie keeps a zero change,
    # and an incumbent snapshot stays intact after its original metrics change.
    recorded_clock = _Clock()
    recorded = OptimizationProcessEvidence(objective_name="min_tardiness", clock=recorded_clock, started_at=0.0)
    reporter = OptimizationSearchReportState(algorithm_profile="graph", seed=0, time_budget_seconds=2,
        objective_name="min_tardiness", started_at=0.0, process_collector=recorded)
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
    assert attempts[0]["elapsed_ms"] == 125 and attempts[0]["event_index"] == 1
    assert attempts[0]["accepted"] is True and attempts[0]["strict_improved"] is None
    assert attempts[0]["comparison"]["state"] == "no_reference"
    assert attempts[0]["comparison"]["metric_deltas"] is None
    tied = _candidate(20.0)
    tied["runtime_ms"] = 10
    recorded_clock.value = 0.25
    assert _candidate_should_replace_best(tied, profile=profile, best=incumbent, attempts=attempts,
        search_report_state=reporter, fingerprint=_identity("tie"), clock=recorded_clock, t_begin=0.0)
    assert attempts[-1]["accepted"] is True and attempts[-1]["strict_improved"] is False
    assert attempts[-1]["comparison"]["reference_score"] == list(incumbent["score"])
    assert attempts[-1]["comparison"]["metric_deltas"]["total_tardiness_hours"] == 0.0
    assert recorded_clock.reads == 2  # The attempt reuses its evaluation timestamp.
    incumbent["metrics"].total_tardiness_hours = 999.0
    assert attempts[-1]["comparison"]["reference_metrics"]["total_tardiness_hours"] == 20.0
    partial_reference, partial_candidate = _candidate(20.0, complete=False), _candidate(10.0, complete=False)
    partial_candidate["metrics"].completion = replace(partial_candidate["metrics"].completion,
        incomplete_batch_ids=("B2",), partial_batch_ids=("B2",), failure_batch_ids=("B2",))
    recorded_clock.value = 0.5
    assert _candidate_should_replace_best(partial_candidate, profile=profile, best=partial_reference, attempts=attempts,
        search_report_state=reporter, fingerprint=_identity("partial"), clock=recorded_clock, t_begin=0.0)
    assert attempts[-1]["comparison"]["state"] == "different_coverage"
    assert attempts[-1]["strict_improved"] is None and attempts[-1]["comparison"]["metric_deltas"] is None
    membership = OptimizationProcessEvidence(objective_name="min_tardiness", clock=recorded_clock, started_at=0.0)
    membership.begin_phase("profiles", at=0.0)
    for index, candidate in enumerate((partial_reference, partial_candidate), 1):
        recorded_clock.value = index * 0.25
        membership.evaluated(candidate, origin="profiles")
        membership.accepted(candidate, origin="profiles")
    changed = membership.finalize(partial_candidate, elapsed_ms=750, stop_reason="completed")["points"]
    assert changed[0]["phase"] == changed[1]["phase"] == "profiles"
    assert changed[0]["phase_visit"] == changed[1]["phase_visit"] == 1
    assert changed[0]["completion"] == changed[1]["completion"]
    assert changed[0]["evaluation_scope"] == {"incomplete_batch_ids": ["B1"]}
    assert changed[1]["evaluation_scope"] == {"incomplete_batch_ids": ["B2"]}
    assert changed[-1]["evaluation_scope"] == changed[1]["evaluation_scope"]


def test_unknown_and_unverified_results_do_not_claim_valid_or_complete_milestones():
    clock = _Clock()
    collector = OptimizationProcessEvidence(objective_name="min_tardiness", clock=clock, started_at=0.0)
    collector.begin_phase("graph_ig", at=0.0)
    unknown = _candidate(30.0, complete=False)
    unknown["metrics"].completion = replace(unknown["metrics"].completion, explained=False)
    unknown["score"] = (1.0,) + objective_score("min_tardiness", unknown["metrics"])
    clock.value = 0.1
    collector.evaluated(unknown, origin="graph_ig")
    collector.accepted(unknown, origin="graph_ig")
    trial = _candidate(5.0)
    clock.value = 0.2
    collector.evaluated(trial, origin="graph_ig", verified=False)
    verified = _candidate(5.0)
    clock.value = 0.3
    collector.evaluated(verified, origin="graph_ig")
    collector.accepted(verified, origin="graph_ig")
    collector.end_phase(at=0.4)
    evidence = collector.finalize(verified, elapsed_ms=400, stop_reason="completed")
    assert evidence["counts"]["evaluated"] == 3 and evidence["counts"]["unverified_trials"] == 1
    first = evidence["points"][0]
    assert first["objective_scope"] == "unknown" and first["primary_value"] is None
    assert first["evaluation_scope"] is None
    assert first["score"] == [1.0, None, None, None, None, None]
    assert "first_valid" not in first["flags"] and "first_expected_complete" not in first["flags"]
    milestones = [point for point in evidence["points"] if "first_valid" in point["flags"]]
    assert len(milestones) == 1 and milestones[0]["event_index"] == 3
    assert milestones[0]["verified"] is True and "first_expected_complete" in milestones[0]["flags"]
    assert milestones[0]["evaluation_scope"] == {"incomplete_batch_ids": []}
    assert evidence["points"][-1]["flags"] == ["final"]

    # Reference re-capture and a subsequent full decode use the actual IG return points.
    identity_by_id = {}
    def fingerprint(candidate, parent=None):
        identity = identity_by_id[id(candidate)]
        return identity.with_context(parent_fingerprint=parent, seen_output_fingerprints=())
    pool = SimpleNamespace(fingerprint=fingerprint, seen_outputs=set())
    recorder = OptimizationSearchReportState(algorithm_profile="graph", seed=0, time_budget_seconds=2,
        objective_name="min_tardiness", started_at=0.0,
        process_collector=OptimizationProcessEvidence(objective_name="min_tardiness", clock=clock, started_at=0.0))
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
    clock = _Clock()
    empty = _candidate(0.0)
    empty["metrics"].completion = BatchCompletion(expected_operation_count=0, missing_operation_count=0,
        unexpected_result_count=0, complete_batch_count=0, incomplete_batch_ids=(), partial_batch_ids=(),
        failure_detail_count=0, failure_batch_ids=())
    empty["summary"] = ScheduleSummary(success=True, total_ops=0, scheduled_ops=0, failed_ops=0,
                                      warnings=[], errors=[], duration_seconds=0.0)
    empty["metrics"].makespan_hours = 0.0
    empty["score"] = (0.0,) + objective_score("min_tardiness", empty["metrics"])
    collector = OptimizationProcessEvidence(objective_name="min_tardiness", clock=clock, started_at=0.0)
    collector.evaluated(empty, origin="graph_ready_base")
    collector.accepted(empty, origin="graph_ready_base")
    own = collector.finalize(empty, elapsed_ms=1, stop_reason="completed", decoder_invocations=1)
    reused = non_search_evidence("min_tardiness", kind="reused", reason="equivalent_optimizer_inputs",
                                 source_candidate_key="graph-source")
    skipped = non_search_evidence("min_tardiness", kind="not_started", reason="candidate_time_budget_reached",
                                  known_not_started=True)
    budget_stopped = non_search_evidence("min_tardiness", kind="budget_skipped", reason="candidate_time_budget_reached",
                                         elapsed_ms=11, known_not_started=False)
    failed = non_search_evidence("min_tardiness", kind="failed", reason="known_candidate_failure", elapsed_ms=17)
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
    comparison = CandidateComparisonOutcome(candidates=plans, selection=select_candidate_plan(plans, policy="score_only"),
        planned_count=4, completed_count=2, failed_count=1, skipped_count=1, time_budget_reached=True,
        selection_policy="score_only", run_time_budget_seconds=1.0, skipped_candidate_labels=["跳过方案"],
        baseline_missing_or_failed=True, reused_count=1)
    payload = ValidatedSchedulePayload(schedule_rows=[], scheduled_op_ids=set(), assigned_by_op_id={})
    computation = CandidateRunComputation(schedule_input=SimpleNamespace(frozen_op_ids=set()),
        orchestration=SimpleNamespace(candidate_comparison=comparison, result_summary_obj={}),
        candidate_payloads={source_plan.candidate_key: payload, reused_plan.candidate_key: payload}, dispositions=[], state="partial")
    saved, receipt = prepare_run_result(computation, {})
    rows = {row["key"]: row for row in saved}
    source_ref = rows[source_plan.candidate_key]["candidate_ref"]
    mapped = rows[reused_plan.candidate_key]["artifact"]["process_evidence"]
    assert mapped["source"]["reused_from_candidate_ref"] == source_ref
    assert "reused_from_candidate_key" not in mapped["source"]
    assert receipt["selection"]["selected_candidate_ref"] == source_ref
    assert reused["source"]["reused_from_candidate_key"] == source_plan.candidate_key
    assert rows[failed_plan.candidate_key]["artifact"]["process_evidence"]["counts"]["evaluated"] is None
    assert rows[skipped_plan.candidate_key]["artifact"]["process_evidence"]["counts"]["evaluated"] == 0
