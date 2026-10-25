"""Operation/resource decisions must be realized by formal SGS with fixed seeds."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from itertools import islice
from types import SimpleNamespace

import pytest

from core.algorithm_contracts.sort_strategies import SortStrategy
from core.algorithm_contracts.types import ScheduleResult
from core.errors import ValidationError
from core.services.scheduler.run.optimizer.candidate_fingerprint import build_candidate_fingerprint
from core.services.scheduler.run.optimizer.graph.candidates import evaluate_graph_ready_candidate
from core.services.scheduler.run.optimizer.graph.iterated_greedy_moves import _parent_from_candidate
from core.services.scheduler.run.optimizer.graph.repair import EliteRepairPool
from core.services.scheduler.run.optimizer.graph.repair_contract import EliteRepairLimits
from core.services.scheduler.run.optimizer.graph.repair_decisions import (
    RepairDecision,
    iter_resource_decisions,
    prepare_repair_parent,
)
from core.services.scheduler.run.optimizer.graph.repair_neighbors import RepairNeighborhood
from core.services.scheduler.run.optimizer.graph.repair_portfolio import (
    ParentRepairPortfolio,
    RepairPortfolio,
    build_repair_portfolio,
)
from core.services.scheduler.run.optimizer.graph.v2_features import enrich_graph_ready_v2_metrics
from core.services.scheduler.run.optimizer.graph.v2_ranks import build_v2_common_rank_cache
from core.services.scheduler.run.optimizer.graph_ready_feature_basis import (
    BATCH_WORKLOAD_BASIS,
    SUCCESSOR_WORKLOAD_BASIS,
)
from core.services.scheduler.run.optimizer.graph_ready_profiles import resolve_v2_profiles
from tests._support.algo_operations import make_batch, make_schedule_result
from tests._support.optimizer_graph_ready_benchmark import (
    BASE_BATCH_ORDER,
    START_DT,
    _scheduler,
    graph_ready_benchmark_batches,
    graph_ready_benchmark_context,
    graph_ready_benchmark_operations,
)


def test_fixed_decision_features_admit_effective_profiles_once_and_preserve_raw_errors(monkeypatch):
    from core.services.scheduler.run.optimizer.graph import candidates
    from core.services.scheduler.run.optimizer.graph.ready import SharedGraphFeatures

    operations, batches = graph_ready_benchmark_operations(), graph_ready_benchmark_batches()
    context = graph_ready_benchmark_context()
    metrics = enrich_graph_ready_v2_metrics(
        context["node_metrics_by_op_id"], operations=operations, batches=batches,
        start_dt=START_DT, graph_ready_context=context,
    )
    ranks = build_v2_common_rank_cache(metrics)
    owner = SharedGraphFeatures(metrics, ranks)
    profiles = resolve_v2_profiles(seed=0, objective_name="min_overdue")
    profile = next(item for item in profiles if item.formula_version.startswith("graph_ready_v2")
                   and item.feature_basis == SUCCESSOR_WORKLOAD_BASIS)
    original = deepcopy((metrics, ranks))
    validate = candidates._validate_decision_features
    calls = []

    def counted(*args, **kwargs):
        calls.append(kwargs["profile"])
        return validate(*args, **kwargs)

    monkeypatch.setattr(candidates, "_validate_decision_features", counted)
    owner.decision_features.validate(profile)
    owner.decision_features.validate(replace(profile, slug="repair-label", candidate_origin="graph_ready_v2_repaired"))
    owner.decision_features.validate(replace(profile, candidate_origin="graph_ready_v2_iterated_greedy"))
    assert len(calls) == 1
    for changed in (replace(profile, formula_slug="spt" if profile.formula_slug != "spt" else "edd"),
                    replace(profile, feature_basis=BATCH_WORKLOAD_BASIS),
                    replace(profile, jitter_seed=profile.jitter_seed + 1),
                    replace(profile, effective_weights=dict(profile.effective_weights, critical_path=99.0))):
        owner.decision_features.validate(changed)
    assert len(calls) == 5
    assert (metrics, ranks) == original

    broken = deepcopy(metrics)
    broken[next(iter(broken))]["impact_count"] = float("nan")
    failed_owner = SharedGraphFeatures(broken, ranks)  # Admission stays at the first actual decision.
    with pytest.raises(ValidationError) as expected:
        validate(broken, profile=profile, v2_common_rank_cache=ranks)
    for _ in range(2):
        with pytest.raises(ValidationError) as actual:
            failed_owner.decision_features.validate(profile)
        assert (actual.value.field, str(actual.value), actual.value.details) == (
            expected.value.field, str(expected.value), expected.value.details)
    assert len(calls) == 7


def test_real_operation_and_qualified_resource_move_preserves_seed_dag_and_downtime(monkeypatch):
    from core.models.objective import target_objectives_for
    from core.services.scheduler.run.optimizer.graph import candidates
    from core.services.scheduler.run.optimizer.shared_archive import SharedScheduleArchive
    from core.services.scheduler.run.optimizer.shared_budget import SharedSearchBudget
    from core.services.scheduler.run.optimizer.shared_decode import SharedDecodeSession

    def unused_ranking(*args, **kwargs):
        raise AssertionError("Explicit decisions must not prepare discarded profile ranks")

    monkeypatch.setattr(candidates, "normalized_v2_metrics_by_op_id", unused_ranking)
    operations, batches = graph_ready_benchmark_operations(), graph_ready_benchmark_batches()
    operations[2].machine_id = operations[2].operator_id = None
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
    metrics = enrich_graph_ready_v2_metrics(
        context["node_metrics_by_op_id"], operations=operations, batches=batches,
        start_dt=START_DT, seed_results=[seed], resource_pool=pool, downtime_map=downtime,
        graph_ready_context=context,
    )
    profile = next(p for p in resolve_v2_profiles(seed=0, objective_name="min_overdue") if p.slug == "v2_seeded_micro_perturbation")
    profile = replace(profile, candidate_origin="graph_ready_v2_repaired", candidate_policy="elite_repair")

    sessions, seed_results = [], [seed]
    targets = target_objectives_for("min_overdue")
    archive = SharedScheduleArchive("min_overdue", targets, [op.id for op in operations] + [seed.op_id], batches)

    def decode(machine, operator, *, decision=None, decoder_operations=None):
        decision = decision or RepairDecision(tuple(BASE_BATCH_ORDER), (1, 3, 4, 2), ((3, machine, operator),))
        decoder_operations = decoder_operations or operations
        scheduler = _scheduler()
        budget = SharedSearchBudget(clock=lambda: 0.0, started_at=0.0, deadline=10.0,
                                    target_objectives=targets, configured_seconds=10)
        session = SharedDecodeSession(
            archive=archive, budget=budget, scheduler=scheduler, operations=decoder_operations, batches=batches,
            seed_results=seed_results, downtime_map=downtime, resource_pool=pool, graph_ready_context=context, start_dt=START_DT,
            clock=lambda: 0.0, started_at=0.0, deadline=10.0,
        )
        sessions.append(session)
        return evaluate_graph_ready_candidate(
            profile=profile, graph_ready_context=context, metrics_by_op_id=metrics, strict_mode=True,
            algo_ops_to_schedule=decoder_operations, strategy=SortStrategy.PRIORITY_FIRST, params={},
            start_dt=START_DT, end_date=None, order=list(decision.batch_order),
            dispatch_rule="slack", resource_pool=pool, objective_name="min_overdue", optimizer_algo_stats=None,
            readiness_gate_enabled=False, version=0, clock=lambda: 0.0,
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
    from core.services.scheduler.run.optimizer.graph import repair_decisions

    counts = {}
    with monkeypatch.context() as patch:
        for name in ("_operations_by_id", "_decoded_rows", "decoded_topological_order", "resource_timeline_groups",
                     "decoded_batch_order"):
            original_helper = getattr(repair_decisions, name)

            def counted(*args, _name=name, _helper=original_helper, **kwargs):
                counts[_name] = counts.get(_name, 0) + 1
                return _helper(*args, **kwargs)

            patch.setattr(repair_decisions, name, counted)

        def repeated_qualification(*args, **kwargs):
            raise AssertionError("A decoded parent's inherited selections must not be qualified again")

        patch.setattr(repair_decisions, "_validated_overrides", repeated_qualification)
        profiles = resolve_v2_profiles(seed=0, objective_name="min_overdue")
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
        ig_parent = _parent_from_candidate(
            stale_parent, operations=mutable_operations, graph_context=context, resource_pool=pool,
            prepared_parent=elite_pool.prepare_parent(stale_parent))
        assert ig_parent.prepared is prepared_parent
        assert ig_parent.predecessors is prepared_parent.predecessors
        assert ig_parent.successors is prepared_parent.successors
        _, internal_overrides = repair_decisions.repair_decision_inputs(
            context, mutable_operations, RepairDecision(parent.batch_order, parent.order, inherited), pool,
            prepared_parent=prepared_parent)
        assert internal_overrides == {3: ("MC-ALT", "OP-ALT"), 4: ("MC-BENCH", "OP-BENCH")}
        assert counts == {"_operations_by_id": 1, "_decoded_rows": 1,
                          "decoded_topological_order": 1, "resource_timeline_groups": 1}
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

    # A resource-free point event contributes no invented pair; external rows and fixed seeds stay out.
    event_operations = deepcopy(mutable_operations)
    event_operations[3].source = "external"
    event_parent = dict(stale_parent, results=[replace(row, machine_id=None, operator_id=None, end_time=row.start_time)
                                             if row.op_id == 3 else row for row in alternative["results"]])
    event_prepared = prepare_repair_parent(event_parent, event_operations, pool, context, resource_moves=True)
    assert event_prepared.inherited_resources == ()
    assert list(iter_resource_decisions(operations=event_operations, resource_pool=pool, batch_order=parent.batch_order,
                                        operation_order=parent.order, prepared_parent=event_prepared)) == []
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
    profile = next(p for p in resolve_v2_profiles(seed=0, objective_name="min_overdue") if p.slug == "v2_seeded_micro_perturbation")
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
    elite = {"neighborhood": parent, "candidate": {}, "prepared_parent": None, "decision_offset": 0, "stream_offsets": {}, "portfolio_id": 1}
    visit_kwargs = dict(
        elite=elite, state=SimpleNamespace(best=None), evaluate=None,
        clock=lambda: 0,
        t_begin=0, attempts=[], improvement_trace=[], report_state=None, strict_mode=True,
        before_decode=lambda: None, improved_elites=[], accounting=RepairWorkAccounting(),
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
    rows = {op_id: make_schedule_result(op_id=op_id, end_time=START_DT) for op_id in (1, 2)}
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

    # Ordinary moves retain adjacent-row vs known-type-identity counting and the historical 0/1 tardy diagnostic.
    results = [ScheduleResult(op_id=index + 1, op_code="R" + str(index + 1), batch_id=batch, seq=index, machine_id="M", op_type_id=kind,
                              start_time=START_DT + timedelta(hours=index), end_time=START_DT + timedelta(hours=index + 1))
               for index, (batch, kind) in enumerate((("BA", "A"), ("blank", ""), ("BB", "B"), ("BC", "C")))]
    batch_map = {batch_id: make_batch(batch_id=batch_id, due_date=due)
                 for batch_id, due in (("BA", "2025-12-31"), ("BB", "2026-01-01"), ("BC", None))}
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
    assert changed.batch_order == ("BA", "BC", "BB")
    assert counts["sort_key"] == len(results)
    window = neighborhood_moves.time_window_move(["BC", "BB", "BA"], results, batch_map)
    assert window.batch_order == ("BA", "BC", "BB")
    assert counts["due"] == len(batch_map)
    tardy = neighborhood_moves.tardy_window_move(["BC", "BB", "BA"], results, batch_map)
    assert tardy.batch_order == window.batch_order
    assert counts["tardy"] == 1

    # Graph repair changeover signals ignore point events, do not bridge across unknown types,
    # and require the same nonblank machine on critical-block pairs.
    from core.services.scheduler.run.optimizer.graph.repair_decisions import _batch_changeovers

    t0, t1, t2, t3 = START_DT, START_DT + timedelta(hours=1), START_DT + timedelta(hours=2), START_DT + timedelta(hours=3)
    row_a = ScheduleResult(op_id=1, op_code="R1", batch_id="BA", seq=1, machine_id="M1", operator_id="O1",
                           op_type_id="TA", start_time=t0, end_time=t1)
    row_point = ScheduleResult(op_id=2, op_code="R2", batch_id="BP", seq=1, machine_id="M1", operator_id="O1",
                               op_type_id=None, start_time=t1, end_time=t1)
    row_unknown = ScheduleResult(op_id=3, op_code="R3", batch_id="BU", seq=1, machine_id="M1", operator_id="O1",
                                 op_type_id=None, start_time=t1, end_time=t2)
    row_b = ScheduleResult(op_id=4, op_code="R4", batch_id="BB", seq=1, machine_id="M1", operator_id="O1",
                           op_type_id="TB", start_time=t2, end_time=t3)
    row_b_touch = replace(row_b, start_time=t1, end_time=t2)
    row_other_machine = replace(row_b_touch, machine_id="M2")
    assert _batch_changeovers({("machine_id", "M1"): [row_a, row_unknown, row_b]}, frozenset({"BA", "BU", "BB"})) == {}
    assert _batch_changeovers({("machine_id", "M1"): [row_a, row_point, row_b_touch]}, frozenset({"BA", "BP", "BB"})) == {
        "BA": 1.0, "BB": 1.0,
    }
    plain_metrics = {1: {"is_on_critical_path": False}, 2: {"is_on_critical_path": False}, 4: {"is_on_critical_path": False}}
    assert operation_neighbors._is_critical_block_pair(row_a, row_b_touch, (1, 4), plain_metrics, t3, "min_changeover")
    assert not operation_neighbors._is_critical_block_pair(
        row_a, row_other_machine, (1, 4), plain_metrics, t3, "min_changeover",
    )
    assert not operation_neighbors._is_critical_block_pair(
        row_a, replace(row_point, op_type_id="TB"), (1, 2), plain_metrics, t3, "min_changeover",
    )


def test_optimizer_changeover_signals_follow_type_identity_and_skip_point_events():
    from core.services.scheduler.run.optimizer import neighborhood_move_support, neighborhood_moves
    from core.services.scheduler.run.optimizer.graph.iterated_greedy_joint import _WindowIndex
    from core.services.scheduler.run.optimizer.graph.iterated_greedy_screen import InsertionScreen

    hour = timedelta(hours=1)

    def row(op_id, type_id, name, start, hours=1, machine="M1", batch=None):
        begin = START_DT + start * hour
        return ScheduleResult(op_id=op_id, op_code="R" + str(op_id), batch_id=batch or "B" + str(op_id), seq=op_id,
                              machine_id=machine, operator_id="O1", op_type_id=type_id, op_type_name=name,
                              start_time=begin, end_time=begin + hours * hour)

    # A point event of another type neither switches nor separates two timed rows of the same type.
    same_around_point = [row(1, "TA", "A", 0), row(2, "TB", "B", 1, hours=0), row(3, "TA", "A", 1)]
    assert neighborhood_move_support.first_changeover_pair(same_around_point) is None
    switched = same_around_point + [row(4, "TB", "B", 2)]
    assert neighborhood_move_support.first_changeover_pair(switched) == (switched[2], switched[3])
    # Identity, not the display label, decides a switch; an unknown identity blocks the bridge.
    assert neighborhood_move_support.first_changeover_pair([row(1, "T1", "SAME", 0), row(2, "T2", "SAME", 1)]) is not None
    assert neighborhood_move_support.first_changeover_pair([row(1, "T1", "N1", 0), row(2, "T1", "N2", 1)]) is None
    assert neighborhood_move_support.first_changeover_pair(
        [row(1, "TA", "A", 0), row(2, None, "A", 1), row(3, "TB", "A", 2)]) is None

    # An empty-batch seed on the bottleneck machine is a safe no-op.
    unbatched = [row(1, "TA", "A", 0, batch=" "), row(2, "TA", "A", 1, batch=" ")]
    move = neighborhood_moves.bottleneck_machine_move(["BA", "BB"], unbatched)
    assert move.noop and move.batch_order == ("BA", "BB")

    # Joint-window switch pressure: point rows stay resource neighbours but never count as switches.
    rows = [row(1, "TA", "N1", 0), row(2, "TB", "N1", 1, hours=0), row(3, "TA", "N2", 1), row(4, "TB", "N2", 2),
            row(5, None, "N2", 3), row(6, "TA", "N2", 4)]
    reference = SimpleNamespace(order=(1, 2, 3, 4, 5, 6), candidate={"results": rows})
    index = _WindowIndex(SimpleNamespace(_require_budget=lambda: None), reference)
    assert {op_id: index.switches[op_id] for op_id in reference.order} == {1: 0, 2: 0, 3: 1, 4: 1, 5: 0, 6: 0}
    assert 2 in index.adjacent[1] and 3 in index.adjacent[2]

    # The insertion screen keeps point rows for successor readiness without occupying or switching.
    search = SimpleNamespace(
        parent=SimpleNamespace(predecessors={1: set(), 2: {1}, 3: {2}, 4: set(), 5: set(), 6: set()}),
        metrics={}, report={"objective_name": "min_changeover"},
    )
    screen = InsertionScreen(search, reference)
    assert screen.supported and 2 in screen.rows
    ends, machines, families = {}, {}, {}
    switches = screen._advance_state(reference.order, ends, machines, {}, {}, families, 0)
    assert ends[2] == 1.0 and ends[3] == 2.0
    assert switches == 1 and families == {"M1": "TA"}


def test_graph_ready_type_group_rank_follows_type_identity_not_label():
    operations, batches = graph_ready_benchmark_operations(), graph_ready_benchmark_batches()
    assert len(operations) >= 3
    operations[0].op_type_id, operations[0].op_type_name = "OT-A", "SAME"
    operations[1].op_type_id, operations[1].op_type_name = "OT-B", "SAME"
    operations[2].op_type_name = "RELABELLED"
    context = graph_ready_benchmark_context()
    metrics = enrich_graph_ready_v2_metrics(
        context["node_metrics_by_op_id"], operations=operations, batches=batches,
        start_dt=START_DT, graph_ready_context=context,
    )
    rank = {op.id: metrics[op.id]["changeover_family_rank"] for op in operations if op.id in metrics}
    assert rank[operations[0].id] != rank[operations[1].id]
    assert {rank[op.id] for op in operations[2:] if op.id in rank} == {2}
