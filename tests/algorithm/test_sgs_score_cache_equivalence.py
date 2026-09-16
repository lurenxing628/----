"""The SGS witness cache must reproduce full re-scoring exactly while skipping unchanged candidates."""

import random
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.algorithms.greedy import auto_assign as auto_assign_module
from core.algorithms.greedy import scheduler as scheduler_module
from core.algorithms.greedy.dispatch.sgs_score_cache import native_auto_assign_context, plain_record_class
from core.algorithms.greedy.run_context import ScheduleRunContext
from core.models.batch import Batch
from core.models.batch_operation import BatchOperation
from tests._support.busy_block_case import BASE as SQLITE_BASE
from tests._support.busy_block_case import native_calendar
from tests._support.sgs_slot_reuse_case import BASE, MemoryCalendar, make_case, make_scheduler


def _payload(rows, summary, strategy, params):
    fields = vars(summary).copy()
    fields.pop("duration_seconds")
    return [(r.op_id, r.machine_id, r.operator_id, r.start_time, r.end_time, r.source) for r in rows], fields, str(strategy), params


def _core(stats):
    """The witness and pair counters; calendar memo counters are covered by their own contract."""
    return {name: stats[name] for name in ("hits", "misses", "pair_hits", "pair_misses")}


def _run(kwargs, *, cache_enabled, scheduler_factory=make_scheduler):
    attach = scheduler_module.attach_sgs_score_cache if cache_enabled else (lambda *args, **kw: None)
    with patch.object(scheduler_module, "attach_sgs_score_cache", attach):
        scheduler = scheduler_factory()
        payload = _payload(*scheduler.schedule(**kwargs))
    return payload, scheduler._last_sgs_score_cache_stats


@pytest.mark.parametrize("auto", [False, True])
@pytest.mark.parametrize("graph", [False, True])
@pytest.mark.parametrize("window", [False, True])
def test_witness_cache_matches_full_rescoring_on_shared_workloads(auto, graph, window):
    expected, off = _run(make_case(24, 6, auto=auto, graph=graph, window=window), cache_enabled=False)
    actual, on = _run(make_case(24, 6, auto=auto, graph=graph, window=window), cache_enabled=True)
    assert actual == expected
    assert not any(off.values())
    assert on["hits"] > 0 and on["misses"] > 0
    assert (on["pair_hits"] > 0) is auto and (on["pair_misses"] > 0) is auto


def _piece_case():
    kwargs = make_case(12, 4, auto=False, graph=True)
    kwargs["graph_ready_context"]["piece_scope"] = True
    for op in kwargs["operations"]:
        op.piece_id = op.batch_id + "-P1"
    return kwargs


def test_piece_scope_matches_full_rescoring_and_ignores_batch_progress():
    expected, _ = _run(_piece_case(), cache_enabled=False)
    actual, stats = _run(_piece_case(), cache_enabled=True)
    assert actual == expected
    assert actual[1]["failed_ops"] == 0
    assert stats["hits"] > stats["misses"]


def _disjoint_case(count, *, machine=None, cls=BatchOperation):
    ops = [cls(id=i, op_code="OP" + str(i), batch_id="B" + str(i), seq=1, machine_id=machine or "M" + str(i),
               operator_id="O" + str(i), setup_hours=0.25, unit_hours=0.75, op_type_name="TURN") for i in range(1, count + 1)]
    batches = {op.batch_id: Batch(batch_id=op.batch_id, part_no="P", quantity=1, due_date="2026-09-30") for op in ops}
    return dict(operations=ops, batches=batches, start_dt=BASE, dispatch_mode="sgs", dispatch_rule="slack")


def test_only_candidates_reading_a_changed_cell_are_rescored():
    _, disjoint = _run(_disjoint_case(3), cache_enabled=True)
    assert _core(disjoint) == {"hits": 3, "misses": 3, "pair_hits": 0, "pair_misses": 0}
    kwargs = _disjoint_case(3)
    kwargs["operations"][1].machine_id = "M1"
    _, shared = _run(kwargs, cache_enabled=True)
    assert _core(shared) == {"hits": 2, "misses": 4, "pair_hits": 0, "pair_misses": 0}


def test_hooked_model_classes_are_scored_every_round():
    class Hooked(BatchOperation):
        def __getattribute__(self, name):
            return object.__getattribute__(self, name)

    assert plain_record_class(BatchOperation) and plain_record_class(SimpleNamespace)
    assert not plain_record_class(Hooked)
    expected, _ = _run(_disjoint_case(3), cache_enabled=True)
    actual, stats = _run(_disjoint_case(3, cls=Hooked), cache_enabled=True)
    assert actual == expected
    assert _core(stats) == {"hits": 0, "misses": 6, "pair_hits": 0, "pair_misses": 0}


def test_native_auto_assign_context_requires_untouched_scheduler_methods():
    class Custom(scheduler_module.GreedyScheduler):
        def _auto_assign_internal_resources_attempt(self, **kwargs):
            return super()._auto_assign_internal_resources_attempt(**kwargs)

    for scheduler_type, expected in ((scheduler_module.GreedyScheduler, True), (Custom, False),
                                     (type("Plain", (scheduler_module.GreedyScheduler,), {}), True)):
        scheduler = scheduler_type(MemoryCalendar())
        ctx = ScheduleRunContext.from_legacy_scheduler(scheduler)
        assert native_auto_assign_context(ctx, scheduler, scheduler_module.GreedyScheduler) is expected


def test_custom_auto_assign_callback_disables_auto_caching_but_keeps_results():
    class Custom(scheduler_module.GreedyScheduler):
        def _auto_assign_internal_resources_attempt(self, **kwargs):
            return super()._auto_assign_internal_resources_attempt(**kwargs)

    def custom_scheduler():
        return Custom(MemoryCalendar(), {"auto_assign_enabled": "yes"})

    expected, _ = _run(make_case(12, 4, auto=True), cache_enabled=False)
    actual, stats = _run(make_case(12, 4, auto=True), cache_enabled=True, scheduler_factory=custom_scheduler)
    assert actual == expected
    assert stats["hits"] == 0 and stats["misses"] > 0 and stats["pair_hits"] == stats["pair_misses"] == 0


def _probe(op, pool, **overrides):
    batch = SimpleNamespace(batch_id="B1", quantity=1, priority="normal", due_date=None, ready_date=None)
    kwargs = dict(calendar=MemoryCalendar(), op=op, batch=batch, batch_progress={}, machine_timeline={}, operator_timeline={},
                  base_time=BASE, end_dt_exclusive=None, machine_downtimes=None, resource_pool=pool, last_op_type_by_machine={},
                  machine_busy_hours={}, operator_busy_hours={}, probe_only=True)
    kwargs.update(overrides)
    return auto_assign_module.auto_assign_internal_resources_attempt(**kwargs)


def test_probe_reports_pair_ties_only_when_feasible_pairs_share_end_and_changeover():
    op = SimpleNamespace(id=1, batch_id="B1", seq=1, source="internal", machine_id="", operator_id="",
                         op_type_id="T", op_type_name="T", setup_hours=0.5, unit_hours=0.5)
    pool = {"machines_by_op_type": {"T": ["M1", "M2"]}, "operators_by_machine": {"M1": ["W1"], "M2": ["W2"]},
            "machines_by_operator": {}, "pair_rank": {}}
    idle = _probe(op, pool)
    assert idle.machine_id and idle.pair_tie_occurred is True
    busy = _probe(op, pool, machine_timeline={"M1": [(BASE, BASE + timedelta(hours=3))]})
    assert (busy.machine_id, busy.operator_id, busy.pair_tie_occurred) == ("M2", "W2", False)
    blocked = _probe(op, pool, end_dt_exclusive=BASE + timedelta(minutes=30))
    assert blocked.machine_id == "" and blocked.pair_tie_occurred is False


def test_eligible_resources_cover_exactly_the_pairs_the_probe_evaluates():
    op = SimpleNamespace(id=1, batch_id="B1", seq=1, source="internal", machine_id="", operator_id="",
                         op_type_id="T1", op_type_name="T1", setup_hours=0.5, unit_hours=0.5)
    pool = {"machines_by_op_type": {"T1": ["M1", "M2", "M3"], "T2": ["M4"]},
            "operators_by_machine": {"M1": ["W1", "W2"], "M2": ["W2"], "M3": ["W3", "W1"], "M4": ["W4"]},
            "machines_by_operator": {}, "pair_rank": {}}
    probed = []
    original = auto_assign_module._pair_score

    def spy(**kwargs):
        probed.append((kwargs["machine_id"], kwargs["operator_id"]))
        return original(**kwargs)

    with patch.object(auto_assign_module, "_pair_score", spy):
        assert not auto_assign_module.native_auto_assign_unchanged()
        _probe(op, pool)
    assert auto_assign_module.native_auto_assign_unchanged()
    machines, operators = auto_assign_module.eligible_auto_assign_resources(op, pool)
    assert set(machines) == {machine for machine, _ in probed} == {"M1", "M2", "M3"}
    assert set(operators) == {operator for _, operator in probed} == {"W1", "W2", "W3"}
    fixed_machine = SimpleNamespace(**{**vars(op), "machine_id": "M3"})
    assert auto_assign_module.eligible_auto_assign_resources(fixed_machine, pool) == (("M3",), ("W3", "W1"))
    assert auto_assign_module.eligible_auto_assign_resources(SimpleNamespace(**{**vars(op), "op_type_id": ""}), pool) is None


def _random_case(seed):
    rng = random.Random(seed)
    machines = ["M" + str(i) for i in range(rng.randint(2, 6))]
    operators = ["W" + str(i) for i in range(rng.randint(2, 6))]
    types = ["T" + str(i) for i in range(rng.randint(1, 3))]
    pool = {
        "machines_by_op_type": {t: rng.sample(machines, rng.randint(1, len(machines))) for t in types},
        "operators_by_machine": {m: rng.sample(operators, rng.randint(1, len(operators))) for m in machines},
        "machines_by_operator": {}, "pair_rank": {},
    }
    batches, operations, predecessors, successors = {}, [], {}, {}
    for b in range(rng.randint(3, 10)):
        bid = "B" + str(b)
        batches[bid] = SimpleNamespace(
            batch_id=bid, priority=rng.choice(["urgent", "normal", "normal"]),
            due_date=(BASE + timedelta(days=rng.randint(1, 12))).date(), ready_status="yes",
            ready_date=(BASE + timedelta(days=rng.randint(0, 2))).date().isoformat() if rng.random() < 0.3 else None,
            created_at=None, quantity=rng.randint(1, 4),
        )
        ops = []
        for seq in range(rng.randint(1, 4)):
            oid = len(operations) + 1
            op_type = rng.choice(types)
            machine, operator = "", ""
            if rng.random() < 0.5:
                machine = rng.choice(pool["machines_by_op_type"][op_type])
                operator = rng.choice(pool["operators_by_machine"][machine])
            elif rng.random() < 0.3:
                machine = rng.choice(pool["machines_by_op_type"][op_type])
            operations.append(SimpleNamespace(
                id=oid, op_code=bid + "_" + str(seq), batch_id=bid, seq=seq, source="internal", machine_id=machine,
                operator_id=operator, setup_hours=rng.choice([0.0, 0.25, 0.5, 1.0]), unit_hours=rng.choice([0.1, 0.3, 0.75, 1.5]),
                op_type_id=op_type, op_type_name="TYPE" + op_type,
            ))
            ops.append(oid)
        for index, oid in enumerate(ops):
            predecessors[oid] = [ops[index - 1]] if index else []
            successors[oid] = [ops[index + 1]] if index + 1 < len(ops) else []
    downtimes = {m: [(BASE + timedelta(days=d, hours=1), BASE + timedelta(days=d, hours=2))] for m in machines for d in (0, 3) if rng.random() < 0.4}
    kwargs = dict(operations=operations, batches=batches, start_dt=BASE, dispatch_mode="sgs",
                  dispatch_rule=rng.choice(["slack", "cr", "atc"]), resource_pool=pool, machine_downtimes=downtimes or None,
                  end_date=(BASE + timedelta(days=rng.randint(2, 6))).date().isoformat() if rng.random() < 0.3 else None)
    if rng.random() < 0.5:
        kwargs["graph_ready_context"] = {
            "enabled": True, "schedulable_op_ids": list(predecessors),
            "predecessor_op_ids_by_op_id": predecessors, "successor_op_ids_by_op_id": successors,
            "fixed_op_ids": [], "score_enabled": rng.random() < 0.5,
            "sort_key_by_op_id": {op.id: (int(op.batch_id[1:]), op.seq, op.id) for op in operations},
            "graph_priority_key_by_op_id": {op.id: (float(op.id % 4), float(op.seq)) for op in operations},
        }
    return kwargs


@pytest.mark.parametrize("seed", range(16))
def test_random_mixed_workloads_match_full_rescoring(seed):
    expected, _ = _run(_random_case(seed), cache_enabled=False)
    actual, stats = _run(_random_case(seed), cache_enabled=True)
    assert actual == expected
    assert stats["misses"] > 0


def test_sqlite_calendar_run_matches_with_certificate_reuse_and_witness_cache_together():
    def sqlite_case():
        ops = [BatchOperation(id=i, op_code="OP" + str(i), batch_id="B" + str(i % 4), seq=i // 4, machine_id="M" + str(i % 3),
                              operator_id="O1", setup_hours=0.25, unit_hours=0.5, op_type_name="TURN") for i in range(1, 13)]
        batches = {"B" + str(b): Batch(batch_id="B" + str(b), part_no="P", quantity=1, due_date="2026-09-30") for b in range(4)}
        return dict(operations=ops, batches=batches, start_dt=SQLITE_BASE, dispatch_mode="sgs", dispatch_rule="cr")

    with native_calendar() as calendar:
        expected, _ = _run(sqlite_case(), cache_enabled=False, scheduler_factory=lambda: scheduler_module.GreedyScheduler(calendar))
        actual, stats = _run(sqlite_case(), cache_enabled=True, scheduler_factory=lambda: scheduler_module.GreedyScheduler(calendar))
    assert actual == expected
    assert actual[1]["failed_ops"] == 0 and stats["misses"] > 0
