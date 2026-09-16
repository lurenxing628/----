"""Template replacement explains and atomically applies complete source facts."""

import pytest

from tests.workbench.batch_support import assert_error, batch_database, detail, ref_for, state
from tests.workbench.identity_metadata_support import insert_row
from tests.workbench.test_batch_actions import confirm, sync_preview

_batch_fixture = batch_database


def internal_template(client):
    conn = client.batch_conn
    conn.execute("UPDATE PartOperations SET source='internal',setup_hours=0.5,unit_hours=0.125,ext_group_id=NULL,ext_days=NULL,supplier_id=NULL")
    conn.commit()


def test_preview_lists_changes_and_exact_resource_assignments_to_clear(batch_client):
    client, conn = batch_client, batch_client.batch_conn
    internal_template(client)
    conn.execute("UPDATE BatchOperations SET machine_id='M1',operator_id='O1' WHERE batch_id='FREE-001'")
    insert_row(conn, "PartOperations", dict(part_no="P1", seq=2, op_type_id="OT1", op_type_name="finish", source="internal", setup_hours=0, unit_hours=0.1, status="active"))
    insert_row(conn, "BatchOperations", dict(batch_id="FREE-001", op_code="FREE-001_03", seq=3, op_type_id="OT1", op_type_name="old", source="internal", setup_hours=1, unit_hours=1, status="pending"))
    conn.commit()
    before = state(client)
    preview = sync_preview(client).get_json()["data"]
    assert state(client) == before
    assert preview["completeness_checked"] is True
    assert preview["change_counts"] == {"added": 1, "removed": 1, "updated": 1, "unchanged": 0}
    assert [row["sequence"] for row in preview["changes"]] == [1, 2, 3]
    cleared = preview["cleared_resources"]
    assert len(cleared) == 1 and cleared[0]["business_code"] == "FREE-001_01"
    assert cleared[0]["machine"]["business_code"] == "M1" and cleared[0]["operator"]["business_code"] == "O1"
    response = confirm(client, preview, "/" + ref_for(client) + "/sync-confirm")
    assert response.status_code == 200, response.get_json()
    after = detail(client)["data"]["operations"]
    assert [row["sequence"] for row in after] == [1, 2]
    assert all(row["machine_ref"] is None and row["operator_ref"] is None for row in after)


def test_replacement_failure_after_delete_keeps_original_operations_and_refs(batch_client, monkeypatch):
    from core.services.workbench.template_lineage import TemplateLineageWriter

    client = batch_client
    internal_template(client)
    insert_row(client.batch_conn, "PartOperations", dict(part_no="P1", seq=2, op_type_id="OT1", op_type_name="finish", source="internal", setup_hours=0, unit_hours=0.1, status="active"))
    client.batch_conn.commit()
    preview = sync_preview(client).get_json()["data"]
    before = state(client)
    original, calls = TemplateLineageWriter.copy_template, []

    def fail_copy(*args, **kwargs):
        calls.append(args)
        if len(calls) == 2:
            raise RuntimeError("fixture template copy failed after first replacement row")
        return original(*args, **kwargs)

    monkeypatch.setattr(TemplateLineageWriter, "copy_template", fail_copy)
    result = confirm(client, preview, "/" + ref_for(client) + "/sync-confirm").get_json()
    assert result["ok"] is False and result["committed"] == "unknown"
    assert len(calls) == 2
    assert state(client) == before


def test_template_changes_after_preview_reject_without_replacing_operations(batch_client):
    client, conn = batch_client, batch_client.batch_conn
    internal_template(client)
    preview = sync_preview(client).get_json()["data"]
    conn.execute("UPDATE PartOperations SET unit_hours=NULL")
    conn.commit()
    before = state(client)
    assert_error(confirm(client, preview, "/" + ref_for(client) + "/sync-confirm"), "stale_write")
    assert state(client) == before


def test_merged_cycle_uses_group_value_and_does_not_require_hidden_internal_hours(batch_client):
    client, conn = batch_client, batch_client.batch_conn
    conn.execute("UPDATE PartOperations SET setup_hours=NULL,unit_hours=NULL,ext_days=NULL")
    conn.execute("UPDATE ExternalGroups SET merge_mode='merged',total_days=2")
    conn.commit()
    response = sync_preview(client)
    assert response.status_code == 200, response.get_json()
    after = response.get_json()["data"]["after"][0]
    assert after["external_group"] == {"merge_mode": "merged", "total_days": 2}
    assert after["setup_hours"] is None and after["unit_hours"] is None and after["external_days"] is None
    conn.execute("UPDATE ExternalGroups SET total_days=NULL")
    conn.commit()
    before = state(client)
    rejected = assert_error(sync_preview(client), "constraint_conflict")
    assert "整组外协周期未填写" in rejected["error"]["message"]
    assert state(client) == before


def test_protected_batch_explains_each_blocked_action(batch_client):
    entity = detail(batch_client, ref_for(batch_client, key="B1"))["data"]
    assert entity["protected"]
    reasons = {row["action"]: row["message"] for row in entity["write_context"]["blocked_reasons"]}
    for action in ("batch.delete", "batch.sync_confirm", "batch.operation_update"):
        assert action in reasons and "已有排产" in reasons[action]


@pytest.mark.parametrize("sql,expected", [
    ("UPDATE PartOperations SET op_type_id=NULL", "缺少明确工种"),
    ("UPDATE Suppliers SET status='inactive'", "供应商不存在或已停用"),
    ("UPDATE PartOperations SET status='inactive'", "尚未录入有效工序"),
])
def test_missing_source_facts_disable_preview_and_preserve_batch(batch_client, sql, expected):
    client = batch_client
    client.batch_conn.execute(sql)
    client.batch_conn.commit()
    before = state(client)
    entity = detail(client)["data"]
    assert not entity["template"]["complete"]
    assert entity["write_context"]["capabilities"]["batch.sync_confirm"] is False
    assert expected in " ".join(row["message"] for row in entity["template"]["diagnostics"])
    rejected = assert_error(sync_preview(client), "constraint_conflict")
    assert expected in rejected["error"]["message"]
    assert state(client) == before
