"""Real calendar, qualification, execution ledger and editable business conflicts."""

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from tests.workbench.trial_support import change, create, official, service, snapshot
from tests.workbench.trial_support import trial_case as trial_case


def codes(data):
    return {row["code"] for row in data["validation"]["issues"]}


def test_resources_and_start_one_change_and_conflict_remains_editable(trial_case):
    case = trial_case
    draft = create(case)
    conflicted = change(case, draft, operator="O1")["data"]
    assert "machine_authorization_missing" in codes(conflicted)
    assert conflicted["validation"]["can_adopt"] is False
    assert conflicted["tasks"][0]["edit_context"]["can_change"] is True
    fixed = change(case, conflicted, key="trial-change-00000002")["data"]
    assert fixed["validation"]["constraints_status"] == "valid", fixed["validation"]
    rows = case.conn.execute("SELECT before_json,after_json FROM WorkbenchTrialChanges ORDER BY revision").fetchall()
    assert len(rows) == 2


def test_no_default_person_and_no_client_duration(trial_case):
    case = trial_case
    draft = create(case)
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        change(case, draft, operator=None)
    assert error.value.code == "resource_required"
    assert snapshot(case.conn) == before
    with pytest.raises(WorkbenchCommandRejected):
        service(case.conn).change(draft["draft_ref"], {"task_ref": draft["tasks"][0]["task_ref"],
            "machine_ref": case.ref("machine", "M2"), "operator_ref": case.ref("operator", "O2"),
            "start": "2026-09-09T13:00:00", "end": "2026-09-09T14:00:00"}, draft["write_context"]["write_token"], "trial-change-00000002")


def test_real_person_calendar_efficiency_and_cross_day_duration(trial_case):
    case = trial_case
    case.conn.execute("""INSERT INTO OperatorCalendar(operator_id,date,day_type,shift_start,shift_hours,efficiency,allow_normal,allow_urgent)
        VALUES ('O2','2026-09-09','workday','08:00',8,0.5,'yes','yes')""")
    case.conn.commit()
    draft = create(case)
    task = change(case, draft, start="2026-09-09T14:00:00")["data"]["tasks"][0]
    assert task["hours"]["total_hours"] == 3
    assert task["end"] == "2026-09-10T12:00:00"


@pytest.mark.parametrize("state", ["lock", "new_start", "new_complete", "legacy_finish"])
def test_fixed_and_unique_execution_projection_protect_changes(trial_case, state):
    case = trial_case
    draft = create(case)
    if state == "lock":
        case.conn.execute("UPDATE Schedule SET lock_status='locked'")
        case.conn.commit()
    elif state == "legacy_finish":
        case.event(case.op_id, "start")
        case.event(case.op_id, "finish")
    else:
        values = case.values(quantity=3 if state == "new_complete" else 1,
                             effective_processing_hours=1, actual_end="2026-09-09T10:00:00" if state == "new_complete" else None)
        case.command("create", case.task(1, case.op_id), values)
    refreshed = service(case.conn).get(draft["draft_ref"])
    assert refreshed["tasks"][0]["edit_context"]["can_change"] is False
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected):
        change(case, refreshed)
    assert snapshot(case.conn) == before


def test_full_chain_and_outside_scope_machine_operator_overlap(trial_case):
    case = trial_case
    second = case.operation(seq=2)
    case.batch("B2")
    third = case.operation("B2")
    case.conn.commit()
    draft = create(case, official(case, ids=[case.op_id, second, third]))
    assert {"machine_overlap", "operator_overlap", "precedence_violation"} <= codes(draft)
    conflicted = change(case, draft, start="2026-09-09T09:00:00", machine="M1", operator="O1")["data"]
    assert conflicted["validation"]["constraints_status"] == "blocked"
    saved = service(case.conn).save(draft["draft_ref"], {"name": "Conflict retained"}, conflicted["write_context"]["write_token"], "trial-save-0000000001")["data"]
    assert saved["validation"]["can_adopt"] is False


def test_unknown_hours_explicit_zero_and_piece_quantity(trial_case):
    case = trial_case
    case.conn.execute("UPDATE BatchOperations SET unit_hours=0,setup_hours=0 WHERE id=?", (case.op_id,))
    case.conn.commit()
    draft = create(case)
    assert "zero_or_invalid_duration" in codes(draft)
    with pytest.raises(WorkbenchCommandRejected) as error:
        change(case, draft)
    assert error.value.code == "zero_or_invalid_duration"


def test_piece_uses_ledger_target_not_whole_batch(trial_case):
    case = trial_case
    case.conn.execute("UPDATE BatchOperations SET piece_id='piece-A' WHERE id=?", (case.op_id,))
    case.conn.commit()
    draft = create(case, official(case, end="2026-09-09T09:00:00"))
    assert draft["tasks"][0]["hours"]["quantity"] == 1
    changed = change(case, draft)["data"]
    assert changed["tasks"][0]["end"] == "2026-09-09T14:00:00"
