"""No-op relationship files keep historical primaries with linear row inspections."""

import pytest
from flask import Blueprint, Flask, g

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_resource_query import ResourcePageRequest
from core.services.workbench.facts import file_writer
from core.services.workbench.resource.queries import WorkbenchResourceQueryService
from core.services.workbench.resource.relation_files import files as module
from core.services.workbench.resource.relation_files.file_codec import read_relation_file
from core.services.workbench.resource.relation_files.file_writer import write_relation_file
from tests.workbench.calendar_file_support import file_bytes
from tests.workbench.identity_metadata_support import insert_row
from tests.workbench.resource_entity_support import identity_for, resource_database, resource_row  # noqa: F401
from web.routes.workbench.relation_files import register_relation_file_routes
from web.routes.workbench.resources import register_resource_routes


def test_primary_planning_groups_rows_once_and_preserves_unchanged_legacy_groups(monkeypatch):
    count = 300
    rows = [{"errors": [], "values": {"operator_code": f"O{i}", "machine_code": "M1",
             "skill_level": "normal", "is_primary": "no"}} for i in range(count)]
    current = {f"O{i}": {"M1": {"skill_level": "normal", "is_primary": "no"}} for i in range(count)}
    rows.append({"errors": [], "values": {"operator_code": "legacy", "machine_code": "M1", "is_primary": "yes"}})
    rows.append({"errors": [], "values": {"operator_code": "legacy", "machine_code": "M2", "is_primary": "yes"}})
    current["legacy"] = {code: {"skill_level": "normal", "is_primary": "yes"} for code in ("M1", "M2")}
    inspections, original = [], module._blocked

    def captured(row):
        inspections.append(True)
        return original(row)

    monkeypatch.setattr(module, "_blocked", captured)
    result = object.__new__(module.WorkbenchRelationFileService)._final_primaries(rows, current)
    assert all(not result[f"O{i}"] for i in range(count))
    assert result["legacy"] == {"M1", "M2"} and all(not row["errors"] for row in rows)
    assert len(inspections) <= 4 * len(rows)


def _replaced_primaries(current, primaries):
    return {operator: [code for code, link in sorted(links.items())
                       if link["is_primary"] == "yes" and code not in primaries[operator]]
            for operator, links in current.items()}


def test_primary_notes_cover_unchanged_claim_demoting_legacy_primary_without_false_positive_on_blank():
    service = object.__new__(module.WorkbenchRelationFileService)
    current = {
        "O1": {
            "M1": {"skill_level": "normal", "is_primary": "yes"},
            "M2": {"skill_level": "normal", "is_primary": "yes"},
            "M3": {"skill_level": "normal", "is_primary": "no"},
        }
    }
    claim_rows = [
        {"row": 1, "errors": [], "notes": [], "requires_confirmation": False,
         "values": {"operator_code": "O1", "machine_code": "M1", "skill_level": "normal", "is_primary": "yes"}},
        {"row": 2, "errors": [], "notes": [], "requires_confirmation": False,
         "values": {"operator_code": "O1", "machine_code": "M3", "skill_level": "expert", "is_primary": None}},
    ]
    primaries = service._final_primaries(claim_rows, current)
    assert primaries["O1"] == {"M1"}
    replaced = _replaced_primaries(current, primaries)
    for row in claim_rows:
        service._classify(row, current, primaries, replaced)
    assert claim_rows[0]["result"] == "unchanged"
    assert claim_rows[0]["notes"] == ["确认后 M2 不再是这个人的主操设备。"]
    assert claim_rows[0]["requires_confirmation"] is True

    drop_rows = [
        {"row": 1, "errors": [], "notes": [], "requires_confirmation": False,
         "values": {"operator_code": "O1", "machine_code": "M1", "skill_level": "expert", "is_primary": None}},
        {"row": 2, "errors": [], "notes": [], "requires_confirmation": False,
         "values": {"operator_code": "O1", "machine_code": "M2", "skill_level": None, "is_primary": "no"}},
    ]
    primaries = service._final_primaries(drop_rows, current)
    assert primaries["O1"] == {"M1"}
    replaced = _replaced_primaries(current, primaries)
    for row in drop_rows:
        service._classify(row, current, primaries, replaced)
    assert drop_rows[0]["result"] == "update"
    assert drop_rows[0]["notes"] == []
    assert drop_rows[0]["requires_confirmation"] is False


def test_relation_export_in_read_snapshot_reuses_loaded_table_facts(resource_conn, monkeypatch):
    conn = resource_conn
    reader = WorkbenchResourceQueryService(conn, "operator")
    service = module.WorkbenchRelationFileService(conn, "operator_machine", reader=reader)
    operator = identity_for(conn, "operator")
    assert operator is not None

    statements = []
    conn.set_trace_callback(statements.append)
    try:
        with reader.read_snapshot() as scope:
            _, cold_count = service.preview_export(scope, "selected", request=ResourcePageRequest(kind="operator"),
                                                   selected_refs=[operator.ref])
    finally:
        conn.set_trace_callback(None)
    selects = [sql for sql in statements if sql.lstrip().upper().startswith("SELECT")]
    assert cold_count == 1 and len(selects) <= 3, selects

    def unexpected(*args, **kwargs):
        raise AssertionError("export inside read_snapshot must reuse table_facts instead of querying repo/links")

    monkeypatch.setattr(service.links, "list_simple_rows_for_operators", unexpected)
    monkeypatch.setattr(service.repo, "raw_many", unexpected)
    filtered_request = ResourcePageRequest(kind="operator", sort="skill_refs")
    with reader.read_snapshot() as scope:
        args, count = service.preview_export(scope, "filtered", request=filtered_request)
    with reader.read_snapshot() as scope:
        rows = service.export_rows(scope, **args)
    assert count >= 1 and len(rows) == count
    assert any(row["operator_code"] == "O1" and row["machine_code"] == "M1" for row in rows)

    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="relation-export-capacity")
    bp = Blueprint("relation_export_capacity", __name__)
    register_resource_routes(bp)
    register_relation_file_routes(bp)
    app.register_blueprint(bp)

    @app.before_request
    def _bind_db():
        g.db = conn

    client = app.test_client()
    listed = client.get("/api/workbench/v1/entities/operator", query_string={"query": "O1"})
    assert listed.status_code == 200
    preview = client.post(
        "/api/workbench/v1/relation-files/operator_machine/export-preview",
        json={
            "selection": "selected",
            "scope": {"query": "O1"},
            "snapshot_ref": listed.get_json()["meta"]["snapshot_ref"],
            "refs": [operator.ref],
        },
    )
    assert preview.status_code == 200
    export_ref = preview.get_json()["data"]["export_ref"]

    monkeypatch.setattr(file_writer, "XLSX_MAX_ROWS", 2)
    boundary_xlsx = client.get(
        "/api/workbench/v1/relation-files/operator_machine/export",
        query_string={"export_ref": export_ref, "format": "xlsx"},
    )
    assert boundary_xlsx.status_code == 200

    projected, original_rows_for = [], module.WorkbenchRelationFileService._rows_for

    def tracked_rows_for(self, scope, codes):
        projected.append(list(codes))
        return original_rows_for(self, scope, codes)

    monkeypatch.setattr(module.WorkbenchRelationFileService, "_rows_for", tracked_rows_for)
    monkeypatch.setattr(file_writer, "XLSX_MAX_ROWS", 1)
    over_xlsx = client.get(
        "/api/workbench/v1/relation-files/operator_machine/export",
        query_string={"export_ref": export_ref, "format": "xlsx"},
    )
    assert over_xlsx.status_code == 422 and over_xlsx.get_json()["error"]["code"] == "invalid_input"
    assert projected == []

    csv_ok = client.get(
        "/api/workbench/v1/relation-files/operator_machine/export",
        query_string={"export_ref": export_ref, "format": "csv"},
    )
    assert csv_ok.status_code == 200 and len(projected) == 1

    projected.clear()
    conn.execute("UPDATE OperatorMachine SET skill_level='normal' WHERE operator_id='O1' AND machine_id='M1'")
    conn.commit()
    stale_xlsx = client.get(
        "/api/workbench/v1/relation-files/operator_machine/export",
        query_string={"export_ref": export_ref, "format": "xlsx"},
    )
    assert stale_xlsx.status_code == 409 and stale_xlsx.get_json()["error"]["code"] == "snapshot_stale"
    assert projected == []


def test_relation_confirm_import_rejects_operator_recreated_with_identical_row(resource_conn):
    conn = resource_conn
    operator = {"operator_id": "OP-REF", "name": "王五",
                "created_at": "2026-01-01 08:00:00", "updated_at": "2026-01-01 08:00:00"}
    insert_row(conn, "Operators", operator)
    conn.commit()
    service = module.WorkbenchRelationFileService(conn, "operator_machine")
    content = file_bytes([("OP-REF", "M1", "普通", "否")], headers=("工号", "设备编号", "技能等级", "主操设备"))
    preview = service.preview_import(content, file_format="csv", mode="upsert")
    row, = preview.as_dict()["rows"]
    assert row["result"] == "new"

    # 删除后按同编号同字段重建人员：触发器换出新的永久 ref，Operators 行逐字段相同。
    conn.execute("DELETE FROM Operators WHERE operator_id='OP-REF'")
    insert_row(conn, "Operators", operator)
    conn.commit()
    assert resource_row(conn, "operator", "OP-REF") == row["expected"]["operator"]["record"]
    assert identity_for(conn, "operator", "OP-REF").ref != row["expected"]["operator"]["identity"]["ref"]

    with pytest.raises(WorkbenchCommandRejected) as exc:
        with service.tx.transaction():
            service.confirm_import(preview)
    assert exc.value.code == "stale_write"
    assert not conn.execute("SELECT 1 FROM OperatorMachine WHERE operator_id='OP-REF'").fetchall()


def test_relation_xlsx_roundtrip_keeps_crlf_in_reference_labels(monkeypatch):
    import openpyxl.xml

    monkeypatch.setattr(openpyxl.xml, "LXML", False)
    download = write_relation_file(
        "operator_machine",
        [{
            "operator_code": "O1",
            "operator_label": "张\r\n三",
            "machine_code": "M1",
            "machine_label": "设\r\n备",
            "skill_level": "掌握",
            "is_primary": "是",
        }],
        "xlsx",
    )
    parsed_rows, _ = read_relation_file("operator_machine", download.content, "xlsx")
    assert parsed_rows[0]["values"]["operator_label"] == "张\r\n三"
    assert parsed_rows[0]["values"]["machine_label"] == "设\r\n备"


def test_relation_import_rejects_null_marker_on_required_columns(resource_conn):
    service = module.WorkbenchRelationFileService(resource_conn, "operator_machine")
    content = file_bytes([("O1", "M1", r"\N", r"\N")], headers=("工号", "设备编号", "技能等级", "主操设备"))
    preview = service.preview_import(content, file_format="csv", mode="upsert").as_dict()
    assert preview["summary"]["rejected"] == 1
    row = preview["rows"][0]
    assert row["result"] == "rejected"
    assert [error["field"] for error in row["errors"]] == ["skill_level", "is_primary"]


def test_relation_import_preserves_legacy_surrounding_whitespace_without_touching_trimmed_sibling(resource_conn):
    conn = resource_conn
    insert_row(conn, "Operators", {"operator_id": " O1 ", "name": "带空格人员"})
    insert_row(conn, "Machines", {"machine_id": " M1 ", "name": "带空格设备", "op_type_id": "OT1"})
    insert_row(conn, "OperatorMachine", {"operator_id": " O1 ", "machine_id": " M1 ",
                                         "skill_level": "normal", "is_primary": "no"})
    conn.commit()
    trimmed_before = tuple(
        conn.execute("SELECT skill_level, is_primary FROM OperatorMachine WHERE operator_id='O1' AND machine_id='M1'").fetchone()
    )

    service = module.WorkbenchRelationFileService(conn, "operator_machine")
    with service.reader.read_snapshot() as scope:
        args, count = service.preview_export(scope, "all", request=ResourcePageRequest(kind="operator"))
        exported_rows = service.export_rows(scope, **args)
    assert count == len(exported_rows) == 2
    assert {(r["operator_code"], r["machine_code"]) for r in exported_rows} == {("O1", "M1"), (" O1 ", " M1 ")}

    for fmt in ("csv", "xlsx"):
        exported_file = write_relation_file("operator_machine", exported_rows, fmt)
        roundtrip = service.preview_import(exported_file.content, file_format=fmt, mode="upsert").as_dict()
        assert roundtrip["summary"] == {"new": 0, "update": 0, "unchanged": 2, "delete": 0, "rejected": 0}
        assert [r["result"] for r in roundtrip["rows"]] == ["unchanged", "unchanged"]

    update_content = file_bytes(
        [(" O1 ", " M1 ", "熟练", "否")],
        headers=("工号", "设备编号", "技能等级", "主操设备"),
    )
    update_preview = service.preview_import(update_content, file_format="csv", mode="upsert")
    update_dict = update_preview.as_dict()
    assert update_dict["summary"] == {"new": 0, "update": 1, "unchanged": 0, "delete": 0, "rejected": 0}
    update_row, = update_dict["rows"]
    assert update_row["result"] == "update"
    assert update_row["business_code"] == " O1  /  M1 "
    assert update_row["changes"] == {"skill_level": {"before": "normal", "after": "expert"}}
    with service.tx.transaction():
        outcome = service.confirm_import(update_preview)
    assert outcome.result == "committed"
    assert tuple(
        conn.execute("SELECT skill_level, is_primary FROM OperatorMachine WHERE operator_id=' O1 ' AND machine_id=' M1 '").fetchone()
    ) == ("expert", "no")
    assert tuple(
        conn.execute("SELECT skill_level, is_primary FROM OperatorMachine WHERE operator_id='O1' AND machine_id='M1'").fetchone()
    ) == trimmed_before

    missing_content = file_bytes(
        [(" O-MISS ", " M1 ", "普通", "否"), (" O1 ", " M-MISS ", "普通", "否"), ("O-MISS", "M1", "普通", "否")],
        headers=("工号", "设备编号", "技能等级", "主操设备"),
    )
    missing_preview = service.preview_import(missing_content, file_format="csv", mode="upsert").as_dict()
    assert missing_preview["summary"]["rejected"] == 3
    assert [(r["errors"][0]["field"], r["errors"][0]["message"]) for r in missing_preview["rows"]] == [
        ("operator_code", "编号不能有首尾空格，请修正后重新导入。"),
        ("machine_code", "编号不能有首尾空格，请修正后重新导入。"),
        ("operator_code", "系统里找不到这个编号，这一行没有导入。请先在基础资料里维护好再导入。"),
    ]
