"""Real HTTP hours confirmation and snapshot refresh retain original templates."""

import pytest

from tests.workbench.merged_cycle_projection_support import (
    assert_group_cycle,
    issue_codes,
    merged_cycle_application,
    operation,
    readonly_detail,
)
from tests.workbench.process_stage_api_support import PART, rejected


def test_hours_save_removes_false_warning_without_rewriting_members(merged_cycle_api):
    api = merged_cycle_api
    api.prepare()
    before = api.preserved()
    original_refs = api.rows("WorkbenchEntityRefs")
    original_confirmations = api.rows("WorkbenchProcessOperationConfirmations", "stage='source'")
    pending = readonly_detail(api)
    assert not pending["workflow"]["ready"]
    assert_group_cycle(pending)
    payload = api.hours()
    for row in payload["groups"]:
        if row["total_days"] == 6.75:
            row["total_days"] = 7.25
    result = api.confirm("hours_confirm", payload)
    assert result["result"] == "committed" and result["replayed"] is False
    after = api.preserved()
    changed_tables = {"ExternalGroups", "WorkbenchEntityRefs"}
    assert {name: rows for name, rows in after.items() if name not in changed_tables} == {
        name: rows for name, rows in before.items() if name not in changed_tables}
    assert api.rows("WorkbenchEntityRefs") == [
        {**row, "revision": row["revision"] + 1}
        if row["kind"] == "template_external_group" and row["entity_key"] == "PROC-G" else row
        for row in original_refs]
    with api.database() as conn:
        names = [row[1] for row in conn.execute("PRAGMA table_info(ExternalGroups)")]
    key, total = names.index("group_id"), names.index("total_days")
    expected = []
    for row in before["ExternalGroups"]:
        values = list(row)
        if row[key] == "PROC-G":
            values[total] = 7.25
        expected.append(tuple(values))
    assert after["ExternalGroups"] == tuple(expected)
    assert api.rows("WorkbenchProcessOperationConfirmations", "stage='source'") == original_confirmations
    final = readonly_detail(api)
    assert final["workflow"]["ready"] is True
    for seq, days in ((20, 7.25), (25, 7.25), (40, 9.5)):
        assert_group_cycle(final, seq, days)
        assert operation(final, seq)["confirmation"]["hours"]["state"] == "confirmed"


@pytest.mark.parametrize("damage", ("total", "member"))
def test_saved_confirmation_is_not_fabricated_after_fact_damage(merged_cycle_api, damage):
    api = merged_cycle_api
    api.prepare()
    api.confirm("hours_confirm", api.hours())
    stored_confirmations = api.rows("WorkbenchProcessOperationConfirmations")
    stored_workflow = api.rows("WorkbenchProcessWorkflow")
    api.execute("UPDATE ExternalGroups SET total_days=NULL WHERE group_id='PROC-G'" if damage == "total" else
                "UPDATE PartOperations SET ext_days=-1 WHERE part_no='PROC-001' AND seq=20")
    entity = readonly_detail(api)
    assert entity["workflow"]["stage"] == "hours" and not entity["workflow"]["ready"]
    row = operation(entity)
    assert row["confirmation"]["hours"]["state"] == "unconfirmed"
    assert ("value_missing" if damage == "total" else "value_invalid") in issue_codes(row)
    assert api.rows("WorkbenchProcessOperationConfirmations") == stored_confirmations
    assert api.rows("WorkbenchProcessWorkflow") == stored_workflow


def test_separate_null_confirmation_is_rejected_without_any_table_changes(merged_cycle_api):
    api = merged_cycle_api
    api.execute("UPDATE ExternalGroups SET merge_mode='separate' WHERE group_id='PROC-G'")
    api.prepare()
    row = operation(readonly_detail(api))
    assert "value_missing" in issue_codes(row) and row["external_days_source"] is None
    body = api.body("hours_confirm", api.hours())
    before = api.snapshot()
    rejected(api.post("hours_confirm", body), "external_days_required", 422)
    assert api.snapshot() == before
    assert all(row["ext_days"] is None for row in api.rows("PartOperations", "part_no=? AND source='external'", (PART,)))
