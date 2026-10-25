"""Real resource, readiness, calendar and external-precedence integration."""

import re
from datetime import datetime

import pytest

from core.services.scheduler.calendar.service import CalendarService
from core.services.workbench.run.compute import compute_candidate_run
from tests.workbench.identity_metadata_support import insert_row
from tests.workbench.run_compute_support import run_case as _run_case  # noqa: F401
from tests.workbench.run_compute_support import unchanged


@pytest.mark.parametrize("hold", ["old_lock_mark", "window"])
def test_only_the_hold_window_keeps_an_original_arrangement(run_case, hold):
    """本次显式填的不重排时段照样保持原安排（08:00-10:00 原样留下）；
    正式计划里旧的锁定标记（旧版「锁定近期排程」顺带打上的）不再起作用，这道工序照常按现在的工时重排（3 件 × 0.25 小时）。"""
    case = run_case
    successor = case.operation(seq=2)
    case.plan(1, [case.op_id])
    settings = case.settings(hold_window={"start": "2026-09-09T09:00", "end": "2026-09-09T09:01"})
    if hold == "old_lock_mark":
        case.conn.execute("UPDATE Schedule SET lock_status='locked'")
        settings = case.settings()
    case.conn.commit()
    result = unchanged(case, lambda: compute_candidate_run(case.conn, settings, case.projections()))
    held = hold == "window"
    assert result.schedule_input.frozen_op_ids == ({case.op_id} if held else set())
    expected = (datetime(2026, 9, 9, 8), datetime(2026, 9, 9, 10) if held else datetime(2026, 9, 9, 8, 45))
    for payload in result.candidate_payloads.values():
        rows = {row.op_id: row for row in payload.schedule_rows}
        assert (rows[case.op_id].start_time, rows[case.op_id].end_time) == expected
        assert rows[successor].start_time >= rows[case.op_id].end_time


@pytest.mark.parametrize("quantity,finish", [(3, datetime(2026, 9, 10, 1, 30)), (36, datetime(2026, 9, 10, 13, 30))])
def test_night_operator_calendar_efficiency_and_downtime_are_real(run_case, quantity, finish):
    case = run_case
    case.conn.execute("UPDATE Batches SET quantity=? WHERE batch_id='B1'", (quantity,))
    insert_row(case.conn, "WorkCalendar", dict(date="2026-09-09", day_type="workday", shift_start="22:30",
               shift_end="06:30", shift_hours=8, efficiency=1, allow_normal="yes", allow_urgent="yes"))
    insert_row(case.conn, "OperatorCalendar", dict(operator_id="O1", date="2026-09-09", day_type="workday",
               shift_start="23:00", shift_end="07:00", shift_hours=8, efficiency=0.5, allow_normal="yes", allow_urgent="yes"))
    insert_row(case.conn, "MachineDowntimes", dict(machine_id="M1", scope_type="machine", scope_value="M1",
               start_time="2026-09-09 22:00:00", end_time="2026-09-10 00:00:00", reason_code="maintenance", status="active"))
    case.conn.commit()
    result = unchanged(case, lambda: compute_candidate_run(case.conn, case.settings(end_date="2026-09-10"), case.projections()))
    for payload in result.candidate_payloads.values():
        row = payload.schedule_rows[0]
        assert row.start_time == datetime(2026, 9, 10)
        assert row.end_time == finish
        assert CalendarService(case.conn).capacity_hours_between(
            row.start_time, row.end_time, priority="normal", operator_id="O1") == pytest.approx(quantity * 0.25)


def test_complex_merged_external_chain_and_shared_resource_competition(run_case):
    case = run_case
    case.conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('EXT','Heat treatment','external')")
    case.conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id) VALUES ('S1','Supplier','EXT')")
    insert_row(case.conn, "ExternalGroups", dict(group_id="EG", part_no="P1", start_seq=2, end_seq=3,
               merge_mode="merged", total_days=0.25, supplier_id="S1"))
    external_ids = []
    for seq in (2, 3):
        insert_row(case.conn, "PartOperations", dict(part_no="P1", seq=seq, op_type_id="EXT", op_type_name="Heat treatment",
                   source="external", supplier_id="S1", ext_group_id="EG", setup_hours=None, unit_hours=None, status="active"))
        external_ids.append(case.operation(seq=seq, op_type_id="EXT", source="external", supplier_id="S1",
                                          machine_id=None, operator_id=None, setup_hours=None, unit_hours=None, ext_days=None))
    last = case.operation(seq=4)
    case.batch("B2", priority="urgent")
    competing = case.operation("B2", unit_hours=1)
    case.conn.commit()
    result = unchanged(case, lambda: compute_candidate_run(case.conn, case.settings("B1", "B2"), case.projections()))
    expected = {case.op_id, last, competing} | set(external_ids)
    for payload in result.candidate_payloads.values():
        assert payload.scheduled_op_ids == expected
        rows = {row.op_id: row for row in payload.schedule_rows}
        first, second = (rows[op_id] for op_id in external_ids)
        assert first.start_time >= rows[case.op_id].end_time
        assert first.end_time == second.end_time
        assert first.start_time == second.start_time
        assert (first.end_time - first.start_time).total_seconds() == 6 * 3600
        assert rows[last].start_time >= second.end_time
        internal = sorted((row for row in rows.values() if row.source == "internal"), key=lambda row: row.start_time)
        assert all(left.end_time <= right.start_time for left, right in zip(internal, internal[1:]))


def test_compute_consumes_captured_calendar_rows_once_and_next_run_sees_changes(run_case):
    case = run_case
    conn = case.conn
    conn.execute("INSERT INTO WorkCalendar(date,shift_start,shift_end,shift_hours,efficiency) "
                 "VALUES ('2026-09-09',NULL,NULL,NULL,NULL)")
    conn.execute("INSERT INTO WorkbenchShiftProfiles(profile_id,name,anchor_date,cycle_days) "
                 "VALUES ('S','Shift','2026-09-09',1)")
    conn.execute("INSERT INTO WorkbenchShiftPatternDays(profile_id,day_offset,is_rest,shift_start,shift_end) "
                 "VALUES ('S',0,0,'09:00','17:00')")
    conn.execute("INSERT INTO WorkbenchShiftDayPeriods(profile_id,day_offset,periods_json) VALUES ('S',0,?)",
                 ('[{"start":"09:00","end":"17:00","day_offset":0}]',))
    conn.execute("INSERT INTO WorkbenchOperatorProfiles(operator_id,shift_profile_id) VALUES ('O1','S')")
    conn.commit()
    tables = ("WorkCalendar", "OperatorCalendar", "WorkbenchCalendarDefaults", "WorkbenchOperatorProfiles",
              "WorkbenchShiftProfiles", "WorkbenchShiftPatternDays", "WorkbenchShiftDayPeriods")

    def run():
        projections = case.projections()
        statements = []
        conn.set_trace_callback(statements.append)
        try:
            result = compute_candidate_run(conn, case.settings(), projections)
            signature = result.schedule_input.cal_svc.certified_decode_checkpoint_snapshot()
        finally:
            conn.set_trace_callback(None)
        for table in tables:
            reads = [sql for sql in statements if re.search(r'\bFROM\s+"?' + table + r'"?\b', sql, re.I)]
            assert len(reads) == 1, (table, reads)
            assert "ORDER BY rowid" in reads[0], (table, reads)
        return result, signature

    original, signature = unchanged(case, run)
    assert original.orchestration.validated_schedule_payload.schedule_rows[0].start_time == datetime(2026, 9, 9, 9)
    conn.execute("UPDATE WorkbenchShiftDayPeriods SET periods_json=? WHERE profile_id='S'",
                 ('[{"start":"11:00","end":"17:00","day_offset":0}]',))
    conn.commit()
    changed, changed_signature = unchanged(case, run)
    assert changed.orchestration.validated_schedule_payload.schedule_rows[0].start_time == datetime(2026, 9, 9, 11)
    assert changed_signature != signature
