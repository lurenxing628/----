"""Ordinary SGS graph priority pruning and score-cache boundary contracts on the certified native calendar."""

from datetime import timedelta
from types import MethodType
from typing import Any, Dict
from unittest.mock import patch

import pytest

from core.algorithm_contracts.types import OpForScheduleAlgo
from core.algorithm_runtime.calendar_timing_memo import native_timing_calendar
from core.algorithms.greedy import scheduler as scheduler_module
from core.algorithms.greedy.dispatch.sgs_graph import _prepare_graph_ready_state, graph_priority_key_map
from core.algorithms.greedy.dispatch.sgs_priority_frontier import make_priority_queue
from core.algorithms.greedy.dispatch.sgs_priority_pruning import GraphPriorityPruning
from core.errors import ValidationError
from tests._support.algo_operations import make_algo_op, make_batch
from tests._support.busy_block_case import BASE, native_calendar
from tests._support.schedule_decode import config_snapshot, production_decode_in_session, production_session


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


def _payload(rows, summary):
    fields = vars(summary).copy()
    fields.pop("duration_seconds")
    return [(r.op_id, r.machine_id, r.operator_id, r.start_time, r.end_time) for r in rows], fields


def _decode(calendar, case, *, cache_enabled):
    attach = scheduler_module.attach_sgs_score_cache if cache_enabled else (lambda *args, **kw: None)
    with patch.object(scheduler_module, "attach_sgs_score_cache", attach):
        scheduler = scheduler_module.GreedyScheduler(
            calendar_service=calendar,
            config_service=config_snapshot(auto_assign_enabled="no"),
        )
        session, decoded = production_decode_in_session(scheduler, **case)
    cache = session.native_preparation.run_context.sgs_score_cache
    return _payload(decoded.results, decoded.summary), (cache.stats() if cache is not None else {})


def _pruning(case, calendar):
    scheduler = scheduler_module.GreedyScheduler(
        calendar_service=calendar,
        config_service=config_snapshot(auto_assign_enabled="no"),
    )
    session = production_session(
        scheduler,
        operations=case["operations"],
        batches=case["batches"],
        graph_ready_context=case["graph_ready_context"],
    )
    preparation = session.native_preparation
    cache = preparation.score_cache_factory(None, auto_assign_enabled=False, resource_pool=None)
    ops_by_batch: Dict[str, list] = {}
    for op in case["operations"]:
        ops_by_batch.setdefault(op.batch_id, []).append(op)
    graph = _prepare_graph_ready_state(preparation.graph_ready_context, ops_by_batch=ops_by_batch)
    assert graph is not None
    pruning = GraphPriorityPruning.for_cache(cache, graph, case["batches"])
    assert pruning is not None
    return pruning, graph


@pytest.mark.parametrize("case_builder", [_saturated_case, _mixed_case])
def test_graph_decode_matches_cache_off_with_memo_and_pruning_on(case_builder):
    outputs = []
    for enabled in (False, True):
        with native_calendar() as calendar:
            outputs.append(_decode(calendar, case_builder(), cache_enabled=enabled))
    (expected, off), (actual, on) = outputs
    assert actual == expected
    assert actual[1]["failed_ops"] == 0 and actual[1]["scheduled_ops"] == 90
    assert not any(off.values())
    assert on["calendar_hits"] > 0 and on["graph_candidates_pruned"] > 0


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


def test_priority_pruning_requires_uniform_admitted_key_width():
    case = _saturated_case(batch_count=2, ops_per_batch=1)
    case["graph_ready_context"]["graph_priority_key_by_op_id"] = graph_priority_key_map(
        {1: (0.0,), 2: (1.0, 0.0)},
        schedulable_ids={1, 2},
    )
    with native_calendar() as calendar:
        pruning, _graph = _pruning(case, calendar)
    assert not pruning.supported


@pytest.mark.parametrize("invalid", [float("nan"), float("inf")])
def test_priority_key_admission_keeps_nonfinite_input_error(invalid):
    case = _saturated_case(batch_count=2, ops_per_batch=1)
    case["graph_ready_context"]["graph_priority_key_by_op_id"][1] = (invalid, 0.0)
    with native_calendar() as calendar, pytest.raises(ValidationError) as exc:
        _decode(calendar, case, cache_enabled=True)
    assert exc.value.field == "graph_ready_context"
    assert exc.value.message == "图评分 key 不能包含 NaN 或 Inf。"


def test_external_calendar_override_disables_both_narrowing_paths_without_disabling_internal_timing():
    with native_calendar() as calendar:
        pruning, graph = _pruning(_mixed_case(batch_count=50), calendar)
        assert pruning.supported and not pruning.fixed_resources and make_priority_queue(graph, pruning) is not None
        calendar.add_calendar_days = MethodType(lambda self, start, days: start + timedelta(days=days), calendar)
        assert native_timing_calendar(calendar) and not native_timing_calendar(calendar, include_calendar_days=True)
        pruning, graph = _pruning(_mixed_case(batch_count=50), calendar)
        internal, internal_graph = _pruning(_saturated_case(batch_count=50), calendar)
        assert internal.intact() and internal.fixed_resources and make_priority_queue(internal_graph, internal) is not None
        assert not pruning.supported and make_priority_queue(graph, pruning) is None
        assert pruning.frontier(list(graph["op_by_id"].values()), graph) is None


@pytest.mark.parametrize("merged", [False, True])
def test_out_of_range_external_duration_keeps_the_complete_path_and_the_calendar_error(merged):
    case = _saturated_case(batch_count=3, ops_per_batch=1)
    first = case["operations"][0]
    first.source = "external"
    if merged:
        first.ext_merge_mode, first.ext_group_id, first.ext_group_total_days = "merged", "G", 36501.0
    else:
        first.ext_days = 36501.0
    errors = []
    for enabled in (False, True):
        with native_calendar() as calendar:
            pruning, _ = _pruning(case, calendar)
            assert not pruning.supported
            with pytest.raises(ValidationError) as exc:
                _decode(calendar, case, cache_enabled=enabled)
            errors.append((exc.value.field, str(exc.value)))
    assert errors[0] == errors[1]
    assert errors[0][0] == "days"


def test_external_duration_descriptor_is_not_read_by_certification():
    calls = []

    class External(OpForScheduleAlgo):
        @property
        def ext_days(self):
            calls.append("duration")
            return 0.25

        @ext_days.setter
        def ext_days(self, value):
            pass

    case = _saturated_case(batch_count=2, ops_per_batch=1)
    first = case["operations"][0]
    fields: Dict[str, Any] = dict(vars(first), source="external")
    case["operations"][0] = External(**fields)
    with native_calendar() as calendar:
        pruning, _ = _pruning(case, calendar)
    assert not pruning.supported and calls == []


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
    for enabled in (False, True):
        with native_calendar() as calendar:
            payload, _ = _decode(calendar, case, cache_enabled=enabled)
            outputs.append(payload)
    assert outputs[0] == outputs[1]
    assert [row[0] for row in outputs[1][0]] == [internal.id]
    assert outputs[1][1]["failed_ops"] == 1
