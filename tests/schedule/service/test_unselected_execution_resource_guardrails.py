"""执行快照保留实际保护内容和原预约区间的事实差异。"""

from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from core.errors import AppError
from core.services.scheduler.execution.execution_fact_provider import ExecutionFact
from core.services.scheduler.execution.execution_snapshot import build_execution_snapshot
from core.services.scheduler.run.schedule_execution_persistence_guard import _validate_unselected_resource_overlap
from core.services.scheduler.run.schedule_execution_reservations import ExecutionResourceReservation
from core.services.scheduler.run.schedule_execution_resource_facts import resource_execution_snapshot
from core.services.scheduler.run.schedule_payload_contract import ValidatedSchedulePayload, ValidatedScheduleRow


def _overlap_payload(rows):
    base = datetime(2026, 9, 8)
    schedule_rows = [ValidatedScheduleRow(index, machine, operator, base + timedelta(hours=start),
                                          base + timedelta(hours=end), "internal")
                     for index, (machine, operator, start, end) in enumerate(rows, start=1)]
    return ValidatedSchedulePayload(schedule_rows, {row.op_id for row in schedule_rows}, {})


@pytest.mark.parametrize("reservations", [
    [(40, "M1", "other", 18, 19), (41, "other", "O1", 7, 8)],
    [(42, "M2", "other", 8, 10), (11, "M1", "other", 17, 18)],
    [(99, "other", "O1", 17, 18)],
    [(12, "M1", "other", 17, 17)],
    [(13, " M1 ", " O1 ", 9, 10)],
    [(14, "M1", "other", 9, 10), (1, "M1", "other", 8, 9)],
])
def test_unselected_overlap_index_preserves_strict_endpoints_points_and_first_conflict(reservations):
    payload = _overlap_payload([("M1", "O1", 8, 18), ("M1", "O1", 10, 11), ("M2", "O2", 9, 9)])
    base = datetime(2026, 9, 8)
    reserved = [ExecutionResourceReservation(op_id, machine, operator, base + timedelta(hours=start),
                                             base + timedelta(hours=end))
                for op_id, machine, operator, start, end in reservations]
    expected = next((reservation.op_id for reservation in reserved for row in payload.schedule_rows
                     if (row.machine_id == reservation.machine_id or row.operator_id == reservation.operator_id)
                     and row.start_time < row.end_time
                     and row.start_time < reservation.end_time and row.end_time > reservation.start_time), None)
    if expected is None:
        _validate_unselected_resource_overlap(payload=payload, reservations=reserved, execution_facts={})
    else:
        with pytest.raises(AppError) as actual:
            _validate_unselected_resource_overlap(payload=payload, reservations=reserved, execution_facts={})
        assert actual.value.details == {"reason": "unselected_execution_resource_overlap", "op_id": expected}
        assert actual.value.message == "新排程与未选中的在制工序占用冲突，本次没有写入新排程。请刷新后重新排。"


def test_unselected_overlap_reads_the_payload_once_for_many_reservations():
    class CountedRows(list):
        iterations = 0

        def __iter__(self):
            self.iterations += 1
            return super().__iter__()

    payload = _overlap_payload([("M1", "O1", index, index + 1) for index in range(1000)])
    rows = CountedRows(payload.schedule_rows)
    payload = replace(payload, schedule_rows=rows)
    start = datetime(2026, 9, 8)
    reservations = [ExecutionResourceReservation(index, "other", "other", start, start + timedelta(hours=1))
                    for index in range(250)]
    _validate_unselected_resource_overlap(payload=payload, reservations=reservations, execution_facts={})
    assert rows.iterations == 1


def test_execution_snapshot_covers_actual_protection_and_original_reservation_content():
    start_time = datetime(2026, 9, 8, 8)
    fact = ExecutionFact(
        op_id=10, batch_id="B1", actual_status="processing", actual_start_time=start_time,
        actual_end_time=None, actual_machine_id="M1", actual_operator_id="O1",
        state_revision="10:1:100", schedule_version=1, schedule_id=100,
        source_table="schedule", effective_plan_role="adopted", target_quantity=1,
        remaining_quantity=1, execution_effective_intervals=((start_time, start_time + timedelta(hours=1)),),
        execution_protection_content={"scope_task": {"task_ref": "original-task", "source": "internal"},
            "ledger_revision": 5,
            "projection": {"reports": [{"completed_quantity": 1}], "data_gaps": []},
            "resources": {"original-machine": {"kind": "machine", "available": True, "business_code": "M1"}}},
    )
    original = build_execution_snapshot({10: fact}).revision
    for changed in (
        replace(fact, actual_start_time=start_time + timedelta(seconds=1)),
        replace(fact, actual_machine_id="M2"),
        replace(fact, remaining_quantity=True),
        replace(fact, target_quantity=1.0),
        replace(fact, execution_effective_intervals=((start_time, start_time + timedelta(hours=2)),)),
        replace(fact, execution_protection_reasons=("pending-reconciliation",)),
        replace(fact, execution_protection_content=dict(fact.execution_protection_content,
            projection={"reports": [{"completed_quantity": True}], "data_gaps": []})),
        replace(fact, execution_protection_content=dict(fact.execution_protection_content,
            resources={"original-machine": {"kind": "machine", "available": 1, "business_code": "M1"}})),
    ):
        assert build_execution_snapshot({10: changed}).revision != original
    arrangement = {"schedule_id": 100, "version": 1, "op_id": 10,
                   "start_time": "2026-09-08 08:00:00", "end_time": "2026-09-08 09:00:00",
                   "machine_id": "M1", "operator_id": "O1", "total_hours": 1.0}
    resource_original = resource_execution_snapshot({10: fact}, {10: arrangement}).revision
    for changed in (dict(arrangement, end_time="2026-09-08 10:00:00"),
                    dict(arrangement, operator_id="O2"), dict(arrangement, total_hours=True)):
        assert resource_execution_snapshot({10: fact}, {10: changed}).revision != resource_original
