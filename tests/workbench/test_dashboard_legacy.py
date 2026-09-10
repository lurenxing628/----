"""Original legacy value types and complete-state semantics survive dashboard writes."""

import json

from core.models.workbench_command import WorkbenchCommandRejected
from tests.workbench.dashboard_support import dashboard_case as _dashboard_case  # noqa: F401
from tests.workbench.dashboard_support import follow, source_rows


def legacy_finish(case):
    schedule = case.conn.execute("SELECT id FROM Schedule WHERE version=1").fetchone()[0]
    previous = 0
    for index, kind in enumerate(("start", "finish")):
        previous = case.conn.execute("""INSERT INTO OperationExecutionEvents
            (schedule_version,schedule_id,op_id,batch_id,source_table,effective_plan_role,event_type,reported_status,event_time,
             actual_machine_id,actual_operator_id,quantity_done,created_by,idempotency_key,request_fingerprint,previous_state_revision,
             remark,created_at) VALUES (1,?,?,'DB1','schedule','adopted',?,?,?,'DM1','DO1',NULL,'legacy',?,'legacy',?,?,?)""",
            (schedule, case.op, kind, "processing" if kind == "start" else "completed",
             "2026-09-09T08:00:00" if kind == "start" else "2026-09-09T10:00:00", "dashboard-legacy-" + kind,
             f"{case.op}:{index}:{previous}", b"old-note", b"old-created-at")).lastrowid
    case.conn.commit()


def test_legacy_complete_not_turned_into_partial_or_zero_hours(dashboard_case):
    case = dashboard_case
    item = case.item("actual")
    case.command(item, follow())
    legacy_finish(case)
    before = source_rows(case.conn)
    item = case.item("actual")
    assert item["source"]["execution_state"] == "complete"
    assert item["source"]["completion_basis"] == "legacy_finish_event"
    assert item["source"]["hours"]["effective_processing_hours"] is None
    assert item["source"]["data_quality"] == "legacy_incomplete"
    assert "feedback_pending" not in item["source"]["risk_codes"]
    case.command(item, follow(remark="Confirmed original completion, processing hours remain unknown"))
    saved = json.loads(case.conn.execute("SELECT source_facts_json FROM WorkbenchDashboardHistory ORDER BY sequence DESC LIMIT 1").fetchone()[0])
    raw = saved["facts"]["legacy"]
    assert len(raw) == 2
    assert raw[1]["remark"] == {"storage_type": "blob", "hex": b"old-note".hex()}
    assert raw[1]["created_at"] == {"storage_type": "blob", "hex": b"old-created-at".hex()}
    assert source_rows(case.conn) == before


def test_legacy_raw_source_edit_stales_token_and_keeps_archived_completion(dashboard_case):
    case = dashboard_case
    case.command(case.item("actual"), follow())
    legacy_finish(case)
    item = case.item("actual")
    case.conn.execute("UPDATE OperationExecutionEvents SET remark='old-note'")
    case.conn.commit()
    try:
        case.command(item, follow(remark="Changed"))
    except WorkbenchCommandRejected as error:
        assert error.code == "stale_write"
    else:
        raise AssertionError("Old token accepted after raw type drift")
    current = case.item("actual")
    assert current["source"]["execution_state"] == "complete"
    assert any(row["code"] == "legacy_source_changed" for row in current["source"]["data_gaps"])
