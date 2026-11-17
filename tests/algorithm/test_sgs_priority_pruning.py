"""Ordinary SGS graph priority pruning and score-cache boundary contracts on the certified native calendar."""

from contextlib import ExitStack, contextmanager
from datetime import timedelta
from typing import Any, Dict
from unittest.mock import patch

import pytest

from core.algorithm_contracts.resource_pool import DISABLED_RESOURCE_POOL
from core.algorithm_runtime.calendar_timing_memo import MemoizedTimingCalendar
from core.algorithm_runtime.run_state import ScheduleRunState
from core.algorithms.greedy import scheduler as scheduler_module
from core.algorithms.greedy.dispatch.sgs_graph import graph_priority_key_map, prepare_graph_ready_state
from core.algorithms.greedy.dispatch.sgs_priority_pruning import GraphPriorityPruning
from core.algorithms.greedy.dispatch.sgs_score_cache import SgsScoreCache
from core.errors import ValidationError
from core.services.scheduler.calendar.engine import CalendarEngine
from tests._support.algo_operations import make_algo_op, make_batch
from tests._support.busy_block_case import BASE, native_calendar
from tests._support.schedule_decode import config_snapshot, production_decode_in_session, required_hours_by_op_id


def _saturated_case(batch_count: int = 30, ops_per_batch: int = 3) -> Dict[str, Any]:
    machines, operators = ["M1", "M2", "M3"], ["O1", "O2"]
    batches, operations, predecessors, successors = {}, [], {}, {}
    for b in range(batch_count):
        bid = f"B{b:03d}"
        batches[bid] = make_batch(
            batch_id=bid,
            priority="urgent" if b % 4 == 0 else "normal",
            due_date=(BASE + timedelta(days=2 + b % 9)).date(),
            quantity=1 + b % 3,
        )
        for seq in range(ops_per_batch):
            oid = b * ops_per_batch + seq + 1
            operations.append(
                make_algo_op(
                    id=oid,
                    op_code=f"{bid}_{seq}",
                    batch_id=bid,
                    seq=seq,
                    machine_id=machines[(b + seq) % 3],
                    operator_id=operators[(b + 2 * seq) % 2],
                    setup_hours=0.25 * (1 + oid % 3),
                    unit_hours=0.2 + 0.1 * (oid % 4),
                    op_type_id=f"T{oid % 2}",
                    op_type_name=f"TYPE{oid % 2}",
                )
            )
            predecessors[oid] = [oid - 1] if seq else []
            successors[oid] = [oid + 1] if seq + 1 < ops_per_batch else []
    context = {
        "enabled": True,
        "schedulable_op_ids": list(predecessors),
        "fixed_op_ids": [],
        "score_enabled": True,
        "predecessor_op_ids_by_op_id": predecessors,
        "successor_op_ids_by_op_id": successors,
        "sort_key_by_op_id": {op.id: ((op.id - 1) // ops_per_batch, op.seq, op.id) for op in operations},
        "graph_priority_key_by_op_id": {op.id: (float((op.id * 7) % 11), float(op.id)) for op in operations},
    }
    return dict(
        operations=operations,
        batches=batches,
        start_dt=BASE,
        dispatch_mode="sgs",
        dispatch_rule="atc",
        graph_ready_context=context,
    )


def _mixed_case(batch_count: int = 30) -> Dict[str, Any]:
    case = _saturated_case(batch_count=batch_count)
    for index, op in enumerate(case["operations"]):
        batch_index, seq = divmod(index, 3)
        if seq == 1 or (seq == 2 and batch_index % 3 == 0):
            op.source, op.machine_id, op.operator_id = "external", None, None
            op.ext_days = 0.25
            if batch_index % 3 == 0:
                op.ext_merge_mode, op.ext_group_id, op.ext_days = "merged", "supplier-group", None
                op.ext_group_total_days = 0.5
    return case


def _single_resource_case(batch_count: int = 48) -> Dict[str, Any]:
    """Every ready operation waits for the same machine and operator: a saturated fixed-resource decode."""
    batches = {f"B{index:03d}": make_batch(batch_id=f"B{index:03d}", priority="normal", quantity=1,
                                           due_date=(BASE + timedelta(days=10)).date())
               for index in range(batch_count)}
    operations = [make_algo_op(id=index + 1, op_code=f"OP{index:03d}", batch_id=f"B{index:03d}",
                               machine_id="M1", operator_id="O1", setup_hours=1.0, unit_hours=0.0,
                               op_type_id="T1", op_type_name="T1")
                  for index in range(batch_count)]
    return dict(operations=operations, batches=batches, start_dt=BASE, dispatch_mode="sgs", dispatch_rule="slack")


def _payload(rows, summary):
    fields = vars(summary).copy()
    fields.pop("duration_seconds")
    return [(r.op_id, r.machine_id, r.operator_id, r.start_time, r.end_time) for r in rows], fields


class _FullScoringCache(SgsScoreCache):
    """Reference decode: every candidate and slot is scored from scratch on the raw calendar, nothing is pruned.

    Without the memoized timing surface ``GraphPriorityPruning.for_cache`` declines, so every ready
    operation is scored; no key, pair or shared-slot memo is ever consulted.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.timing = None

    def resolve(self, op, batch_id, graph_state, score):
        return score()

    def scoring_slot_estimate(self, *, compute, **_inputs):
        return compute()

    def pair_estimate(self, **_inputs):
        return None


_TIMING_METHODS = ("adjust_to_working_time", "add_effective_hours", "working_hours_between",
                   "certified_slot_window", "get_efficiency")


@contextmanager
def _memo_answers():
    """Count memoized timing calls answered without asking the native calendar."""
    asked, answered = [0], [0]
    with ExitStack() as stack:
        for name in _TIMING_METHODS:
            def ask(*args, _native=getattr(CalendarEngine, name), **kwargs):
                asked[0] += 1
                return _native(*args, **kwargs)

            def memo(*args, _memoized=getattr(MemoizedTimingCalendar, name), **kwargs):
                before = asked[0]
                value = _memoized(*args, **kwargs)
                answered[0] += asked[0] == before
                return value

            stack.enter_context(patch.object(CalendarEngine, name, autospec=True, side_effect=ask))
            stack.enter_context(patch.object(MemoizedTimingCalendar, name, autospec=True, side_effect=memo))
        yield answered


def _decode(calendar, case, *, cache_type=SgsScoreCache):
    with patch.object(SgsScoreCache, "for_preparation", side_effect=cache_type.for_preparation):
        scheduler = scheduler_module.GreedyScheduler(
            calendar_service=calendar,
            config_service=config_snapshot(auto_assign_enabled="no"),
        )
        _session, decoded = production_decode_in_session(scheduler, **case)
    return _payload(decoded.results, decoded.summary)


def _pruning(case, calendar):
    scheduler = scheduler_module.GreedyScheduler(
        calendar_service=calendar,
        config_service=config_snapshot(auto_assign_enabled="no"),
    )
    preparation = scheduler_module.prepare_native_schedule_inputs(
        {}, scheduler=scheduler, operations=case["operations"], batches=case["batches"],
        required_hours_by_op_id=required_hours_by_op_id(case["operations"], case["batches"]), seed_results=[],
        resource_pool=DISABLED_RESOURCE_POOL, graph_ready_context=case["graph_ready_context"],
    )
    cache = SgsScoreCache.for_preparation(preparation, state=ScheduleRunState(base_time=BASE))
    ops_by_batch: Dict[str, list] = {}
    for op in case["operations"]:
        ops_by_batch.setdefault(op.batch_id, []).append(op)
    # The same request context a decode receives: the run's graph input with this request's admitted keys.
    topology = preparation.graph_topology()
    context = case["graph_ready_context"]
    request = dict(context, score_enabled=True, graph_priority_key_by_op_id=graph_priority_key_map(
        context["graph_priority_key_by_op_id"], schedulable_ids=topology.schedulable_ids))
    graph = prepare_graph_ready_state(topology, request, ops_by_batch=ops_by_batch, skip_initial_frontier=False)
    pruning = GraphPriorityPruning.for_cache(cache, graph)
    assert pruning is not None
    return pruning, graph


@pytest.mark.parametrize("case_builder", [_saturated_case, _mixed_case])
def test_graph_decode_with_memo_and_pruning_matches_full_scoring(case_builder):
    outputs, resolved, memo_answered = [], [], []
    for cache_type in (_FullScoringCache, SgsScoreCache):
        with native_calendar() as calendar, _memo_answers() as answered, \
                patch.object(cache_type, "resolve", autospec=True, side_effect=cache_type.resolve) as resolve:
            outputs.append(_decode(calendar, case_builder(), cache_type=cache_type))
        resolved.append(resolve.call_count)
        memo_answered.append(answered[0])
    expected, actual = outputs
    assert actual == expected
    assert actual[1]["failed_ops"] == 0 and actual[1]["scheduled_ops"] == 90
    # The reference resolves every ready operation on the raw calendar; production prunes later
    # graph-key groups and answers repeated timing questions from the memo.
    assert 0 < resolved[1] < resolved[0]
    assert memo_answered[0] == 0 and memo_answered[1] > 0


def test_saturated_fixed_resources_retire_key_reuse_and_stay_exact():
    retirements = []
    advance = SgsScoreCache.next_round

    def observed_round(cache):
        reusing = cache._reuse_keys
        advance(cache)
        if reusing and not cache._reuse_keys:
            retirements.append((cache.round, cache._shared_slots.hits))

    outputs = []
    for cache_type in (_FullScoringCache, SgsScoreCache):
        with native_calendar() as calendar, \
                patch.object(SgsScoreCache, "next_round", autospec=True, side_effect=observed_round):
            outputs.append(_decode(calendar, _single_resource_case(), cache_type=cache_type))
    assert outputs[0] == outputs[1]
    assert outputs[1][1]["failed_ops"] == 0 and outputs[1][1]["scheduled_ops"] == 48
    # No key is ever reused on one shared resource; shared-slot answers accumulated over the
    # whole decode retire key reuse at the first eligible round, in production only.
    assert [round_index for round_index, _hits in retirements] == [8]
    assert retirements[0][1] >= 256


def test_priority_pruning_selects_lowest_admitted_key_group_and_rejects_missing_keys_at_admission():
    case = _saturated_case(batch_count=4, ops_per_batch=1)
    keys: Any = {op.id: (float((op.id - 1) // 2), 0.0) for op in case["operations"]}
    case["graph_ready_context"]["graph_priority_key_by_op_id"] = keys

    with native_calendar() as calendar:
        pruning, graph = _pruning(case, calendar)
        candidates = list(graph["op_by_id"].values())
        assert pruning.supported
        frontiers = [pruning.frontier(candidates[index:], graph) for index in (0, 1)]
        assert all(frontier is not None for frontier in frontiers)
        assert [[op.id for _batch, op in (frontier or ())] for frontier in frontiers] == [
            [1, 2],
            [2],
        ]
        missing = dict(keys)
        missing.pop(1)
        with pytest.raises(ValidationError) as exc:
            graph_priority_key_map(missing, schedulable_ids=set(keys))
        assert exc.value.field == "graph_ready_context"


def test_priority_key_admission_rejects_mixed_widths_and_yields_static_orders():
    admitted = graph_priority_key_map({3: (1.0, 0.0), 1: (0.0, 5.0), 2: (1.0, 0.0)}, schedulable_ids=frozenset({1, 2, 3}))
    assert admitted.order == (1, 2, 3) and admitted.preorder == ((1,), (2, 3))
    assert graph_priority_key_map(admitted, schedulable_ids=admitted.schedulable_ids) is admitted
    case = _saturated_case(batch_count=2, ops_per_batch=1)
    case["graph_ready_context"]["graph_priority_key_by_op_id"] = {1: (0.0,), 2: (1.0, 0.0)}
    with native_calendar() as calendar, pytest.raises(ValidationError) as exc:
        _decode(calendar, case)
    assert exc.value.field == "graph_ready_context"
    assert exc.value.message == "图评分 key 长度必须一致。"


@pytest.mark.parametrize("invalid", [float("nan"), float("inf")])
def test_priority_key_admission_keeps_nonfinite_input_error(invalid):
    case = _saturated_case(batch_count=2, ops_per_batch=1)
    case["graph_ready_context"]["graph_priority_key_by_op_id"][1] = (invalid, 0.0)
    with native_calendar() as calendar, pytest.raises(ValidationError) as exc:
        _decode(calendar, case)
    assert exc.value.field == "graph_ready_context"
    assert exc.value.message == "图评分 key 不能包含 NaN 或 Inf。"


def test_blocked_lowest_external_group_still_scores_the_other_ready_operations():
    case = _saturated_case(batch_count=2, ops_per_batch=1)
    external, internal = case["operations"]
    external.source, external.ext_days = "external", 2.0
    case["end_date"] = BASE.date()
    case["graph_ready_context"]["graph_priority_key_by_op_id"] = {
        external.id: (0.0, 0.0),
        internal.id: (1.0, 0.0),
    }
    outputs = []
    for cache_type in (_FullScoringCache, SgsScoreCache):
        with native_calendar() as calendar:
            outputs.append(_decode(calendar, case, cache_type=cache_type))
    assert outputs[0] == outputs[1]
    assert [row[0] for row in outputs[1][0]] == [internal.id]
    assert outputs[1][1]["failed_ops"] == 1
