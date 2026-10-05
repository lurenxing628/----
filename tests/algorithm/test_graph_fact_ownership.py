"""Shared scheduling facts retain scope checks and independent mutable outputs."""

from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest

from core.algorithms.greedy.algo_stats import capture_algo_stats, make_algo_stats
from core.algorithms.greedy.dispatch import sgs_graph
from core.algorithms.greedy.dispatch.sgs_checkpoint import DecodeCheckpointRequest
from core.algorithms.greedy.scheduler import GreedyScheduler
from core.errors import ValidationError
from core.models.batch_operation import BatchOperation
from core.services.scheduler.run.optimizer.graph import v2_features
from core.services.scheduler.run.optimizer.graph.repair_decisions import (
    RepairDecision,
    apply_repair_decision,
    native_readonly_inputs,
)
from core.services.scheduler.run.optimizer.graph_ready_feature_basis import BASELINE_ORDERING_FIELD
from core.services.scheduler.run.optimizer.graph_ready_profiles import graph_ready_v2_profiles
from core.services.scheduler.run.optimizer.signature_support import schedule_with_optional_strict_mode
from tests._support.optimizer_graph_ready_benchmark import (
    BASE_BATCH_ORDER,
    START_DT,
    _scheduler,
    graph_ready_benchmark_batches,
    graph_ready_benchmark_context,
    graph_ready_benchmark_operations,
)


def _context():
    return {"enabled": True, "schedulable_op_ids": {1, 2}, "fixed_op_ids": {99},
            "fixed_op_sources_by_op_id": {99: "seed"},
            "predecessor_op_ids_by_op_id": {1: {99}, 2: {1}, 99: set()},
            "successor_op_ids_by_op_id": {1: {2}, 2: set(), 99: {1}},
            "sort_key_by_op_id": {1: (0, 1, 1), 2: (0, 2, 2)},
            "score_enabled": True, "graph_priority_key_by_op_id": {1: (0.0,), 2: (1.0,)}}


def _ops():
    return [BatchOperation(id=op_id, op_code="OP" + str(op_id), batch_id="A", seq=op_id) for op_id in (1, 2)]


def test_shared_topology_prepares_once_and_progress_is_per_decode(monkeypatch):
    context, operations = _context(), _ops()
    calls = []
    detect = sgs_graph._detect_graph_ready_cycle
    monkeypatch.setattr(sgs_graph, "_detect_graph_ready_cycle", lambda **kwargs: (calls.append(1), detect(**kwargs))[-1])
    topology = sgs_graph.prepare_graph_ready_topology(context, operations)
    context["_prepared_graph_ready_topology"] = topology
    states = [sgs_graph._prepare_graph_ready_state(context, ops_by_batch={"A": operations}) for _ in range(3)]
    assert calls == [1]
    assert all(state["predecessor_op_ids_by_op_id"] is topology.predecessors for state in states)
    states[0]["completed_or_fixed_op_ids"].add(1)
    assert states[1]["completed_or_fixed_op_ids"] == {99}
    with pytest.raises(TypeError):
        topology.predecessors[2] = frozenset()


@pytest.mark.parametrize("change", ["cycle", "bool_id", "bool_link", "list_sort"])
def test_changed_raw_topology_cannot_reuse_a_previous_proof(change):
    context, operations = _context(), _ops()
    context["_prepared_graph_ready_topology"] = sgs_graph.prepare_graph_ready_topology(context, operations)
    if change == "cycle":
        context["predecessor_op_ids_by_op_id"][1].add(2)
        context["successor_op_ids_by_op_id"][2].add(1)
    elif change == "bool_id":
        context["schedulable_op_ids"] = {True, 2}
    elif change == "bool_link":
        context["predecessor_op_ids_by_op_id"][2] = {True}
    else:
        context["sort_key_by_op_id"][1] = [0, 1, 1]
    with pytest.raises(ValidationError):
        sgs_graph._prepare_graph_ready_state(context, ops_by_batch={"A": operations})


def test_native_readonly_decisions_share_only_unmodified_records():
    operations = _ops()
    scheduler = GreedyScheduler(object())
    assert native_readonly_inputs(schedule_with_optional_strict_mode, scheduler, operations)
    assert not native_readonly_inputs(lambda *args, **kwargs: None, scheduler, operations)
    decision = RepairDecision(("A",), (2, 1))
    _, shared = apply_repair_decision({}, operations, decision, None, share_unchanged=True)
    _, isolated = apply_repair_decision({}, operations, decision, None)
    assert all(left is right for left, right in zip(shared, operations))
    assert all(left is not right for left, right in zip(isolated, operations))
    isolated[0].seq = 99
    assert operations[0].seq == 1
    for op in operations:
        op.op_type_id = "T"
    _, override = apply_repair_decision({}, operations, RepairDecision(("A",), resource_overrides=((1, "M1", "O1"),)),
        {"machines_by_op_type": {"T": ["M1"]}, "operators_by_machine": {"M1": ["O1"]}}, share_unchanged=True)
    assert override[0] is not operations[0] and override[1] is operations[1]
    assert override[0].machine_id == "M1" and operations[0].machine_id is None


def test_native_candidate_trials_share_topology_and_do_not_copy_order_only_inputs(monkeypatch):
    from core.algorithms import SortStrategy
    from core.services.scheduler.run.optimizer.graph import candidates, repair_decisions

    operations, batches, context = graph_ready_benchmark_operations(), graph_ready_benchmark_batches(), graph_ready_benchmark_context()
    operations = [BatchOperation(**vars(op)) for op in operations]
    metrics = v2_features.enrich_graph_ready_v2_metrics(context["node_metrics_by_op_id"], operations=operations,
                                                       batches=batches, start_dt=START_DT)
    profile = replace(graph_ready_v2_profiles(max_candidate_profiles=60)[0][1],
                      candidate_origin="graph_ready_v2_repaired", candidate_policy="elite_repair")
    source = deepcopy(operations)
    checks, copies = [], []
    detect, copy_op = sgs_graph._detect_graph_ready_cycle, repair_decisions.copy
    def checked(**kwargs):
        checks.append(1)
        return detect(**kwargs)
    def copied(op):
        copies.append(op.id)
        return copy_op(op)
    monkeypatch.setattr(sgs_graph, "_detect_graph_ready_cycle", checked)
    monkeypatch.setattr(repair_decisions, "copy", copied)
    cache, checkpoints = {}, []
    for index, order in enumerate(((1, 3, 4, 2), (1, 4, 3, 2))):
        result = candidates.evaluate_graph_ready_candidate(
            profile=profile, graph_ready_context=context, metrics_by_op_id=metrics, scheduler=_scheduler(), strict_mode=True,
            algo_ops_to_schedule=operations, batches=batches, strategy=SortStrategy.PRIORITY_FIRST, params={},
            start_dt=START_DT, end_date=None, downtime_map={}, order=list(BASE_BATCH_ORDER), seed_sr_list=[],
            dispatch_rule="slack", resource_pool=None, objective_name="min_overdue", optimizer_algo_stats=None,
            schedule_fn=schedule_with_optional_strict_mode, readiness_gate_enabled=False, version=0, clock=lambda: 0.0,
            repair_decision=RepairDecision(tuple(BASE_BATCH_ORDER), order), topology_cache=cache,
            decode_checkpoints=DecodeCheckpointRequest([1], checkpoints.append) if index == 0 else None,
            decode_resume=checkpoints[0] if index else None)
        assert result["summary"].failed_ops == 0 and len(result["results"]) == len(operations)
    assert checks == [1] and copies == []
    assert operations == source


def test_both_feature_bases_share_common_preparation(monkeypatch):
    calls = []
    for name in ("_duration_by_op_id_with_zero_total_trace", "_processing_time_ranks", "seed_results_by_resource_id"):
        function = getattr(v2_features, name)
        def counted(*args, _function=function, _name=name, **kwargs):
            calls.append(_name)
            return _function(*args, **kwargs)
        monkeypatch.setattr(v2_features, name, counted)
    metrics = v2_features.enrich_graph_ready_v2_metrics(
        graph_ready_benchmark_context()["node_metrics_by_op_id"], operations=graph_ready_benchmark_operations(),
        batches=graph_ready_benchmark_batches(), start_dt=START_DT)
    assert len(calls) == len(set(calls)) == 3
    assert all(row["graph_ready_workload_version"] != row[BASELINE_ORDERING_FIELD]["graph_ready_workload_version"]
               for row in metrics.values())


def test_statistics_capture_copies_samples_once_and_keeps_source_independent():
    calls = []
    class Sample(dict):
        def __deepcopy__(self, memo):
            calls.append(1)
            return deepcopy(dict(self), memo)
    stats = make_algo_stats()
    stats["fallback_samples"]["reason"] = [Sample(value=[1])]
    source = SimpleNamespace(_last_algo_stats=stats)
    captured = capture_algo_stats(source)
    assert calls == [1]
    captured["fallback_samples"]["reason"][0]["value"].append(2)
    assert stats["fallback_samples"]["reason"][0]["value"] == [1]
