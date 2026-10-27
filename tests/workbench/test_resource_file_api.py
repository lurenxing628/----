"""Actual Flask registration, frozen scope, no-write previews and receipt replay."""

import csv
import json
import re
from contextlib import contextmanager
from io import BytesIO, StringIO

import pytest
from flask import Blueprint

from tests.workbench.material_actions_api_support import database, expire_contexts, snapshot, without_startup_logs
from tests.workbench.resource_file_support import exported, file_bytes

BASE = "/api/workbench/v1"


def registered(app):
    from web.routes.workbench.resource_actions import register_resource_action_routes
    if not any(rule.rule == BASE + "/imports/<kind>/preview" for rule in app.url_map.iter_rules()):
        bp = Blueprint("resource_actions_test", __name__)
        register_resource_action_routes(bp)
        app.register_blueprint(bp)
    return app.test_client()


@pytest.fixture
def client(db_env):
    from app import create_app
    return registered(create_app())


def upload(client, kind, rows, *, category=None, fmt="csv", headers=None, extra=None):
    from core.models.workbench_resource_file import column_label

    # 用例按列键描述文件；文件里写导出、模板用的中文列名（导入只认中文列名）。
    keys = headers or (("business_code", "label", "category") if kind == "op_type" else ("business_code", "label", "status"))
    labels = tuple(column_label(kind, key) for key in keys)
    fields = {"file": (BytesIO(file_bytes(rows, fmt, labels)), "input." + fmt), "format": fmt, "mode": "upsert"}
    if category is not None:
        fields["category"] = category
    fields.update(extra or {})
    return client.post(BASE + "/imports/" + kind + "/preview", data=fields, content_type="multipart/form-data")


def command(client, kind, preview, *, key="resource-api-request-00001", operation="import", extra=None):
    body = {"request_key": key, "write_token": preview["write_context"]["write_token"], "input": {"preview_ref": preview["preview_ref"]}}
    body.update(extra or {})
    path = "/imports/" + kind + "/confirm" if operation == "import" else "/entities/" + kind + "/bulk-confirm"
    return client.post(BASE + path, json=body)


CATEGORY_LABELS = {"internal": "自制", "external": "外协"}


def new_preview(client, kind, category=None):
    # 导入文件只认导出写出的中文；范围参数 category 仍是接口代号。
    headers = ["business_code", "label", "category" if kind == "op_type" else "status"]
    cell = CATEGORY_LABELS[category] if category else "可用"
    rows = [["R1", "Resource 1", cell], ["R2", "Resource 2", cell]]
    if kind == "supplier":
        headers.append("default_days")
        rows = [row + [2.5] for row in rows]
    response = upload(client, kind, rows, category=category, headers=headers)
    assert response.status_code == 200, response.get_data(as_text=True)
    result = response.get_json()
    assert result["meta"]["snapshot_ref"] and result["data"]["can_confirm"]
    return result["data"]


@pytest.mark.parametrize('kind,category', [('op_type', 'external')])
def test_real_registration_public_preview_and_committed_restart_replay(client, kind, category):
    before = snapshot(client)
    preview = new_preview(client, kind, category)
    assert preview["write_context"]["write_token"] == preview["preview_ref"]
    assert preview["write_context"]["expires_at"] == preview["expires_at"]
    assert snapshot(client) == before
    assert preview["operation"] == kind + ".import" and preview["commit_policy"] == "atomic"
    assert preview["scope"]["category"] == category
    if category:
        assert preview["category"] == category
    row = preview["rows"][0]
    assert set(row) == {"row", "business_code", "entity_ref", "action", "result", "before", "after", "changes", "errors", "requires_confirmation", "reference_count", "reference_fields"}
    assert set(row["after"]) <= {item["key"] for item in preview["columns"]}
    assert "entity_key" not in json.dumps(preview) and "revision" not in json.dumps(preview)
    first = command(client, kind, preview)
    assert first.status_code == 200, first.get_data(as_text=True)
    with database(client) as conn:
        conn.executemany("UPDATE OpTypes SET remark=? WHERE op_type_id=?", [("", "R1"), ("keep", "R2")])
        conn.commit()
        content = exported(conn, kind, "csv", category=category).content
    response = client.post(BASE + "/imports/" + kind + "/preview", data={
        "file": (BytesIO(content), "input.csv"), "format": "csv", "mode": "upsert", "category": category},
        content_type="multipart/form-data")
    assert response.status_code == 200, response.get_data(as_text=True)
    roundtrip = response.get_json()["data"]
    assert all(row["errors"] == [] and row["result"] == "unchanged" for row in roundtrip["rows"])
    response = upload(client, kind, [("R2", "'")], category=category, headers=("business_code", "remark"))
    assert response.status_code == 200, response.get_data(as_text=True)
    row = response.get_json()["data"]["rows"][0]
    assert row["errors"] == [] and row["changes"] == {} and row["result"] == "unchanged"
    assert row["after"]["remark"] == "keep"
    expire_contexts(client)
    replay = command(client, kind, preview)
    assert replay.get_json() == {**first.get_json(), "replayed": True}
    from app import create_app
    restarted = registered(create_app())
    before = without_startup_logs(snapshot(restarted))
    replay = command(restarted, kind, preview)
    assert replay.get_json() == {**first.get_json(), "replayed": True}
    assert without_startup_logs(snapshot(restarted)) == before


@pytest.mark.parametrize("kind", ("op_type", "machine", "operator", "supplier"))
def test_resource_import_rejects_english_column_names(client, kind):
    # 导入只认导出、模板写出的中文列名；英文列键不再作为别名被接受。
    english = ("business_code", "label", "category" if kind == "op_type" else "status")
    fields = {"file": (BytesIO(file_bytes([("R9", "Resource 9", "外协" if kind == "op_type" else "可用")], "csv", english)),
                       "input.csv"), "format": "csv", "mode": "upsert", **({"category": "external"} if kind == "op_type" else {})}
    before = snapshot(client)
    response = client.post(BASE + "/imports/" + kind + "/preview", data=fields, content_type="multipart/form-data")
    assert response.status_code == 422, response.get_json()
    error = response.get_json()["error"]
    assert error["code"] == "invalid_input" and error["fields"][0]["path"] == "headers"
    assert snapshot(client) == before


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_export_file_is_written_after_the_read_snapshot_is_released(client, monkeypatch, fmt):
    """整份导出行在读快照里读完；生成文件时读事务已结束，不挡别人提交写入。资源、物料两条下载路由同一做法。"""
    from flask import g

    from core.services.workbench.material import files as material_files
    from core.services.workbench.resource import files as resource_files
    from tests.workbench.material_actions_api_support import export_preview, register_actions, seed

    register_actions(client.application)
    assert command(client, "machine", new_preview(client, "machine")).status_code == 200
    seed(client)
    seen = []

    def spy(module, name, kind):
        original = getattr(module, name)

        def wrapped(*args, **kwargs):
            seen.append((kind, g.db.in_transaction))
            return original(*args, **kwargs)
        monkeypatch.setattr(module, name, wrapped)

    spy(resource_files.WorkbenchResourceFileService, "export_rows", "read")
    spy(resource_files, "write_resource_file", "write")
    spy(material_files.WorkbenchMaterialFileService, "export_rows", "read")
    spy(material_files, "write_material_file", "write")
    listed = client.get(BASE + "/entities/machine", query_string={"size": 200})
    assert listed.status_code == 200, listed.get_data(as_text=True)
    approved = client.post(BASE + "/exports/machine/preview", json={
        "selection": "all", "scope": {}, "page_size": 200, "snapshot_ref": listed.get_json()["meta"]["snapshot_ref"]}).get_json()
    result = client.get(BASE + "/exports/machine", query_string={"export_ref": approved["data"]["export_ref"], "format": fmt})
    assert result.status_code == 200, result.get_json()
    assert int(result.headers["X-Workbench-Row-Count"]) == approved["data"]["row_count"] > 0
    assert seen == [("read", True), ("write", False)]
    seen.clear()
    approved = export_preview(client, "all")
    result = client.get(BASE + "/exports/material", query_string={"export_ref": approved["data"]["export_ref"], "format": fmt})
    assert result.status_code == 200, result.get_json()
    assert seen == [("read", True), ("write", False)]


@pytest.mark.parametrize("selection", ("all", "filtered", "selected"))
def test_resource_export_shares_captured_facts_for_preview_and_csv(client, monkeypatch, selection):
    from core.services.workbench.resource.queries import WorkbenchResourceQueryService

    with database(client) as conn:
        conn.executemany("INSERT INTO OpTypes(op_type_id,name,category) VALUES (?,?,'internal')",
                         [("EXPORT-T1", "Turning"), ("EXPORT-T2", "Milling")])
        conn.executemany("INSERT INTO Machines(machine_id,name,op_type_id,status) VALUES (?,?,'EXPORT-T1','active')",
                         [("EXPORT-M1", "Lathe"), ("EXPORT-M2", "Second")])
        conn.execute("INSERT INTO MachineOpTypes(machine_id,op_type_id) VALUES ('EXPORT-M1','EXPORT-T2')")
        conn.execute("INSERT INTO WorkbenchMachineGroups(group_id,name) VALUES ('EXPORT-G1','Group')")
        conn.execute("INSERT INTO WorkbenchMachineGroupMembers(machine_id,group_id) VALUES ('EXPORT-M1','EXPORT-G1')")
        conn.commit()
    scope = {"query": "EXPORT-M1"}
    listed = client.get(BASE + "/entities/machine", query_string={**scope, "size": 200})
    assert listed.status_code == 200, listed.get_json()
    body = {"selection": selection, "scope": scope, "page_size": 200,
            "snapshot_ref": listed.get_json()["meta"]["snapshot_ref"]}
    if selection == "selected":
        body["refs"] = [listed.get_json()["data"]["entities"][0]["ref"]]
    queries = []
    read_snapshot = WorkbenchResourceQueryService.read_snapshot

    @contextmanager
    def observed(reader, *args, **kwargs):
        reader.conn.set_trace_callback(queries.append)
        try:
            with read_snapshot(reader, *args, **kwargs) as fingerprint:
                yield fingerprint
        finally:
            reader.conn.set_trace_callback(None)

    def assert_single_capture():
        tables = ("Machines", "MachineOpTypes", "OpTypes", "WorkbenchMachineGroupMembers")
        counts = {table: sum(bool(re.match(r"\s*SELECT\s+\*\s+FROM\s+" + table + r"\b", sql, re.IGNORECASE))
                             for sql in queries) for table in tables}
        assert counts == dict.fromkeys(tables, 1), queries

    monkeypatch.setattr(WorkbenchResourceQueryService, "read_snapshot", observed)
    approved = client.post(BASE + "/exports/machine/preview", json=body)
    assert approved.status_code == 200, approved.get_json()
    assert_single_capture()
    queries.clear()
    result = client.get(BASE + "/exports/machine", query_string={
        "export_ref": approved.get_json()["data"]["export_ref"], "format": "csv"})
    assert result.status_code == 200, result.get_json()
    assert_single_capture()
    rows = list(csv.reader(StringIO(result.data.decode("utf-8-sig"))))
    headers = rows[0]
    assert not any("ref" in field for field in headers)
    data = [dict(zip(headers, (value[1:] if value.startswith("'") else value for value in row))) for row in rows[1:]]
    expected = ["EXPORT-M1", "EXPORT-M2"] if selection == "all" else ["EXPORT-M1"]
    assert [row["编号"] for row in data] == expected
    assert int(result.headers["X-Workbench-Row-Count"]) == approved.get_json()["data"]["row_count"] == len(expected)
    assert "自制工种编号" not in headers
    assert {key: data[0][key] for key in ("名称", "设备组编号", "可做工种编号")} == {
        "名称": "Lathe", "设备组编号": "EXPORT-G1", "可做工种编号": "EXPORT-T1、EXPORT-T2"}


@pytest.mark.parametrize(
    "sort,direction,expected_codes",
    (
        ("label", "asc", ["EXPORT-M2", "EXPORT-M1"]),
        ("business_code", "desc", ["EXPORT-M2", "EXPORT-M1"]),
    ),
)
def test_filtered_export_without_column_filters_preserves_toolbar_sort_order(client, sort, direction, expected_codes):
    with database(client) as conn:
        conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('EXPORT-T1','Turning','internal')")
        conn.executemany(
            "INSERT INTO Machines(machine_id,name,op_type_id,status) VALUES (?,?,'EXPORT-T1','active')",
            [("EXPORT-M1", "Zulu Lathe"), ("EXPORT-M2", "Alpha Mill")],
        )
        conn.commit()
    scope = {"sort": sort, "direction": direction}
    listed = client.get(BASE + "/entities/machine", query_string={**scope, "size": 200})
    assert listed.status_code == 200, listed.get_json()
    listed_codes = [item["business_code"] for item in listed.get_json()["data"]["entities"]]
    assert listed_codes == expected_codes
    approved = client.post(
        BASE + "/exports/machine/preview",
        json={
            "selection": "filtered",
            "scope": scope,
            "page_size": 200,
            "snapshot_ref": listed.get_json()["meta"]["snapshot_ref"],
        },
    )
    assert approved.status_code == 200, approved.get_json()
    result = client.get(
        BASE + "/exports/machine",
        query_string={"export_ref": approved.get_json()["data"]["export_ref"], "format": "csv"},
    )
    assert result.status_code == 200, result.get_json()
    rows = list(csv.reader(StringIO(result.data.decode("utf-8-sig"))))
    headers = rows[0]
    exported_codes = [
        dict(zip(headers, (value[1:] if value.startswith("'") else value for value in row)))["编号"]
        for row in rows[1:]
    ]
    assert exported_codes == expected_codes


@pytest.mark.parametrize("kind", ("machine", "operator", "supplier"))
def test_resource_status_instructions_match_new_and_existing_row_rules(client, kind):
    from core.models.workbench_resource_file import REQUIRED, table_descriptor

    status = next(column for column in table_descriptor(kind)["columns"] if column["key"] == "status")
    assert REQUIRED[kind] == ("business_code",) and status["required"] is False
    assert status["value_hint"] == "只填固定状态值；新增时必须填，已有的留空保持原样"
    assert status["error_hint"] == "新增时留空，或填了固定状态值以外的文字"
    missing = upload(client, kind, [("T20-NEW", "New resource", "")])
    assert missing.status_code == 200, missing.get_json()
    rejected = missing.get_json()["data"]
    assert rejected["can_confirm"] is False
    assert any(error["field"] == "status" and "新增" in error["message"] for error in rejected["rows"][0]["errors"])
    assert command(client, kind, new_preview(client, kind)).status_code == 200
    unchanged_status = upload(client, kind, [("R1", "Renamed resource", "")])
    assert unchanged_status.status_code == 200, unchanged_status.get_json()
    row = unchanged_status.get_json()["data"]["rows"][0]
    assert row["errors"] == [] and row["before"]["status"] == row["after"]["status"] == "active"


@pytest.mark.parametrize("kind,label,other_label", (("machine", "可做工种编号", "外协工种编号"),
                                                   ("supplier", "外协工种编号", "可做工种编号")))
def test_resource_work_type_errors_use_the_same_kind_specific_column_label(client, kind, label, other_label):
    from core.models.workbench_resource_file import column_label, public_columns

    assert column_label(kind, "op_type_codes") == label
    assert next(column["label"] for column in public_columns(kind) if column["key"] == "op_type_codes") == label
    assert column_label("operator", "shift_profile_code") == "班次编号"
    assert column_label("machine", "remark") == "备注（只读）"
    headers = ["business_code", "label", "status", "op_type_codes"]
    values = ["T20-MISSING", "Missing work type", "可用", "T20-UNKNOWN-TYPE"]
    if kind == "supplier":
        headers.append("default_days")
        values.append("2.5")
    response = upload(client, kind, [values], headers=headers)
    assert response.status_code == 200, response.get_json()
    data = response.get_json()["data"]
    assert data["can_confirm"] is False
    error, = data["rows"][0]["errors"]
    assert error["field"] == "op_type_codes"
    assert label in error["message"] and other_label not in error["message"]


def test_op_type_import_marks_in_file_duplicate_labels_across_existing_and_conflicting_rows(client):
    assert command(client, "op_type", new_preview(client, "op_type", "external")).status_code == 200
    response = upload(
        client,
        "op_type",
        [
            ("R1", "", "外协", "keep existing label"),
            ("R2", "Resource 1", "外协", "rename to R1 label"),
            ("R3", "Resource 1", "外协", "new with R1 label"),
        ],
        category="external",
        headers=("business_code", "label", "category", "remark"),
    )
    assert response.status_code == 200, response.get_json()
    data = response.get_json()["data"]
    assert data["can_confirm"] is False
    for row in data["rows"]:
        assert any(
            err["field"] == "label"
            and err["code"] == "duplicate_entry"
            and "第 2, 3, 4 行" in err["message"]
            for err in row["errors"]
        ), row


def test_op_type_import_rejects_label_owned_by_another_saved_code_as_row_duplicate(client):
    # 名称已被库里另一个编号占用：新增行和改名行都按行级重复报错，不让整份文件变成 409。
    assert command(client, "op_type", new_preview(client, "op_type", "external")).status_code == 200
    response = upload(client, "op_type", [("R2", "Resource 1", "外协"), ("R3", "Resource 2", "外协")],
                      category="external")
    assert response.status_code == 200, response.get_json()
    data = response.get_json()["data"]
    assert data["can_confirm"] is False
    for row, label in zip(data["rows"], ("Resource 1", "Resource 2")):
        error, = row["errors"]
        assert (error["field"], error["code"]) == ("label", "duplicate_entry") and label in error["message"], row


def test_internal_op_type_import_with_merge_mode_is_a_row_conflict(client):
    response = upload(client, "op_type", [("T-INT", "Internal type", "自制", "分别设置")], category="internal",
                      headers=("business_code", "label", "category", "default_merge_mode"))
    assert response.status_code == 200, response.get_json()
    data = response.get_json()["data"]
    assert data["can_confirm"] is False
    error, = data["rows"][0]["errors"]
    assert error["code"] == "constraint_conflict" and "外协周期规则" in error["message"]


@pytest.mark.parametrize(
    "kind,field,kept_code",
    (
        ("machine", "op_type_codes", "LEGACY-EXT"),
        ("operator", "skill_codes", "LEGACY-EXT"),
        ("supplier", "op_type_codes", "LEGACY-INT"),
    ),
)
def test_resource_import_allows_keeping_existing_bound_work_type_when_pruning_list(client, kind, field, kept_code):
    with database(client) as conn:
        conn.executemany(
            "INSERT INTO OpTypes(op_type_id,name,category) VALUES (?,?,?)",
            [
                ("LEGACY-EXT", "Legacy External", "external"),
                ("LEGACY-INT", "Legacy Internal", "internal"),
                ("VALID-INT", "Valid Internal", "internal"),
                ("VALID-EXT", "Valid External", "external"),
            ],
        )
        conn.execute(
            "INSERT INTO Machines(machine_id,name,op_type_id,status) VALUES ('R-LEGACY','Machine','LEGACY-EXT','active')"
        )
        conn.execute(
            "INSERT INTO MachineOpTypes(machine_id,op_type_id) VALUES ('R-LEGACY','VALID-INT')"
        )
        conn.execute(
            "INSERT INTO Operators(operator_id,name,status) VALUES ('R-LEGACY','Operator','active')"
        )
        conn.executemany(
            "INSERT INTO OperatorSkill(operator_id,op_type_id) VALUES ('R-LEGACY',?)",
            [("LEGACY-EXT",), ("VALID-INT",)],
        )
        conn.execute(
            "INSERT INTO WorkbenchOperatorProfiles(operator_id,skills_declared) VALUES ('R-LEGACY',1)"
        )
        conn.execute(
            "INSERT INTO Suppliers(supplier_id,name,default_days,status) VALUES ('R-LEGACY','Supplier',2.0,'active')"
        )
        conn.executemany(
            "INSERT INTO WorkbenchSupplierOpTypes(supplier_id,op_type_id) VALUES ('R-LEGACY',?)",
            [("LEGACY-INT",), ("VALID-EXT",)],
        )
        conn.commit()

    response = upload(client, kind, [("R-LEGACY", kept_code)], headers=("business_code", field))
    assert response.status_code == 200, response.get_json()
    preview = response.get_json()["data"]
    assert preview["can_confirm"] is True, preview
    row = preview["rows"][0]
    assert row["errors"] == []
    assert row["after"][field] == [kept_code]
    confirmed = command(client, kind, preview, key=f"keep-existing-{kind}")
    assert confirmed.status_code == 200, confirmed.get_json()
    assert confirmed.get_json()["result"] == "committed"
