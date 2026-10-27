"""Calendar files batch their reads while retaining day identities and stale checks."""

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.resource.calendar_files.operator_files import WorkbenchOperatorCalendarFileService
from core.services.workbench.resource.operator_calendars import WorkbenchOperatorCalendarService
from tests.workbench.calendar_file_support import file_bytes

DAY = "2026-10-05"


def test_operator_calendar_bulk_reads_cross_chunks_and_preserve_histories(schema_conn, record_property):
    conn = schema_conn
    codes = ["OP" + str(index).zfill(4) for index in range(400)] + ["工:号%"]
    conn.executemany("INSERT INTO Operators(operator_id,name) VALUES (?,?)", [(code, "姓名" + code) for code in codes])
    conn.executemany("INSERT INTO OperatorCalendar(operator_id,date,day_type,shift_start,shift_end,shift_hours,efficiency) "
                     "VALUES (?,?,'workday','09:00','17:00',8,1)", [(code, DAY) for code in codes])
    conn.execute("DELETE FROM OperatorCalendar WHERE operator_id=? AND date=?", (codes[0], DAY))
    conn.commit()
    rows = [{"errors": [], "values": {"operator_code": code, "date": DAY}} for code in codes]
    service, trace = WorkbenchOperatorCalendarFileService(conn), []
    conn.set_trace_callback(trace.append)
    try:
        service._resolve_operators(rows)
        states = service._load_states(rows)
    finally:
        conn.set_trace_callback(None)
    reads = [sql for sql in trace if sql.lstrip().upper().startswith("SELECT")]
    assert len(reads) == 8
    for code in (codes[0], codes[1], codes[-1]):
        assert states[code] == WorkbenchOperatorCalendarService(conn, code).range_states(DAY, DAY)
    assert states[codes[0]][DAY]["row"] is None and states[codes[0]][DAY]["history"]
    assert rows[-1]["values"]["operator_label"] == "姓名工:号%"
    trace.clear()
    with TransactionManager(conn).transaction():
        conn.set_trace_callback(trace.append)
        try:
            _, exported = service._states_and_rows(DAY, DAY)
        finally:
            conn.set_trace_callback(None)
    assert len(exported) == 400 and len(trace) == 7
    assert next(row for row in exported if row["operator_code"] == codes[-1])["operator_label"] == "姓名工:号%"
    record_property("operator_calendar_read_queries_401_people", len(reads))


@pytest.mark.parametrize("damage", ("identity", "date"))
def test_operator_calendar_bulk_reads_keep_storage_conflicts(schema_conn, damage):
    conn = schema_conn
    conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('OP','姓名')")
    stored = DAY if damage == "identity" else DAY + "broken"
    conn.execute("INSERT INTO OperatorCalendar(operator_id,date,day_type,shift_hours,efficiency) VALUES ('OP',?,'workday',8,1)", (stored,))
    if damage == "identity":
        conn.execute("UPDATE WorkbenchEntityRefs SET active=0 WHERE kind='operator_calendar'")
    conn.commit()
    with pytest.raises(WorkbenchCommandRejected) as original:
        WorkbenchOperatorCalendarService(conn, "OP").range_states("2026-10-01", "2026-10-31")
    with pytest.raises(WorkbenchCommandRejected) as batched:
        WorkbenchOperatorCalendarFileService(conn)._states_for(["OP"], "2026-10-01", "2026-10-31")
    assert (batched.value.code, str(batched.value)) == (original.value.code, str(original.value))


def test_operator_calendar_confirmation_reloads_current_operator_rows(schema_conn):
    conn = schema_conn
    conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('OP','旧姓名')")
    conn.commit()
    content = file_bytes([("OP", DAY, "工作日", "09:00", "17:00", "100")],
                         headers=("工号", "日期", "类型", "班次开始", "班次结束", "效率（%）"))
    service = WorkbenchOperatorCalendarFileService(conn)
    preview = service.preview_import(content, file_format="csv")
    assert all(not row["errors"] for row in preview.as_dict()["rows"])
    conn.execute("UPDATE Operators SET name='新姓名' WHERE operator_id='OP'")
    conn.commit()
    with pytest.raises(WorkbenchCommandRejected) as rejected:
        with TransactionManager(conn).transaction(begin_immediate=True):
            service.confirm_import(preview, content, file_format="csv")
    assert rejected.value.code == "stale_write"
    assert conn.execute("SELECT COUNT(*) FROM OperatorCalendar").fetchone()[0] == 0


def test_operator_calendar_rest_day_rejects_allow_flags_and_periods(schema_conn):
    conn = schema_conn
    conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('OP','姓名')")
    conn.commit()
    content = file_bytes(
        [
            ("OP", "2026-10-05", "假期", "", "", "", "是", "否", ""),
            ("OP", "2026-10-06", "假期", "09:00", "17:00", "", "否", "否", "1"),
        ],
        headers=(
            "工号", "日期", "类型", "班次开始", "班次结束",
            "效率（%）", "允许普通件", "允许急件", "工作时段数",
        ),
    )
    preview = WorkbenchOperatorCalendarFileService(conn).preview_import(content, file_format="csv").as_dict()
    assert preview["summary"]["rejected"] == 2
    assert [row["result"] for row in preview["rows"]] == ["rejected", "rejected"]
    assert preview["rows"][0]["errors"] == [
        {"row": 2, "field": "allow_normal", "code": "invalid_input", "message": "休息日的普通件和急件都不可排产。"}
    ]
    assert preview["rows"][1]["errors"] == [
        {"row": 3, "field": "period_count", "code": "invalid_input", "message": "休息日不能填写工作时段。"}
    ]
