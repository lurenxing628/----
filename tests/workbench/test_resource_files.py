"""Four-kind sparse upsert, explicit relations and lossless read-only roundtrips."""

from unittest.mock import patch

import pytest

from core.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.models.workbench_resource_file import public_columns
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.resource_files import WorkbenchResourceFileService
from tests.workbench.identity_metadata_support import business_snapshot
from tests.workbench.resource_entity_support import create_catalog
from tests.workbench.resource_file_support import (
    SCOPES,
    TABLES,
    confirm,
    decode,
    exported,
    file_bytes,
    ref,
    resource_database,
    scope,
    snapshot,
)
from tests.workbench.resource_file_support import existing_raw as raw


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
@pytest.mark.parametrize("kind,category", SCOPES)
def test_all_resources_upsert_and_blanks_preserve_fields(resource_conn, fmt, kind, category):
    conn = resource_conn
    table, key = TABLES[kind]
    code = "EXT" if category == "external" else {"op_type": "OT1", "machine": "M1", "operator": "O1", "supplier": "S1"}[kind]
    conn.execute(f"ALTER TABLE {table} ADD COLUMN hidden_fact TEXT DEFAULT 'keep hidden'")
    conn.commit()
    old = raw(conn, kind, code)
    headers = ["business_code", "label"] + (["category"] if kind == "op_type" else ["status"])
    rows = [[code, "updated " + code, None], ["000123", "new " + kind, category or "active"]]
    if kind == "supplier":
        headers.append("default_days")
        rows[0].append(None)
        rows[1].append(2.5)
    content = file_bytes(rows, fmt, headers)
    service = WorkbenchResourceFileService(conn, kind)
    before, changes = snapshot(conn), conn.total_changes
    preview = service.preview_import(content, file_format=fmt, scope=scope(category))
    assert [row["result"] for row in preview.as_dict()["rows"]] == ["update", "new"]
    assert snapshot(conn) == before and conn.total_changes == changes
    outcome = confirm(conn, kind, preview, content, fmt)
    assert outcome["result"] == "committed"
    current = raw(conn, kind, code)
    assert current["name"] == "updated " + code
    assert {k: v for k, v in current.items() if k not in ("name", "updated_at")} == {k: v for k, v in old.items() if k not in ("name", "updated_at")}
    assert raw(conn, kind, "000123")["hidden_fact"] == "keep hidden"


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
@pytest.mark.parametrize("kind,category", SCOPES)
def test_readonly_export_roundtrip_keeps_unknown_and_original_relations(resource_conn, fmt, kind, category):
    conn = resource_conn
    table, _ = TABLES[kind]
    if kind != "op_type":
        conn.execute(f"UPDATE {table} SET status='legacy HOLD '")
    conn.execute(f"UPDATE {table} SET remark=?", ("  \\N old,\n'fact  ",))
    conn.commit()
    before, changes = business_snapshot(conn), conn.total_changes
    download = exported(conn, kind, fmt, category=category)
    headers, rows = decode(download, fmt)
    assert len(rows) == download.row_count
    assert headers == [item["label"] for item in public_columns(kind)]
    preview = WorkbenchResourceFileService(conn, kind).preview_import(download.content, file_format=fmt, scope=scope(category))
    assert preview.as_dict()["summary"]["unchanged"] == download.row_count
    assert conn.total_changes == changes
    assert confirm(conn, kind, preview, download.content, fmt)["result"] == "unchanged"
    assert business_snapshot(conn) == before


@pytest.mark.parametrize("kind,field,code", [("machine", "category", "M1"), ("machine", "remark", "M1"),
                                            ("operator", "remark", "O1"), ("supplier", "remark", "S1"),
                                            ("op_type", "default_hours", "OT1"), ("machine", "created_at", "M1")])
def test_readonly_columns_are_reference_values_not_changes(resource_conn, kind, field, code):
    value = 99 if field == "default_hours" else "reference only"
    content = file_bytes([[code, value]], headers=("business_code", field))
    preview = WorkbenchResourceFileService(resource_conn, kind).preview_import(content, file_format="csv", scope=scope("internal" if kind == "op_type" else None))
    row = preview.as_dict()["rows"][0]
    assert row["result"] == "unchanged" and row["reference_fields"] == [field]
    assert row["input"]["fields"] == {} and not row["input"].get("relationships")
    before = business_snapshot(resource_conn)
    assert confirm(resource_conn, kind, preview, content)["result"] == "unchanged"
    assert business_snapshot(resource_conn) == before


@pytest.mark.parametrize("kind,code,field,value", [
    ("machine", "M1", "op_type_code", "OT2"), ("operator", "O1", "skill_codes", '["OT1","OT2"]'),
    ("supplier", "S1", "op_type_codes", '["EXT"]'),
])
def test_relations_resolve_business_codes_and_warn_without_authorizing_machines(resource_conn, kind, code, field, value):
    before = [tuple(row) for row in resource_conn.execute("SELECT * FROM OperatorMachine")]
    content = file_bytes([[code, value]], headers=("business_code", field))
    service = WorkbenchResourceFileService(resource_conn, kind)
    preview = service.preview_import(content, file_format="csv", scope={})
    row = preview.as_dict()["rows"][0]
    assert row["result"] == "update" and row["requires_confirmation"]
    assert field in row["changes"]
    confirm(resource_conn, kind, preview, content)
    assert [tuple(row) for row in resource_conn.execute("SELECT * FROM OperatorMachine")] == before
    reread = service.preview_import(content, file_format="csv", scope={})
    assert reread.as_dict()["summary"]["unchanged"] == 1


def test_group_shift_and_explicit_clears_cover_current_form_relations(resource_conn):
    create_catalog(resource_conn, "machine_group")
    create_catalog(resource_conn, "shift_profile")
    for kind, code, field, selected in (("machine", "M1", "group_code", "G1"), ("operator", "O1", "shift_profile_code", "SHIFT1")):
        for value in (selected, r"\N"):
            content = file_bytes([[code, value]], headers=("business_code", field))
            preview = WorkbenchResourceFileService(resource_conn, kind).preview_import(content, file_format="csv", scope={})
            assert preview.as_dict()["summary"]["update"] == 1
            confirm(resource_conn, kind, preview, content)
    for value in ("capacity note", r"\N"):
        content = file_bytes([["OT1", value]], headers=("business_code", "remark"))
        preview = WorkbenchResourceFileService(resource_conn, "op_type").preview_import(content, file_format="csv", scope=scope("internal"))
        confirm(resource_conn, "op_type", preview, content)
    assert raw(resource_conn, "op_type", "OT1")["remark"] is None


@pytest.mark.parametrize("kind,code,field,value", [
    ("machine", "M1", "op_type_code", "EXT"), ("machine", "M1", "op_type_code", "missing"),
    ("operator", "O1", "skill_codes", '["EXT"]'), ("supplier", "S1", "op_type_codes", '["OT2"]'),
    ("operator", "O1", "skill_codes", "OT1,OT2"), ("operator", "O1", "skill_codes", '["OT1","OT1"]'),
    ("operator", "O1", "skill_codes", r"\N"), ("machine", "M1", "status", r"\N"),
    ("op_type", "OT1", "category", "external"), ("op_type", "EXT", "category", "internal"),
    ("op_type", "OT1", "remark", "   "), ("op_type", "OT1", "default_merge_mode", "merged"),
])
def test_bad_relations_nulls_and_cross_category_reject(resource_conn, kind, code, field, value):
    content = file_bytes([[code, value]], headers=("business_code", field))
    preview = WorkbenchResourceFileService(resource_conn, kind).preview_import(content, file_format="csv", scope=scope("internal" if kind == "op_type" else None))
    assert preview.as_dict()["summary"]["rejected"] == 1


def test_external_policy_is_writable_only_in_bound_category(resource_conn):
    service = WorkbenchResourceFileService(resource_conn, "op_type")
    for value in ("merged", "separate", r"\N"):
        content = file_bytes([["EXT", value]], headers=("business_code", "default_merge_mode"))
        preview = service.preview_import(content, file_format="csv", scope=scope("external"))
        assert preview.as_dict()["summary"]["update"] == 1
        confirm(resource_conn, "op_type", preview, content)


@pytest.mark.parametrize("kind,category", SCOPES)
def test_new_required_values_and_duplicate_codes_rejected(resource_conn, kind, category):
    service = WorkbenchResourceFileService(resource_conn, kind)
    content = file_bytes([["DUP", "same", "active"], ["DUP", "same", "active"]], headers=("business_code", "label", "status") if kind != "op_type" else ("business_code", "label", "remark"))
    assert service.preview_import(content, file_format="csv", scope=scope(category)).as_dict()["summary"]["rejected"] == 2
    content = file_bytes([["NO-NAME"]], headers=("business_code",))
    assert service.preview_import(content, file_format="csv", scope=scope(category)).as_dict()["summary"]["rejected"] == 1


def test_import_original_facts_and_selected_relation_change_reject_atomically(resource_conn):
    content = file_bytes([["M1", "changed", "OT2"], ["NEW", "new", "OT2"]], headers=("business_code", "label", "op_type_code"))
    service = WorkbenchResourceFileService(resource_conn, "machine")
    preview = service.preview_import(content, file_format="csv", scope={})
    resource_conn.execute("UPDATE OpTypes SET remark='concurrent' WHERE op_type_id='OT2'")
    resource_conn.commit()
    before = snapshot(resource_conn)
    with pytest.raises(WorkbenchCommandRejected) as exc:
        confirm(resource_conn, "machine", preview, content)
    assert exc.value.code == "stale_write" and snapshot(resource_conn) == before


@pytest.mark.parametrize("failure", ("last_write", "receipt"))
def test_import_rollback_and_receipt_before_dead_preview(resource_conn, failure):
    content = file_bytes([["M1", "changed", "active"], ["NEW", "new", "active"]])
    service = WorkbenchResourceFileService(resource_conn, "machine")
    preview = service.preview_import(content, file_format="csv", scope={})
    command = WorkbenchCommandService(resource_conn)
    original = type(service.adapter).apply
    def fail(adapter, action, payload, identity=None):
        result = original(adapter, action, payload, identity)
        if failure == "last_write" and payload.get("business_code") == "NEW":
            raise RuntimeError("after last write")
        return result
    before = snapshot(resource_conn)
    with patch.object(type(service.adapter), "apply", fail):
        if failure == "receipt":
            command.repo.insert = lambda **_: (_ for _ in ()).throw(RuntimeError("receipt failure"))
        with pytest.raises(WorkbenchCommandUncertain):
            confirm(resource_conn, "machine", preview, content, command=command)
    assert snapshot(resource_conn) == before
    first = confirm(resource_conn, "machine", preview, content, key="replay-resource-import")
    replay = confirm(resource_conn, "machine", preview, content, key="replay-resource-import", guard=lambda: pytest.fail("expired preview guard must not run"))
    assert replay == {**first, "replayed": True}
