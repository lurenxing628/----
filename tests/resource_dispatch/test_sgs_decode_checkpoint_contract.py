"""Decode checkpoints: a graph-mode SGS decode resumed after k picks equals the full decode bit for bit.

The contract is the equivalence proof behind trial acceleration in the graph phase: checkpoints are
taken during a complete decode, a resumed decode must reproduce the full decode of any order that
keeps the checkpoint's required prefix, and every other reuse fails loudly. Real production inputs
(shift calendar, downtime, shared operators, resource pool with auto-assign, frozen seed, readiness
gate, external operation) come from the end-to-end fixtures.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

import pytest

from core.algorithm_contracts.types import ScheduleResult
from core.algorithm_runtime.checkpoint_calendar import checkpoint_calendar_signature
from core.algorithms import GreedyScheduler, SortStrategy
from core.algorithms.greedy.dispatch import sgs as sgs_module
from core.algorithms.greedy.dispatch.sgs_checkpoint import (
    DecodeCheckpoint,
    DecodeCheckpointRequest,
    decode_output_digest,
)
from core.infrastructure.errors import ValidationError
from core.services.scheduler.run.schedule_graph_report import prepare_schedule_graph_for_dispatch
from tests._support.optimizer_end_to_end_cases import case_environment, fixture_data

RUN_CONFIG = {"seed": 0, "time_budget_seconds": 1}


class _Case:
    def __init__(self, schedule_input: Any) -> None:
        # The candidate runner supplies graph weights per candidate; one weighted config stands in here.
        values = dict(vars(schedule_input.cfg))
        values.update(graph_analysis_mode="on", graph_critical_weight=1, graph_impact_weight=1, graph_downstream_weight=1)
        schedule_input.cfg = SimpleNamespace(**values)
        self.input = schedule_input
        self.scheduler = GreedyScheduler(calendar_service=schedule_input.cal_svc, config_service=schedule_input.cfg)
        preparation = prepare_schedule_graph_for_dispatch(schedule_input)
        self.context = preparation.graph_ready_context
        assert isinstance(self.context, dict) and self.context.get("enabled"), "fixture must produce a graph context"
        self.operations = list(schedule_input.algo_ops_to_schedule)
        self.seeds = [ScheduleResult(**{key: row[key] for key in (
            "op_id", "op_code", "batch_id", "seq", "source", "machine_id", "operator_id", "op_type_name",
            "start_time", "end_time")}) for row in schedule_input.seed_results]
        self.predecessors = {int(op_id): set(ids) for op_id, ids in self.context["predecessor_op_ids_by_op_id"].items()}

    def base_order(self) -> Tuple[int, ...]:
        # Batch-major, sequence-minor: topological for every fixture chain.
        return tuple(int(op.id) for op in sorted(self.operations, key=lambda op: (str(op.batch_id), int(op.seq), int(op.id))))

    def context_for(self, order: Tuple[int, ...]) -> Dict[str, Any]:
        context = dict(self.context)
        context["score_enabled"] = True
        context["graph_priority_key_by_op_id"] = {op_id: (float(rank),) for rank, op_id in enumerate(order)}
        return context

    def decode(self, order: Tuple[int, ...], *, seeds: Optional[List[ScheduleResult]] = None,
               resume: Optional[DecodeCheckpoint] = None, checkpoints: Optional[DecodeCheckpointRequest] = None,
               dispatch_mode: str = "sgs", dispatch_rule: str = "slack", graph: bool = True) -> Tuple[List[ScheduleResult], Any, str]:
        results, summary, _strategy, _params = self.scheduler.schedule(
            operations=self.operations, batches=self.input.batches, strategy=SortStrategy.PRIORITY_FIRST,
            start_dt=self.input.start_dt_norm, end_date=None, machine_downtimes=self.input.downtime_map,
            seed_results=self.seeds if seeds is None else seeds, dispatch_mode=dispatch_mode, dispatch_rule=dispatch_rule,
            resource_pool=self.input.resource_pool, readiness_gate_enabled=bool(self.input.readiness_gate_enabled),
            strict_mode=True, graph_ready_context=self.context_for(order) if graph else None,
            decode_resume=resume, decode_checkpoints=checkpoints,
        )
        return results, summary, decode_output_digest(results, summary)

    def independent_adjacent_pairs(self, order: Tuple[int, ...], *, start: int) -> List[int]:
        """Positions i >= start where order[i] and order[i + 1] have no precedence between them."""
        positions = []
        for index in range(start, len(order) - 1):
            first, second = order[index], order[index + 1]
            if first not in self.predecessors[second] and second not in self.predecessors[first]:
                positions.append(index)
        return positions


@pytest.fixture(params=["frozen_ready_external", "shift_pool"])
def case(request):
    data = fixture_data(request.param)
    with case_environment(data, "min_tardiness", RUN_CONFIG) as schedule_input:
        yield _Case(schedule_input)


def _capture(case: _Case, order: Tuple[int, ...], positions) -> Tuple[List[DecodeCheckpoint], str]:
    captured: List[DecodeCheckpoint] = []
    request = DecodeCheckpointRequest(positions, captured.append)
    _results, _summary, digest = case.decode(order, checkpoints=request)
    assert request.captured == len(captured) == len(set(positions))
    return sorted(captured, key=lambda item: item.position), digest


def _count_picks(monkeypatch) -> List[int]:
    counts = [0]
    original = sgs_module._dispatch_selected

    def counting(*args, **kwargs):
        counts[0] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(sgs_module, "_dispatch_selected", counting)
    return counts


def test_resuming_the_same_order_reproduces_the_full_decode_from_every_checkpoint(case, monkeypatch):
    order = case.base_order()
    size = len(order)
    positions = sorted({1, 2, size // 3, size // 2, size - 1})
    checkpoints, full_digest = _capture(case, order, positions)
    assert [item.position for item in checkpoints] == positions
    counts = _count_picks(monkeypatch)
    for checkpoint in checkpoints:
        assert checkpoint.picked_op_ids == order[: checkpoint.position]
        assert checkpoint.prefix_op_ids == order[: checkpoint.position]
        for _repeat in range(2):  # the checkpoint itself is never consumed by a resume
            counts[0] = 0
            _results, summary, digest = case.decode(order, resume=checkpoint)
            assert digest == full_digest
            assert counts[0] == size - checkpoint.position
            assert summary.scheduled_ops + summary.failed_ops == summary.total_ops


def test_resume_is_exact_for_orders_that_only_change_after_the_required_prefix(case, monkeypatch):
    order = case.base_order()
    size = len(order)
    checkpoints, _digest = _capture(case, order, [size // 3])
    checkpoint = checkpoints[0]
    swaps = case.independent_adjacent_pairs(order, start=checkpoint.prefix_length)
    assert swaps, "fixture needs an independent adjacent pair after the prefix"
    counts = _count_picks(monkeypatch)
    for index in swaps[:3]:
        changed = list(order)
        changed[index], changed[index + 1] = changed[index + 1], changed[index]
        changed = tuple(changed)
        counts[0] = 0
        _results, _summary, full_digest = case.decode(changed)
        assert counts[0] == size
        counts[0] = 0
        _results, _summary, resumed_digest = case.decode(changed, resume=checkpoint)
        assert resumed_digest == full_digest
        assert counts[0] == size - checkpoint.position


def test_resume_rejects_an_order_that_changes_the_prefix(case):
    order = case.base_order()
    checkpoints, _digest = _capture(case, order, [len(order) // 2])
    checkpoint = checkpoints[0]
    swaps = case.independent_adjacent_pairs(order, start=0)
    inside = [index for index in swaps if index + 1 < checkpoint.prefix_length]
    assert inside, "fixture needs an independent adjacent pair inside the prefix"
    changed = list(order)
    changed[inside[0]], changed[inside[0] + 1] = changed[inside[0] + 1], changed[inside[0]]
    with pytest.raises(ValidationError) as excinfo:
        case.decode(tuple(changed), resume=checkpoint)
    assert excinfo.value.field == "decode_checkpoint"
    assert excinfo.value.details["reason"] == "decode_checkpoint_prefix_mismatch"


def test_resume_rejects_different_decode_inputs(case):
    order = case.base_order()
    checkpoints, _digest = _capture(case, order, [2])
    checkpoint = checkpoints[0]
    # Same order, one other input changed: the frozen seed is dropped, or the dispatch rule differs.
    variant = {"seeds": []} if case.seeds else {"dispatch_rule": "cr"}
    with pytest.raises(ValidationError) as excinfo:
        case.decode(order, resume=checkpoint, **variant)
    assert excinfo.value.details["reason"] == "decode_checkpoint_signature_mismatch"


def test_checkpoints_require_graph_mode_sgs_and_valid_positions(case):
    order = case.base_order()
    request = DecodeCheckpointRequest([1], lambda item: None)
    with pytest.raises(ValidationError) as excinfo:
        case.decode(order, checkpoints=request, graph=False)
    assert excinfo.value.details["reason"] == "decode_checkpoint_requires_graph_mode"
    with pytest.raises(ValidationError) as excinfo:
        case.decode(order, checkpoints=request, dispatch_mode="batch_order", graph=False)
    assert excinfo.value.details["reason"] == "decode_checkpoint_requires_graph_mode"
    for bad in ([], [0], [-1], [True], [1.5]):
        with pytest.raises(ValidationError) as excinfo:
            DecodeCheckpointRequest(bad, lambda item: None)
        assert excinfo.value.details["reason"] == "decode_checkpoint_bad_position"
    with pytest.raises(ValidationError) as excinfo:
        DecodeCheckpointRequest([1], None)  # type: ignore[arg-type]
    assert excinfo.value.details["reason"] == "decode_checkpoint_bad_sink"


def test_checkpoint_state_is_independent_of_the_decode_that_produced_it(case):
    order = case.base_order()
    checkpoints, _digest = _capture(case, order, [3])
    checkpoint = checkpoints[0]
    assert len(checkpoint.state.results) == 3 + len(case.seeds)
    snapshot_rows = list(checkpoint.state.results)
    snapshot_progress = dict(checkpoint.state.batch_progress)
    case.decode(order, resume=checkpoint)
    assert list(checkpoint.state.results) == snapshot_rows
    assert dict(checkpoint.state.batch_progress) == snapshot_progress
    assert checkpoint.graph_progress["completed_or_fixed_op_ids"] >= set(order[:3])


@pytest.mark.parametrize("field,value", [
    ("ready_date", "2026-01-15"), ("quantity", 2), ("priority", "critical"), ("due_date", "2026-02-15"),
])
def test_resume_rejects_changed_batch_semantics_even_when_batch_ids_are_unchanged(case, field, value):
    order = case.base_order()
    checkpoints, _digest = _capture(case, order, [3])
    batch = case.input.batches["B01"]
    setattr(batch, field, value)
    with pytest.raises(ValidationError) as excinfo:
        case.decode(order, resume=checkpoints[0])
    assert excinfo.value.field == "decode_checkpoint"
    assert excinfo.value.details["reason"] == "decode_checkpoint_signature_mismatch"


def test_checkpoint_input_evidence_rejects_unknown_values_without_calling_repr(case):
    class UnknownValue:
        def __repr__(self):
            pytest.fail("an object repr cannot certify checkpoint input semantics")

    case.input.batches["B01"].unknown_value = UnknownValue()
    with pytest.raises(ValidationError) as excinfo:
        _capture(case, case.base_order(), [3])
    assert excinfo.value.details["reason"] == "decode_checkpoint_unsupported_input"
    assert excinfo.value.details["input_field"] == "batches"


@pytest.mark.parametrize("change", ["global", "personal", "shift_profile", "shift_day", "operator_profile"])
def test_resume_rejects_changes_to_every_calendar_business_source(case, change):
    calendar = case.input.cal_svc
    conn = calendar.conn
    conn.execute("INSERT INTO Operators(operator_id,name) VALUES('O0','O0')")
    conn.execute("INSERT INTO WorkbenchShiftProfiles(profile_id,name,anchor_date,cycle_days) VALUES('P','P','2026-01-05',1)")
    conn.execute("INSERT INTO WorkbenchShiftPatternDays VALUES('P',0,0,'08:00','16:00')")
    conn.execute("INSERT INTO WorkbenchOperatorProfiles(operator_id,shift_profile_id) VALUES('O0','P')")
    conn.commit()
    calendar._engine.clear_policy_cache()
    order = case.base_order()
    checkpoints, _digest = _capture(case, order, [3])
    edits = {
        "global": "UPDATE WorkCalendar SET efficiency=0.5 WHERE date='2026-01-05'",
        "personal": "INSERT INTO OperatorCalendar(operator_id,date,shift_start,shift_end) VALUES('O0','2026-01-05','09:00','17:00')",
        "shift_profile": "UPDATE WorkbenchShiftProfiles SET status='inactive' WHERE profile_id='P'",
        "shift_day": "UPDATE WorkbenchShiftPatternDays SET shift_start='09:00',shift_end='17:00' WHERE profile_id='P'",
        "operator_profile": "UPDATE WorkbenchOperatorProfiles SET shift_profile_id=NULL WHERE operator_id='O0'",
    }
    conn.execute(edits[change])
    conn.commit()
    calendar._engine.clear_policy_cache()
    with pytest.raises(ValidationError) as excinfo:
        case.decode(order, resume=checkpoints[0])
    assert excinfo.value.details["reason"] == "decode_checkpoint_signature_mismatch"


@pytest.mark.parametrize("read_only", [False, True])
def test_calendar_cache_population_does_not_change_signature_or_rescan_business_tables(case, read_only):
    calendar = case.input.cal_svc
    conn = calendar.conn
    if read_only:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
    signature = checkpoint_calendar_signature(calendar)
    calendar._engine._policy_for_date("2026-03-05", operator_id="O0")
    queries = []
    conn.set_trace_callback(queries.append)
    try:
        assert checkpoint_calendar_signature(calendar) == signature
        calendar._engine.clear_policy_cache()
        assert checkpoint_calendar_signature(calendar) == signature
    finally:
        conn.set_trace_callback(None)
    assert queries and all(query.startswith("PRAGMA ") for query in queries)
    assert len(queries) == 8  # Two certificate calls, each with four O(1) metadata reads.


def test_calendar_content_restored_after_writes_still_reproduces_the_checkpoint(case):
    order = case.base_order()
    checkpoints, full_digest = _capture(case, order, [3])
    conn = case.input.cal_svc.conn
    conn.execute("UPDATE WorkCalendar SET efficiency=0.5")
    conn.execute("UPDATE WorkCalendar SET efficiency=1.0")
    conn.commit()
    case.input.cal_svc._engine.clear_policy_cache()
    _results, _summary, digest = case.decode(order, resume=checkpoints[0])
    assert digest == full_digest


def test_writable_transaction_signature_does_not_survive_rollback_and_begin(case):
    calendar = case.input.cal_svc
    conn = calendar.conn
    conn.execute("UPDATE WorkCalendar SET efficiency=0.5")
    calendar._engine.clear_policy_cache()
    order = case.base_order()
    checkpoints, _digest = _capture(case, order, [3])
    changes = conn.total_changes
    conn.rollback()
    conn.execute("BEGIN")
    assert conn.total_changes == changes and conn.in_transaction
    calendar._engine.clear_policy_cache()
    with pytest.raises(ValidationError) as excinfo:
        case.decode(order, resume=checkpoints[0])
    assert excinfo.value.details["reason"] == "decode_checkpoint_signature_mismatch"


@pytest.mark.parametrize("temporary", [False, True])
def test_calendar_ddl_cannot_reuse_a_signature_just_because_total_changes_is_unchanged(case, temporary):
    order = case.base_order()
    checkpoints, _digest = _capture(case, order, [3])
    conn = case.input.cal_svc.conn
    changes = conn.total_changes
    columns = "date,day_type,shift_start,shift_end,shift_hours,efficiency*0.5 AS efficiency,allow_normal,allow_urgent,remark"
    if temporary:
        conn.execute("CREATE TEMP VIEW WorkCalendar AS SELECT " + columns + " FROM main.WorkCalendar")
    else:
        conn.execute("ALTER TABLE WorkCalendar RENAME TO OriginalWorkCalendar")
        conn.execute("CREATE VIEW WorkCalendar AS SELECT " + columns + " FROM OriginalWorkCalendar")
    assert conn.total_changes == changes
    with pytest.raises(ValidationError) as excinfo:
        case.decode(order, resume=checkpoints[0])
    assert excinfo.value.details["reason"] == "decode_checkpoint_signature_mismatch"


def test_unknown_calendar_remains_usable_for_full_decode_but_cannot_capture_checkpoints(case):
    from core.services.scheduler.calendar_service import CalendarService

    class UncertifiedCalendar(CalendarService):
        pass

    case.scheduler.calendar = UncertifiedCalendar(case.input.cal_svc.conn)
    _results, summary, _digest = case.decode(case.base_order())
    assert summary.success
    with pytest.raises(ValidationError) as excinfo:
        _capture(case, case.base_order(), [3])
    assert excinfo.value.details["reason"] == "decode_checkpoint_unsupported_calendar"


def test_execution_release_floors_are_bound_along_with_the_underlying_calendar(case):
    from datetime import timedelta

    from core.services.scheduler.run.schedule_execution_reservations import ExecutionResourceCalendar

    calendar = ExecutionResourceCalendar(case.input.cal_svc, [])
    case.scheduler.calendar = calendar
    order = case.base_order()
    checkpoints, _digest = _capture(case, order, [3])
    calendar._release_by_operator["O0"] = case.input.start_dt_norm + timedelta(days=10)
    with pytest.raises(ValidationError) as excinfo:
        case.decode(order, resume=checkpoints[0])
    assert excinfo.value.details["reason"] == "decode_checkpoint_signature_mismatch"


def test_declared_continuous_calendar_requires_unchanged_methods_and_empty_state(monkeypatch):
    from core.services.scheduler.run.optimizer_proof_oracle import _ContinuousCalendar
    from tests._support.optimizer_graph_ready_benchmark import ContinuousCalendar

    for kind in (_ContinuousCalendar, ContinuousCalendar):
        calendar = kind()
        assert checkpoint_calendar_signature(calendar) == ()
        calendar.new_semantic_state = 1
        with pytest.raises(ValidationError) as excinfo:
            checkpoint_calendar_signature(calendar)
        assert excinfo.value.details["reason"] == "decode_checkpoint_unsupported_calendar"
        del calendar.new_semantic_state
        with monkeypatch.context() as patch:
            patch.setattr(kind, "get_efficiency", lambda *args, **kwargs: 0.5)
            with pytest.raises(ValidationError) as excinfo:
                checkpoint_calendar_signature(calendar)
            assert excinfo.value.details["reason"] == "decode_checkpoint_unsupported_calendar"


@pytest.mark.parametrize("read_only", [False, True])
def test_calendar_changes_from_another_connection_are_bound_to_the_visible_read_snapshot(case, tmp_path, read_only):
    import sqlite3

    from core.services.scheduler.calendar_service import CalendarService

    path = str(tmp_path / "checkpoint-calendar.db")
    writer = sqlite3.connect(path)
    reader = None
    try:
        case.input.cal_svc.conn.backup(writer)
        writer.execute("PRAGMA journal_mode=WAL")
        reader = sqlite3.connect(path)
        reader.row_factory = sqlite3.Row
        if read_only:
            reader.execute("PRAGMA query_only=ON")
            reader.execute("BEGIN")
        case.scheduler.calendar = CalendarService(reader)
        order = case.base_order()
        checkpoints, full_digest = _capture(case, order, [3])
        writer.execute("UPDATE WorkCalendar SET efficiency=0.5")
        writer.commit()
        if read_only:
            # The active read transaction still sees the original calendar.
            _results, _summary, digest = case.decode(order, resume=checkpoints[0])
            assert digest == full_digest
            reader.rollback()
            reader.execute("BEGIN")
        with pytest.raises(ValidationError) as excinfo:
            case.decode(order, resume=checkpoints[0])
        assert excinfo.value.details["reason"] == "decode_checkpoint_signature_mismatch"
    finally:
        if reader is not None:
            reader.close()
        writer.close()
