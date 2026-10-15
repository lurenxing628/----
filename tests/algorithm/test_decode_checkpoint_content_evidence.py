"""Checkpoint content comparisons preserve resumed decoding and calendar rollback checks."""

from collections import OrderedDict
from copy import deepcopy
from dataclasses import replace
from time import perf_counter
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.algorithm_contracts.types import ScheduleResult, ScheduleSummary
from core.algorithms import SortStrategy
from core.algorithms.evaluation import compute_metrics, objective_score
from core.algorithms.greedy import schedule_preparation as native_preparation
from core.algorithms.greedy.dispatch.sgs_checkpoint import DecodeCheckpointRequest, decode_output_contents
from core.algorithms.greedy.dispatch.sgs_checkpoint_tail import DecodeTailReuse
from core.algorithms.greedy.scheduler import GreedyScheduler
from core.errors import ValidationError
from core.models.objective import target_objectives_for
from core.services.scheduler.calendar.checkpoint_certificate import calendar_checkpoint_snapshot
from core.services.scheduler.calendar.service import CalendarService
from core.services.scheduler.run.optimizer.graph import iterated_greedy as ig_module
from core.services.scheduler.run.optimizer.graph.iterated_greedy_checkpoints import CheckpointStore
from core.services.scheduler.run.optimizer.graph_ready_profiles import default_weight_profiles
from core.services.scheduler.run.optimizer.shared_archive import SharedScheduleArchive
from core.services.scheduler.run.optimizer.shared_budget import SharedSearchBudget
from core.services.scheduler.run.optimizer.shared_decode import SharedDecodeSession, decode_and_metrics
from core.services.scheduler.run.optimizer.signature_support import schedule_with_optional_strict_mode
from core.services.scheduler.run.schedule_execution_reservations import (
    ExecutionResourceCalendar,
    ExecutionResourceReservation,
)
from data.repositories.calendar_checkpoint_repo import CalendarCheckpointRepository
from tests._support.busy_block_case import at, native_calendar
from tests.algorithm.test_execution_calendar_certified_overlay import _saturated_case


def test_checkpoint_resumes_same_inputs_and_rejects_changed_type_or_prefix():
    case = _saturated_case(batch_count=2, ops_per_batch=2)
    seed = ScheduleResult(99, "SEED", "FROZEN", 1, "M1", "O1", at(-1), at(),
                          op_type_name="SAME LABEL", op_type_id="T0")
    case["seed_results"] = [seed]
    with native_calendar() as calendar:
        scheduler = GreedyScheduler(calendar_service=calendar, config_service={"auto_assign_enabled": "no"})
        captured = []
        full = scheduler.schedule(**case, decode_checkpoints=DecodeCheckpointRequest([1, 2, 4], captured.append))
        checkpoint = captured[0]
        assert len(captured) == 3 and isinstance(checkpoint.signature, tuple)
        resumed = scheduler.schedule(**case, decode_resume=checkpoint)
        assert full[0] == resumed[0]
        contents = decode_output_contents(*full[:2])
        assert isinstance(contents, tuple) and contents == decode_output_contents(*resumed[:2])

        tail = DecodeTailReuse(captured)
        tail_result = scheduler.schedule(
            **case, decode_resume=checkpoint,
            decode_checkpoints=DecodeCheckpointRequest([1, 2, 4], lambda item: None, tail_reuse=tail),
        )
        assert tail_result[0] == full[0]
        assert tail.reused_picks == 2

        changed = dict(case, seed_results=[replace(seed, op_type_id="T1")])
        with pytest.raises(ValidationError) as caught:
            scheduler.schedule(**changed, decode_resume=checkpoint)
        assert caught.value.details["reason"] == "decode_checkpoint_signature_mismatch"
        changed_rows = [replace(row, op_type_id="OTHER") if row.op_id == 99 else row for row in full[0]]
        assert decode_output_contents(changed_rows, full[1]) != contents
        changed_rows = [replace(row, seq=True) if row.op_id == 99 else row for row in full[0]]
        assert decode_output_contents(changed_rows, full[1]) != contents
        summary = deepcopy(full[1])
        summary.failure_details = [{"op_id": 99, "reasons": ["original"]}]
        frozen = decode_output_contents(full[0], summary)
        saved_summary = deepcopy(summary)
        summary.failure_details[0]["reasons"].append("changed")
        assert frozen == decode_output_contents(full[0], saved_summary)
        assert frozen != decode_output_contents(full[0], summary)

        changed = deepcopy(case)
        first = checkpoint.prefix_op_ids[0]
        changed["graph_ready_context"]["graph_priority_key_by_op_id"][first] = (999.0, 999.0)
        with pytest.raises(ValidationError) as caught:
            scheduler.schedule(**changed, decode_resume=checkpoint)
        assert caught.value.details["reason"] == "decode_checkpoint_prefix_mismatch"

        # A completed request owns no checkpoint sink: a cached resumed result is verified,
        # while an explicit fresh capture still performs a real full decode.
        owned = dict(case, machine_downtimes={}, resource_pool=None, batch_order_override=list(case["batches"]))
        archive = SharedScheduleArchive("min_overdue", target_objectives_for("min_overdue"),
                                        [op.id for op in owned["operations"]] + [99],
                                        set(owned["batches"]) | {"FROZEN"})
        started = perf_counter()
        budget = SharedSearchBudget(clock=perf_counter, started_at=started, deadline=started + 10,
                                    target_objectives=archive.target_objectives, configured_seconds=10)
        session = SharedDecodeSession(archive=archive, budget=budget, scheduler=scheduler,
                                      operations=owned["operations"], batches=owned["batches"],
                                      seed_results=owned["seed_results"], downtime_map=owned["machine_downtimes"],
                                      resource_pool=None, graph_ready_context=owned["graph_ready_context"],
                                      clock=perf_counter, started_at=started, deadline=started + 10)

        def decode(*, owner=session, decoder=scheduler, **extra):
            return decode_and_metrics(decode_session=owner, scheduler=decoder,
                                      schedule_fn=schedule_with_optional_strict_mode,
                                      expected_operations=owned["operations"], objective_name="min_overdue",
                                      **dict(owned, **extra))

        def new_session(decoder):
            begin = perf_counter()
            next_budget = SharedSearchBudget(clock=perf_counter, started_at=begin, deadline=begin + 10,
                                             target_objectives=archive.target_objectives, configured_seconds=10)
            return SharedDecodeSession(archive=archive, budget=next_budget, scheduler=decoder,
                                       operations=owned["operations"], batches=owned["batches"],
                                       seed_results=owned["seed_results"], downtime_map=owned["machine_downtimes"],
                                       resource_pool=None, graph_ready_context=owned["graph_ready_context"],
                                       clock=perf_counter, started_at=begin, deadline=begin + 10)

        def observe(decoded, elapsed):
            candidate = dict(results=decoded.results, summary=decoded.summary, metrics=decoded.metrics,
                             score=(float(decoded.summary.failed_ops),) + objective_score("min_overdue", decoded.metrics),
                             runtime_ms=7, decode_receipt=decoded.receipt)
            observation = archive.observe(candidate, validation_state="valid", decode_completed=True,
                                          origin={"origin": "checkpoint-content"}, elapsed_ms=elapsed)
            assert observation.entry_id is not None
            session.bind_observation(decoded.receipt, observation.entry_id, True, candidate=candidate)
            return observation.entry_id

        metadata = []
        metadata_statements = {"pragma main.data_version", "pragma main.schema_version",
                               "pragma temp.schema_version", "pragma query_only"}
        calendar.conn.set_trace_callback(lambda sql: metadata.append(sql)
                                         if sql.strip().lower() in metadata_statements else None)
        with patch("core.services.scheduler.run.optimizer.shared_decode.compute_metrics", wraps=compute_metrics) as metrics, \
                patch.object(native_preparation, "checkpoint_calendar_signature",
                             wraps=native_preparation.checkpoint_calendar_signature) as certificate, \
                patch.object(native_preparation, "input_value", wraps=native_preparation.input_value) as calendar_encoding:
            first_capture = []
            before_calls = scheduler._decode_invocations
            ordinary = decode()
            entry_id = observe(ordinary, 1)
            assert certificate.call_count == calendar_encoding.call_count == len(metadata) == 0
            original = decode(decode_checkpoints=DecodeCheckpointRequest([1, 2], first_capture.append))
            assert observe(original, 2) == entry_id
            assert len(first_capture) == 2 and metrics.call_count == 2
            assert certificate.call_count == calendar_encoding.call_count == 1 and len(metadata) == 4
            component = first_capture[0].signature[10]
            assert component == checkpoint.signature[10]
            assert component is session.native_preparation.checkpoint_calendar_component()
            first_found = archive.entry(entry_id).first_found_elapsed_ms
            cached_sink = []
            reused = decode(decode_resume=first_capture[0],
                            decode_checkpoints=DecodeCheckpointRequest([1, 2], cached_sink.append))
            assert reused.receipt["execution_kind"] == "decision_reused" and reused.receipt["verified"]
            assert reused.receipt["actual_decoder_calls"] == 0 and not cached_sink
            assert reused.results == original.results and reused.metrics == original.metrics
            assert metrics.call_count == 2 and scheduler._decode_invocations == before_calls + 2
            trial_context = dict(owned["graph_ready_context"])
            priority = dict(trial_context["graph_priority_key_by_op_id"])
            priority[4] = priority[2]
            trial_context["graph_priority_key_by_op_id"] = priority
            trial_sink = []
            trial = decode(graph_ready_context=trial_context, decode_resume=first_capture[0],
                           decode_checkpoints=DecodeCheckpointRequest([1, 2], trial_sink.append))
            assert trial.receipt["execution_kind"] == "trial_decode" and not trial.receipt["verified"]
            assert trial.receipt["actual_decoder_calls"] == 1 and metrics.call_count == 3
            assert trial_sink and all(item.signature[10] is component for item in trial_sink)
            recaptured_sink = []
            recaptured = decode(redecode_reason="capture_checkpoints",
                                decode_checkpoints=DecodeCheckpointRequest([1, 2], recaptured_sink.append))
            assert recaptured.receipt["execution_kind"] == "capture_checkpoints"
            assert len(recaptured_sink) == 2 and metrics.call_count == 4
            assert observe(recaptured, 9) == entry_id
            assert archive.entry(entry_id).first_found_elapsed_ms == first_found
            assert session.actual_decoder_calls == scheduler._decode_invocations - before_calls == 4
            assert session.new_decisions == session.reused_decisions == 1
            assert certificate.call_count == calendar_encoding.call_count == 1 and len(metadata) == 4
            assert all(item.signature[10] is component for item in recaptured_sink)

            next_owner = new_session(scheduler)
            assert next_owner.native_preparation is not session.native_preparation
            next_capture = []
            decode(owner=next_owner, decode_checkpoints=DecodeCheckpointRequest([1], next_capture.append))
            assert certificate.call_count == calendar_encoding.call_count == 2 and len(metadata) == 8
            assert next_capture[0].signature[10] == component

            release_components = []
            for release in (0.5, 1.5):
                overlay = ExecutionResourceCalendar(calendar, [ExecutionResourceReservation(
                    100, "M2", "O1", at(), at(release))])
                overlay_scheduler = GreedyScheduler(calendar_service=overlay, config_service={"auto_assign_enabled": "no"})
                overlay_owner = new_session(overlay_scheduler)
                overlay_capture = []
                decoded = decode(owner=overlay_owner, decoder=overlay_scheduler,
                                 decode_checkpoints=DecodeCheckpointRequest([1], overlay_capture.append))
                assert all(row.start_time >= at(release) for row in decoded.results
                           if row.operator_id == "O1" and row.op_id != 99)
                release_components.append(overlay_capture[0].signature[10])
            assert release_components[0] != release_components[1]
            assert certificate.call_count == calendar_encoding.call_count == 4 and len(metadata) == 16

            class UnregisteredCalendar:
                def __getattr__(self, name):
                    return getattr(calendar, name)

            unsupported_scheduler = GreedyScheduler(calendar_service=UnregisteredCalendar(),
                                                     config_service={"auto_assign_enabled": "no"})
            unsupported_owner = new_session(unsupported_scheduler)
            decode(owner=unsupported_owner, decoder=unsupported_scheduler)
            assert certificate.call_count == 4
            with pytest.raises(ValidationError) as caught:
                decode(owner=unsupported_owner, decoder=unsupported_scheduler,
                       decode_checkpoints=DecodeCheckpointRequest([1], lambda item: None))
            assert caught.value.details["reason"] == "decode_checkpoint_unsupported_calendar"
            assert unsupported_owner.native_preparation._calendar_signature is None
            assert certificate.call_count == 5 and calendar_encoding.call_count == 4 and len(metadata) == 16
            print("R28 native checkpoint counts:", {"same_session_certificate": 1, "same_session_encoding": 1,
                  "same_session_metadata": 4, "same_session_actual_decodes": session.actual_decoder_calls,
                  "new_session_certificate": 1, "two_release_calendars_certificate": 2,
                  "unsupported_ordinary_certificate": 0, "unsupported_capture_failures": 1,
                  "total_calendar_certificate_attempts": certificate.call_count,
                  "total_calendar_encodings": calendar_encoding.call_count, "total_metadata_pragmas": len(metadata)})
        calendar.conn.set_trace_callback(None)


def test_ig_pending_contents_bound_memory_expire_scores_and_verify_full_decode(monkeypatch):
    from tests._support.optimizer_graph_ready_benchmark import ContinuousCalendar

    search = object.__new__(ig_module._IteratedGreedySearch)
    profile = default_weight_profiles(max_weight_profiles=1)[0][0]
    search.profile = ig_module.ig_decode_profile(profile)
    search.parent = SimpleNamespace(batch_order=("B1",), order=(1,), inherited=())
    search.scores, search.pending_outputs, search.decoded_entries = {}, OrderedDict(), OrderedDict()
    search.pending_output_rows, search.scored_decodes = 0, 0
    search.checkpoints = CheckpointStore(1)
    monkeypatch.setattr(search.checkpoints, "best_for", lambda *args, **kwargs: SimpleNamespace(position=1))
    search.solution_pool = SimpleNamespace(size=3)
    search.clock, search.t_begin, search.decode_seconds = lambda: 0.0, 0.0, []
    oracle_targets = target_objectives_for("min_overdue")
    oracle_archive = SharedScheduleArchive("min_overdue", oracle_targets, (), {})
    oracle_budget = SharedSearchBudget(clock=search.clock, started_at=0.0, deadline=10.0,
                                       target_objectives=oracle_targets, configured_seconds=10)
    oracle_scheduler = GreedyScheduler(calendar_service=ContinuousCalendar(), config_service={})
    search.decode_session = SharedDecodeSession(
        archive=oracle_archive, budget=oracle_budget, scheduler=oracle_scheduler, operations=[], batches={},
        seed_results=[], downtime_map={}, resource_pool=None, clock=search.clock, started_at=0.0, deadline=10.0,
    )
    search.report = {"duplicate_decision_pruned": 0, "reference_capture_decodes": 0,
                     "validation_decodes": 0, "context_switches": 0}
    search.incumbent = SimpleNamespace(best={"score": (0.0,)}, observe_trial=lambda candidate: None, report_state=None)
    search.attempts, search.strict_mode = [], True
    accepted, evaluations = [], []
    search._consider_for_incumbent = accepted.append
    original_append_graph_attempt = ig_module.append_graph_attempt
    monkeypatch.setattr(ig_module, "append_graph_attempt", lambda **kwargs: None)
    template = {"results": [], "summary": ScheduleSummary(True, 0, 0, 0, [], [], 0.0), "score": (10.0,)}

    def evaluate(**kwargs):
        evaluations.append((kwargs["repair_decision"].operation_order, "decode_resume" in kwargs))
        return {"results": list(template["results"]), "summary": deepcopy(template["summary"]), "score": template["score"]}

    search.evaluate = evaluate
    reference = SimpleNamespace(checkpoints=[], order=(1,))
    for index in range(33):
        assert search._score_trial((index + 1,), reference) == ((10.0,), True)
    assert len(search.pending_outputs) == 32 and search.pending_output_rows == 0
    assert (1,) not in search.scores and (1,) not in search.pending_outputs
    assert search._score_trial((1,), reference) == ((10.0,), True)
    assert evaluations.count(((1,), True)) == 2

    rows = [ScheduleResult(index, "OP", "B1", index, "M1", "O1", at(), at(1), op_type_id="T1")
            for index in range(1, 20001)]
    template.update(results=rows, summary=ScheduleSummary(True, 20000, 20000, 0, [], [], 0.0))
    first, second = tuple(range(1, 20001)), (2, 1) + tuple(range(3, 20001))
    search._score_trial(first, reference)
    search._score_trial(second, reference)
    assert len(search.pending_outputs) == 1 and search.pending_output_rows == 20000
    assert first not in search.scores and first not in search.pending_outputs
    entry = search._decode_entry(second)
    assert entry is not None and entry.score == (10.0,)
    assert search.pending_output_rows == 0 and not search.pending_outputs
    assert search.scores[second] == ((10.0,), True) and search.checkpoints.equivalence_checks == 1
    assert len(accepted) == 1 and evaluations[-1] == (second, False)

    for index, changed in enumerate(("output", "score", "score_type"), 30000):
        template.update(results=[rows[0]], summary=ScheduleSummary(True, 1, 1, 0, [], [], 0.0),
                        score=(1.0,) if changed == "score_type" else (10.0,))
        order = (index,)
        search._score_trial(order, reference)
        if changed == "output":
            template["results"] = [replace(rows[0], op_type_id="T2")]
        elif changed == "score":
            template["score"] = (11.0,)
        else:
            template["score"] = (True,)
        with pytest.raises(ValidationError) as caught:
            search._decode_entry(order)
        assert caught.value.details["reason"] == "decode_checkpoint_equivalence_violation"
        assert order not in search.pending_outputs and order not in search.scores
        assert search.pending_output_rows == 0 and len(accepted) == 1

    template.update(score=(10.0,))
    search._score_trial((40000,), reference)
    search._set_parent(SimpleNamespace(batch_order=("B2",), order=(1,), inherited=()), profile)
    assert not search.pending_outputs and search.pending_output_rows == 0
    assert not search.scores and not search.decoded_entries and search.report["context_switches"] == 1

    # Keep the existing bounded-content oracle above, then exercise the new shared path
    # with native decoding, native metrics and the real archive observer.
    monkeypatch.setattr(ig_module, "append_graph_attempt", original_append_graph_attempt)
    from core.services.scheduler.graph.metrics import build_node_metrics
    from core.services.scheduler.graph.precedence_builder import build_precedence_graph
    from core.services.scheduler.graph.types import OperationGraphEdge, OperationGraphNode
    from core.services.scheduler.run.optimizer.graph.candidates import evaluate_graph_ready_candidate
    from core.services.scheduler.run.optimizer.graph.iterated_greedy_contract import (
        IteratedGreedyLimits,
        new_iterated_greedy_report,
    )
    from core.services.scheduler.run.optimizer.graph.iterated_greedy_moves import _parent_from_candidate
    from core.services.scheduler.run.optimizer.graph.repair import EliteRepairPool
    from core.services.scheduler.run.optimizer.graph.repair_contract import EliteRepairLimits
    from core.services.scheduler.run.optimizer.graph.repair_decisions import RepairDecision
    from core.services.scheduler.run.optimizer.graph.v2_features import enrich_graph_ready_v2_metrics
    from core.services.scheduler.run.optimizer.search_report import OptimizationSearchReportState
    from core.services.scheduler.run.optimizer.search_state import OptimizerSearchState
    from core.services.scheduler.run.schedule_shared_optimizer import _GoalView, _SharedSearch

    def native_search(calendar, *, clock=perf_counter, after_schedule=None):
        case = _saturated_case(batch_count=2, ops_per_batch=2)
        operations, batches, context = case["operations"], case["batches"], case["graph_ready_context"]
        case.update(seed_results=[], machine_downtimes={}, resource_pool=None,
                    batch_order_override=list(batches), dispatch_rule="slack")
        nodes = [OperationGraphNode(node_id=str(op.id), batch_id=op.batch_id, op_code=op.op_code,
                                    seq=op.seq, name=op.op_code,
                                    duration_minutes=round((op.setup_hours + op.unit_hours * batches[op.batch_id].quantity) * 60),
                                    machine_id=op.machine_id, operator_id=op.operator_id, op_type_id=op.op_type_id)
                 for op in operations]
        edges = [OperationGraphEdge(str(parent), str(child))
                 for child, parents in context["predecessor_op_ids_by_op_id"].items() for parent in parents]
        graph = build_precedence_graph(nodes, edges)
        context["node_metrics_by_op_id"] = {int(key): value for key, value in build_node_metrics(graph).items()}
        metrics = enrich_graph_ready_v2_metrics(context["node_metrics_by_op_id"], operations=operations,
                                                batches=batches, start_dt=case["start_dt"], calendar_service=calendar,
                                                graph_ready_context=context)
        scheduler = GreedyScheduler(calendar_service=calendar, config_service={"auto_assign_enabled": "no"})
        started = clock()
        archive = SharedScheduleArchive("min_overdue", target_objectives_for("min_overdue"),
                                        (op.id for op in operations), batches)
        budget = SharedSearchBudget(clock=clock, started_at=started, deadline=started + 10,
                                    target_objectives=archive.target_objectives, configured_seconds=10)
        owner = _SharedSearch(archive=archive, clock=clock, started_at=started, budget=budget)
        session = SharedDecodeSession(archive=archive, budget=budget, scheduler=scheduler, operations=operations,
                                      batches=batches, seed_results=case["seed_results"],
                                      downtime_map=case["machine_downtimes"], resource_pool=None,
                                      graph_ready_context=context, clock=clock, started_at=started, deadline=started + 10,
                                      event_sink=owner.record_event)
        owner.decode_session = session
        report = OptimizationSearchReportState(
            algorithm_profile="graph_ready", seed=0, time_budget_seconds=10, objective_name="min_overdue",
            started_at=started, strict_mode=True, candidate_clock=clock,
            candidate_observer=lambda **kw: owner.observe("min_overdue", **kw),
            candidate_acceptance_observer=lambda **kw: owner.accept("min_overdue", **kw))
        view = _GoalView("min_overdue", OptimizerSearchState(shared_archive=archive), report)
        owner.views["min_overdue"] = view
        decode_profile = ig_module.ig_decode_profile(profile)

        def schedule(decoder, **kwargs):
            try:
                return decoder.schedule(**kwargs)
            finally:
                if after_schedule is not None:
                    after_schedule(kwargs)

        def evaluate(**kwargs):
            return evaluate_graph_ready_candidate(
                graph_ready_context=context, metrics_by_op_id=metrics, scheduler=scheduler, strict_mode=True,
                algo_ops_to_schedule=operations, batches=batches, strategy=SortStrategy.PRIORITY_FIRST, params={}, start_dt=case["start_dt"],
                end_date=None, downtime_map=case["machine_downtimes"], seed_sr_list=case["seed_results"],
                dispatch_rule="slack", resource_pool=None, objective_name="min_overdue", optimizer_algo_stats=None,
                schedule_fn=schedule, readiness_gate_enabled=False, version=0, clock=clock, **kwargs)

        decision = RepairDecision(tuple(batches), tuple(op.id for op in operations))
        source = evaluate(profile=decode_profile, order=list(decision.batch_order), repair_decision=decision,
                          decode_session=session)
        report.mark_candidate_evaluated(source, origin="baseline")
        owner.sync(view)
        source = view.candidate
        parent = _parent_from_candidate(source, operations=operations, graph_context=context, resource_pool=None)
        limits = IteratedGreedyLimits(due_date_seed=False, checkpoint_count=3, max_decodes=20)
        pool = EliteRepairPool(limits=EliteRepairLimits(enabled=False), objective_name="min_overdue",
                                operations=operations, metrics_by_op_id=metrics, start_dt=case["start_dt"], seed=0,
                                best=source, report_state=report, graph_context=context, decode_session=session)
        search = ig_module._IteratedGreedySearch(
            limits=limits, parent=parent, profile=decode_profile, pool=pool, evaluate=evaluate,
            metrics_by_op_id=metrics, start_dt=case["start_dt"], seed=0, deadline=started + 10,
            clock=clock, t_begin=started, attempts=[], improvement_trace=[], report_state=report, strict_mode=True,
            report=new_iterated_greedy_report(limits, objective_name="min_overdue"), operations=operations,
            graph_context=context, decode_session=session)
        search.best = source
        return search, owner, session, scheduler

    with native_calendar() as calendar:
        native, owner, session, scheduler = native_search(calendar)
        source_entry = native.best["_shared_entry_id"]
        reference = native._decode_entry((1, 2, 3, 4), redecode_reason="capture_checkpoints")
        assert reference is not None and len(reference.checkpoints) == 3
        trial_order = (1, 3, 2, 4)
        # An actual DAG alternative preserves the first pick, so its native continuation
        # remains a trial until a full decode verifies its contents.
        resume = native.checkpoints.best_for(reference.checkpoints, base_order=reference.order,
                                              trial_order=trial_order)
        assert resume is not None and resume.prefix_length == 1
        before_entries, before_new = owner.archive.retained_entry_ids, session.new_decisions
        trial = native._decode(trial_order, resume=resume)
        assert trial is not None and not trial["decode_receipt"]["verified"]
        assert trial["decode_receipt"]["execution_kind"] == "trial_decode"
        assert owner.archive.retained_entry_ids == before_entries and session.new_decisions == before_new
        assert "_shared_entry_id" not in trial and not trial["decode_receipt"].get("observation_bound")
        assert native.report["unverified_trial_decodes"] == 1
        native._remember_output(trial_order, trial)
        verified = native._decode_entry(trial_order)
        assert verified is not None and verified.candidate["decode_receipt"]["verified"]
        assert verified.candidate["decode_receipt"]["execution_kind"] == "validation_decode"
        assert verified.candidate["decode_receipt"]["observation_bound"]
        assert native.checkpoints.equivalence_checks == 1 and not native.pending_outputs
        assert session.actual_decoder_calls == scheduler._decode_invocations == 4
        assert session.new_decisions == 2 and owner.archive.entry(source_entry).first_found_elapsed_ms >= 0

        # Expired phase-local scores do not turn a known full result back into a trial.
        native.scores.pop(trial_order)
        native.decoded_entries.pop(trial_order)
        before_calls, before_trials = session.actual_decoder_calls, native.report["unverified_trial_decodes"]
        assert native._score_trial(trial_order, reference) == (verified.score, True)
        assert session.actual_decoder_calls == before_calls and session.reused_decisions == 1
        assert native.report["unverified_trial_decodes"] == before_trials and not native.pending_outputs
        assert session.stats()["execution_counts"]["trial_decode"] == 1

    class UncertifiedCalendar(CalendarService):
        """Use the real SQLite calendar; only its concrete type lacks checkpoint certification."""

    with native_calendar(calendar_type=UncertifiedCalendar) as calendar:
        native, owner, session, scheduler = native_search(calendar)
        entry = native._decode_entry(native.parent.order, redecode_reason="capture_checkpoints")
        assert entry is not None and not entry.checkpoints
        assert native.checkpoints.disabled_reason == "decode_checkpoint_unsupported_calendar"
        assert native.report["checkpoint_capture_rejections"] == 1
        assert session.actual_decoder_calls == scheduler._decode_invocations == 3
        assert session.failed_decoder_calls == 1
        assert session.stats()["execution_counts"]["capture_checkpoints"] == 2
        assert session.new_decisions == 1

    controlled_clock = SimpleNamespace(now=0.0)

    def exhaust_after_capture(kwargs):
        controlled_clock.now = 10.0 if kwargs.get("decode_checkpoints") is not None else 0.1

    with native_calendar(calendar_type=UncertifiedCalendar) as calendar:
        native, owner, session, scheduler = native_search(
            calendar, clock=lambda: controlled_clock.now, after_schedule=exhaust_after_capture)
        order = native.parent.order
        assert native._decode_entry(order, redecode_reason="capture_checkpoints") is None
        assert native.last_decode_skip is not None and native.last_decode_skip.reason == "time_budget"
        assert order not in native.scores and order not in native.decoded_entries
        assert session.actual_decoder_calls == scheduler._decode_invocations == 2
        assert session.failed_decoder_calls == session.skipped_requests == 1
        assert session.new_decisions == 1 and len(owner.archive.retained_entry_ids) == 1


def test_calendar_content_cache_does_not_reuse_rolled_back_transaction(schema_conn):
    conn = schema_conn
    conn.execute("INSERT INTO WorkCalendar (date,shift_hours,efficiency) VALUES ('2026-09-08',8,1)")
    conn.commit()
    calendar = CalendarService(conn)
    original_reader = CalendarCheckpointRepository.calendar_signature_rows
    with patch.object(CalendarCheckpointRepository, "calendar_signature_rows", autospec=True,
                      side_effect=original_reader) as reader:
        original = calendar_checkpoint_snapshot(calendar)
        assert original[0] == "calendar-business-v1" and isinstance(original[1], tuple)
        assert calendar_checkpoint_snapshot(calendar) is original
        assert reader.call_count == 1

        conn.execute("BEGIN")
        conn.execute("UPDATE WorkCalendar SET efficiency=0.5 WHERE date='2026-09-08'")
        changed = calendar_checkpoint_snapshot(calendar)
        before_rollback = conn.total_changes
        assert changed != original and "_decode_checkpoint_calendar_cache" not in vars(calendar)
        conn.rollback()
        conn.execute("BEGIN")
        assert conn.total_changes == before_rollback
        assert calendar_checkpoint_snapshot(calendar) == original
        assert reader.call_count == 3
        conn.rollback()

        conn.execute("PRAGMA query_only=ON")
        readonly = calendar_checkpoint_snapshot(calendar)
        assert readonly == original and calendar_checkpoint_snapshot(calendar) is readonly
        assert reader.call_count == 4
