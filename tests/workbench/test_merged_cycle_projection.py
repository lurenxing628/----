"""NULL group members are not missing cycles; damaged facts stay visible."""

import pytest

from tests.workbench.merged_cycle_projection_support import (
    assert_group_cycle,
    issue_codes,
    merged_cycle_application,
    operation,
    readonly_detail,
)
from tests.workbench.process_stage_api_support import PART


@pytest.mark.parametrize("state", ("legacy", "source", "hours", "ready"))
def test_valid_null_cycles_preserve_legacy_and_managed_confirmations(merged_cycle_api, state):
    api = merged_cycle_api
    if state != "legacy":
        api.prepare("source" if state == "source" else "hours")
    if state == "ready":
        api.confirm("hours_confirm", api.hours())
    entity = readonly_detail(api)
    assert entity["workflow"]["origin"] == ("legacy" if state == "legacy" else "managed")
    assert entity["workflow"]["stage"] == ("source" if state == "legacy" else state)
    assert entity["workflow"]["ready"] == (state == "ready")
    for seq, total in ((20, 6.75), (25, 6.75), (40, 9.5)):
        assert_group_cycle(entity, seq, total)
        assert operation(entity, seq)["confirmation"]["hours"]["state"] == (
            "confirmed" if state == "ready" else "unconfirmed")
    if state == "legacy":
        assert "legacy_confirmation_unknown" in issue_codes(entity)


@pytest.mark.parametrize("change,group_code,member_code", [
    ("UPDATE ExternalGroups SET merge_mode='unknown' WHERE group_id='PROC-G'", "external_group_mode_unknown", None),
    ("UPDATE ExternalGroups SET merge_mode='separate' WHERE group_id='PROC-G'", None, None),
    ("UPDATE PartOperations SET ext_group_id='absent' WHERE seq=20 AND part_no='PROC-001'", None, "relation_missing"),
    ("UPDATE PartOperations SET ext_group_id=NULL WHERE seq=20 AND part_no='PROC-001'", None, None),
    ("UPDATE ExternalGroups SET part_no='PROC-002' WHERE group_id='PROC-G'", None, "external_group_part_mismatch"),
    ("UPDATE ExternalGroups SET start_seq=26 WHERE group_id='PROC-G'", "external_group_range_invalid", None),
    ("UPDATE ExternalGroups SET start_seq='bad' WHERE group_id='PROC-G'", "external_group_range_invalid", None),
    ("UPDATE ExternalGroups SET start_seq=21 WHERE group_id='PROC-G'", "external_group_members_invalid", None),
    ("UPDATE PartOperations SET source='internal' WHERE seq=25 AND part_no='PROC-001'", "external_group_members_invalid", None),
    ("UPDATE PartOperations SET part_no='PROC-002' WHERE seq=25 AND part_no='PROC-001'", "external_group_part_mismatch", None),
])
def test_invalid_group_never_supplies_a_missing_member_cycle(merged_cycle_api, change, group_code, member_code):
    api = merged_cycle_api
    api.execute(change)
    entity = readonly_detail(api)
    row = operation(entity)
    assert row["external_days"] is None and row["external_days_source"] is None
    assert "value_missing" in issue_codes(row)
    if member_code:
        assert member_code in issue_codes(row)
    if group_code:
        group = next(item for item in entity["external_groups"] if item["ref"] == row["external_group_ref"])
        assert group_code in issue_codes(group)
        assert "external_group_invalid" in issue_codes(row)
    assert_group_cycle(entity, 40, 9.5)


@pytest.mark.parametrize("total,code", [(None, "value_missing"), (0, "value_invalid"),
                                       ("bad", "value_invalid"), (float("inf"), "value_invalid")])
def test_invalid_total_is_not_replaced_by_member_or_supplier_defaults(merged_cycle_api, total, code):
    api = merged_cycle_api
    api.execute("UPDATE ExternalGroups SET total_days=? WHERE group_id='PROC-G'", (total,))
    entity = readonly_detail(api)
    row = operation(entity)
    group = next(item for item in entity["external_groups"] if item["ref"] == row["external_group_ref"])
    assert group["total_days"] is None and code in issue_codes(group)
    assert row["external_days_source"] is None and "value_missing" in issue_codes(row)
    assert "external_group_invalid" in issue_codes(row)
    assert_group_cycle(entity, 40, 9.5)


@pytest.mark.parametrize("value", (0, -1, "bad", float("inf"), 3.25))
def test_nonnull_member_cycles_keep_their_own_validation(merged_cycle_api, value):
    api = merged_cycle_api
    api.execute("UPDATE PartOperations SET ext_days=? WHERE part_no=? AND seq=20", (value, PART))
    entity = readonly_detail(api)
    row = operation(entity)
    if value == 3.25:
        assert row["external_days"] == value and row["external_days_source"] == "operation"
        assert row["issues"] == []
    else:
        assert row["external_days"] is None and row["external_days_source"] is None
        assert "value_invalid" in issue_codes(row) and "value_missing" not in issue_codes(row)
    assert_group_cycle(entity, 25)


def test_only_active_members_affect_group_validity(merged_cycle_api):
    api = merged_cycle_api
    api.execute("UPDATE PartOperations SET status='deleted',seq=99,source='internal' WHERE part_no=? AND seq=25", (PART,))
    entity = readonly_detail(api)
    assert_group_cycle(entity)
    assert operation(entity, 99)["external_days_source"] is None
