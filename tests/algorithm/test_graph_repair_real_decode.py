"""Operation/resource decisions must be realized by formal SGS with fixed seeds."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta

from core.algorithms import ScheduleResult, SortStrategy
from core.services.scheduler.run.optimizer_candidate_fingerprint import build_candidate_fingerprint
from core.services.scheduler.run.optimizer_graph_ready_candidates import evaluate_graph_ready_candidate
from core.services.scheduler.run.optimizer_graph_ready_profiles import graph_ready_v2_profiles
from core.services.scheduler.run.optimizer_graph_ready_repair_decisions import RepairDecision
from core.services.scheduler.run.optimizer_graph_ready_v2_features import enrich_graph_ready_v2_metrics
from tests._support.optimizer_graph_ready_benchmark import (
    BASE_BATCH_ORDER,
    START_DT,
    _schedule_with_scheduler,
    _scheduler,
    graph_ready_benchmark_batches,
    graph_ready_benchmark_context,
    graph_ready_benchmark_operations,
)


def test_real_operation_and_qualified_resource_move_preserves_seed_dag_and_downtime():
    operations, batches = graph_ready_benchmark_operations(), graph_ready_benchmark_batches()
    operations[2].machine_id = operations[2].operator_id = ""
    context = graph_ready_benchmark_context()
    seed = ScheduleResult(op_id=99, op_code="FIXED", batch_id="B_LONG", seq=0,
                          machine_id="MC-BENCH", operator_id="OP-BENCH", op_type_name="BENCH",
                          start_time=START_DT, end_time=START_DT + timedelta(hours=1))
    context["fixed_op_ids"] = {99}
    context["fixed_op_sources_by_op_id"] = {99: "seed"}
    context["predecessor_op_ids_by_op_id"].update({99: set(), 1: {99}, 2: {1}})
    context["successor_op_ids_by_op_id"].update({99: {1}, 1: {2}})
    pool = {"machines_by_op_type": {"OT-BENCH": ["MC-BENCH", "MC-ALT"]},
            "operators_by_machine": {"MC-BENCH": ["OP-BENCH"], "MC-ALT": ["OP-ALT"]}}
    downtime = {"MC-ALT": [(START_DT, START_DT + timedelta(hours=4))]}
    original = deepcopy((operations, context, pool, seed))
    metrics = enrich_graph_ready_v2_metrics(context["node_metrics_by_op_id"], operations=operations, batches=batches,
                                            start_dt=START_DT, seed_results=[seed], resource_pool=pool, downtime_map=downtime)
    profile = graph_ready_v2_profiles(max_candidate_profiles=60)[0][1]
    profile = replace(profile, candidate_origin="graph_ready_v2_repaired", candidate_policy="elite_repair")

    def decode(machine, operator):
        decision = RepairDecision(tuple(BASE_BATCH_ORDER), (1, 3, 4, 2), ((3, machine, operator),))
        return evaluate_graph_ready_candidate(
            profile=profile, graph_ready_context=context, metrics_by_op_id=metrics, scheduler=_scheduler(), strict_mode=True,
            algo_ops_to_schedule=operations, batches=batches, strategy=SortStrategy.PRIORITY_FIRST, params={},
            start_dt=START_DT, end_date=None, downtime_map=downtime, order=list(BASE_BATCH_ORDER), seed_sr_list=[seed],
            dispatch_rule="slack", resource_pool=pool, objective_name="min_overdue", optimizer_algo_stats=None,
            schedule_fn=_schedule_with_scheduler, readiness_gate_enabled=False, version=0, clock=lambda: 0.0,
            repair_decision=decision,
        )

    same_resource = decode("MC-BENCH", "OP-BENCH")
    alternative = decode("MC-ALT", "OP-ALT")
    rows = {row.op_id: row for row in alternative["results"]}
    assert alternative["summary"].failed_ops == 0
    assert rows[99] == seed
    assert rows[1].start_time >= seed.end_time
    assert rows[2].start_time >= rows[1].end_time
    assert rows[3].machine_id == "MC-ALT" and rows[3].operator_id == "OP-ALT"
    assert rows[3].start_time >= downtime["MC-ALT"][0][1]
    assert rows[3].start_time < next(row.start_time for row in same_resource["results"] if row.op_id == 3)
    assert (operations, context, pool, seed) == original
    first = build_candidate_fingerprint(same_resource, objective_name="min_overdue", parent_fingerprint=None, seen_output_fingerprints=[])
    second = build_candidate_fingerprint(alternative, objective_name="min_overdue", parent_fingerprint=first.output_fingerprint,
                                         seen_output_fingerprints=[first.output_fingerprint])
    assert second.decision_fingerprint != first.decision_fingerprint
    assert second.fingerprint_changed and not second.same_as_seen
