"""Large real SQLite plans: full scope survives one adjustment and restoration."""

from datetime import datetime
from time import monotonic

import pytest

from core.services.scheduler.calendar_service import CalendarService
from tests.workbench.trial_support import change, connect, create, service
from tests.workbench.trial_support import trial_case as trial_case


@pytest.mark.parametrize("count", [1000, 10000])
def test_large_plan_preserves_every_original_task(trial_case, count):
    case = trial_case
    case.conn.execute("UPDATE BatchOperations SET unit_hours=1.0/180.0 WHERE id=?", (case.op_id,))
    case.conn.executemany("""INSERT INTO BatchOperations
        (op_code,batch_id,seq,op_type_id,op_type_name,source,setup_hours,unit_hours,machine_id,operator_id,status)
        VALUES (?,'B1',?,'T1','Turning','internal',0,1.0/180.0,'M1','O1','pending')""",
        [("large-" + str(index), index) for index in range(2, count + 1)])
    case.conn.execute("INSERT INTO ScheduleHistory(version,strategy,result_status,result_summary) VALUES (1,'trial','success','{}')")
    calendar = CalendarService(case.conn)
    cursor, plan_rows = datetime(2026, 9, 9, 8), []
    for op_id, in case.conn.execute("SELECT id FROM BatchOperations ORDER BY seq"):
        start = calendar.adjust_to_working_time(cursor, priority="normal", operator_id="O1")
        end = calendar.add_working_hours(start, 1.0 / 60, priority="normal", operator_id="O1")
        plan_rows.append((op_id, start.isoformat(), end.isoformat()))
        cursor = end
    case.conn.executemany("""INSERT INTO Schedule(version,op_id,machine_id,operator_id,start_time,end_time)
        VALUES (1,?,'M1','O1',?,?)""", plan_rows)
    case.conn.commit()
    started = monotonic()
    draft = create(case, {"base": {"plan_ref": case.plan_ref(1)}, "scope": {
        "range_start": "2026-09-09T08:00:00", "range_end": "2026-09-09T08:01:00"}})
    assert draft["task_count"] == count
    assert draft["validation"]["constraints_status"] == "valid", draft["validation"]
    refs = [(row["row_ref"], row["task_ref"]) for row in draft["tasks"]]
    updated = change(case, draft, start=plan_rows[-1][1], task=count - 1)["data"]
    assert updated["task_count"] == count
    conn = connect(case.path)
    try:
        restored = service(conn).get(draft["draft_ref"])
        assert [(row["row_ref"], row["task_ref"]) for row in restored["tasks"]] == refs
        assert restored["tasks"] == updated["tasks"]
    finally:
        conn.close()
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchTrialRows").fetchone()[0] == count
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchTrialChanges").fetchone()[0] == 1
    actual = [(row[0], row[1], row[2]) for row in case.conn.execute("SELECT op_id,start_time,end_time FROM Schedule ORDER BY id")]
    assert actual == plan_rows
    print("trial_capacity", count, "elapsed_seconds", round(monotonic() - started, 3))
