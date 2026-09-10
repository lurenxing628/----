"""Real preflight API read-only, field, scope, execution and token contracts."""

import sqlite3

import pytest

from core.infrastructure.workbench_execution_ledger_schema import execution_ledger_contract_issues
from core.models.workbench_command import WorkbenchCommandRejected
from tests.workbench.test_preflight_support import BASE, add_op, checked, legacy_events, payload, ref_for, snapshot
from tests.workbench.test_preflight_support import pf as pf_fixture
from tests.workbench.test_preflight_support import pf_legacy_schema as pf_legacy_fixture
from web.routes.workbench.preflight import resolve_preflight_input


@pytest.mark.parametrize("fixture_name,source", [("pf", "execution_ledger"), ("pf_legacy_schema", "legacy_guard_only")])
def test_read_only_zero_hours_and_unavailable_worker(request, fixture_name, source):
    pf = request.getfixturevalue(fixture_name)
    data = checked(pf)
    assert data["counts"]["ready_tasks"] == 1
    assert data["counts"]["blocked_tasks"] == 0
    assert data["calendar_check"] == "not_evaluated"
    assert data["effective_start"] == "2026-09-09T00:00:00"
    assert data["effective_end_exclusive"] == "2026-09-10T00:00:00"
    assert data["write_context"]["capabilities"]["scheduling.run"] is False
    assert data["write_context"]["write_token"] is None
    reasons = {row["code"] for row in data["run_blocked_reasons"]}
    assert data["run_blocked"] is True and "schedule_not_computed" in reasons
    assert data["execution_projection_source"] == source
    assert ("execution_ledger_unavailable" in reasons) == (source == "legacy_guard_only")


@pytest.mark.parametrize("damage", ["DROP INDEX idx_wb_execution_reports_operation", "DELETE FROM WorkbenchExecutionLedgerClock"])
def test_current_unavailable_ledger_warns_without_repair(pf, damage):
    pf.conn.execute(damage)
    pf.conn.commit()
    issues = execution_ledger_contract_issues(pf.conn)
    assert issues
    data = checked(pf)
    assert data["execution_projection_source"] == "legacy_guard_only"
    assert "execution_ledger_unavailable" in {row["code"] for row in data["run_blocked_reasons"]}
    assert data["run_blocked"] is True and data["write_context"]["write_token"] is None
    assert execution_ledger_contract_issues(pf.conn) == issues


@pytest.mark.parametrize("field", ["setup_hours", "unit_hours", "op_type_id"])
def test_missing_resource_exclusion_cannot_mask_required_fields(pf, field):
    pf.conn.execute('UPDATE BatchOperations SET "' + field + '"=NULL,machine_id=NULL WHERE batch_id=?', ("PF-0000",))
    pf.conn.commit()
    data = checked(pf, missing_resource_policy="exclude")
    assert data["counts"]["blocked_tasks"] == 1 and data["eligible_tasks"] == 0


@pytest.mark.parametrize("policy,state", [("exclude", "skipped"), ("auto_assign", "auto_assign_required")])
def test_missing_resources_and_downstream_chain(pf, policy, state):
    add_op(pf.conn)
    pf.conn.execute("UPDATE BatchOperations SET machine_id=NULL WHERE op_code='PF-0000-1'")
    pf.conn.commit()
    data = checked(pf, missing_resource_policy=policy)
    first, second = data["tasks"]
    assert first["status"] == state
    assert second["status"] == ("skipped" if policy == "exclude" else "eligible")
    if policy == "exclude":
        assert second["issues"][-1]["code"] == "predecessor_excluded"
        assert second["issues"][-1]["related_operation_ref"] == first["operation_ref"]
        assert data["counts"]["skipped_tasks"] == 2


def test_unready_and_missing_route_are_separate(pf):
    add_op(pf.conn)
    pf.conn.execute("UPDATE Batches SET ready_status='no' WHERE batch_id='PF-0000'")
    pf.conn.commit()
    data = checked(pf)
    assert data["counts"]["unready_batches"] == 1
    assert data["counts"]["skipped_tasks"] == 2
    assert data["tasks"][1]["issues"][-1]["code"] == "predecessor_excluded"
    assert checked(pf, ready_check=False)["eligible_tasks"] == 2
    pf.conn.execute("DELETE FROM BatchOperations WHERE batch_id='PF-0000'")
    pf.conn.commit()
    data = checked(pf)
    assert data["counts"]["no_route_batches"] == 1 and data["counts"]["selected_tasks"] == 0


def test_external_requirements_never_autofilled(pf):
    pf.conn.execute("UPDATE BatchOperations SET source='external',supplier_id=NULL,ext_days=NULL WHERE batch_id='PF-0000'")
    pf.conn.commit()
    data = checked(pf, missing_resource_policy="exclude")
    assert data["counts"]["blocked_tasks"] == 1
    assert {row["code"] for row in data["tasks"][0]["issues"]} == {"supplier_missing", "external_days_missing"}


@pytest.mark.parametrize("setup_hours", [0, 2])
def test_known_zero_quantity_not_unknown(pf, setup_hours):
    pf.conn.execute("UPDATE Batches SET quantity=0 WHERE batch_id='PF-0000'")
    pf.conn.execute("UPDATE BatchOperations SET setup_hours=? WHERE batch_id='PF-0000'", (setup_hours,))
    pf.conn.commit()
    data = checked(pf)
    assert data["tasks"][0]["issues"] == []
    assert data["tasks"][0]["status"] == "eligible"
    assert data["eligible_tasks"] == 1 and data["counts"]["blocked_tasks"] == 0
    assert data["write_context"]["write_token"] is None
    assert pf.conn.execute("SELECT quantity FROM Batches WHERE batch_id='PF-0000'").fetchone()[0] == 0
    pf.conn.execute("UPDATE Batches SET quantity='unknown' WHERE batch_id='PF-0000'")
    pf.conn.commit()
    unknown = checked(pf)
    assert "quantity_unknown" in {row["code"] for row in unknown["tasks"][0]["issues"]}
    assert unknown["eligible_tasks"] == 0 and unknown["counts"]["blocked_tasks"] == 1


@pytest.mark.parametrize("finish", [False, True])
@pytest.mark.parametrize("fixture_name", ["pf", "pf_legacy_schema"])
def test_cross_midnight_legacy_actuals_preserved_without_quantity(request, fixture_name, finish):
    pf = request.getfixturevalue(fixture_name)
    legacy_events(pf.conn, finish)
    add_op(pf.conn)
    if fixture_name == "pf":
        bindings = pf.conn.execute("""SELECT f.operation_ref, f.recorded_against_task_ref, f.recorded_against_plan_ref
            FROM WorkbenchExecutionLegacyFacts f JOIN WorkbenchTaskRefs t ON t.ref=f.recorded_against_task_ref
            JOIN WorkbenchPlanSourceRefs p ON p.ref=t.plan_ref AND p.kind='official' AND p.version=7
            JOIN WorkbenchPlanSourceRefs r ON r.ref=t.row_ref AND r.source_key='42'
            WHERE f.recorded_against_plan_ref=p.ref AND f.operation_ref=r.operation_ref""").fetchall()
        assert len(bindings) == (2 if finish else 1)
    data = checked(pf)
    first, second = data["tasks"]
    assert first["status"] == "protected" and first["execution"]["remaining_quantity"] is None
    assert first["execution"]["execution_state"] == ("complete" if finish else "started")
    assert first["execution"]["completion_basis"] == ("legacy_finish_event" if finish else None)
    assert first["execution"]["data_quality"] == "legacy_incomplete"
    assert data["counts"]["protected_tasks"] == data["counts"]["actual_fact_tasks"] == 1
    assert second["status"] == ("eligible" if finish else "skipped")
    if finish:
        assert first["execution"]["confirmed_finish"] == "2026-09-09T06:30:00"


@pytest.mark.parametrize("later_version", [None, 7, 8])
def test_legacy_without_history_never_borrows_a_later_plan(pf, later_version):
    legacy_events(pf.conn, history=False)
    add_op(pf.conn)
    archived = snapshot(pf.conn)["WorkbenchExecutionLegacyFacts"]
    bindings = pf.conn.execute("""SELECT operation_ref, recorded_against_task_ref, recorded_against_plan_ref
        FROM WorkbenchExecutionLegacyFacts ORDER BY id""").fetchall()
    assert len(bindings) == 2
    assert all(row[0] and row[1] is None and row[2] is None for row in bindings)
    if later_version is not None:
        pf.conn.execute("""INSERT INTO ScheduleHistory(version,strategy,result_status,result_summary,schedule_time)
            VALUES (?,'preflight-later','success','{}','2026-09-09 07:00:00')""", (later_version,))
        if later_version == 8:
            pf.conn.execute("""INSERT INTO Schedule(version,op_id,machine_id,operator_id,start_time,end_time)
                SELECT 8,op_id,machine_id,operator_id,start_time,end_time FROM Schedule WHERE id=42""")
        pf.conn.commit()
        assert pf.conn.execute("""SELECT count(*) FROM WorkbenchTaskRefs t
            JOIN WorkbenchPlanSourceRefs p ON p.ref=t.plan_ref JOIN WorkbenchPlanSourceRefs r ON r.ref=t.row_ref
            WHERE p.kind='official' AND p.version=? AND r.operation_id=(
                SELECT id FROM BatchOperations WHERE op_code='PF-0000-1')""",
            (later_version,)).fetchone()[0] == 1
    data = checked(pf)
    first, second = data["tasks"]
    assert data["execution_projection_source"] == "execution_ledger"
    assert first["status"] == "protected" and second["status"] == "skipped"
    assert first["execution"]["execution_state"] == "unreported"
    assert first["execution"]["data_quality"] == "invalid"
    assert all(first["execution"][field] is None for field in
               ("first_actual_start", "confirmed_finish", "completion_basis", "remaining_quantity"))
    assert {row["code"] for row in first["issues"]} >= {"legacy_identity_unresolved", "invalid_legacy_sequence"}
    assert "execution_review_required" in {row["code"] for row in data["blockers"]}
    assert data["eligible_tasks"] == 0 and data["counts"]["protected_tasks"] == 1
    assert second["issues"][-1]["related_operation_ref"] == first["operation_ref"]
    assert snapshot(pf.conn)["WorkbenchExecutionLegacyFacts"] == archived
    assert pf.conn.execute("SELECT count(*) FROM WorkbenchProductionReports").fetchone()[0] == 0


def test_ready_date_after_window_not_silently_clamped(pf):
    pf.conn.execute("UPDATE Batches SET ready_date='2026-09-10' WHERE batch_id='PF-0000'")
    pf.conn.commit()
    assert checked(pf)["tasks"][0]["issues"][0]["code"] == "ready_after_window"


def test_unconfirmed_execution_marker_not_counted_as_actual_fact(pf):
    pf.conn.execute("UPDATE BatchOperations SET status='completed' WHERE batch_id='PF-0000'")
    pf.conn.commit()
    data = checked(pf)
    assert data["counts"]["actual_fact_tasks"] == 0 and data["counts"]["protected_tasks"] == 1
    assert data["tasks"][0]["execution"]["confirmed_finish"] is None


@pytest.mark.parametrize("patch", [{"batch_refs": None}, {"batch_refs": ["PF-0000"]}, {"start_date": "2026-02-30"},
    {"end_date": "2026-09-08"}, {"end_date": "9999-12-31"}, {"ready_check": 1}, {"completed_policy": "reopen"},
    {"missing_resource_policy": "fallback"}, {"batch_ids": ["PF-0000"]}])
def test_invalid_input_no_writes(pf, patch):
    before = snapshot(pf.conn)
    response = pf.post(BASE, json=payload(pf, **patch))
    assert response.status_code == 422 and response.get_json()["committed"] is False
    assert snapshot(pf.conn) == before


def test_empty_duplicate_large_and_recreated_refs(pf):
    assert checked(pf, batch_refs=[])["counts"]["selected_tasks"] == 0
    ref = ref_for(pf.conn)
    for refs in ([ref, ref], [f"{index:048x}" for index in range(5001)]):
        assert pf.post(BASE, json=payload(pf, batch_refs=refs)).status_code == 422
    pf.conn.execute("DELETE FROM Batches WHERE batch_id='PF-0000'")
    pf.conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES('PF-0000','P1',3)")
    pf.conn.commit()
    response = pf.post(BASE, json=payload(pf, batch_refs=[ref]))
    assert response.status_code == 404
    assert ref_for(pf.conn) != ref


@pytest.mark.parametrize("change", ["UPDATE WorkCalendar SET shift_end='07:00'", "UPDATE ScheduleConfig SET config_value='2'",
    "UPDATE Operators SET remark='outside-scope'", "UPDATE BatchOperations SET unit_hours=0.1 WHERE batch_id='B1'"])
def test_input_ref_binds_complete_input_and_full_facts(pf, change):
    pf.conn.execute("INSERT INTO ScheduleConfig(config_key,config_value) VALUES('preflight-test','1')")
    pf.conn.commit()
    data = checked(pf)
    with pf.application.app_context():
        pf.conn.execute("BEGIN")
        normalized = resolve_preflight_input(pf.conn, data["input_ref"])
        assert normalized == payload(pf)
        pf.conn.rollback()
        pf.conn.execute(change)
        pf.conn.commit()
        pf.conn.execute("BEGIN")
        with pytest.raises(WorkbenchCommandRejected, match="已经变化"):
            resolve_preflight_input(pf.conn, data["input_ref"])
        pf.conn.rollback()


def test_expired_context_and_read_failure_stay_uncommitted(pf):
    checked(pf)
    with pf.application.app_context():
        pf.conn.execute("BEGIN")
        with pytest.raises(WorkbenchCommandRejected, match="失效"):
            resolve_preflight_input(pf.conn, "invalid")
        pf.conn.rollback()
    pf.conn.set_authorizer(lambda action, table, _col, _db, _trigger: sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_READ and table == "BatchOperations" else sqlite3.SQLITE_OK)
    try:
        response = pf.post(BASE, json=payload(pf))
        assert response.status_code == 500 and response.get_json()["committed"] is False
    finally:
        pf.conn.set_authorizer(lambda *_: sqlite3.SQLITE_OK)
