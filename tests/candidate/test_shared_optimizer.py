"""One shared optimizer session uses real decodes and preserves business input constraints."""

from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime, timedelta
from functools import partial
from random import Random
from time import monotonic
from types import SimpleNamespace
from typing import Callable
from unittest.mock import patch

import pytest

from core.algorithm_contracts.sort_strategies import SortStrategy
from core.algorithm_contracts.types import ScheduleResult
from core.algorithms import evaluation_completion as evaluation_inputs
from core.algorithms.evaluation import compute_metrics, objective_score, prepare_evaluation_context
from core.algorithms.greedy import scheduler as native_scheduler_module
from core.algorithms.greedy.auto_assign import qualified_resource_pairs
from core.algorithms.greedy.dispatch.sgs_checkpoint import DecodeCheckpointRequest
from core.algorithms.greedy.scheduler import GreedyScheduler
from core.models.objective import objective_metric_keys, target_objectives_for
from core.models.schedule_config_runtime_fields import default_snapshot_values
from core.models.schedule_config_runtime_snapshot import snapshot_from_values
from core.services.scheduler.graph.analysis_service import ScheduleGraphAnalysisService
from core.services.scheduler.graph.input_adapter import build_operation_nodes_from_rows
from core.services.scheduler.run import schedule_shared_search
from core.services.scheduler.run.optimizer import shared_process
from core.services.scheduler.run.optimizer.candidate_fingerprint import schedule_content_key
from core.services.scheduler.run.optimizer.graph.candidates import (
    PreparedDecisionFeatures,
    evaluate_graph_ready_candidate,
)
from core.services.scheduler.run.optimizer.graph.iterated_greedy import _IteratedGreedySearch
from core.services.scheduler.run.optimizer.graph.iterated_greedy_acceptance import PoolEntry, SolutionPool
from core.services.scheduler.run.optimizer.graph.iterated_greedy_contract import (
    IteratedGreedyLimits,
    ig_decode_profile,
    new_iterated_greedy_report,
)
from core.services.scheduler.run.optimizer.graph.iterated_greedy_iteration import IGIteration
from core.services.scheduler.run.optimizer.graph.iterated_greedy_moves import _parent_from_candidate
from core.services.scheduler.run.optimizer.graph.iterated_greedy_reference import capture_reference, decode_reference
from core.services.scheduler.run.optimizer.graph.iterated_greedy_run import IteratedGreedyRun
from core.services.scheduler.run.optimizer.graph.ready import GraphStageBundle
from core.services.scheduler.run.optimizer.graph.repair import EliteRepairPool
from core.services.scheduler.run.optimizer.graph.repair_contract import EliteRepairLimits
from core.services.scheduler.run.optimizer.graph.repair_decisions import prepare_repair_parent
from core.services.scheduler.run.optimizer.graph.stages import GraphSearchState, IteratedGreedyStage
from core.services.scheduler.run.optimizer.graph.v2_features import enrich_graph_ready_v2_metrics
from core.services.scheduler.run.optimizer.graph.v2_ranks import build_v2_common_rank_cache
from core.services.scheduler.run.optimizer.graph_ready_profiles import (
    GRAPH_READY_V2_ITERATED_GREEDY_ORIGIN,
    resolve_v2_profiles,
)
from core.services.scheduler.run.optimizer.local_search import LocalSearchStage
from core.services.scheduler.run.optimizer.multi_start import _evaluate_multi_start_candidate
from core.services.scheduler.run.optimizer.runtime import _default_runtime, resolve_runtime
from core.services.scheduler.run.optimizer.search_budget import SearchBudget
from core.services.scheduler.run.optimizer.search_report import OptimizationSearchReportState
from core.services.scheduler.run.optimizer.search_stage import SearchStage
from core.services.scheduler.run.optimizer.search_state import OptimizerSearchState
from core.services.scheduler.run.optimizer.shared_archive import CandidateArchiveRef, SharedScheduleArchive
from core.services.scheduler.run.optimizer.shared_budget import SharedSearchBudget, SharedSearchSkip
from core.services.scheduler.run.optimizer.shared_decode import SharedDecodeSession, decode_and_metrics
from core.services.scheduler.run.schedule_candidate_runner import _business_representative, run_candidate_comparison
from core.services.scheduler.run.schedule_graph_report import ScheduleGraphDispatchPreparation
from core.services.scheduler.run.schedule_input_contracts import ScheduleRunInput
from core.services.scheduler.run.schedule_shared_optimizer import optimize_shared_schedule
from core.services.workbench.facts.piece_scope import build_piece_adoption_scope
from core.services.workbench.run.compute_graph import piece_graph_preparer
from tests._support.algo_operations import make_algo_op, make_batch
from tests._support.optimizer_business_cases import batch_operation_from_fixture
from tests._support.optimizer_graph_ready_benchmark import (
    START_DT,
    ContinuousCalendar,
    graph_ready_benchmark_batches,
    graph_ready_benchmark_context,
    graph_ready_benchmark_operations,
)
from tests._support.schedule_decode import production_decode
from tests._support.shared_schedule_archive import _observe_decoded, _register_decode


class RecordingScheduler(GreedyScheduler):
    """Record inputs and actual outputs while every solve remains the native greedy scheduler."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.calls = []

    def schedule_prepared(self, prepared_inputs, **changes):
        context = changes["graph_ready_context"]
        record = {
            "dispatch_mode": changes["params"].dispatch_mode_key,
            "graph_ready_context": ({key: deepcopy(value) for key, value in context.items()
                                     if "topology" not in key} if context is not None else None),
            "operations": deepcopy(changes["operations"]),
            "seed_results": deepcopy(prepared_inputs.seed_results),
            "resource_pool": changes["resource_pool"],
            "decode_checkpoints": changes["decode_checkpoints"] is not None,
            "decode_resume": changes["decode_resume"] is not None,
        }
        self.calls.append(record)
        results, summary, strategy, params = super().schedule_prepared(prepared_inputs, **changes)
        record.update(results=[replace(row) for row in results], summary=deepcopy(summary))
        return results, summary, strategy, params


class PausedIteration(IGIteration):
    """Keep the in-flight trial paused while testing the shared adoption boundary."""

    def step(self) -> bool:
        return True


class CallbackStage(SearchStage):
    name = "local_search"

    def __init__(self, action: Callable[[], object]) -> None:
        self.action = action

    def run_task(self) -> None:
        self.action()


def _config(*, mode="improve", graph="on"):
    values = default_snapshot_values()
    values.update(sort_strategy="fifo", dispatch_mode="batch_order", dispatch_rule="slack",
                  auto_assign_enabled="yes", objective="min_overdue", algo_mode=mode,
                  time_budget_seconds=1, ortools_enabled="no", freeze_window_enabled="no", freeze_window_days=0,
                  graph_analysis_mode=graph)
    return snapshot_from_values(values)


def _runtime(created):
    def factory(**kwargs):
        scheduler = RecordingScheduler(**kwargs)
        created.append(scheduler)
        return scheduler

    return replace(_default_runtime(), scheduler_factory=factory, clock=monotonic, rng_factory=Random)


def _run_budget(cfg):
    """The run budget exactly as its only producer (run_candidate_comparison) builds it."""
    seconds = float(cfg.time_budget_seconds)
    started = monotonic()
    return SearchBudget(clock=monotonic, started_at=started, deadline=started + seconds, assigned_seconds=seconds)


def _shared_budget(archive, started_at, seconds=10.0):
    return SharedSearchBudget(clock=monotonic, started_at=started_at, deadline=started_at + seconds,
                              target_objectives=archive.target_objectives, configured_seconds=seconds)


def _fixed_seed():
    return ScheduleResult(
        op_id=99, op_code="FIXED", batch_id="B_LONG", seq=1, machine_id="MC-BENCH", operator_id="OP-BENCH",
        start_time=START_DT, end_time=START_DT + timedelta(hours=1), source="internal", op_type_name="BENCH",
        seed_source="execution_fact", state_revision="r1", op_type_id="OT-BENCH",
    )


def _linear_fixture():
    operations, batches = graph_ready_benchmark_operations(), graph_ready_benchmark_batches()
    operations[1].batch_id, operations[1].seq = "B_LONG", 20
    del batches["B_MED"]
    for op in operations[2:]:
        op.machine_id = op.operator_id = None
    context = graph_ready_benchmark_context()
    context["fixed_op_ids"] = {99}
    context["fixed_op_sources_by_op_id"] = {99: "seed"}
    context["predecessor_op_ids_by_op_id"].update({99: set(), 1: {99}, 2: {1}})
    context["successor_op_ids_by_op_id"].update({99: {1}, 1: {2}})
    pool = {
        "machines_by_op_type": {"OT-BENCH": ["MC-BENCH", "MC-ALT"]},
        "machines_by_operator": {},
        "operators_by_machine": {"MC-BENCH": ["OP-BENCH"], "MC-ALT": ["OP-ALT"]},
    }
    downtime = {"MC-ALT": [(START_DT, START_DT + timedelta(hours=4))]}
    return operations, batches, context, pool, downtime, _fixed_seed()


def _comparison_input(*, cfg, calendar, operations, batches, seeds, pool, downtime):
    batch_operations = [batch_operation_from_fixture(vars(operation)) for operation in operations]
    operation_ids = {operation.id for operation in operations}
    frozen_ids = {row["op_id"] for row in seeds}
    return ScheduleRunInput(
        cfg=cfg, cal_svc=calendar, start_dt_norm=START_DT, end_date_norm=None,
        normalized_batch_ids=list(batches), t0=0.0, readiness_gate_enabled=False,
        batches=dict(batches),
        operations=batch_operations, missing_internal_resource_op_ids=set(),
        algo_ops=operations, algo_ops_to_schedule=operations,
        prev_version=0, frozen_op_ids=frozen_ids, seed_results=seeds, execution_facts={},
        execution_completed_op_ids=set(), execution_seed_results=[],
        execution_snapshot_revision="fixture", execution_snapshot_op_ids=[], execution_snapshot_op_count=0,
        schedule_output_allowed_op_ids=operation_ids | frozen_ids, payload_validation_operations=batch_operations,
        freeze_meta={}, downtime_meta={}, resource_pool_meta={},
        downtime_map=downtime, resource_pool=pool, optimizer_seed_version=0,
    )


def _piece_fixture(cfg):
    operations = graph_ready_benchmark_operations()
    for op, piece, sequence, machine, operator in (
        (operations[0], "item-A", 20, "MC-BENCH", "OP-BENCH"),
        (operations[1], "item-B", 20, "MC-ALT", "OP-ALT"),
        (operations[2], "item-A", 30, "MC-BENCH", "OP-BENCH"),
        (operations[3], "item-B", 30, "MC-ALT", "OP-ALT"),
    ):
        op.batch_id, op.piece_id, op.seq = "B_LONG", piece, sequence
        op.machine_id, op.operator_id = machine, operator
    fixed = replace(operations[0], id=99, op_code="FIXED", piece_id=None, seq=10, setup_hours=1.0)
    join = replace(fixed, id=100, op_code="JOIN", seq=40)
    operations.append(join)
    batches = {"B_LONG": graph_ready_benchmark_batches()["B_LONG"]}
    batches["B_LONG"].quantity = 2
    seed = replace(_fixed_seed(), seq=10)
    prepared = SimpleNamespace(
        operations=[fixed] + operations, batches=batches, algo_ops=[fixed] + operations,
        algo_ops_to_schedule=operations, frozen_op_ids={99}, seed_results=[asdict(seed)],
        resource_pool=None, cfg=cfg, piece_scope=build_piece_adoption_scope([fixed] + operations, {"B_LONG": 2}),
    )
    return prepared, seed


def _assert_arrangement(results, *, operations, seed, context, pool, downtime):
    rows = {row.op_id: row for row in results}
    assert set(rows) == {99} | {op.id for op in operations}
    assert len(rows) == len(results) and rows[99] == seed
    for op in operations:
        row = rows[op.id]
        if op.machine_id:
            assert row.machine_id == op.machine_id and row.operator_id == op.operator_id
        else:
            assert row.machine_id in pool["machines_by_op_type"][op.op_type_id]
            assert row.operator_id in pool["operators_by_machine"][row.machine_id]
        assert row.start_time >= START_DT and row.end_time > row.start_time
        assert all(row.start_time >= rows[previous].end_time
                   for previous in context["predecessor_op_ids_by_op_id"].get(op.id, ()))
        assert not any(row.start_time < end and start < row.end_time
                       for start, end in downtime.get(row.machine_id, ()))
    for field in ("machine_id", "operator_id"):
        for index, left in enumerate(results):
            for right in results[index + 1:]:
                if getattr(left, field) == getattr(right, field):
                    assert not (left.start_time < right.end_time and right.start_time < left.end_time)


def _assert_target_evaluations(archive, entry_id, *, operations, batches, seed):
    candidate = archive.materialize(entry_id)
    metrics = compute_metrics(candidate["results"], batches, expected_operations=operations,
                              seed_results=[seed], failure_details=candidate["summary"].failure_details)
    entry = archive.entry(entry_id)
    assert set(entry.evaluations) == set(target_objectives_for("min_overdue"))
    for objective, evaluation in entry.evaluations.items():
        assert evaluation.field_order == ("failed_ops",) + objective_metric_keys(objective)
        assert evaluation.score == (float(candidate["summary"].failed_ops),) + objective_score(objective, metrics)


def _assert_controlled_worse_reference_keeps_source():
    operations, batches = [], {}
    for op_id, hours in enumerate((12.0, 8.0, 2.0), 1):
        batch_id = f"B{op_id}"
        operations.append(make_algo_op(id=op_id, op_code=f"OP{op_id}", batch_id=batch_id, seq=10, setup_hours=hours,
                                       unit_hours=0.0, op_type_id="T", op_type_name="T"))
        batches[batch_id] = make_batch(batch_id=batch_id, due_date="2026-01-01")
    pool = {"machines_by_op_type": {"T": ["M"]}, "machines_by_operator": {}, "operators_by_machine": {"M": ["O"]}}
    scheduler = GreedyScheduler(calendar_service=ContinuousCalendar(), config_service=_config(mode="greedy"))
    started_at = monotonic()
    decoded = production_decode(
        scheduler, operations=operations, batches=batches, strategy=SortStrategy.FIFO, strategy_params={}, start_dt=START_DT,
        dispatch_mode="batch_order", dispatch_rule="slack", batch_order_override=["B3", "B2", "B1"],
        resource_pool=pool, machine_downtimes={}, seed_results=[],
    )
    results, summary, strategy, params = decoded.results, decoded.summary, decoded.used_strategy, decoded.used_params
    metrics = compute_metrics(results, batches, expected_operations=operations, seed_results=[],
                              failure_details=summary.failure_details)
    ordinary = {"results": results, "summary": summary, "strategy": strategy, "params": params,
                "metrics": metrics, "score": (float(summary.failed_ops),) + objective_score("min_overdue", metrics),
                "dispatch_mode": "batch_order", "dispatch_rule": "slack", "order": ["B3", "B2", "B1"],
                "resource_pool": pool, "candidate_origin": "multi_start", "seed_result_count": 0,
                "locked_seed_range": []}
    assert summary.success and summary.failed_ops == 0
    assert (metrics.overdue_count, metrics.total_tardiness_hours) == (1, 6.0)
    archive = SharedScheduleArchive("min_overdue", target_objectives_for("min_overdue"), {1, 2, 3}, set(batches))
    session = schedule_shared_search.SharedSearch(archive=archive, clock=monotonic, started_at=started_at,
                                                  budget=_shared_budget(archive, started_at))
    report = OptimizationSearchReportState(
        objective_name="min_overdue",
        started_at=started_at, candidate_clock=monotonic,
        candidate_observer=partial(session.observe, "min_overdue"),
        candidate_acceptance_observer=partial(session.accept, "min_overdue"),
        reference_capture_observer=partial(session.capture, "min_overdue"),
    )
    view = schedule_shared_search.GoalView("min_overdue", OptimizerSearchState(), report)
    session.views[view.objective] = view
    session.phase = "multi_start"
    _register_decode(archive, ordinary)
    fingerprint = report.mark_candidate_evaluated(ordinary, origin="multi_start")
    report.mark_candidate_accepted(ordinary, origin="multi_start", fingerprint=fingerprint)
    session.sync(view)
    source = view.candidate
    source_id = view.entry_id
    assert source is not None and source_id is not None
    source_snapshot = archive.entry(source_id)
    source_results = deepcopy(source["results"])
    nodes = build_operation_nodes_from_rows(operations, batches=batches, resource_pool=pool)
    node_metrics = ScheduleGraphAnalysisService().analyze_precedence(nodes, []).node_metrics
    context = {
        "enabled": True, "schedulable_op_ids": {1, 2, 3}, "fixed_op_ids": set(), "fixed_op_sources_by_op_id": {},
        "predecessor_op_ids_by_op_id": {op.id: set() for op in operations},
        "successor_op_ids_by_op_id": {op.id: set() for op in operations},
        "sort_key_by_op_id": {op.id: (0, op.seq, op.id) for op in operations},
        "graph_priority_key_by_op_id": {op.id: (0.0,) for op in operations},
        "node_metrics_by_op_id": {node.raw["id"]: node_metrics[node.node_id] for node in nodes},
    }
    parent = _parent_from_candidate(source, graph_context=context, prepared=prepare_repair_parent(
        source, operations, context, resource_pairs_for=partial(qualified_resource_pairs, resource_pool=pool)))
    assert parent is not None and parent.order == (3, 2, 1)
    assert parent.inherited == ((1, "M", "O"), (2, "M", "O"), (3, "M", "O"))
    graph_metrics = enrich_graph_ready_v2_metrics(
        context["node_metrics_by_op_id"], operations=operations, batches=batches, start_dt=START_DT,
        calendar_service=scheduler.calendar, resource_pool=pool, downtime_map={}, graph_ready_context=context,
        seed_results=[],
    )
    profile = ig_decode_profile(next(p for p in resolve_v2_profiles(seed=0, objective_name="min_overdue") if p.slug == "balanced"))
    limits = IteratedGreedyLimits(due_date_seed=False, checkpoint_count=2, max_decodes=2, max_iterations=1)
    ig_report = new_iterated_greedy_report(limits, objective_name="min_overdue")
    owned_seeds, owned_downtime = [], {}
    decode_budget = SharedSearchBudget(clock=monotonic, started_at=started_at, deadline=started_at + 1,
                                       target_objectives=archive.target_objectives, configured_seconds=1)
    session.decode_session = SharedDecodeSession(
        archive=archive, budget=decode_budget, scheduler=scheduler, operations=operations, batches=batches,
        seed_results=owned_seeds, downtime_map=owned_downtime, resource_pool=pool, graph_ready_context=context,
        clock=monotonic, started_at=started_at, deadline=started_at + 1, event_sink=session.record_event,
    )
    repair_pool = EliteRepairPool(limits=EliteRepairLimits(), objective_name="min_overdue",
                                  operations=operations, metrics_by_op_id=graph_metrics, start_dt=START_DT, seed=0,
                                  best=source, report_state=report, graph_context=context,
                                  decode_session=session.decode_session)

    decision_features = PreparedDecisionFeatures(graph_metrics, build_v2_common_rank_cache(graph_metrics))

    def evaluate(**kwargs):
        return evaluate_graph_ready_candidate(
            prepared_decision_features=decision_features,
            strategy=strategy, params={}, start_dt=START_DT,
            end_date=None, dispatch_rule="slack", resource_pool=pool,
            objective_name="min_overdue", optimizer_algo_stats=None,
            readiness_gate_enabled=False, version=0, clock=monotonic, **kwargs,
        )

    search = _IteratedGreedySearch(
        limits=limits, parent=parent, profile=profile, pool=repair_pool, evaluate=evaluate,
        metrics_by_op_id=graph_metrics, start_dt=START_DT, seed=0, deadline=started_at + 1.0, clock=monotonic,
        t_begin=started_at, attempts=[], improvement_trace=[], report_state=report,
        report=ig_report, operations=operations, graph_context=context, decode_session=session.decode_session,
    )
    search.best = source
    session.phase = "controlled_reference_order"
    before_decodes = scheduler._decode_invocations
    reference = decode_reference(search, (1, 2, 3), before=source, reference_kind="controlled_reference_order")
    assert reference is not None and reference.order == (1, 2, 3)
    assert scheduler._decode_invocations - before_decodes == ig_report["decodes"] == 1
    assert session.decode_session.actual_decoder_calls == 1
    assert search.checkpoints.full_decodes == 1 and search.checkpoints.resumed_decodes == 0
    assert len(reference.checkpoints) == 2
    assert reference.candidate["summary"].success and reference.candidate["summary"].failed_ops == 0
    assert (reference.candidate["metrics"].overdue_count, reference.candidate["metrics"].total_tardiness_hours) == (2, 10.0)
    assert reference.score > source["score"]
    after_id = reference.candidate["archive_ref"].entry_id
    assert after_id != source_id and source_id in archive and after_id in archive
    assert archive.entry(after_id).content_key != source_snapshot.content_key
    assert archive.best_by_objective == {objective: source_id for objective in archive.target_objectives}
    assert archive.improvement_counts == {objective: 0 for objective in archive.target_objectives}
    assert archive.entry(source_id).content_key == source_snapshot.content_key
    assert archive.entry(source_id).first_found_elapsed_ms == source_snapshot.first_found_elapsed_ms
    assert archive.materialize(source_id)["results"] == source_results
    assert search.best is source
    observations = [event for event in session.events if event["event_type"] == "archive_observation"]
    assert len(observations) == 2 and observations[-1]["entry_id"] == after_id and observations[-1]["verified"]
    assert observations[-1]["origin"] == GRAPH_READY_V2_ITERATED_GREEDY_ORIGIN
    adopted_origin = archive.entry(after_id).evidence_origin
    assert adopted_origin["origin"] == GRAPH_READY_V2_ITERATED_GREEDY_ORIGIN
    assert adopted_origin["phase"] == "controlled_reference_order" and adopted_origin["search_objective"] == view.objective
    assert len(session.bridges) == 1
    bridge = session.bridges[0]
    assert bridge["reference_kind"] == bridge["phase"] == "controlled_reference_order"
    assert bridge["before_entry_id"] == source_id and bridge["after_entry_id"] == after_id
    assert bridge["decoder_executed"] is True and bridge["same_arrangement"] is False
    assert bridge["elapsed_ms"] >= 0 and bridge["finished_elapsed_ms"] >= bridge["started_elapsed_ms"]
    assert session.events[-1]["event_type"] == "reference_capture"
    assert session.events[-1]["event_id"] == bridge["source_event_id"]
    return session, view, search, reference, scheduler


def test_unaffordable_required_ig_capture_stops_stage_and_preserves_other_work():
    from core.services.scheduler.run.optimizer.candidate_profile import derive_grasp_ig_limits
    from core.services.scheduler.run.optimizer.graph.budget import GraphReadySearchBudget
    from core.services.scheduler.run.optimizer.graph.iterated_greedy_contract import _BudgetExhausted
    from core.services.scheduler.run.optimizer.graph.predecode import GraphReadyProfileSearch
    from core.services.scheduler.run.optimizer.graph.repair import EliteRepairRun
    from core.services.scheduler.run.optimizer.graph.stages import ProfileStage, RepairStage
    from core.services.scheduler.run.optimizer.grasp_ig_candidates import GraspIGStage
    from core.services.scheduler.run.optimizer.multi_start import MultiStartStage
    from core.services.scheduler.run.schedule_shared_optimizer import _next_stage

    session, view, search, reference, scheduler = _assert_controlled_worse_reference_keeps_source()
    decoder = session.decode_session
    assert decoder is not None
    now = monotonic()

    def clock():
        return now

    deadline = now + 2.0
    budget = SharedSearchBudget(clock=clock, started_at=now - 8.0, deadline=deadline,
                                target_objectives=session.archive.target_objectives, configured_seconds=10)
    budget.record_decode("sgs_full", 6.0)
    budget.record_decode("batch_order_full", 0.1)
    decoder.budget, decoder.clock, decoder.deadline = budget, clock, deadline
    search.clock, search.deadline = clock, deadline
    search.report["decodes"] = 0
    search.reference = reference
    search.best = reference.candidate
    old_parent, old_profile = search.parent, search.profile
    state = GraphSearchState(view.candidate)
    run = IteratedGreedyRun(
        limits=search.limits, state=state, parent_profile=lambda candidate: search.profile,
        pool=search.pool, evaluate=search.evaluate, operations=search.operations, graph_context=search.graph_context,
        metrics_by_op_id=search.metrics, objective_name=view.objective, start_dt=search.start_dt,
        seed=0, deadline=deadline, clock=clock, t_begin=now - 8.0, attempts=[], improvement_trace=[],
        report_state=view.report, decode_session=decoder,
    )
    run.search, run.report, run.started_at = search, search.report, now
    ig = IteratedGreedyStage(run, startup_ready=lambda: True)
    ordinary = MultiStartStage(
        keys=[SortStrategy.FIFO.value], dispatch_modes=["sgs", "batch_order"], dispatch_rule_cfg="slack",
        valid_dispatch_rules=["slack"], start_dt=START_DT, end_date=None,
        cfg=scheduler.config, resource_pool=decoder.resource_pool,
        objective_name=view.objective, deadline=deadline, t_begin=now - 8.0,
        build_order=lambda strategy, params: list(decoder.batches), clock=clock,
        search_report_state=view.report, state=view.state, decode_session=decoder,
    )
    view.stages = [ig, ordinary]
    before_calls, before_skips = decoder.actual_decoder_calls, decoder.skipped_requests
    assert _next_stage(view) is ig
    ig.run_task()
    assert not ig.available() and ig.unavailable_reason() == "estimated_decode_cost"
    assert run.stopped and run.report["stop_reason"] == "estimated_decode_cost"
    assert search.parent is old_parent and search.profile == old_profile and search.reference is reference
    assert search.best is state.best is view.candidate
    assert decoder.actual_decoder_calls == before_calls and decoder.skipped_requests == before_skips + 1
    # A previously decoded reference still reuses its checkpoints without admission.
    assert search._decode_entry(reference.order) is reference
    # MultiStart skips the unaffordable sgs mode once, then still runs the affordable batch_order mode.
    assert _next_stage(view) is ordinary
    ordinary.run_task()
    assert ordinary.available()
    assert decoder.actual_decoder_calls == before_calls and decoder.skipped_requests == before_skips + 2
    assert _next_stage(view) is ordinary
    ordinary.run_task()
    assert ordinary.efficiency["decoded_candidates"] == 1
    assert decoder.actual_decoder_calls == before_calls + 1 and decoder.skipped_requests == before_skips + 2
    assert _next_stage(view) is None
    ig.finish()
    assert run.report["status"] == "skipped_by_budget"
    assert run.report["stop_reason"] == "estimated_decode_cost"

    # When sgs_resume + sgs_full exceeds the remaining time (or only one decode slot remains) but a single
    # verified sgs_full still fits, _score_trial degrades to one full verified decode and never exceeds max_decodes.
    budget.record_decode("sgs_full", 6.0, unpruned_sgs=True)
    for _ in range(3):
        budget.record_decode("sgs_full", 1.0)
        budget.record_decode("sgs_resume", 0.8)
        budget.record_decode("batch_order_full", 0.1)
    capped_limits = replace(search.limits, max_decodes=2)
    capped_report = new_iterated_greedy_report(capped_limits, objective_name=view.objective)
    capped_search = _IteratedGreedySearch(
        limits=capped_limits, parent=old_parent, profile=old_profile, pool=search.pool, evaluate=search.evaluate,
        metrics_by_op_id=search.metrics, start_dt=search.start_dt, seed=2, deadline=deadline, clock=clock,
        t_begin=now - 8.0, attempts=[], improvement_trace=[], report_state=view.report,
        report=capped_report, operations=search.operations, graph_context=search.graph_context, decode_session=decoder,
    )
    capped_search.best, capped_search.reference = reference.candidate, reference
    before_calls, before_skips = decoder.actual_decoder_calls, decoder.skipped_requests
    trial_order = (reference.order[0], reference.order[2], reference.order[1])
    assert capped_search.checkpoints.best_for(reference.checkpoints, base_order=reference.order, trial_order=trial_order) is not None
    assert not budget.can_afford_decode("sgs_resume", reserve_full=True)
    assert budget.can_afford_decode("sgs_full")
    scored = capped_search._score_trial(trial_order, reference)
    assert scored is not None and not capped_search.pending_outputs
    assert capped_report["decodes"] == 1
    assert decoder.actual_decoder_calls == before_calls + 1 and decoder.skipped_requests == before_skips
    for _ in range(3):
        budget.record_decode("sgs_resume", 0.1)
    assert budget.can_afford_decode("sgs_resume", reserve_full=True)
    next_order = (reference.order[2], reference.order[0], reference.order[1])
    assert capped_search._score_trial(next_order, reference) is not None
    assert not capped_search.pending_outputs and capped_report["decodes"] == capped_limits.max_decodes == 2
    with pytest.raises(_BudgetExhausted) as cap_hit:
        capped_search._decode((reference.order[1], reference.order[0], reference.order[2]))
    assert cap_hit.value.reason == "decode_budget"
    assert capped_report["decodes"] == capped_limits.max_decodes

    # LocalSearchStage tracks cost rejections per dispatch_mode: when sgs is unaffordable and best adopts
    # an affordable batch_order candidate, local search restarts into batch_order and switches VNS neighborhoods.
    assert view.candidate is not None
    sgs_best = dict(view.candidate, dispatch_mode="sgs", dispatch_rule="slack")
    batch_best = dict(view.candidate, dispatch_mode="batch_order", dispatch_rule="slack",
                      order=["B3", "B1", "B2"])
    mode_stage = LocalSearchStage(
        best=sgs_best, version=0, deadline=deadline, batches=decoder.batches,
        start_dt=START_DT, end_date=None, dispatch_mode_cfg="sgs", dispatch_rule_cfg="slack",
        resource_pool=decoder.resource_pool, objective_name=view.objective, attempts=[], improvement_trace=[],
        optimizer_algo_stats=None, t_begin=now - 8.0, readiness_gate_enabled=False,
        clock=clock, rng_factory=Random, search_report_state=view.report, decode_session=decoder,
    )
    assert mode_stage.vns_state.neighborhoods == ("sgs_dispatch_rule",)
    mode_stage.run_task()
    assert not mode_stage.available() and mode_stage.unavailable_reason() == "estimated_decode_cost"
    mode_stage.best = batch_best
    assert mode_stage.available() and mode_stage.pending_restart
    mode_stage.run_task()
    assert mode_stage.available()
    assert mode_stage.strategy_state[2] == "batch_order"
    assert mode_stage.vns_state.neighborhoods != ("sgs_dispatch_rule",)

    # When every decode kind exceeds the remaining time, each stage stops on its first budget rejection
    # instead of staying available and tail-spinning across thousands of no-decode actions.
    for _ in range(3):
        budget.record_decode("batch_order_full", 6.0)
        budget.record_decode("sgs_full", 6.0, unpruned_sgs=True)
        budget.record_decode("sgs_resume", 6.0)
    local_stage = LocalSearchStage(
        best=view.candidate, version=0, deadline=deadline, batches=decoder.batches,
        start_dt=START_DT, end_date=None, dispatch_mode_cfg="sgs", dispatch_rule_cfg="slack",
        resource_pool=decoder.resource_pool, objective_name=view.objective, attempts=[], improvement_trace=[],
        optimizer_algo_stats=None, t_begin=now - 8.0, readiness_gate_enabled=False,
        clock=clock, rng_factory=Random, search_report_state=view.report, decode_session=decoder,
    )
    grasp_stage = GraspIGStage(
        version=7, candidate_construction=derive_grasp_ig_limits(10),
        start_dt=START_DT, end_date=None, base_strategy=SortStrategy.FIFO, base_params={},
        build_order=lambda strategy, params: list(reversed(decoder.batches)), dispatch_rule_cfg="cr",
        resource_pool=decoder.resource_pool, objective_name=view.objective, deadline=deadline,
        optimizer_algo_stats=None, t_begin=now - 8.0, readiness_gate_enabled=False,
        clock=clock, rng_factory=Random, search_report_state=view.report, state=view.state, decode_session=decoder,
    )
    graph_budget = GraphReadySearchBudget(deadline=deadline, clock=clock)
    profiles = [p for slug in ("v2_spt", "v2_successor_edd") for p in resolve_v2_profiles(seed=0, objective_name="min_overdue") if p.slug == slug]
    graph_evaluate = partial(search.evaluate, decode_session=decoder)
    profile_search = GraphReadyProfileSearch(evaluate=graph_evaluate, budget=graph_budget, profile_count=len(profiles))
    repair_pool = EliteRepairPool(
        limits=EliteRepairLimits(), objective_name=view.objective, operations=search.operations,
        metrics_by_op_id=search.metrics, start_dt=START_DT, seed=0, best=view.candidate, report_state=view.report,
        graph_context=search.graph_context, decode_session=decoder,
    )
    assert view.candidate is not None
    repair_pool.observe(view.candidate, profiles[0])
    profile_stage = ProfileStage(
        profiles=profiles, search=profile_search, pool=repair_pool, state=state,
        order=list(decoder.batches), attempts=[], improvement_trace=[], search_report_state=view.report,
        clock=clock, t_begin=now - 8.0,
    )
    repair_run = EliteRepairRun(
        pool=repair_pool, state=state, evaluate=graph_evaluate, budget=graph_budget,
        deadline=deadline, clock=clock, t_begin=now - 8.0, attempts=[], improvement_trace=[],
        report_state=view.report,
    )
    repair_stage = RepairStage(repair_run)
    trial_report = new_iterated_greedy_report(search.limits, objective_name=view.objective)
    trial_search = _IteratedGreedySearch(
        limits=search.limits, parent=old_parent, profile=old_profile, pool=repair_pool, evaluate=search.evaluate,
        metrics_by_op_id=search.metrics, start_dt=search.start_dt, seed=1, deadline=deadline, clock=clock,
        t_begin=now - 8.0, attempts=[], improvement_trace=[], report_state=view.report,
        report=trial_report, operations=search.operations, graph_context=search.graph_context, decode_session=decoder,
    )
    trial_search.best, trial_search.reference = reference.candidate, reference
    trial_run = IteratedGreedyRun(
        limits=search.limits, state=state, parent_profile=lambda candidate: old_profile,
        pool=repair_pool, evaluate=search.evaluate, operations=search.operations, graph_context=search.graph_context,
        metrics_by_op_id=search.metrics, objective_name=view.objective, start_dt=search.start_dt,
        seed=1, deadline=deadline, clock=clock, t_begin=now - 8.0, attempts=[], improvement_trace=[],
        report_state=view.report, decode_session=decoder,
    )
    trial_run.search, trial_run.report, trial_run.started_at = trial_search, trial_report, now
    trial_run.iteration = IGIteration(trial_search)
    trial_ig_stage = IteratedGreedyStage(trial_run, startup_ready=lambda: True)
    view.stages = [local_stage, grasp_stage, profile_stage, repair_stage, trial_ig_stage]
    for stage in list(view.stages):
        assert _next_stage(view) is stage
        stage.run_task()
        assert not stage.available()
        assert stage.unavailable_reason() == "estimated_decode_cost"
    assert _next_stage(view) is None
    assert budget.select_goal(()) is None
    assert budget.should_stop() == "search_exhausted"


def test_piece_graph_repeats_sequences_per_piece_without_duplicate_seq_warnings():
    """回归：两个分件各自使用 seq=20/30，分件图分析不能把它们当成同批重复顺序号。"""
    prepared, _seed = _piece_fixture(_config(mode="greedy", graph="off"))
    preparation = piece_graph_preparer(prepared)(prepared)
    public, diagnostics = preparation.graph_analysis_public, preparation.graph_analysis_diagnostics
    assert public is not None and diagnostics is not None
    assert public["warning_count"] == 0
    assert diagnostics["warnings_sample"] == []


def test_real_shared_optimizer_preserves_start_archive_resource_bridge_and_piece_dag(monkeypatch, record_property):
    from dataclasses import fields

    from core.services.scheduler.run.optimizer.graph import candidates as graph_candidates
    from core.services.scheduler.run.schedule_optimizer_steps import run_ortools_warmstart

    default = _default_runtime()
    assert tuple(field.name for field in fields(default)) == (
        "scheduler_factory", "clock", "rng_factory", "run_ortools_warmstart")
    assert default.clock is monotonic and default.rng_factory is Random
    assert default.run_ortools_warmstart is run_ortools_warmstart
    assert isinstance(default.scheduler_factory(calendar_service=ContinuousCalendar(), config_service=_config()), GreedyScheduler)

    def budget_clock():
        return 100.0

    runtime_budget = SearchBudget(clock=budget_clock, started_at=100.0, deadline=101.0, assigned_seconds=1.0)
    resolved = resolve_runtime(default, runtime_budget)
    assert resolved is not default and resolved.clock is budget_clock and default.clock is monotonic
    assert all(getattr(resolved, field) is getattr(default, field) for field in (
        "scheduler_factory", "rng_factory", "run_ortools_warmstart"))
    assert resolve_runtime(None, runtime_budget).clock is budget_clock

    prepared_scopes = []
    original_scope_payload = shared_process.score_scope_payload

    def prepare_scope(scope):
        prepared_scopes.append(scope)
        return original_scope_payload(scope)

    monkeypatch.setattr(shared_process, "score_scope_payload", prepare_scope)
    _assert_controlled_worse_reference_keeps_source()
    operations, batches, context, pool, downtime, seed = _linear_fixture()
    original = deepcopy((operations, batches, context, pool, downtime, seed))
    cfg, created, prepared_contexts = _config(), [], []

    def prepare_graph():
        prepared_contexts.append(context)
        return ScheduleGraphDispatchPreparation(None, None, context)

    with patch.object(graph_candidates, "_validate_decision_features",
                      wraps=graph_candidates._validate_decision_features) as feature_admissions:
        shared = optimize_shared_schedule(
            calendar_service=ContinuousCalendar(), cfg=cfg, algo_ops_to_schedule=operations,
            batches=batches, start_dt=START_DT, end_date=None, downtime_map=downtime,
            seed_results=[asdict(seed)], resource_pool=pool, version=0, readiness_gate_enabled=False,
            graph_prepare=prepare_graph, search_budget=_run_budget(cfg), _runtime=_runtime(created),
        )
    admitted = set()
    for call in feature_admissions.call_args_list:
        profile = call.kwargs["profile"]
        identity = (id(call.args[0]), profile.formula_version, profile.formula_slug, profile.feature_basis,
                    tuple(sorted(profile.effective_weights.items())), profile.jitter_seed)
        assert identity not in admitted
        admitted.add(identity)
    assert admitted
    assert len(created) == len(prepared_contexts) == 1
    scheduler = created[0]
    assert scheduler.calls[0]["dispatch_mode"] == "batch_order"
    assert scheduler.calls[0]["graph_ready_context"] is None
    assert not scheduler.calls[0]["decode_checkpoints"]
    assert (operations, batches, context, pool, downtime, seed) == original
    assert shared.target_objectives == target_objectives_for("min_overdue")
    primary_materialized = shared.archive.materialize(shared.archive.best_by_objective[shared.target_objectives[0]])
    assert primary_materialized["summary"].success and primary_materialized["summary"].failed_ops == 0
    _assert_arrangement(primary_materialized["results"], operations=operations, seed=seed, context=context,
                        pool=pool, downtime=downtime)
    facts = shared.process_facts
    assert facts["initial_construction_count"] == 1
    assert facts["graph_preparation_calls"] == facts["feature_preparation_calls"] == 1
    assert facts["first_complete_elapsed_ms"] is not None and facts["first_complete_elapsed_ms"] >= 0
    assert facts["actions"][0]["phase"] == "multi_start"
    assert facts["actions"][0]["initial_construction"] is True
    assert sum(action.get("initial_construction", False) for action in facts["actions"]) == 1
    assert tuple(action["search_objective"] for action in facts["actions"][1:4]) == shared.target_objectives
    initial_id = facts["initial_entry_id"]
    assert initial_id in shared.archive
    assert shared.archive.entry(initial_id).content_key == schedule_content_key(scheduler.calls[0]["results"])
    assert shared.archive.entry(initial_id).first_found_elapsed_ms <= facts["first_complete_elapsed_ms"]
    _assert_target_evaluations(shared.archive, initial_id, operations=operations, batches=batches, seed=seed)
    assert facts["events"]
    assert [event["event_id"] for event in facts["events"]] == list(range(1, len(facts["events"]) + 1))
    verified_events = [event for event in facts["events"] if event["event_type"] == "archive_observation"
                       and event["verified"] and event["entry_id"] is not None]
    assert verified_events and verified_events[0]["entry_id"] == initial_id
    # A first decode carries its own integer runtime_ms, which binds as the request's source runtime.
    first_decode_runtimes = [(event["phase"], event["decode_receipt"]["source_runtime_ms"]) for event in verified_events
                             if event["decode_receipt"]["execution_kind"] == "new_decision"]
    assert "multi_start" in {phase for phase, runtime in first_decode_runtimes if runtime is not None}
    assert all(type(runtime) is int for _phase, runtime in first_decode_runtimes if runtime is not None)
    for event in verified_events:
        assert set(event["evaluations"]) == set(shared.target_objectives)
        assert event["phase"] and event["origin"]
        for objective, evaluation in event["evaluations"].items():
            assert tuple(evaluation["field_order"]) == ("failed_ops",) + objective_metric_keys(objective)
            if event["entry_id"] in shared.archive:
                assert tuple(evaluation["score"]) == shared.archive.entry(event["entry_id"]).evaluations[objective].score
    retained_ids = {event["entry_id"] for event in verified_events if event["entry_id"] in shared.archive}
    for entry_id in retained_ids:
        _assert_target_evaluations(shared.archive, entry_id, operations=operations, batches=batches, seed=seed)
        _assert_arrangement(shared.archive.materialize(entry_id)["results"], operations=operations, seed=seed,
                            context=context, pool=pool, downtime=downtime)
    assert len({shared.archive.entry(entry_id).content_key for entry_id in retained_ids}) > 1
    assert all(call["seed_results"] == [seed] for call in scheduler.calls)
    process = facts["unified_process"]
    assert process["version"] == "unified-optimization-process-v1"
    assert process["elapsed_ms"] == facts["runtime_ms"]
    assert abs(process["elapsed_ms"] - int(process["budget"]["elapsed_seconds"] * 1000)) <= 1
    assert [event["event_id"] for event in process["events"]] == list(range(1, len(process["events"]) + 1))
    assert [event["elapsed_ms"] for event in process["events"]] == sorted(
        event["elapsed_ms"] for event in process["events"])
    assert process["counts"]["actual_decoder_calls"] == process["budget"]["actual_decoder_count"] == len(scheduler.calls)
    assert sum(event.get("actual_decoder_calls", 0) for event in facts["events"]) == len(scheduler.calls)
    for objective, target in process["targets"].items():
        points = target["points"]
        assert 1 <= len(points) <= 200
        assert {flag for point in points for flag in point["flags"]} >= {
            "first_valid", "first_expected_complete", "final"}
        assert all(point["field_order"] == ["failed_ops"] + list(objective_metric_keys(objective))
                   and process["scopes"][point["scope_ref"]] for point in points)
        final = [point for point in points if "final" in point["flags"]]
        assert len(final) == 1
        final = final[0]
        entry_id = shared.archive.best_by_objective[objective]
        assert final["entry_id"] == target["best_entry_id"] == entry_id
        assert tuple(final["score"]) == shared.archive.entry(entry_id).evaluations[objective].score
    for objective, opportunity in process["budget"]["objectives"].items():
        actions = [action for action in facts["actions"] if action["search_objective"] == objective]
        assert opportunity["new_decisions"] == sum(action["new_decisions"] for action in actions)
        assert opportunity["minimum_opportunity"] is any(
            action["new_decisions"] > 0 and not action["initial_construction"] for action in actions)
        assert opportunity["minimum_opportunity"] or opportunity["unavailable_reason"] or opportunity["budget_reason"]
    assert len(prepared_scopes) == len(process["scopes"])
    assert list(process["scopes"]) == [str(index + 1) for index in range(len(process["scopes"]))]
    scoped_rows = [event for event in process["events"] if "scope_ref" in event]
    scoped_rows += [point for target in process["targets"].values() for point in target["points"]]
    assert len(scoped_rows) > len(process["scopes"])
    assert all("score_scope" not in row and row["scope_ref"] in process["scopes"] for row in scoped_rows)
    for scope_ref, scope in zip(process["scopes"], prepared_scopes):
        assert process["scopes"][scope_ref] == original_scope_payload(scope)
    record_property("unified_process_scope_payloads", len(prepared_scopes))
    record_property("unified_process_scope_references", len(scoped_rows))

    assert facts["bridges"]
    for bridge in facts["bridges"]:
        assert bridge["decoder_executed"] is True and bridge["elapsed_ms"] >= 0
        before_id, after_id = bridge["before_entry_id"], bridge["after_entry_id"]
        assert before_id is not None and after_id is not None
        assert bridge["same_arrangement"] is (before_id == after_id)
    first_bridge = facts["bridges"][0]
    before = shared.archive.materialize(first_bridge["before_entry_id"])
    after_id = first_bridge["after_entry_id"]
    capture_key = shared.archive.entry(after_id).content_key
    captures = [call for call in scheduler.calls if call["decode_checkpoints"] and not call["decode_resume"]
                and schedule_content_key(call["results"]) == capture_key]
    assert captures
    actual_resources = {row.op_id: (row.machine_id, row.operator_id) for row in before["results"] if row.op_id in {3, 4}}
    for op in captures[0]["operations"]:
        if op.id in actual_resources:
            assert (op.machine_id, op.operator_id) == actual_resources[op.id]
    primary = shared.target_objectives[0]
    final_best = shared.archive.entry(shared.archive.best_by_objective[primary]).evaluations[primary].score
    assert final_best <= shared.archive.entry(first_bridge["before_entry_id"]).evaluations[primary].score
    assert final_best <= shared.archive.entry(after_id).evaluations[primary].score

    # A no-op local round still consumes just its own startup opportunity before the auxiliaries run.
    ordinary_cfg, ordinary_created = _config(graph="off"), []
    ordinary = optimize_shared_schedule(
        calendar_service=ContinuousCalendar(), cfg=ordinary_cfg,
        algo_ops_to_schedule=operations, batches=batches, start_dt=START_DT, end_date=None,
        downtime_map=downtime, seed_results=[asdict(seed)], resource_pool=pool, version=0,
        readiness_gate_enabled=False, search_budget=_run_budget(ordinary_cfg),
        _runtime=_runtime(ordinary_created),
    )
    ordinary_facts = ordinary.process_facts
    assert len(ordinary_created) == ordinary_facts["initial_construction_count"] == 1
    assert ordinary_facts["graph_preparation_calls"] == ordinary_facts["feature_preparation_calls"] == 0
    assert ordinary_created[0].calls[0]["dispatch_mode"] == "batch_order"
    assert all(call["graph_ready_context"] is None for call in ordinary_created[0].calls)
    assert ordinary_facts["actions"][0]["initial_construction"] is True
    startup = ordinary_facts["actions"][1:4]
    assert tuple(action["search_objective"] for action in startup) == ordinary.target_objectives
    assert startup[0]["evaluation_count"] == 0
    assert all(action["phase"] == "local_search" and not action["initial_construction"] for action in startup)
    assert ordinary_facts["bridges"] == []
    ordinary_process = ordinary_facts["unified_process"]
    assert ordinary_process["counts"]["actual_decoder_calls"] == len(ordinary_created[0].calls)
    for objective, opportunity in ordinary_process["budget"]["objectives"].items():
        assert opportunity["minimum_opportunity"] is any(
            action["search_objective"] == objective and action["new_decisions"] > 0
            and not action["initial_construction"] for action in ordinary_facts["actions"])
    ordinary_primary = ordinary.archive.materialize(ordinary.archive.best_by_objective[ordinary.target_objectives[0]])
    _assert_arrangement(ordinary_primary["results"], operations=operations, seed=seed,
                        context=context, pool=pool, downtime=downtime)

    # Graph-off piece work still carries its real fanout/join DAG into the unique ordinary SGS start.
    piece_cfg, piece_created, piece_contexts = _config(mode="greedy", graph="off"), [], []
    prepared, piece_seed = _piece_fixture(piece_cfg)
    prepare_piece = piece_graph_preparer(prepared)

    def prepare_piece_once():
        preparation = prepare_piece(prepared)
        piece_contexts.append(preparation.graph_ready_context)
        return preparation

    piece = optimize_shared_schedule(
        calendar_service=ContinuousCalendar(), cfg=piece_cfg,
        algo_ops_to_schedule=prepared.algo_ops_to_schedule, batches=prepared.batches,
        start_dt=START_DT, end_date=None, downtime_map={}, seed_results=prepared.seed_results,
        resource_pool=None, version=0, readiness_gate_enabled=False,
        graph_prepare=prepare_piece_once, search_budget=_run_budget(piece_cfg), _runtime=_runtime(piece_created),
    )
    assert len(piece_created) == len(piece_contexts) == 1
    assert len(piece_created[0].calls) == 1
    piece_call = piece_created[0].calls[0]
    assert piece_call["dispatch_mode"] == "sgs"
    assert piece_call["graph_ready_context"]["piece_scope"] is True
    assert piece_call["graph_ready_context"]["score_enabled"] is False
    assert piece_call["graph_ready_context"]["fixed_op_ids"] == {99}
    assert set(piece_call["graph_ready_context"]["predecessor_op_ids_by_op_id"][100]) == {3, 4}
    assert not piece_call["decode_checkpoints"] and not piece_call["decode_resume"]
    piece_primary = piece.archive.materialize(piece.archive.best_by_objective[piece.target_objectives[0]])
    assert piece_primary["summary"].success and piece_primary["summary"].failed_ops == 0
    _assert_arrangement(piece_primary["results"], operations=prepared.algo_ops_to_schedule,
                        seed=piece_seed, context=piece_call["graph_ready_context"], pool=None, downtime={})
    assert piece.process_facts["initial_construction_count"] == 1
    assert piece.process_facts["graph_preparation_calls"] == 1
    assert piece.process_facts["feature_preparation_calls"] == 0
    assert len(piece.process_facts["actions"]) == 1 and piece.process_facts["bridges"] == []
    assert piece.process_facts["unified_process"]["counts"]["actual_decoder_calls"] == 1
    _assert_target_evaluations(piece.archive, piece.process_facts["initial_entry_id"],
                               operations=prepared.algo_ops_to_schedule, batches=prepared.batches, seed=piece_seed)

    # The public adapter consumes those same native archives, with no decoder replay or target-wise solve.
    for actual, actual_cfg, actual_ops, actual_batches, actual_seeds, actual_pool, actual_downtime, actual_created in (
        (shared, cfg, operations, batches, [asdict(seed)], pool, downtime, created),
        (ordinary, ordinary_cfg, operations, batches, [asdict(seed)], pool, downtime, ordinary_created),
        (piece, piece_cfg, prepared.algo_ops_to_schedule, prepared.batches, prepared.seed_results, None, {}, piece_created),
    ):
        env = _comparison_input(cfg=actual_cfg, calendar=actual_created[0].calendar,
            operations=actual_ops, batches=actual_batches, seeds=actual_seeds,
            pool=actual_pool, downtime=actual_downtime)
        decoder_count = len(actual_created[0].calls)
        with patch("core.services.scheduler.run.schedule_candidate_runner.optimize_shared_schedule", return_value=actual) as solve:
            public = run_candidate_comparison(schedule_input=env)
        assert solve.call_count == 1 and len(actual_created[0].calls) == decoder_count
        assert solve.call_args.kwargs["algo_ops_to_schedule"] is actual_ops
        assert solve.call_args.kwargs["seed_results"] is actual_seeds
        assert public.generation_policy_version == "unified_search_v1"
        assert public.primary_objective == actual.archive.primary_objective
        assert public.target_objectives == list(actual.target_objectives)
        assert public.unified_process is actual.process_facts["unified_process"]
        selected_ids = actual.process_facts["selected_entries_by_objective"]
        entry_ids = list(dict.fromkeys(selected_ids[target] for target in actual.target_objectives))
        assert 1 <= len(public.candidates) == len(entry_ids) <= 3
        assert [plan.candidate_key for plan in public.candidates] == ["business_" + str(index + 1) for index in range(len(entry_ids))]
        for plan, entry_id in zip(public.candidates, entry_ids):
            entry = actual.archive.entry(entry_id)
            assert public.primary_objective is not None
            assert plan.search_evidence_ref is not None and plan.origin is not None
            assert plan.kind == "business_objective" and plan.status == "completed" and plan.health is None
            assert schedule_content_key(plan.results) == entry.content_key
            assert plan.score == entry.evaluations[public.primary_objective].score
            assert plan.representative_objectives == [target for target in actual.target_objectives if selected_ids[target] == entry_id]
            assert plan.first_found_elapsed_ms == entry.first_found_elapsed_ms
            assert plan.search_evidence_ref["source_event_id"] == actual.process_facts["evidence_event_ids_by_entry"][entry_id]
            assert plan.origin["origin"] == entry.evidence_origin["origin"]
            assert plan.dispatch_mode == plan.used_params["dispatch_mode"]
            assert plan.dispatch_rule == plan.adopted_dispatch_rule == plan.used_params["dispatch_rule"]
            assert plan.attempts == [] and plan.search_report == {}
        selection = public.selection.to_dict()
        assert set(selection) == {"generation_policy_version", "selection_policy_version", "primary_objective", "target_objectives",
            "selected_candidate_key", "objective_winners", "objective_winner_reasons", "objective_field_order", "selected_score",
            "reason_code", "scoring_scope", "evidence_state"}
        assert selection["reason_code"] == "primary_objective_best_found"
        assert all(value is None for value in selection["objective_winner_reasons"].values())
        assert public.selection.selected_plan is public.candidates[0]
        for target, winner in selection["objective_winners"].items():
            plan = next(plan for plan in public.candidates if plan.candidate_key == winner)
            assert target in plan.representative_objectives
    assert piece.process_facts["initial_entry_id"] in piece.archive and len(public.candidates) == 1
    assert public.candidates[0].representative_objectives == list(piece.target_objectives)


def test_shared_decode_ledger_reuses_effective_requests_and_restores_only_explicit_parents():
    operations, batches, context, pool, downtime, seed = _linear_fixture()
    scheduler = RecordingScheduler(calendar_service=ContinuousCalendar(), config_service=_config())
    seed_results, order = [seed], list(batches)
    profile = next(p for p in resolve_v2_profiles(seed=0, objective_name="min_overdue") if p.slug == "graph_neutral")
    metrics_by_op_id = enrich_graph_ready_v2_metrics(context["node_metrics_by_op_id"], operations=operations,
                                                     batches=batches, start_dt=START_DT, graph_ready_context=context,
                                                     calendar_service=scheduler.calendar, downtime_map={},
                                                     seed_results=[])
    decision_features = PreparedDecisionFeatures(metrics_by_op_id, build_v2_common_rank_cache(metrics_by_op_id))
    context = dict(context, score_enabled=True,
                   graph_priority_key_by_op_id=decision_features.priority_keys_for_profile(profile))
    targets = target_objectives_for("min_overdue")
    started_at = monotonic()

    def make_session(retention_limit=64):
        archive = SharedScheduleArchive("min_overdue", targets, {99} | {op.id for op in operations}, set(batches),
                                        retention_limit=retention_limit)
        budget = SharedSearchBudget(clock=monotonic, started_at=started_at, deadline=started_at + 10,
                                    target_objectives=targets, configured_seconds=10)
        shared = schedule_shared_search.SharedSearch(archive=archive, clock=monotonic, started_at=started_at,
                                                     budget=budget)
        decoder = SharedDecodeSession(
            archive=archive, budget=budget, scheduler=scheduler, operations=operations, batches=batches,
            seed_results=seed_results, downtime_map=downtime, resource_pool=pool, graph_ready_context=context,
            clock=monotonic, started_at=started_at, deadline=started_at + 10, event_sink=shared.record_event,
        )
        shared.decode_session = decoder
        return shared, archive, budget, decoder

    shared, archive, budget, decoder = make_session()

    def observe(candidate, objective="min_overdue", origin="ledger_native", verified=True):
        shared.search_objective = objective
        shared.observe(objective, candidate=candidate, origin=origin, verified=verified,
                       elapsed_ms=max(int((monotonic() - started_at) * 1000), 0))
        return candidate

    def decode_candidate(*, objective="min_overdue", verified=True, origin="ledger_native", start_dt: datetime = START_DT,
                         end_date=None, dispatch_rule="slack", graph_priority_key_by_op_id=context["graph_priority_key_by_op_id"],
                         operation_resources=None, resource_pair_rank=None, decode_resume=None,
                         decode_checkpoints=None, redecode_reason=None):
        decoded = decode_and_metrics(
            decode_session=decoder, objective_name=objective, strategy=SortStrategy.FIFO, strategy_params={},
            start_dt=start_dt, end_date=end_date, batch_order_override=order, dispatch_mode="sgs", dispatch_rule=dispatch_rule,
            readiness_gate_enabled=False, graph_enabled=True, graph_score_enabled=context["score_enabled"],
            graph_priority_key_by_op_id=graph_priority_key_by_op_id, operation_resources=operation_resources,
            resource_pair_rank=resource_pair_rank, decode_resume=decode_resume, decode_checkpoints=decode_checkpoints,
            redecode_reason=redecode_reason,
        )
        candidate = dict(results=decoded.results, summary=decoded.summary, metrics=decoded.metrics,
                         strategy=decoded.used_strategy, params=decoded.used_params, algo_stats=decoded.algo_stats,
                         dispatch_mode="sgs", dispatch_rule=dispatch_rule, order=order,
                         resource_pool=pool, decode_receipt=decoded.receipt,
                         runtime_ms=decoded.receipt["source_runtime_ms"] or decoded.receipt["original_decode_ms"],
                         score=(float(decoded.summary.failed_ops),) + objective_score(objective, decoded.metrics),
                         archive_ref=decoded.archive_ref())
        return observe(candidate, objective=objective, origin=origin, verified=verified)

    with patch("core.services.scheduler.run.optimizer.shared_decode.compute_metrics", wraps=compute_metrics) as metrics:
        shared.phase = "multi_start"
        source = _evaluate_multi_start_candidate(
            dispatch_mode="sgs", objective_name=targets[0], decode_session=decoder,
            strategy=SortStrategy.FIFO, params={}, start_dt=START_DT, end_date=None,
            order=order, dispatch_rule="slack", resource_pool=pool, optimizer_algo_stats=None,
            readiness_gate_enabled=False, graph_ready_context=context,
        )
        observe(source, origin="ordinary_multi_start")
        source_id = source["archive_ref"].entry_id
        source_entry = archive.entry(source_id)
        shared.phase = "graph_ready_candidate_search"
        # Two real caller families and two targets form exactly the same SGS request.
        reused = evaluate_graph_ready_candidate(
            profile=profile, prepared_decision_features=decision_features, objective_name=targets[1],
            version=7, clock=monotonic, decode_session=decoder,
            strategy=SortStrategy.DUE_DATE_FIRST, params={}, start_dt=START_DT,
            end_date=None, order=order, dispatch_rule="slack", resource_pool=pool, optimizer_algo_stats=None,
            readiness_gate_enabled=False,
        )
        observe(reused, objective=targets[1], origin=profile.candidate_origin)
        assert reused["decode_receipt"]["execution_kind"] == "decision_reused"
        assert reused["decode_receipt"]["request_id"] == source["decode_receipt"]["request_id"]
        assert reused["strategy"] is SortStrategy.DUE_DATE_FIRST
        assert reused["metrics"] is source["metrics"]
        assert reused["results"] is source["results"]
        assert reused["runtime_ms"] == source["decode_receipt"]["source_runtime_ms"]
        assert archive.entry(source_id).evidence_origin == source_entry.evidence_origin
        assert archive.entry(source_id).first_found_elapsed_ms == source_entry.first_found_elapsed_ms
        observed_sources = [event["origin"] for event in shared.events
                            if event["event_type"] == "archive_observation" and event["entry_id"] == source_id]
        assert observed_sources == ["ordinary_multi_start", profile.candidate_origin]
        assert archive.improvement_counts == dict.fromkeys(targets, 0)
        assert metrics.call_count == len(scheduler.calls) == 1

        equivalent = dict(context, graph_priority_key_by_op_id={op.id: (0.0 if op.id == 3 else 9.0,)
                                                               for op in operations})
        assert decode_candidate(objective=targets[2], graph_priority_key_by_op_id=equivalent["graph_priority_key_by_op_id"])["decode_receipt"][
            "execution_kind"] == "decision_reused"
        # Flattening both weak orders yields 3,1,2,4; their tie classes still differ.
        changed_tie = dict(equivalent, graph_priority_key_by_op_id={**equivalent["graph_priority_key_by_op_id"],
                                                                  4: (10.0,)})
        tied = decode_candidate(graph_priority_key_by_op_id=changed_tie["graph_priority_key_by_op_id"])
        atc_one = decode_candidate(dispatch_rule="atc:k=1")
        atc_four = decode_candidate(dispatch_rule="atc:k=4")
        pair_rank = {("OP-BENCH", "MC-BENCH"): 1, ("OP-ALT", "MC-ALT"): 2}
        ranked = decode_candidate(resource_pair_rank=pair_rank)
        pair_rank[("OP-ALT", "MC-ALT")] = 1
        changed_rank = decode_candidate(resource_pair_rank=pair_rank)
        decisions = (source, tied, atc_one, atc_four, ranked, changed_rank)
        assert len({candidate["decode_receipt"]["request_id"] for candidate in decisions}) == 6
        assert all(candidate["decode_receipt"]["actual_decoder_calls"] == 1 for candidate in decisions)
        assert metrics.call_count == len(scheduler.calls) == decoder.new_decisions == 6

        captured = []
        capture = decode_candidate(decode_checkpoints=DecodeCheckpointRequest([1], captured.append),
                                   redecode_reason="capture_checkpoints")
        assert capture["decode_receipt"]["execution_kind"] == "capture_checkpoints" and len(captured) == 1
        retained_before_trial = {candidate["archive_ref"].entry_id for candidate in (*decisions, capture)}
        assert all(entry_id in archive for entry_id in retained_before_trial)
        trial_context = dict(context, graph_priority_key_by_op_id={3: (0.0,), 1: (1.0,), 2: (2.0,), 4: (3.0,)})
        trial = decode_candidate(graph_priority_key_by_op_id=trial_context["graph_priority_key_by_op_id"],
                                 decode_resume=captured[0], verified=False)
        assert trial["decode_receipt"]["execution_kind"] == "trial_decode" and not trial["decode_receipt"]["verified"]
        assert "observation_bound" not in trial["decode_receipt"]
        # An unverified trial never adds a retained payload: it is either a known arrangement or a temporary number.
        assert trial["archive_ref"].entry_id in retained_before_trial or trial["archive_ref"].entry_id not in archive
        assert all(entry_id in archive for entry_id in retained_before_trial)
        assert decoder.actual_decoder_calls == metrics.call_count == len(scheduler.calls) == 8
        assert decoder.new_decisions == 6 and decoder.reused_decisions == 2
        assert budget.summary()["actual_decoder_count"] == 8

        # Evicted completed decisions remain seen. A real exploration-parent restore
        # keeps its original identity and first-found time without rewarding progress.
        shared, archive, budget, decoder = make_session(retention_limit=1)
        forced = deepcopy(operations)
        for op in forced[2:]:
            op.machine_id, op.operator_id = "MC-BENCH", "OP-BENCH"
        worse = decode_candidate(operation_resources={op.id: (op.machine_id, op.operator_id) for op in forced})
        old_id, old_entry = worse["archive_ref"].entry_id, archive.entry(worse["archive_ref"].entry_id)
        with archive.retention_scope():
            better = decode_candidate()
            better_id = better["archive_ref"].entry_id
            assert better["score"] < worse["score"]
            for objective in targets:
                archive.set_starting_entries(objective, ())
                archive.accept_exploration(objective, better_id)
        assert old_id not in archive and better_id in archive and archive.retention_limit == 1
        before_calls, before_metrics = len(scheduler.calls), metrics.call_count
        with pytest.raises(SharedSearchSkip) as seen:
            decode_candidate(operation_resources={op.id: (op.machine_id, op.operator_id) for op in forced})
        assert seen.value.reason == "seen_without_payload"
        assert seen.value.receipt is not None
        assert seen.value.receipt["actual_decoder_calls"] == 0
        assert len(scheduler.calls) == before_calls and metrics.call_count == before_metrics
        with archive.retention_scope():
            restored = decode_candidate(operation_resources={op.id: (op.machine_id, op.operator_id) for op in forced}, redecode_reason="restore_parent")
            assert restored["decode_receipt"]["execution_kind"] == "restore_parent"
            assert restored["archive_ref"].entry_id == old_id
            archive.accept_exploration(targets[0], old_id)
        assert archive.current_by_objective[targets[0]] == old_id
        assert archive.entry(old_id).first_found_elapsed_ms == old_entry.first_found_elapsed_ms
        assert archive.best_by_objective[targets[0]] == better_id
        assert shared.events[-1]["restored"] and shared.events[-1]["improved_objectives"] == []
        assert decoder.new_decisions == 2
        assert decoder.actual_decoder_calls == budget.summary()["actual_decoder_count"] == 3
        assert len(scheduler.calls) == before_calls + 1 and metrics.call_count == before_metrics + 1

    # Native calls share one static evaluation and downtime preparation. Changed
    # output still changes completion.
    scheduler = GreedyScheduler(calendar_service=ContinuousCalendar(), config_service=_config())
    native_decode = partial(decode_and_metrics, strategy=SortStrategy.FIFO, strategy_params={}, start_dt=START_DT, end_date=None,
                         batch_order_override=order, dispatch_mode="sgs", dispatch_rule="slack",
                         readiness_gate_enabled=False, graph_enabled=True,
                         graph_score_enabled=context["score_enabled"],
                         graph_priority_key_by_op_id=context["graph_priority_key_by_op_id"])
    with patch("core.services.scheduler.run.optimizer.shared_decode.prepare_evaluation_context",
               wraps=prepare_evaluation_context) as preparation, \
            patch.object(evaluation_inputs, "_prepare_expected_keys",
                         wraps=evaluation_inputs._prepare_expected_keys) as expected, \
            patch.object(evaluation_inputs, "normalize_priority", wraps=evaluation_inputs.normalize_priority) as priorities, \
            patch.object(evaluation_inputs, "_parse_due_date_state", wraps=evaluation_inputs._parse_due_date_state) as due, \
            patch.object(native_scheduler_module, "_normalize_machine_downtimes",
                         wraps=native_scheduler_module._normalize_machine_downtimes) as normalized, \
            patch("core.services.scheduler.run.optimizer.shared_decode.compute_metrics", wraps=compute_metrics) as metrics:
        shared, archive, budget, decoder = make_session()
        assert preparation.call_count == expected.call_count == normalized.call_count == 1
        assert priorities.call_count == due.call_count == len(batches)
        assert decoder.native_preparation.normalized_machine_downtimes == downtime
        complete = decode_candidate()
        partial_candidate = decode_candidate(end_date=START_DT.date())
        assert complete["results"] == source["results"]
        assert complete["metrics"].completion.objective_defined
        assert partial_candidate["metrics"].completion.missing_operation_count > 0
        assert not partial_candidate["metrics"].completion.objective_defined
        assert partial_candidate["metrics"].completion.expected_operation_count == complete["metrics"].completion.expected_operation_count
        assert decoder.actual_decoder_calls == metrics.call_count == scheduler._decode_invocations == 2
        assert normalized.call_count == 1
        assert decode_candidate(end_date=START_DT.date())["decode_receipt"]["execution_kind"] == "decision_reused"
        assert metrics.call_count == 2

        # A partial-only publication archive consumes the same validated native output.
        partial_entry = archive.entry(partial_candidate["archive_ref"].entry_id)
        assert partial_entry.score_scope.components_known and not partial_entry.score_scope.is_complete
        publication_archive = SharedScheduleArchive(targets[0], targets, archive.expected_operation_ids, archive.batch_ids)
        published = publication_archive.register_decode(partial_candidate, verified=True,
            elapsed_ms=partial_entry.first_found_elapsed_ms)
        publication_archive.finish_observation(published, partial_candidate, origin=partial_entry.evidence_origin)
        assert published.entry_id is not None
        publication_entry = publication_archive.entry(published.entry_id)
        publication_search = schedule_shared_search.SharedSearch(
            archive=publication_archive, clock=monotonic, started_at=started_at,
            budget=_shared_budget(publication_archive, started_at))
        partial_public = _business_representative(
            SimpleNamespace(archive=publication_archive, process_facts={
                "selected_entries_by_objective": {target: publication_search.selected_entry(target) for target in targets},
                "evidence_event_ids_by_entry": {published.entry_id: shared.evidence_event_ids[partial_entry.entry_id]}}),
            publication_entry, sequence=0, primary=targets[0], targets=targets, cfg=scheduler.config,
            preparation=None, total_budget=1.0)
        assert partial_public.status == "completed" and partial_public.representative_objectives == list(targets)
        assert partial_public.results == partial_candidate["results"] and partial_public.summary == partial_candidate["summary"]
        assert partial_public.score == partial_entry.evaluations[targets[0]].score
        for target, evaluation in partial_public.evaluations.items():
            assert evaluation["field_order"] == ["failed_ops"] + list(objective_metric_keys(target))
            assert evaluation["score"] == list(partial_entry.evaluations[target].score)
            assert evaluation["scoring_scope"]["components_known"] and not evaluation["scoring_scope"]["is_complete"]
            assert set(evaluation["scoring_scope"]["scheduled_operation_ids"]) == {row.op_id for row in partial_candidate["results"]}
        assert metrics.call_count == 2 and scheduler._decode_invocations == 2

        assert all(call.kwargs["prepared"] is decoder.evaluation_context for call in metrics.call_args_list)

    # Preparation after initial admission can consume the deadline. The shared
    # rejection records this known request once, without invoking the decoder.
    timer, rejected_events = SimpleNamespace(value=0.0), []
    controlled_clock = lambda: timer.value
    rejected_archive = SharedScheduleArchive("min_overdue", targets, {99} | {op.id for op in operations}, set(batches))
    rejected_budget = SharedSearchBudget(clock=controlled_clock, started_at=0.0, deadline=1.0,
                                         target_objectives=targets, configured_seconds=1.0)
    rejected_session = SharedDecodeSession(
        archive=rejected_archive, budget=rejected_budget, scheduler=scheduler, operations=operations, batches=batches,
        seed_results=seed_results, downtime_map=downtime, resource_pool=pool, graph_ready_context=context,
        clock=controlled_clock, started_at=0.0, deadline=1.0,
        event_sink=lambda event: rejected_events.append(event) or len(rejected_events),
    )
    before_calls = scheduler._decode_invocations
    with patch.object(rejected_budget, "require_decode", wraps=rejected_budget.require_decode) as admission, \
            patch.object(rejected_budget, "reject", wraps=rejected_budget.reject) as rejection, \
            pytest.raises(SharedSearchSkip) as late:
        native_decode(
            decode_session=rejected_session, objective_name=targets[0],
            before_decode=lambda: setattr(timer, "value", 2.0),
        )
    assert late.value.reason == "time_budget" and late.value.request_id == 1
    assert admission.call_count == rejection.call_count == 1
    assert rejection.call_args.args == ("time_budget",)
    assert late.value.receipt is not None
    assert late.value.receipt["actual_decoder_calls"] == 0 and not late.value.receipt["verified"]
    assert late.value.receipt["execution_kind"] == "decode_skipped" and late.value.receipt["reason"] == "time_budget"
    assert rejected_budget.summary()["admission_skips"] == {"time_budget": 1}
    assert rejected_budget.summary()["actual_decoder_count"] == rejected_session.actual_decoder_calls == 0
    assert rejected_session.skipped_requests == 1 and scheduler._decode_invocations == before_calls
    assert len(rejected_events) == 1 and rejected_events[0]["event_type"] == "decode_skipped"
    assert rejected_events[0]["request_id"] == late.value.request_id
    print("U3.8 late admission counts:", {"require_decode_calls": admission.call_count,
          "reject_calls": rejection.call_count, "budget_skips": rejected_budget.summary()["admission_skips"],
          "session_skips": rejected_session.skipped_requests, "request_id": late.value.request_id,
          "decoder_calls": rejected_session.actual_decoder_calls, "request_events": len(rejected_events)})


def test_shared_ig_sync_keeps_same_evidence_pointer_and_defers_new_parent():
    operations, batches, _context, pool, downtime, seed = _linear_fixture()
    cfg = _config()
    scheduler = GreedyScheduler(calendar_service=ContinuousCalendar(), config_service=cfg)

    def decoded(*, forced=False, overrides=None, batch_order=None, graph_context=None, checkpoints=None,
                objective="min_overdue", keep_receipt=False):
        actual_operations = deepcopy(operations)
        if forced:
            for op in actual_operations[2:]:
                op.machine_id, op.operator_id = "MC-BENCH", "OP-BENCH"
        for op in actual_operations:
            if overrides is not None and op.id in overrides:
                op.machine_id, op.operator_id = overrides[op.id]
        mode = "sgs" if graph_context is not None else "batch_order"
        result = production_decode(
            scheduler, operations=actual_operations, batches=batches, start_dt=START_DT, strategy=SortStrategy.FIFO,
            strategy_params={},
            dispatch_mode=mode, dispatch_rule="slack", machine_downtimes=downtime,
            seed_results=[seed], resource_pool=pool, batch_order_override=batch_order,
            graph_ready_context=graph_context, decode_checkpoints=checkpoints,
        )
        results, summary, strategy, params = result.results, result.summary, result.used_strategy, result.used_params
        metrics = compute_metrics(results, batches, expected_operations=operations, seed_results=[seed],
                                  failure_details=summary.failure_details)
        assert summary.success and summary.failed_ops == 0
        candidate = {"results": results, "summary": summary, "strategy": strategy, "params": params,
                     "metrics": metrics, "score": (0.0,) + objective_score(objective, metrics),
                     "dispatch_mode": mode, "dispatch_rule": "slack", "resource_pool": pool,
                     "order": list(batch_order or batches)}
        if keep_receipt:
            candidate["decode_receipt"] = result.receipt
        return candidate

    worse, better = decoded(forced=True), decoded()
    assert better["score"] < worse["score"]

    def target_view(candidate, *, parent_candidate, retention_limit=64, all_targets=False):
        started_at = monotonic()
        archive = SharedScheduleArchive("min_overdue", target_objectives_for("min_overdue"),
                                        {99} | {op.id for op in operations}, set(batches), retention_limit=retention_limit)
        session = schedule_shared_search.SharedSearch(archive=archive, clock=monotonic, started_at=started_at,
                                                      budget=_shared_budget(archive, started_at))
        report = OptimizationSearchReportState(objective_name="min_overdue", started_at=started_at)
        view = schedule_shared_search.GoalView("min_overdue", OptimizerSearchState(), report)
        session.views[view.objective] = view
        if all_targets:
            for objective in archive.target_objectives[1:]:
                target_report = OptimizationSearchReportState(objective_name=objective, started_at=started_at)
                session.views[objective] = schedule_shared_search.GoalView(objective, OptimizerSearchState(), target_report)
        _observe_decoded(session, view.objective, candidate=candidate, origin="native_initial", verified=True, elapsed_ms=1)
        session.sync(view)
        deadline = started_at + 1
        budget = SharedSearchBudget(clock=monotonic, started_at=started_at, deadline=deadline,
                                    target_objectives=archive.target_objectives, configured_seconds=1)
        decoder = SharedDecodeSession(
            archive=archive, budget=budget, scheduler=scheduler, operations=operations, batches=batches,
            seed_results=[seed], downtime_map=downtime, resource_pool=pool, graph_ready_context=_context,
            clock=monotonic, started_at=started_at, deadline=deadline, event_sink=session.record_event,
        )
        session.decode_session = decoder
        parent = _parent_from_candidate(parent_candidate, graph_context=_context,
                                        prepared=prepare_repair_parent(
                                            parent_candidate, operations, _context,
                                            resource_pairs_for=decoder.native_preparation.qualified_resource_pairs))
        assert parent is not None
        reference = PoolEntry(order=parent.order, score=tuple(candidate["score"]), candidate=candidate,
                              batch_order=parent.batch_order, resource_overrides=parent.inherited)
        metrics = _context["node_metrics_by_op_id"]
        profile = ig_decode_profile(next(p for p in resolve_v2_profiles(seed=0, objective_name="min_overdue") if p.slug == "balanced"))
        limits = IteratedGreedyLimits(due_date_seed=False)
        repair_pool = EliteRepairPool(
            limits=EliteRepairLimits(), objective_name=view.objective, operations=operations,
            metrics_by_op_id=metrics, start_dt=START_DT, seed=0, best=candidate, report_state=report,
            graph_context=_context, decode_session=decoder,
        )
        decision_metrics = enrich_graph_ready_v2_metrics(metrics, operations=operations, batches=batches,
                                                         start_dt=START_DT, graph_ready_context=_context,
                                                         calendar_service=scheduler.calendar, downtime_map={},
                                                         seed_results=[])
        evaluate = partial(
            evaluate_graph_ready_candidate,
            prepared_decision_features=PreparedDecisionFeatures(decision_metrics,
                                                                build_v2_common_rank_cache(decision_metrics)),
            strategy=SortStrategy.FIFO, params={}, start_dt=START_DT, end_date=None,
            dispatch_rule="slack", resource_pool=pool, objective_name=view.objective, optimizer_algo_stats=None,
            readiness_gate_enabled=False, version=0, clock=monotonic, decode_session=decoder,
        )
        graph_state = GraphSearchState(view.candidate)
        run = IteratedGreedyRun(
            limits=limits, state=graph_state, parent_profile=lambda candidate: profile,
            pool=repair_pool, evaluate=evaluate, operations=operations, graph_context=_context,
            metrics_by_op_id=metrics, objective_name=view.objective, start_dt=START_DT, seed=0,
            deadline=deadline, clock=monotonic, t_begin=started_at, attempts=[], improvement_trace=[],
            report_state=report, decode_session=decoder,
        )
        search = _IteratedGreedySearch(
            limits=limits, parent=parent, profile=profile, pool=repair_pool, evaluate=evaluate,
            metrics_by_op_id=metrics, start_dt=START_DT, seed=0, deadline=deadline, clock=monotonic,
            t_begin=started_at, attempts=[], improvement_trace=[], report_state=report,
            report=run.report, operations=operations, graph_context=_context, decode_session=decoder,
        )
        search.best, search.reference = candidate, reference
        run.search, run.iteration = search, PausedIteration(search)
        stage = IteratedGreedyStage(run, startup_ready=lambda: True)
        view.graph_bundle = GraphStageBundle(graph_state, [stage])
        return session, view, run, parent, reference

    session, view, run, parent, reference = target_view(worse, parent_candidate=worse)
    assert run.search is not None and view.graph_bundle is not None
    owned = view.candidate
    assert run.search.best is not owned
    session.sync(view)
    assert view.candidate is run.search.best is view.graph_bundle.state.best is owned
    session.sync(view)
    assert view.candidate is run.search.best is owned
    IteratedGreedyRun._advance(run)
    assert run.search.parent is parent and run.search.reference is reference and run.pending_adoption is None

    _observe_decoded(session, view.objective, candidate=better, origin="native_other_target", verified=True, elapsed_ms=2)
    new_entry = better["archive_ref"].entry_id
    assert new_entry != worse["archive_ref"].entry_id
    session.sync(view)
    assert view.entry_id == new_entry and view.candidate is not owned
    assert run.search.best is owned and view.graph_bundle.state.best is view.candidate
    assert run.search.parent is parent and run.search.reference is reference and run.pending_adoption is None
    IteratedGreedyRun._advance(run)
    assert run.pending_adoption is view.candidate and run.search.best is view.candidate
    assert run.search.parent is parent and run.search.reference is reference
    session.sync(view)
    assert run.search.best is view.candidate

    tied = decoded(batch_order=["B_LONG", "B_SHORT_B", "B_SHORT_A"])
    assert tied["score"] == better["score"]
    assert schedule_content_key(tied["results"]) != schedule_content_key(better["results"])
    _observe_decoded(session, view.objective, candidate=tied, origin="grasp_ig", verified=True, elapsed_ms=3)
    assert tied["archive_ref"].entry_id != new_entry and session.selected_entry(view.objective) == new_entry
    view.state.best = tied
    view.report.mark_candidate_accepted(
        tied, origin="grasp_ig", fingerprint=view.report.mark_candidate_evaluated(tied, origin="grasp_ig"))
    assert view.report._best_candidate is tied and view.report.best_origin == "grasp_ig"
    session.sync(view)
    assert view.candidate is not None
    assert view.state.best is view.candidate and view.report._best_candidate is view.candidate
    assert view.report.best_origin == "native_other_target"
    restored_identity = view.report.fingerprint_identity(view.candidate)
    assert restored_identity is not None and view.report.best_fingerprint == restored_identity.output_key

    # An upgraded evidence revision of the same arrangement follows the same pending-adoption boundary.
    not_yet_complete = deepcopy(better)
    not_yet_complete["summary"].success = False
    upgrade_session, upgrade_view, upgrade_run, upgrade_parent, upgrade_reference = target_view(not_yet_complete, parent_candidate=better)
    assert upgrade_run.search is not None
    upgrade_session.sync(upgrade_view)
    old_evidence = upgrade_view.candidate
    same_entry = upgrade_view.entry_id
    assert same_entry is not None
    accepted_evidence = deepcopy(better)
    _observe_decoded(upgrade_session, upgrade_view.objective, candidate=accepted_evidence, origin="completed_evidence",
                            verified=True, elapsed_ms=3)
    assert accepted_evidence["archive_ref"].entry_id == same_entry
    assert accepted_evidence["archive_ref"].evidence_revision == 1
    upgrade_session.sync(upgrade_view)
    assert upgrade_view.entry_id == same_entry and upgrade_view.evidence_revision == 1
    assert upgrade_view.candidate is not None
    assert upgrade_view.candidate is not old_evidence and upgrade_run.search.best is old_evidence
    assert upgrade_view.candidate["summary"].success and upgrade_session.archive.entry(same_entry).score_scope.is_complete
    assert upgrade_run.search.parent is upgrade_parent and upgrade_run.search.reference is upgrade_reference
    assert upgrade_run.pending_adoption is None
    IteratedGreedyRun._advance(upgrade_run)
    assert upgrade_run.pending_adoption is upgrade_view.candidate and upgrade_run.search.best is upgrade_view.candidate
    assert upgrade_run.search.parent is upgrade_parent and upgrade_run.search.reference is upgrade_reference

    # Active generator references outlive the payload cap, including across another target's ordinary action.
    life, life_view, life_run, _life_parent, _life_reference = target_view(
        deepcopy(better), parent_candidate=better, retention_limit=1, all_targets=True,
    )
    assert life_run.search is not None
    for target in life.views.values():
        life.sync(target)
    best_id = life_view.entry_id
    ordinary_view = life.views["min_tardiness"]
    life_run.search.reference = None
    life_run.search.solution_pool = SolutionPool(3)
    life_run.search.decoded_entries.clear()
    life_decoder = life_run.decode_session
    ordinary_candidate = ordinary_view.candidate
    assert ordinary_candidate is not None
    ordinary_stage = LocalSearchStage(
        best=ordinary_candidate, version=0, deadline=life.started_at + 1,
        batches=batches, start_dt=START_DT, end_date=None, dispatch_mode_cfg="batch_order", dispatch_rule_cfg="slack",
        resource_pool=pool, objective_name=ordinary_view.objective, attempts=[], improvement_trace=[],
        optimizer_algo_stats=None, t_begin=life.started_at, readiness_gate_enabled=False,
        clock=monotonic, rng_factory=Random, search_report_state=ordinary_view.report, decode_session=life_decoder,
    )
    ordinary_view.local_stage = ordinary_stage
    ordinary_state = ordinary_stage.local_state
    assert ordinary_state is not None
    ordinary_noop = CallbackStage(lambda: 0)
    old_reference = deepcopy(worse)
    old_pool_candidate = decoded(overrides={3: ("MC-BENCH", "OP-BENCH")})
    old_decoded_candidate = decoded(overrides={4: ("MC-BENCH", "OP-BENCH")})
    captured = []
    capture_context = dict(_context, score_enabled=True,
                           graph_priority_key_by_op_id={op.id: (float(op.id),) for op in operations})
    checkpoint_source = decoded(forced=True, graph_context=capture_context,
                                checkpoints=DecodeCheckpointRequest([1, 2], captured.append), keep_receipt=True)
    assert len(captured) == 2 and schedule_content_key(checkpoint_source["results"]) == schedule_content_key(old_reference["results"])

    def pool_entry(candidate, *, checkpoints=()):
        parent = _parent_from_candidate(candidate, graph_context=_context,
                                        prepared=prepare_repair_parent(
                                            candidate, operations, _context,
                                            resource_pairs_for=partial(qualified_resource_pairs, resource_pool=pool)))
        assert parent is not None
        return PoolEntry(order=parent.order, score=tuple(candidate["score"]), candidate=candidate,
                         batch_order=parent.batch_order, resource_overrides=parent.inherited,
                         checkpoints=list(checkpoints), decoded_order=bool(checkpoints))

    with life.archive.retention_scope():
        for index, candidate in enumerate((old_reference, old_pool_candidate, old_decoded_candidate), 3):
            _observe_decoded(life, life_view.objective, candidate=candidate, origin="native_retained_parent", verified=True,
                         elapsed_ms=index)
        # The reference's arrangement and checkpoints come from checkpoint_source's real decode; every
        # production reference carries that decode's receipt, attached after the archive registration above.
        old_reference["decode_receipt"] = checkpoint_source["decode_receipt"]
        reference_entry = pool_entry(old_reference, checkpoints=captured)
        life_run.search.reference = reference_entry
        life_run.search.solution_pool.add(pool_entry(old_pool_candidate))
        cached_entry = pool_entry(old_decoded_candidate)
        life_run.search.decoded_entries[cached_entry.order] = cached_entry
        life.run_action(ordinary_view, ordinary_noop)
    held_ids = {candidate["archive_ref"].entry_id for candidate in (old_reference, old_pool_candidate, old_decoded_candidate)}
    assert len(held_ids) == 3 and best_id not in held_ids
    assert all(entry_id in life.archive for entry_id in {best_id} | held_ids)
    assert life.archive.current_by_objective[life_view.objective] == old_reference["archive_ref"].entry_id
    assert life.archive.starting_entries_by_objective[life_view.objective] == (old_pool_candidate["archive_ref"].entry_id,)
    for candidate in (old_reference, old_pool_candidate, old_decoded_candidate):
        assert life.archive.materialize(candidate["archive_ref"].entry_id)["results"] == candidate["results"]
    before_capture = scheduler._decode_invocations
    assert capture_reference(life_run.search, reference_entry) is reference_entry
    assert scheduler._decode_invocations == before_capture
    assert life_decoder.actual_decoder_calls == 0

    newly_current = decoded(batch_order=["B_LONG", "B_SHORT_B", "B_SHORT_A"], objective=ordinary_view.objective)
    # Local candidates always carry the pair ranks they were decoded with (evaluate_local_search_candidate).
    newly_current["resource_pair_rank"] = {}

    def observe_then_accept():
        _observe_decoded(life, ordinary_view.objective, candidate=newly_current, origin="local_search", verified=True, elapsed_ms=7)
        assert newly_current["archive_ref"].entry_id in life.archive
        ordinary_state.accept_current(newly_current)
        return 0

    life.run_action(ordinary_view, CallbackStage(observe_then_accept))
    current_id = newly_current["archive_ref"].entry_id
    assert current_id not in {best_id} | held_ids
    assert all(entry_id in life.archive for entry_id in {best_id, current_id} | held_ids)
    assert life.archive.current_by_objective[ordinary_view.objective] == current_id
    assert life.archive.materialize(current_id)["results"] == newly_current["results"]
    assert capture_reference(life_run.search, reference_entry) is reference_entry
    assert scheduler._decode_invocations == before_capture + 1
    assert life_decoder.actual_decoder_calls == 0

    # A pending adoption alone keeps its old payload; releasing it and the other references restores eviction.
    life_run.search.decoded_entries.clear()
    life_run.pending_adoption = old_decoded_candidate
    life.run_action(ordinary_view, ordinary_noop)
    assert old_decoded_candidate["archive_ref"].entry_id in life.archive
    elite_candidate = life.archive.materialize(current_id, objective=life_view.objective)
    elite_candidate["archive_ref"] = CandidateArchiveRef(current_id, evidence_revision=life.revisions.get(current_id, 0))
    life_run.pool.elites.append({"candidate": elite_candidate})
    # Current moves back onto best's archived arrangement; like every local candidate it carries its pair ranks.
    ordinary_state.accept_current(dict(ordinary_state.best, resource_pair_rank={}))
    life.run_action(ordinary_view, ordinary_noop)
    assert life.archive.current_by_objective[ordinary_view.objective] == best_id
    assert current_id in life.archive
    assert life.archive.materialize(current_id)["results"] == newly_current["results"]
    life_run.search.reference = None
    life_run.search.solution_pool.entries.clear()
    life_run.pending_adoption = None
    life_run.pool.elites.clear()
    life.run_action(ordinary_view, ordinary_noop)
    assert best_id in life.archive and life.archive.retention_limit == 1
    assert not any(entry_id in life.archive for entry_id in held_ids | {current_id})
    assert life.archive.current_by_objective == {objective: best_id for objective in life.archive.target_objectives}
    assert all(entries == () for entries in life.archive.starting_entries_by_objective.values())
