"""Unknown legacy values, night shifts, source-specific duration and live drift."""

import sqlite3

import pytest

from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.models.workbench_trial_codec import load
from core.services.workbench.run_worker import WorkbenchRunWorker
from tests.workbench.trial_support import change, create, official, service, snapshot
from tests.workbench.trial_support import trial_case as trial_case


def issue_codes(draft):
    return {item["code"] for item in draft["validation"]["issues"]}


@pytest.mark.parametrize("hours", [None, sqlite3.Binary(b"invalid hours")])
def test_unknown_hours_retained_not_coerced_or_epsilon(trial_case, hours):
    case = trial_case
    case.conn.execute("UPDATE BatchOperations SET unit_hours=? WHERE id=?", (hours, case.op_id))
    case.conn.commit()
    draft = create(case)
    assert "hours_missing" in issue_codes(draft)
    assert draft["tasks"][0]["hours"]["total_hours"] is None
    assert draft["tasks"][0]["edit_context"]["can_change"] is False
    original = load(case.conn.execute("SELECT original_json FROM WorkbenchTrialRows").fetchone()[0])
    assert original["operation"]["unit_hours"] == (bytes(hours) if hours is not None else None)
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        change(case, draft)
    assert error.value.code == "hours_missing"
    assert snapshot(case.conn) == before


def test_person_night_calendar_windows_and_end_are_real(trial_case):
    case = trial_case
    case.conn.execute("""INSERT INTO OperatorCalendar(operator_id,date,day_type,shift_start,shift_end,shift_hours,efficiency,allow_normal,allow_urgent)
        VALUES ('O2','2026-09-09','workday','22:00','06:00',8,1,'yes','yes')""")
    case.conn.commit()
    draft = create(case)
    changed = change(case, draft, start="2026-09-09T23:00:00")["data"]
    assert changed["tasks"][0]["end"] == "2026-09-10T02:00:00"
    assert changed["validation"]["constraints_status"] == "valid", changed["validation"]
    person = next(row for row in changed["capacity"]["resources"] if row["resource_type"] == "operator")
    assert person["calendar"]["windows"][0]["start"] == "2026-09-09T23:00:00"
    assert person["calendar"]["windows"][0]["end"] == "2026-09-10T02:00:00"
    assert person["available_occupied_hours"] == 3


def test_outside_calendar_request_keeps_requested_start_and_blocks(trial_case):
    case = trial_case
    draft = create(case)
    changed = change(case, draft, start="2026-09-09T06:00:00")["data"]
    assert changed["tasks"][0]["start"] == "2026-09-09T06:00:00"
    assert changed["tasks"][0]["end"] == "2026-09-09T11:00:00"
    assert "calendar_duration_conflict" in issue_codes(changed)
    assert changed["tasks"][0]["edit_context"]["can_change"] is True


def test_downtime_conflict_is_saved_as_conflict_not_shifted_away(trial_case):
    case = trial_case
    case.conn.execute("""INSERT INTO MachineDowntimes(machine_id,start_time,end_time,reason_detail,status)
        VALUES ('M2','2026-09-09 14:00:00','2026-09-09 15:00:00','fixture','active')""")
    case.conn.commit()
    draft = create(case)
    changed = change(case, draft)["data"]
    assert "machine_downtime" in issue_codes(changed)
    assert changed["tasks"][0]["start"] == "2026-09-09T13:00:00"
    assert changed["tasks"][0]["end"] == "2026-09-09T16:00:00"


def test_saved_original_can_be_read_with_broken_live_calendar(trial_case):
    case = trial_case
    draft = create(case)
    case.conn.execute("INSERT INTO WorkCalendar(date,day_type) VALUES ('broken-date','workday')")
    case.conn.commit()
    read = service(case.conn).get(draft["draft_ref"])
    assert read["tasks"][0]["original"] == draft["tasks"][0]["original"]
    assert "calendar_unproven" in issue_codes(read)
    with pytest.raises(WorkbenchCommandRejected) as error:
        change(case, read)
    assert error.value.code == "calendar_unproven"


def test_external_cycle_uses_calendar_days_and_no_internal_resources(trial_case):
    case = trial_case
    case.conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('EXT','Coat','external')")
    case.conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id) VALUES ('S1','Coater','EXT')")
    case.conn.execute("UPDATE BatchOperations SET source='external',op_type_id='EXT',supplier_id='S1',ext_days=2,machine_id=NULL,operator_id=NULL WHERE id=?", (case.op_id,))
    case.conn.commit()
    value = official(case, end="2026-09-11T08:00:00")
    case.conn.execute("UPDATE Schedule SET machine_id=NULL,operator_id=NULL")
    case.conn.commit()
    draft = create(case, value)
    changed = change(case, draft, machine=None, operator=None)["data"]
    assert changed["tasks"][0]["source"] == "external"
    assert changed["tasks"][0]["end"] == "2026-09-11T13:00:00"
    assert changed["tasks"][0]["hours"]["days"] == 2
    assert changed["validation"]["constraints_status"] == "valid", changed["validation"]


def test_outside_base_actual_resource_release_stays_blocked(trial_case):
    case = trial_case
    case.batch("B2")
    other = case.operation("B2")
    case.conn.commit()
    case.plan(1, [other])
    case.command("create", case.task(1, other), case.values(quantity=1, effective_processing_hours=1))
    case.plan(2, [case.op_id], start="2026-09-10T08:00:00", end="2026-09-10T11:00:00")
    draft = create(case, {"base": {"plan_ref": case.plan_ref(2)}})
    assert draft["task_count"] == 1
    assert "execution_resource_release_unknown" in issue_codes(draft)


def test_saved_scenario_row_failure_rolls_back_close_and_receipt(trial_case):
    case = trial_case
    draft = create(case)
    case.conn.execute("""CREATE TEMP TRIGGER test_trial_scenario_failure BEFORE INSERT ON WorkbenchTrialScenarioRows
        BEGIN SELECT RAISE(ABORT,'injected scenario row failure'); END""")
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandUncertain):
        service(case.conn).save(draft["draft_ref"], {"name": "No partial save"}, draft["write_context"]["write_token"], "trial-save-fail-00001")
    assert snapshot(case.conn) == before
    assert service(case.conn).get(draft["draft_ref"])["status"] == "editing"


def test_invalid_due_date_is_not_on_time(trial_case):
    case = trial_case
    case.conn.execute("UPDATE Batches SET due_date='bad date' WHERE batch_id='B1'")
    case.conn.commit()
    draft = create(case)
    result = draft["comparison"]
    assert result["late_count"] is None
    assert result["batches"][0]["risk"] == "invalid_data"


def test_real_partial_candidate_keeps_unplanned_original_scope(trial_case):
    case = trial_case
    case.batch("B2", ready_status="no")
    case.operation("B2")
    case.conn.commit()
    accepted = case.accept(settings=case.settings("B1", "B2"))
    result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    draft = create(case, {"base": {"candidate_ref": result["candidates"][0]["candidate_ref"]}})
    assert draft["task_count"] == 1
    assert draft["scope_complete"] is False
    assert len(draft["unplanned_operations"]) == 1
    assert draft["unplanned_operations"][0]["batch_ref"] == case.ref("batch", "B2")
    assert "trial_base_incomplete" in issue_codes(draft)
    assert draft["comparison"]["late_count"] is None
