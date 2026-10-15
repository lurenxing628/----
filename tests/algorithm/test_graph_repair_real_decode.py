"""Operation/resource decisions must be realized by formal SGS with fixed seeds."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from itertools import islice
from types import SimpleNamespace

import pytest

from core.algorithms import ScheduleResult, SortStrategy
from core.errors import ValidationError
from core.services.scheduler.run.optimizer.candidate_fingerprint import build_candidate_fingerprint
from core.services.scheduler.run.optimizer.graph.candidates import evaluate_graph_ready_candidate
from core.services.scheduler.run.optimizer.graph.iterated_greedy_moves import _parent_from_candidate
from core.services.scheduler.run.optimizer.graph.repair import EliteRepairPool
from core.services.scheduler.run.optimizer.graph.repair_contract import EliteRepairLimits
from core.services.scheduler.run.optimizer.graph.repair_decisions import (
    RepairDecision,
    decoded_resource_overrides,
    iter_resource_decisions,
)
from core.services.scheduler.run.optimizer.graph.repair_neighbors import RepairNeighborhood
from core.services.scheduler.run.optimizer.graph.repair_portfolio import (
    ParentRepairPortfolio,
    RepairPortfolio,
    build_repair_portfolio,
)
from core.services.scheduler.run.optimizer.graph.v2_features import enrich_graph_ready_v2_metrics
from core.services.scheduler.run.optimizer.graph_ready_feature_basis import (
    BATCH_WORKLOAD_BASIS,
    SUCCESSOR_WORKLOAD_BASIS,
)
from core.services.scheduler.run.optimizer.graph_ready_profiles import graph_ready_v2_profiles
from tests._support.optimizer_graph_ready_benchmark import (
    BASE_BATCH_ORDER,
    START_DT,
    _schedule_with_scheduler,
    _scheduler,
    graph_ready_benchmark_batches,
    graph_ready_benchmark_context,
    graph_ready_benchmark_operations,
)


def test_real_operation_and_qualified_resource_move_preserves_seed_dag_and_downtime(monkeypatch):
    from core.models.objective import target_objectives_for
    from core.services.scheduler.run.optimizer.graph import candidates
    from core.services.scheduler.run.optimizer.shared_archive import SharedScheduleArchive
    from core.services.scheduler.run.optimizer.shared_budget import SharedSearchBudget
    from core.services.scheduler.run.optimizer.shared_decode import SharedDecodeSession

    def unused_ranking(*args, **kwargs):
        raise AssertionError("Explicit decisions must not prepare discarded profile ranks")

    monkeypatch.setattr(candidates, "_normalized_v2_metrics_by_op_id", unused_ranking)
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

    sessions, seed_results = [], [seed]

    def decode(machine, operator, *, decision=None, decoder_operations=None):
        decision = decision or RepairDecision(tuple(BASE_BATCH_ORDER), (1, 3, 4, 2), ((3, machine, operator),))
        decoder_operations = decoder_operations or operations
        scheduler = _scheduler()
        targets = target_objectives_for("min_overdue")
        archive = SharedScheduleArchive("min_overdue", targets, (op.id for op in decoder_operations), batches)
        budget = SharedSearchBudget(clock=lambda: 0.0, started_at=0.0, deadline=10.0,
                                    target_objectives=targets, configured_seconds=10)
        session = SharedDecodeSession(
            archive=archive, budget=budget, scheduler=scheduler, operations=decoder_operations, batches=batches,
            seed_results=seed_results, downtime_map=downtime, resource_pool=pool, graph_ready_context=context,
            clock=lambda: 0.0, started_at=0.0, deadline=10.0,
        )
        sessions.append(session)
        return evaluate_graph_ready_candidate(
            profile=profile, graph_ready_context=context, metrics_by_op_id=metrics, scheduler=scheduler, strict_mode=True,
            algo_ops_to_schedule=decoder_operations, batches=batches, strategy=SortStrategy.PRIORITY_FIRST, params={},
            start_dt=START_DT, end_date=None, downtime_map=downtime, order=list(decision.batch_order), seed_sr_list=seed_results,
            dispatch_rule="slack", resource_pool=pool, objective_name="min_overdue", optimizer_algo_stats=None,
            schedule_fn=_schedule_with_scheduler, readiness_gate_enabled=False, version=0, clock=lambda: 0.0,
            repair_decision=decision, decode_session=session,
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
    second = build_candidate_fingerprint(alternative, objective_name="min_overdue", parent_fingerprint=first,
                                         seen_output_fingerprints=[first.output_key])
    assert second.output_key != first.output_key
    assert second.fingerprint_changed and not second.same_as_seen

    # Subsequent stages inherit both real selections even when the old decision is stale.
    mutable_operations = deepcopy(operations)
    mutable_operations[3].machine_id = mutable_operations[3].operator_id = ""
    stale_parent = dict(alternative, decoded_batch_order=list(reversed(BASE_BATCH_ORDER)), repair_decision={
        "resource_overrides": [[3, "MC-BENCH", "OP-BENCH"], [4, "MC-ALT", "OP-ALT"]],
        "operation_order": [2, 4, 3, 1],
    })
    inherited = ((3, "MC-ALT", "OP-ALT"), (4, "MC-BENCH", "OP-BENCH"))
    assert decoded_resource_overrides(stale_parent, mutable_operations, pool) == inherited
    parent = _parent_from_candidate(stale_parent, operations=mutable_operations, graph_context=context, resource_pool=pool)
    assert parent is not None and parent.inherited == inherited
    assert parent.order.index(1) < parent.order.index(2)
    portfolio = build_repair_portfolio(
        stale_parent, operations=mutable_operations, metrics_by_op_id=metrics, start_dt=START_DT, seed=0,
        objective_name="min_overdue", graph_context=context, resource_pool=pool,
    )
    assert portfolio.batches.order == parent.batch_order
    decisions = list(portfolio.decisions())
    pure_order = [(kind, decision) for kind, decision in decisions if kind != "resource_alternative"]
    assert pure_order and all(decision.resource_overrides == inherited for _, decision in pure_order)
    assert any(kind in ("critical_block_swap", "operation_time_insert") for kind, _ in pure_order)
    resource_moves = [decision for kind, decision in decisions if kind == "resource_alternative"]
    assert resource_moves
    for decision in resource_moves:
        assert decision.operation_order == parent.order
        assert sum(left != right for left, right in zip(decision.resource_overrides, inherited)) == 1

    # Both basis variants consume the same decoded parent facts, including qualified selections.
    from core.services.scheduler.run.optimizer.graph import repair_decisions, repair_neighbors

    counts = {}
    with monkeypatch.context() as patch:
        for name in ("_operations_by_id", "_decoded_rows", "decoded_topological_order", "resource_timeline_groups",
                     "_decoded_resource_facts", "decoded_batch_order"):
            original_helper = getattr(repair_decisions, name)

            def counted(*args, _name=name, _helper=original_helper, **kwargs):
                counts[_name] = counts.get(_name, 0) + 1
                return _helper(*args, **kwargs)

            patch.setattr(repair_decisions, name, counted)

        def repeated_changeover_scan(*args, **kwargs):
            raise AssertionError("Prepared basis variants must reuse the machine projection")

        patch.setattr(repair_neighbors, "_add_changeover_signals", repeated_changeover_scan)
        profiles = graph_ready_v2_profiles(max_candidate_profiles=60)[0]
        successor = next(item for item in profiles if item.feature_basis == SUCCESSOR_WORKLOAD_BASIS
                         and item.formula_version.startswith("graph_ready_v2"))
        baseline = next(item for item in profiles if item.feature_basis == BATCH_WORKLOAD_BASIS
                        and item.formula_version.startswith("graph_ready_v2"))
        elite_pool = EliteRepairPool(
            limits=EliteRepairLimits(), objective_name="min_overdue", operations=mutable_operations,
            metrics_by_op_id=metrics, start_dt=START_DT, seed=0, best=stale_parent, report_state=None,
            graph_context=context, resource_pool=pool, decode_session=sessions[-1],
        )
        elite = elite_pool.make_elite(stale_parent, successor)
        prepared_parent = elite["prepared_parent"]
        elite_pool.add_basis_variant(elite, baseline)
        assert elite["prepared_parent"] is prepared_parent
        assert len(elite["neighborhood"].variants) == 2
        assert all(value == 1 for value in counts.values()) and len(counts) == 6
        assert prepared_parent.inherited_resources == inherited
        assert prepared_parent.operation_order == parent.order
        assert all(portfolio.inherited_resources is prepared_parent.inherited_resources
                   for _profile, portfolio in elite["neighborhood"].variants)
    pure_decoded = decode(None, None, decision=pure_order[0][1], decoder_operations=mutable_operations)
    pure_rows = {row.op_id: row for row in pure_decoded["results"]}
    assert pure_rows[99] == seed
    assert (pure_rows[3].machine_id, pure_rows[3].operator_id) == ("MC-ALT", "OP-ALT")
    assert (pure_rows[4].machine_id, pure_rows[4].operator_id) == ("MC-BENCH", "OP-BENCH")
    assert pure_rows[2].start_time >= pure_rows[1].end_time
    assert pure_rows[3].start_time >= downtime["MC-ALT"][0][1]

    # Existing qualification and fixed-input errors apply to actual output evidence.
    fixed_conflict = dict(stale_parent, results=[replace(row, machine_id="MC-ALT") if row.op_id == 1 else row
                                               for row in alternative["results"]])
    with pytest.raises(ValidationError) as exc:
        decoded_resource_overrides(fixed_conflict, mutable_operations, pool)
    assert exc.value.details["reason"] == "graph_ready_repair_fixed_resource"
    unqualified = dict(stale_parent, results=[replace(row, operator_id="OP-BENCH") if row.op_id == 3 else row
                                            for row in alternative["results"]])
    with pytest.raises(ValidationError) as exc:
        decoded_resource_overrides(unqualified, mutable_operations, pool)
    assert exc.value.details["reason"] == "graph_ready_repair_resource_qualification"

    # A resource-free point event contributes no invented pair; external rows and fixed seeds stay out.
    event_operations = deepcopy(mutable_operations)
    event_operations[3].source = "external"
    event_parent = dict(stale_parent, results=[replace(row, machine_id=None, operator_id=None, end_time=row.start_time)
                                             if row.op_id == 3 else row for row in alternative["results"]])
    assert decoded_resource_overrides(event_parent, event_operations, pool) == ()
    assert list(iter_resource_decisions(event_parent, event_operations, pool, parent.batch_order, parent.order)) == []
    assert (operations, context, pool, seed) == original


def test_repair_positions_and_move_prefixes_preserve_exact_consumption(monkeypatch):
    from core.models.objective import target_objectives_for
    from core.services.scheduler.run.optimizer import neighborhood_move_support, neighborhood_moves
    from core.services.scheduler.run.optimizer.graph import operation_neighbors
    from core.services.scheduler.run.optimizer.graph.repair_accounting import RepairWorkAccounting
    from core.services.scheduler.run.optimizer.shared_archive import SharedScheduleArchive
    from core.services.scheduler.run.optimizer.shared_budget import SharedSearchBudget
    from core.services.scheduler.run.optimizer.shared_decode import SharedDecodeSession

    order = tuple("B" + str(index) for index in range(10))
    batches = RepairNeighborhood(order, tuple(("adjacent_swap", index, index + 1) for index in range(9)))
    portfolio = RepairPortfolio(batches, (), ())
    profile = graph_ready_v2_profiles(max_candidate_profiles=60)[0][1]
    expanded = []
    expand = RepairPortfolio._batch_decision

    def counted_expand(self, index):
        expanded.append(index)
        return expand(self, index)

    monkeypatch.setattr(RepairPortfolio, "_batch_decision", counted_expand)
    consumed = list(islice(portfolio.decisions(), 8))
    assert len(consumed) == 8 and expanded == list(range(8))
    expanded.clear()
    parent = ParentRepairPortfolio(((profile, portfolio),))
    ninth = next(parent.profiled_decisions({profile.feature_basis: 8}))
    assert expanded == [8] and ninth[1].batch_order == order[:8] + (order[9], order[8])
    other = replace(profile, feature_basis=SUCCESSOR_WORKLOAD_BASIS)
    added = parent.with_variant(other, portfolio)
    expanded.clear()
    stream = added.profiled_decisions({profile.feature_basis: 8, other.feature_basis: 0})
    assert next(stream) == ninth
    assert next(stream)[2] is other and expanded == [8, 0]
    assert added.candidate_count == 18 and parent.candidate_count == 9

    # The real elite visit also stops before expanding an unconsumed ninth move.
    from core.services.scheduler.run.optimizer.graph import repair

    targets = target_objectives_for("min_overdue")
    archive = SharedScheduleArchive("min_overdue", targets, (), {})
    budget = SharedSearchBudget(clock=lambda: 0.0, started_at=0.0, deadline=10.0,
                                target_objectives=targets, configured_seconds=10)
    session = SharedDecodeSession(
        archive=archive, budget=budget, scheduler=_scheduler(), operations=[], batches={},
        seed_results=[], downtime_map={}, resource_pool=None, clock=lambda: 0.0, started_at=0.0, deadline=10.0,
    )
    visit_pool = EliteRepairPool(
        limits=EliteRepairLimits(), objective_name="min_overdue", operations=[], metrics_by_op_id={},
        start_dt=START_DT, seed=0, best=None, report_state=None, decode_session=session,
    )
    elite = {"neighborhood": parent, "candidate": {}, "decision_offset": 0, "stream_offsets": {}, "portfolio_id": 1}
    visit_kwargs = dict(
        elite=elite, elite_index=0, state=SimpleNamespace(best=None), evaluate=None,
        clock=lambda: 0,
        t_begin=0, attempts=[], improvement_trace=[], report_state=None, strict_mode=True,
        before_decode=lambda: None, improved_elites=[], accounting=RepairWorkAccounting(), decode_session=session,
    )
    with monkeypatch.context() as patch:
        patch.setattr(repair, "_evaluate_neighbor", lambda *args, **kwargs: None)
        expanded.clear()
        assert len(list(repair._repair_one_elite(visit_pool, **visit_kwargs))) == 8
        assert expanded == list(range(8))
        expanded.clear()
        assert len(list(repair._repair_one_elite(visit_pool, **visit_kwargs))) == 1
        assert expanded == [8] and elite["decision_offset"] == 9
        assert visit_pool.report["repair_pruning_report"]["generated_candidates"] == 9

    generated = []

    def family(kind):
        def moves(timeline, *args):
            for index in range(10):
                generated.append((kind, timeline[0].op_id, index))
                yield kind, index + 1, index + 2
        return moves

    monkeypatch.setattr(operation_neighbors, "_critical_block_moves", family("critical_block_swap"))
    monkeypatch.setattr(operation_neighbors, "_time_insert_moves", family("operation_time_insert"))
    rows = {1: SimpleNamespace(op_id=1, end_time=START_DT), 2: SimpleNamespace(op_id=2, end_time=START_DT)}
    moves = operation_neighbors._operation_moves([[rows[1]], [rows[2]]], rows, {}, START_DT, "min_overdue")
    assert next(moves) == ("critical_block_swap", 1, 2)
    assert generated == [("critical_block_swap", 1, 0), ("operation_time_insert", 1, 0)]

    inspected = []

    def valid_moves():
        for target in range(3, 12):
            inspected.append(target)
            yield "operation_time_insert", 1, target

    operation_order = tuple(range(1, 13))
    ranks = {op_id: index for index, op_id in enumerate(operation_order)}
    predecessors = {op_id: set() for op_id in operation_order}
    assert len(list(operation_neighbors._bounded_operation_orders(operation_order, ranks, predecessors, valid_moves(), 8))) == 8
    assert inspected == list(range(3, 11))
    inspected.clear()

    def invalid_moves():
        for index in range(33):
            inspected.append(index)
            yield "operation_time_insert", 1, 1

    assert list(operation_neighbors._bounded_operation_orders(operation_order, ranks, predecessors, invalid_moves(), 8)) == []
    assert inspected == list(range(32))

    # Ordinary moves retain adjacent-row vs nonblank-type counting and the historical 0/1 tardy diagnostic.
    results = [ScheduleResult(op_id=index + 1, op_code="R" + str(index + 1), batch_id=batch, seq=index, machine_id="M", op_type_name=kind,
                              start_time=START_DT + timedelta(hours=index), end_time=START_DT + timedelta(hours=index + 1))
               for index, (batch, kind) in enumerate((("BA", "A"), ("blank", ""), ("BB", "B"), ("BC", "C")))]
    batch_map = {"BA": SimpleNamespace(due_date="2025-12-31"), "BB": SimpleNamespace(due_date="2026-01-01"),
                 "BC": SimpleNamespace(due_date=None)}
    counts = {"sort_key": 0, "due": 0, "tardy": 0}
    for name, key in (("result_time_key", "sort_key"), ("batch_due_date", "due"), ("most_tardy_batch", "tardy")):
        helper = getattr(neighborhood_move_support, name)

        def counted(*args, _key=key, _helper=helper, **kwargs):
            counts[_key] += 1
            return _helper(*args, **kwargs)

        monkeypatch.setattr(neighborhood_move_support, name, counted)
        if name == "most_tardy_batch":
            monkeypatch.setattr(neighborhood_moves, name, counted)
    changed = neighborhood_moves.changeover_block_move(["BA", "BB", "BC"], results)
    assert changed.batch_order == ("BA", "BC", "BB") and changed.diagnostics["changeover_count"] == 2
    assert counts["sort_key"] == len(results)
    window = neighborhood_moves.time_window_move(["BC", "BB", "BA"], results, batch_map)
    assert window.batch_order == ("BA", "BC", "BB") and window.diagnostics["due_window_batch_count"] == 2
    assert counts["due"] == len(batch_map)
    tardy = neighborhood_moves.tardy_window_move(["BC", "BB", "BA"], results, batch_map)
    assert tardy.batch_order == window.batch_order and tardy.diagnostics["tardy_batch_count"] == 1
    assert counts["tardy"] == 1
