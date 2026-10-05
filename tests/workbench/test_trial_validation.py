"""Real calendar, qualification, execution ledger and editable business conflicts."""

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from tests.workbench.trial_support import change, create, service, snapshot
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


@pytest.mark.parametrize("state", ["new_complete"])
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
