"""Operation/resource decisions must be realized by formal SGS with fixed seeds."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime, timedelta
from functools import partial
from itertools import islice
from types import SimpleNamespace

from core.algorithm_contracts.sort_strategies import SortStrategy
from core.algorithm_contracts.types import ScheduleResult
from core.algorithms.evaluation import prepare_evaluation_context
from core.services.scheduler.run.optimizer.candidate_fingerprint import (
    build_candidate_fingerprint,
    schedule_content_key,
)
from core.services.scheduler.run.optimizer.graph.candidates import (
    PreparedDecisionFeatures,
    evaluate_graph_ready_candidate,
)
from core.services.scheduler.run.optimizer.graph.iterated_greedy import _IteratedGreedySearch
from core.services.scheduler.run.optimizer.graph.iterated_greedy_contract import (
    IteratedGreedyLimits,
    ig_decode_profile,
    new_iterated_greedy_report,
)
from core.services.scheduler.run.optimizer.graph.iterated_greedy_moves import _parent_from_candidate
from core.services.scheduler.run.optimizer.graph.repair import EliteRepairPool
from core.services.scheduler.run.optimizer.graph.repair_contract import EliteRepairLimits
from core.services.scheduler.run.optimizer.graph.repair_decisions import (
    RepairDecision,
    iter_resource_decisions,
    prepare_repair_parent,
    prepare_repair_scope,
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
from core.services.scheduler.run.optimizer.search_report import OptimizationSearchReportState
from core.services.scheduler.run.optimizer.shared_budget import SharedSearchSkip
from tests._support.algo_operations import make_batch, make_schedule_result
from tests._support.optimizer_graph_ready_benchmark import (
    BASE_BATCH_ORDER,
    START_DT,
    ContinuousCalendar,
    _scheduler,
    graph_ready_benchmark_batches,
    graph_ready_benchmark_context,
    graph_ready_benchmark_operations,
)
from tests._support.schedule_decode import production_session


def test_fixed_decision_features_admit_effective_profiles_once_and_preserve_raw_errors(monkeypatch):
    from core.services.scheduler.run.optimizer.graph import candidates
    from core.services.scheduler.run.optimizer.graph.ready import SharedGraphFeatures

    operations, batches = graph_ready_benchmark_operations(), graph_ready_benchmark_batches()
    context = graph_ready_benchmark_context()
    preparation = production_session(_scheduler(), operations=operations, batches=batches,
                                     graph_ready_context=context).native_preparation
    metrics = enrich_graph_ready_v2_metrics(
        context["node_metrics_by_op_id"], operations=operations, batches=batches,
        start_dt=START_DT, graph_ready_context=context, calendar_service=ContinuousCalendar(),
        downtime_map={}, seed_results=[], deadline=float("inf"), clock=lambda: 0.0,
        native_preparation=preparation,
    )
    assert metrics is not None
    ranks = build_v2_common_rank_cache(metrics)
    owner = SharedGraphFeatures(metrics, ranks, frozenset(metrics))
    profiles = resolve_v2_profiles(seed=0, objective_name="min_overdue")
    profile = next(item for item in profiles if item.formula_version.startswith("graph_ready_v2")
                   and item.feature_basis == SUCCESSOR_WORKLOAD_BASIS)
    original = deepcopy((metrics, ranks))
    compute = candidates._priority_keys_for_profile
    calls = []

    def counted(*args, **kwargs):
        calls.append(kwargs["profile"])
        return compute(*args, **kwargs)

    monkeypatch.setattr(candidates, "_priority_keys_for_profile", counted)
    first = owner.decision_features.priority_keys_for_profile(profile)
    assert owner.decision_features.priority_keys_for_profile(
        replace(profile, slug="repair-label", candidate_origin="graph_ready_v2_repaired")) is first
    assert owner.decision_features.priority_keys_for_profile(
        replace(profile, candidate_origin="graph_ready_v2_iterated_greedy")) is first
    assert len(calls) == 1
    for changed in (replace(profile, formula_slug="spt" if profile.formula_slug != "spt" else "edd"),
                    replace(profile, feature_basis=BATCH_WORKLOAD_BASIS),
                    replace(profile, jitter_seed=profile.jitter_seed + 1),
                    replace(profile, effective_weights=dict(profile.effective_weights, critical_path=99.0))):
        owner.decision_features.priority_keys_for_profile(changed)
    assert len(calls) == 5
    assert (metrics, ranks) == original


def test_real_operation_and_qualified_resource_move_preserves_seed_dag_and_downtime(monkeypatch):
    from core.models.objective import target_objectives_for
    from core.services.scheduler.run.optimizer.graph import candidates
    from core.services.scheduler.run.optimizer.shared_archive import SharedScheduleArchive
    from core.services.scheduler.run.optimizer.shared_budget import SharedSearchBudget
    from core.services.scheduler.run.optimizer.shared_decode import SharedDecodeSession

    operations, batches = graph_ready_benchmark_operations(), graph_ready_benchmark_batches()
    operations[2].machine_id = operations[2].operator_id = None
    context = graph_ready_benchmark_context()
    seed = ScheduleResult(op_id=99, op_code="FIXED", batch_id="B_LONG", seq=0,
                          machine_id="MC-BENCH", operator_id="OP-BENCH", op_type_name="BENCH",
                          start_time=START_DT, end_time=START_DT + timedelta(hours=1))
    context["fixed_op_ids"] = {99}
    context["predecessor_op_ids_by_op_id"].update({99: set(), 1: {99}, 2: {1}})
    context["successor_op_ids_by_op_id"].update({99: {1}, 1: {2}})
    pool = {"machines_by_op_type": {"OT-BENCH": ["MC-BENCH", "MC-ALT"]},
            "machines_by_operator": {},
            "operators_by_machine": {"MC-BENCH": ["OP-BENCH"], "MC-ALT": ["OP-ALT"]},
            "pair_rank": {}}
    downtime = {"MC-ALT": [(START_DT, START_DT + timedelta(hours=4))]}
    original = deepcopy((operations, context, pool, seed))
    preparation = production_session(_scheduler(), operations=operations, batches=batches, seed_results=[seed],
                                     machine_downtimes=downtime, resource_pool=pool,
                                     graph_ready_context=context).native_preparation
    metrics = enrich_graph_ready_v2_metrics(
        context["node_metrics_by_op_id"], operations=operations, batches=batches,
        start_dt=START_DT, seed_results=[seed], resource_pool=pool, downtime_map=downtime,
        graph_ready_context=context, calendar_service=ContinuousCalendar(),
        deadline=float("inf"), clock=lambda: 0.0, native_preparation=preparation,
    )
    assert metrics is not None
    features = PreparedDecisionFeatures(metrics, build_v2_common_rank_cache(metrics), schedulable_ids=frozenset(metrics))
    base_profile = next(p for p in resolve_v2_profiles(seed=0, objective_name="min_overdue")
                        if p.slug == "v2_seeded_micro_perturbation")
    profile = replace(base_profile, candidate_origin="graph_ready_v2_repaired", candidate_policy="elite_repair")

    sessions, seed_results = [], [seed]
    targets = target_objectives_for("min_overdue")
    archive = SharedScheduleArchive("min_overdue", targets, [op.id for op in operations] + [seed.op_id], batches)

    def run(decoder_operations, *, decode_profile, order, repair=None):
        scheduler = _scheduler()
        budget = SharedSearchBudget(clock=lambda: 0.0, started_at=0.0, deadline=10.0,
                                    target_objectives=targets, configured_seconds=10)
        session = SharedDecodeSession(
            archive=archive, budget=budget, scheduler=scheduler, operations=decoder_operations, batches=batches,
            seed_results=seed_results, downtime_map=downtime, resource_pool=pool, graph_ready_context=context,
            clock=lambda: 0.0, started_at=0.0, deadline=10.0,
        )
        sessions.append(session)
        return evaluate_graph_ready_candidate(
            profile=decode_profile, strategy=SortStrategy.PRIORITY_FIRST, params={},
            start_dt=START_DT, end_date=None, order=order,
            dispatch_rule="slack", resource_pool=pool, objective_name="min_overdue", optimizer_algo_stats=None,
            readiness_gate_enabled=False, version=0, clock=lambda: 0.0,
            repair=repair, decode_session=session, prepared_decision_features=features,
        )

    # Explicit decisions are generated from a decoded parent: decode one plain profile first,
    # with operation 3 on its benchmark pair as the parent's actual selection.
    assigned = deepcopy(operations)
    assigned[2].machine_id, assigned[2].operator_id = "MC-BENCH", "OP-BENCH"
    plain_parent = run(assigned, decode_profile=base_profile, order=list(BASE_BATCH_ORDER))
    pairs_for = sessions[-1].native_preparation.qualified_resource_pairs
    topology = sessions[-1].native_preparation.graph_topology()
    decoded_parent = prepare_repair_parent(
        plain_parent,
        scope=prepare_repair_scope(operations, topology, resource_pairs_for=pairs_for),
    )

    def unused_ranking(*args, **kwargs):
        raise AssertionError("Explicit decisions must not prepare discarded profile ranks")

    monkeypatch.setattr(candidates, "normalized_v2_metrics_by_op_id", unused_ranking)

    def decode(machine, operator, *, decision=None, decoder_operations=None, parent=None):
        decision = decision or RepairDecision(tuple(BASE_BATCH_ORDER), (1, 3, 4, 2), ((3, machine, operator),))
        return run(decoder_operations or operations, decode_profile=profile, order=list(decision.batch_order),
                   repair=(decision, parent or decoded_parent))

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
    stale_parent = dict(alternative, decoded_batch_order=tuple(reversed(BASE_BATCH_ORDER)), repair_decision={
        "resource_overrides": [[3, "MC-BENCH", "OP-BENCH"], [4, "MC-ALT", "OP-ALT"]],
        "operation_order": [2, 4, 3, 1],
    })
    inherited = ((3, "MC-ALT", "OP-ALT"), (4, "MC-BENCH", "OP-BENCH"))
    stale_prepared = prepare_repair_parent(
        stale_parent,
        scope=prepare_repair_scope(mutable_operations, topology, resource_pairs_for=pairs_for),
    )
    parent = _parent_from_candidate(stale_parent, prepared=stale_prepared)
    assert parent is not None and parent.inherited == inherited
    assert parent.order.index(1) < parent.order.index(2)
    portfolio = build_repair_portfolio(
        operations=mutable_operations, metrics_by_op_id=metrics, start_dt=START_DT, seed=0,
        objective_name="min_overdue", prepared_parent=stale_prepared,
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
    from core.services.scheduler.run.optimizer import shared_decode
    from core.services.scheduler.run.optimizer.graph import repair_decisions

    counts = {}
    with monkeypatch.context() as patch:
        # The decoded batch order is computed once at the decode boundary; parent preparation only reads it.
        for module, name in ((repair_decisions, "_operations_by_id"), (repair_decisions, "_decoded_rows"),
                             (repair_decisions, "decoded_topological_order"),
                             (repair_decisions, "resource_timeline_groups"), (shared_decode, "decoded_batch_order")):
            original_helper = getattr(module, name)

            def counted(*args, _name=name, _helper=original_helper, **kwargs):
                counts[_name] = counts.get(_name, 0) + 1
                return _helper(*args, **kwargs)

            patch.setattr(module, name, counted)

        profiles = resolve_v2_profiles(seed=0, objective_name="min_overdue")
        successor = next(item for item in profiles if item.feature_basis == SUCCESSOR_WORKLOAD_BASIS
                         and item.formula_version.startswith("graph_ready_v2"))
        baseline = next(item for item in profiles if item.feature_basis == BATCH_WORKLOAD_BASIS
                        and item.formula_version.startswith("graph_ready_v2"))
        elite_pool = EliteRepairPool(
            limits=EliteRepairLimits(), objective_name="min_overdue", operations=mutable_operations,
            start_dt=START_DT, seed=0, best=stale_parent,
            report_state=OptimizationSearchReportState(objective_name="min_overdue", started_at=0.0),
            clock=lambda: 0.0, deadline=10.0, decode_session=sessions[-1],
            decision_features=features,
        )
        elite = elite_pool.make_elite(stale_parent, successor)
        prepared_parent = elite["prepared_parent"]
        elite_pool.add_basis_variant(elite, baseline)
        assert elite["prepared_parent"] is prepared_parent
        assert len(elite["neighborhood"].variants) == 2
        other_elite = elite_pool.make_elite(dict(stale_parent), successor)
        assert other_elite["prepared_parent"] is prepared_parent
        rebuilt_wrapper = dict(
            stale_parent,
            archive_ref=SimpleNamespace(
                entry_id=stale_parent["archive_ref"].entry_id,
                evidence_revision=stale_parent["archive_ref"].evidence_revision,
            ),
        )
        assert elite_pool.prepare_parent(rebuilt_wrapper) is prepared_parent
        # The iterated-greedy start pool builds an elite's parent from the elite's own preparation.
        ig_parent = _parent_from_candidate(stale_parent, prepared=elite["prepared_parent"])
        assert ig_parent.predecessors is prepared_parent.predecessors
        assert ig_parent.successors is prepared_parent.successors
        # The IG start and its start pool ask for the same candidate again: it is prepared only once.
        assert elite_pool.prepare_parent(stale_parent) is prepared_parent
        elite_pool.sync_ig_candidates(rebuilt_wrapper)
        assert elite_pool._parent_key(stale_parent) in elite_pool._prepared_parents
        elite_pool.sync_ig_candidates()
        assert not elite_pool._prepared_parents
        _, internal_overrides = repair_decisions.repair_decision_inputs(
            RepairDecision(parent.batch_order, parent.order, inherited), prepared_parent)
        assert internal_overrides == {3: ("MC-ALT", "OP-ALT"), 4: ("MC-BENCH", "OP-BENCH")}
        assert counts == {"_operations_by_id": 1, "_decoded_rows": 1,
                          "decoded_topological_order": 1, "resource_timeline_groups": 1}
        assert prepared_parent.inherited_resources == inherited
        assert prepared_parent.operation_order == parent.order
        assert all(portfolio.inherited_resources is prepared_parent.inherited_resources
                   for _profile, portfolio in elite["neighborhood"].variants)
    pure_decoded = decode(None, None, decision=pure_order[0][1], decoder_operations=mutable_operations,
                          parent=prepared_parent)
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
    event_prepared = prepare_repair_parent(
        event_parent,
        scope=prepare_repair_scope(event_operations, topology, resource_pairs_for=pairs_for),
    )
    assert event_prepared.inherited_resources == ()
    assert list(iter_resource_decisions(batch_order=parent.batch_order,
                                        operation_order=parent.order, prepared_parent=event_prepared)) == []
    assert (operations, context, pool, seed) == original


def test_repair_positions_and_move_prefixes_preserve_exact_consumption(monkeypatch):
    from core.models.objective import target_objectives_for
    from core.services.scheduler.run.optimizer import neighborhood_move_support, neighborhood_moves
    from core.services.scheduler.run.optimizer.graph import operation_neighbors
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
    empty_graph = {"enabled": True, "schedulable_op_ids": set(), "fixed_op_ids": set(), "sort_key_by_op_id": {},
                   "predecessor_op_ids_by_op_id": {}, "successor_op_ids_by_op_id": {}}
    session = SharedDecodeSession(
        archive=archive, budget=budget, scheduler=_scheduler(), operations=[], batches={},
        seed_results=[], downtime_map={}, resource_pool=None, graph_ready_context=empty_graph,
        clock=lambda: 0.0, started_at=0.0, deadline=10.0,
    )
    visit_report = OptimizationSearchReportState(objective_name="min_overdue", started_at=0.0)
    visit_pool = EliteRepairPool(
        limits=EliteRepairLimits(), objective_name="min_overdue", operations=[],
        start_dt=START_DT, seed=0, best=None, report_state=visit_report,
        clock=lambda: 0.0, deadline=10.0, decode_session=session,
        decision_features=PreparedDecisionFeatures({}, build_v2_common_rank_cache({}), schedulable_ids=frozenset()),
    )
    visit_candidate = {"archive_ref": SimpleNamespace(entry_id=1, evidence_revision=None), "results": [],
                       "decoded_batch_order": ()}
    elite = {"neighborhood": parent, "candidate": visit_candidate, "prepared_parent": None, "decision_offset": 0,
             "stream_offsets": {}}

    def skipped_neighbor(**_kwargs):
        # A neighbour the shared session declines to decode (production skip reason) still yields once.
        raise SharedSearchSkip("seen_without_payload")

    visit_kwargs = dict(
        elite=elite, state=SimpleNamespace(best=None), evaluate=skipped_neighbor,
        report_state=visit_report,
        improved_elites=[],
        active_groups=([elite],),
    )
    expanded.clear()
    assert len(list(repair._repair_one_elite(visit_pool, **visit_kwargs))) == 8
    assert expanded == list(range(8))
    expanded.clear()
    assert len(list(repair._repair_one_elite(visit_pool, **visit_kwargs))) == 1
    assert expanded == [8] and elite["decision_offset"] == 9

    generated = []

    def family(kind):
        def moves(timeline, *args):
            for index in range(10):
                generated.append((kind, timeline[0].op_id, index))
                yield kind, index + 1, index + 2
        return moves

    monkeypatch.setattr(operation_neighbors, "_critical_block_moves", family("critical_block_swap"))
    monkeypatch.setattr(operation_neighbors, "_time_insert_moves", family("operation_time_insert"))
    rows = {op_id: make_schedule_result(op_id=op_id, machine_id=None, operator_id=None, start_time=START_DT, end_time=START_DT) for op_id in (1, 2)}
    moves = operation_neighbors._operation_moves([[rows[1]], [rows[2]]], rows, {}, START_DT, "min_overdue",
                                                 latest=START_DT)
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
            yield "operation_time_insert", 1, 99

    assert list(operation_neighbors._bounded_operation_orders(operation_order, ranks, predecessors, invalid_moves(), 8)) == []
    assert inspected == list(range(32))

    # Ordinary moves retain adjacent-row vs known-type-identity counting and the historical 0/1 tardy diagnostic.
    results = [ScheduleResult(op_id=index + 1, op_code="R" + str(index + 1), batch_id=batch, seq=index, machine_id="M", operator_id=None, op_type_id=kind,
                              start_time=START_DT + timedelta(hours=index), end_time=START_DT + timedelta(hours=index + 1))
               for index, (batch, kind) in enumerate((("BA", "A"), ("blank", ""), ("BB", "B"), ("BC", "C")))]
    batch_map = {batch_id: make_batch(batch_id=batch_id, due_date=due)
                 for batch_id, due in (("BA", "2025-12-31"), ("BB", "2026-01-01"), ("BC", None))}
    counts = {"sort_key": 0, "tardy": 0, "finish": 0}
    for name, key in (("result_time_key", "sort_key"), ("_most_tardy_batch", "tardy"), ("_finish_by_batch", "finish")):
        helper = getattr(neighborhood_move_support, name)

        def counted(*args, _key=key, _helper=helper, **kwargs):
            counts[_key] += 1
            return _helper(*args, **kwargs)

        monkeypatch.setattr(neighborhood_move_support, name, counted)
    # Due facts come prepared from the run's evaluation context; the moves never parse or bound a due date again.
    due_batches = prepare_evaluation_context(batches=batch_map, expected_operations=[], seed_results=[]).due_batches
    assert [(item.batch_id, item.due_date, item.due_exclusive) for item in due_batches] == [
        ("BA", date(2025, 12, 31), datetime(2026, 1, 1)), ("BB", date(2026, 1, 1), datetime(2026, 1, 2)),
        ("BC", None, None)]
    result_facts = neighborhood_move_support.LocalSearchResultFacts(results, due_batches=due_batches)
    changed = neighborhood_moves.changeover_block_move(["BA", "BB", "BC"], result_facts)
    assert changed.batch_order == ("BA", "BC", "BB")
    assert counts["sort_key"] == len(results)
    window = neighborhood_moves.time_window_move(["BC", "BB", "BA"], result_facts)
    assert window.batch_order == ("BA", "BC", "BB")
    assert counts["finish"] == 1
    tardy = neighborhood_moves.tardy_window_move(["BC", "BB", "BA"], result_facts)
    assert tardy.batch_order == window.batch_order
    assert counts["tardy"] == 1
    assert counts["finish"] == 1
    assert neighborhood_moves.changeover_block_move(["BA", "BB", "BC"], result_facts) == changed
    assert counts["sort_key"] == len(results)

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
    from core.services.scheduler.run.optimizer import neighborhood_moves
    from core.services.scheduler.run.optimizer.graph.iterated_greedy_joint import _WindowIndex
    from core.services.scheduler.run.optimizer.graph.iterated_greedy_screen import InsertionScreen
    from core.services.scheduler.run.optimizer.neighborhood_move_support import LocalSearchResultFacts

    hour = timedelta(hours=1)

    def row(op_id, type_id, name, start, hours=1, machine="M1", batch=None):
        begin = START_DT + start * hour
        return ScheduleResult(op_id=op_id, op_code="R" + str(op_id), batch_id=batch or "B" + str(op_id), seq=op_id,
                              machine_id=machine, operator_id="O1", op_type_id=type_id, op_type_name=name,
                              start_time=begin, end_time=begin + hours * hour)

    def changeover_pair(rows):
        return LocalSearchResultFacts(rows, due_batches=()).changeover_pair()

    # A point event of another type neither switches nor separates two timed rows of the same type.
    same_around_point = [row(1, "TA", "A", 0), row(2, "TB", "B", 1, hours=0), row(3, "TA", "A", 1)]
    assert changeover_pair(same_around_point) is None
    switched = same_around_point + [row(4, "TB", "B", 2)]
    assert changeover_pair(switched) == (switched[2], switched[3])
    # Identity, not the display label, decides a switch; an unknown identity blocks the bridge.
    assert changeover_pair([row(1, "T1", "SAME", 0), row(2, "T2", "SAME", 1)]) is not None
    assert changeover_pair([row(1, "T1", "N1", 0), row(2, "T1", "N2", 1)]) is None
    assert changeover_pair([row(1, "TA", "A", 0), row(2, None, "A", 1), row(3, "TB", "A", 2)]) is None

    # An empty-batch seed on the bottleneck machine is a safe no-op.
    unbatched = [row(1, "TA", "A", 0, batch=" "), row(2, "TA", "A", 1, batch=" ")]
    move = neighborhood_moves.bottleneck_machine_move(["BA", "BB"], LocalSearchResultFacts(unbatched, due_batches=()))
    assert move.noop and move.batch_order == ("BA", "BB")

    # Joint-window switch pressure: point rows stay resource neighbours but never count as switches.
    rows = [row(1, "TA", "N1", 0), row(2, "TB", "N1", 1, hours=0), row(3, "TA", "N2", 1), row(4, "TB", "N2", 2),
            row(5, None, "N2", 3), row(6, "TA", "N2", 4)]
    reference = SimpleNamespace(order=(1, 2, 3, 4, 5, 6), candidate={"results": rows}, features=None)
    index = _WindowIndex(SimpleNamespace(_require_budget=lambda: None), reference)
    assert {op_id: index.switches[op_id] for op_id in reference.order} == {1: 0, 2: 0, 3: 1, 4: 1, 5: 0, 6: 0}
    assert 2 in index.adjacent[1] and 3 in index.adjacent[2]

    # The insertion screen keeps point rows for successor readiness without occupying or switching.
    screen_metric = {
        "due_deadline_hours": 8.0,
        "due_pressure": 0.5,
        "weighted_due_pressure": 0.5,
        "weighted_processing_hours": 1.0,
    }
    search = SimpleNamespace(
        parent=SimpleNamespace(predecessors={1: set(), 2: {1}, 3: {2}, 4: set(), 5: set(), 6: set()}),
        metrics={op_id: dict(screen_metric) for op_id in reference.order},
        report={"objective_name": "min_changeover"},
    )
    screen = InsertionScreen(search, reference)
    assert screen.supported and 2 in screen.rows
    other_search = SimpleNamespace(parent=search.parent, metrics=search.metrics, report={"objective_name": "min_overdue"})
    reused_screen = InsertionScreen(other_search, reference)
    assert reused_screen.search is other_search
    assert reused_screen.rows is screen.rows and reused_screen.due is screen.due and reused_screen.weights is screen.weights
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
    preparation = production_session(_scheduler(), operations=operations, batches=batches,
                                     graph_ready_context=context).native_preparation
    metrics = enrich_graph_ready_v2_metrics(
        context["node_metrics_by_op_id"], operations=operations, batches=batches,
        start_dt=START_DT, graph_ready_context=context, calendar_service=ContinuousCalendar(),
        downtime_map={}, seed_results=[], deadline=float("inf"), clock=lambda: 0.0,
        native_preparation=preparation,
    )
    assert metrics is not None
    rank ={op.id: metrics[op.id]["changeover_family_rank"] for op in operations if op.id in metrics}
    assert rank[operations[0].id] != rank[operations[1].id]
    assert {rank[op.id] for op in operations[2:] if op.id in rank} == {2}


def _same_content_decodes():
    """Separate resources make every priority order decode one schedule, enumerated in its own pick order."""
    from core.models.objective import target_objectives_for
    from core.services.scheduler.run.optimizer.multi_start import _evaluate_multi_start_candidate
    from core.services.scheduler.run.optimizer.shared_archive import SharedScheduleArchive
    from core.services.scheduler.run.optimizer.shared_budget import SharedSearchBudget
    from core.services.scheduler.run.optimizer.shared_decode import SharedDecodeSession

    operations, batches = graph_ready_benchmark_operations(), graph_ready_benchmark_batches()
    context = graph_ready_benchmark_context()
    for op in operations:
        op.machine_id, op.operator_id = f"M-{op.id}", f"O-{op.id}"
    targets = target_objectives_for("min_overdue")
    archive = SharedScheduleArchive("min_overdue", targets, [op.id for op in operations], batches)
    session = SharedDecodeSession(
        archive=archive, budget=SharedSearchBudget(clock=lambda: 0.0, started_at=0.0, deadline=10.0,
                                                   target_objectives=targets, configured_seconds=10),
        scheduler=_scheduler(), operations=operations, batches=batches, seed_results=[], downtime_map={},
        resource_pool=None, graph_ready_context=context, clock=lambda: 0.0, started_at=0.0, deadline=10.0,
    )
    metrics = enrich_graph_ready_v2_metrics(
        context["node_metrics_by_op_id"], operations=operations, batches=batches, start_dt=START_DT,
        seed_results=[], resource_pool=None, downtime_map={}, graph_ready_context=context,
        calendar_service=ContinuousCalendar(), deadline=float("inf"), clock=lambda: 0.0,
        native_preparation=session.native_preparation,
    )
    assert metrics is not None
    features = PreparedDecisionFeatures(metrics, build_v2_common_rank_cache(metrics),
                                        schedulable_ids=session.native_preparation.graph_topology().schedulable_ids)
    plain = _evaluate_multi_start_candidate(
        strategy=SortStrategy.PRIORITY_FIRST, params={}, start_dt=START_DT, end_date=None,
        order=list(reversed(batches)), dispatch_mode="batch_order", dispatch_rule="slack", resource_pool=None,
        objective_name="min_overdue", optimizer_algo_stats=None, readiness_gate_enabled=False,
        graph_ready_context=None, decode_session=session,
    )
    report = OptimizationSearchReportState(objective_name="min_overdue", started_at=0.0)
    pool = EliteRepairPool(
        limits=EliteRepairLimits(), objective_name="min_overdue", operations=operations, start_dt=START_DT,
        seed=0, best=plain, report_state=report, clock=lambda: 0.0, deadline=10.0,
        decode_session=session, decision_features=features,
    )
    profile = next(item for item in resolve_v2_profiles(seed=0, objective_name="min_overdue")
                   if item.slug == "v2_successor_edd")
    evaluate = partial(
        evaluate_graph_ready_candidate, strategy=SortStrategy.PRIORITY_FIRST, params={}, start_dt=START_DT,
        end_date=None, dispatch_rule="slack", resource_pool=None, objective_name="min_overdue",
        optimizer_algo_stats=None, readiness_gate_enabled=False, version=0, clock=lambda: 0.0,
        prepared_decision_features=features,
    )
    return SimpleNamespace(archive=archive, session=session, batches=batches, context=context, metrics=metrics,
                           plain=plain, report=report, pool=pool, profile=profile, evaluate=evaluate)


def test_same_content_parents_share_one_preparation_whatever_their_enumeration_order():
    case = _same_content_decodes()
    plain, pool = case.plain, case.pool
    graph = case.evaluate(profile=case.profile, order=list(case.batches), decode_session=case.session)
    # One content identity reached by an ordinary and a graph decode, each in its own native enumeration.
    assert schedule_content_key(plain["results"]) == schedule_content_key(graph["results"])
    assert plain["archive_ref"].entry_id is not None
    assert plain["archive_ref"].entry_id == graph["archive_ref"].entry_id
    assert [row.op_id for row in plain["results"]] != [row.op_id for row in graph["results"]]
    assert plain["results"] is not graph["results"]

    pool.observe(graph, case.profile, fingerprint=pool.fingerprint(graph))
    elite = pool.elites[0]
    assert elite["candidate"] is graph
    assert pool.prepare_parent(plain) is elite["prepared_parent"]
    assert len(pool._prepared_parents) == 1


def test_full_validation_keeps_its_own_enumeration_when_its_content_is_archived():
    """A resumed trial reaching archived content in another enumeration still validates bit for bit."""
    case = _same_content_decodes()
    plain, archive = case.plain, case.archive
    entry_id = plain["archive_ref"].entry_id
    parent = _parent_from_candidate(plain, prepared=case.pool.prepare_parent(plain))
    assert parent is not None
    search = _IteratedGreedySearch(
        limits=IteratedGreedyLimits(due_date_seed=False, checkpoint_count=3, max_decodes=20), parent=parent,
        profile=ig_decode_profile(case.profile), pool=case.pool, evaluate=case.evaluate,
        metrics_by_op_id=case.metrics, start_dt=START_DT, seed=0, deadline=10.0, clock=lambda: 0.0,
        report_state=case.report, report=new_iterated_greedy_report(objective_name="min_overdue"),
        decode_session=case.session,
    )
    search.best = plain
    reference = search._decode_entry((1, 2, 3, 4))
    assert reference is not None
    trial_order = (1, 3, 2, 4)
    resume = search.checkpoints.best_for(reference.checkpoints, base_order=reference.order, trial_order=trial_order)
    assert resume is not None and resume.prefix_length == 1
    trial = search._decode(trial_order, resume=resume)
    assert not trial["decode_receipt"]["verified"]
    # The resumed trial reaches the archived content, but enumerates it differently from the archived decode.
    archived = archive.results(entry_id)
    assert trial["archive_ref"].entry_id == entry_id
    assert schedule_content_key(trial["results"]) == schedule_content_key(archived)
    assert [row.op_id for row in trial["results"]] != [row.op_id for row in archived]

    search._remember_output(trial_order, trial)
    verified = search._decode_entry(trial_order)
    assert verified is not None
    assert verified.candidate["decode_receipt"]["execution_kind"] == "validation_decode"
    assert verified.candidate["archive_ref"].entry_id == entry_id
    assert verified.candidate["results"] is not archived
    assert [row.op_id for row in verified.candidate["results"]] == [row.op_id for row in trial["results"]]
    assert not search.pending_outputs
