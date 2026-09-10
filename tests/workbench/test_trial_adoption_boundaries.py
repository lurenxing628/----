"""Saved conflicts, post-preview drift and missing evidence cannot publish."""

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.trial_adoption_validation import validate_trial_adoption
from tests.workbench.test_run_candidate_support import corrupt_update
from tests.workbench.trial_adoption_support import INTENT, KEY, full_plan, preview, saved_scenario, service
from tests.workbench.trial_adoption_support import trial_case as trial_case
from tests.workbench.trial_support import change, create, snapshot
from tests.workbench.trial_support import service as trial_service


@pytest.mark.parametrize("kind", ["resource", "calendar", "precedence", "readiness", "process"])
def test_saved_conflicts_do_not_become_valid_through_http_success(trial_case, kind):
    case = trial_case
    if kind == "precedence":
        value, second = full_plan(case)
        case.conn.execute("UPDATE Schedule SET start_time='2026-09-09T08:00:00',end_time='2026-09-09T08:45:00' WHERE op_id=?", (second,))
    else:
        case.plan(1, [case.op_id], end="2026-09-09T11:00:00")
        value = {"base": {"plan_ref": case.plan_ref(1)}}
    if kind == "calendar":
        case.conn.execute("INSERT INTO OperatorCalendar(operator_id,date,shift_hours,efficiency) VALUES ('O1','2026-09-09',8,0.5)")
    elif kind == "readiness":
        case.conn.execute("UPDATE Batches SET ready_status='no'")
    elif kind == "process":
        case.conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T2','Different process')")
        case.conn.execute("UPDATE Machines SET op_type_id='T2'")
    case.conn.commit()
    if kind == "resource":
        draft = create(case, value)
        draft = change(case, draft, operator="O1")["data"]
        saved = trial_service(case.conn).save(draft["draft_ref"], {"name": "Conflicted saved scene"},
            draft["write_context"]["write_token"], "cq-conflict-save-request")["data"]
    else:
        saved = saved_scenario(case, value, changed=False)
    before = snapshot(case.conn)
    result = service(case.conn).preview(saved["scenario_ref"])
    assert result["validation"]["can_adopt"] is False
    assert result["write_context"]["write_token"] is None
    with pytest.raises(WorkbenchCommandRejected):
        service(case.conn).adopt(saved["scenario_ref"], "fake", KEY, INTENT)
    assert snapshot(case.conn) == before


@pytest.mark.parametrize("kind", ["baseline", "execution", "resource", "calendar", "template", "lock", "hours"])
def test_confirm_rechecks_drift_after_valid_preview(trial_case, kind):
    case = trial_case
    saved = saved_scenario(case)
    token = preview(case, saved)
    if kind == "baseline":
        case.plan(2, [case.op_id])
    elif kind == "execution":
        case.command("create", case.task(1, case.op_id), case.values(quantity=1))
    else:
        sql = {"resource": "UPDATE Machines SET status='maintenance' WHERE machine_id='M2'",
               "calendar": "INSERT INTO WorkCalendar(date,shift_hours) VALUES ('2026-09-09',1)",
               "template": "INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,unit_hours) VALUES ('P1',1,'T1','Turning',5)",
               "lock": "UPDATE Schedule SET lock_status='locked'",
               "hours": "UPDATE BatchOperations SET unit_hours=5"}[kind]
        case.conn.execute(sql)
        case.conn.commit()
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        service(case.conn).adopt(saved["scenario_ref"], token, KEY, INTENT)
    assert error.value.status == 409 and snapshot(case.conn) == before
    assert service(case.conn).lookup(saved["scenario_ref"], KEY) is None


@pytest.mark.parametrize("kind", ["scenario_hash", "scenario_row", "draft_current", "receipt"])
def test_missing_or_inconsistent_saved_evidence_never_rebuilt(trial_case, kind):
    case = trial_case
    saved = saved_scenario(case)
    if kind == "scenario_hash":
        corrupt_update(case.conn, "WorkbenchTrialScenarios", "UPDATE WorkbenchTrialScenarios SET snapshot_hash='invalid'")
    elif kind == "scenario_row":
        corrupt_update(case.conn, "WorkbenchTrialScenarioRows", "DELETE FROM WorkbenchTrialScenarioRows")
    elif kind == "draft_current":
        corrupt_update(case.conn, "WorkbenchTrialRows", "UPDATE WorkbenchTrialRows SET current_json='{}'")
    else:
        case.conn.execute("PRAGMA foreign_keys=OFF")
        try:
            corrupt_update(case.conn, "WorkbenchCommandReceipts", "DELETE FROM WorkbenchCommandReceipts WHERE action='trial.save'")
        finally:
            case.conn.execute("PRAGMA foreign_keys=ON")
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected):
        validate_trial_adoption(case.conn, saved["scenario_ref"])
    assert snapshot(case.conn) == before


def test_wrong_token_subject_and_caller_transaction_cannot_write(trial_case):
    case = trial_case
    saved = saved_scenario(case)
    other = saved_scenario(case, {"base": saved["base"]}, suffix="0002")
    token = preview(case, saved)
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        service(case.conn).adopt(other["scenario_ref"], token, KEY, INTENT)
    assert error.value.code == "stale_write" and snapshot(case.conn) == before
    case.conn.execute("BEGIN")
    try:
        with pytest.raises(RuntimeError):
            service(case.conn).adopt(saved["scenario_ref"], token, KEY, INTENT)
        assert case.conn.in_transaction
    finally:
        case.conn.rollback()
    assert snapshot(case.conn) == before


def test_missing_schema_is_not_installed_on_preview(trial_case):
    case = trial_case
    saved = saved_scenario(case)
    case.conn.execute("DROP TABLE ScheduleVersionSeq")
    case.conn.commit()
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        service(case.conn).preview(saved["scenario_ref"])
    assert error.value.code == "adoption_schema_unavailable" and snapshot(case.conn) == before

