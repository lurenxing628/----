"""Outsourcing-stage preview, confirmation and receipt replay."""

import uuid
from datetime import datetime

import pytest

from core.infrastructure.transaction import TransactionManager
from core.services.process.workflow_state import record_confirmation
from tests.workbench.process_commands_support import CONFIRMED_AT
from tests.workbench.process_stage_api_support import (
    BASE,
    PART,
    rejected,
    seed_stage_scale,
    stage_api_fixture,
    success,
    unscheduled_stage_api_fixture,
)

_api_fixture = stage_api_fixture
_unscheduled_api_fixture = unscheduled_stage_api_fixture


def edit(api, days=8.125):
    entity = api.detail()["data"]
    return {
        "groups": [
            {
                "ref": entity["external_groups"][0]["ref"],
                "operation_refs": [row["ref"] for row in entity["operations"] if row["source"] == "external"],
                "supplier_ref": entity["operations"][1]["supplier_ref"],
                "total_days": days,
            }
        ],
        "discard_group_refs": [],
    }


def _update_resource_via_api(api, kind, code, payload):
    ref = api.ref(kind, code)
    detail = success(api.client.get(f"{BASE}/entities/{kind}/{ref}"))["data"]
    token = detail["write_context"]["write_token"]
    return success(
        api.client.post(
            f"{BASE}/entities/{kind}/{ref}/update",
            json={"request_key": "res-upd-" + uuid.uuid4().hex, "write_token": token, "input": payload},
        )
    )


@pytest.mark.parametrize("action", ("route_confirm", "source_confirm", "hours_confirm", "groups_confirm"))
def test_single_part_write_context_ignores_unrelated_template_changes(stage_api, action):
    api = stage_api
    api.prepare()
    payload = {
        "route_confirm": lambda: {"route": api.route(), "discard_group_refs": []},
        "source_confirm": api.source,
        "hours_confirm": api.hours,
        "groups_confirm": lambda: edit(api),
    }[action]()
    body = api.body(action, payload)
    with api.database() as conn:
        seed_stage_scale(conn, "UNRELATED", 3)
    assert success(api.post(action, body))["result"] in ("committed", "unchanged")


def test_single_part_write_context_keeps_hidden_deleted_template_facts(stage_api):
    api = stage_api
    api.prepare()
    api.execute(
        "INSERT INTO PartOperations(part_no,seq,op_type_name,source,status,private_stage_note) "
        "VALUES (?,40,'历史工序','internal','deleted','保留的历史资料')",
        (PART,),
    )
    body = api.body("hours_confirm", api.hours())
    api.execute("UPDATE PartOperations SET private_stage_note='历史资料已变更' WHERE part_no=? AND seq=40", (PART,))
    before = api.snapshot()
    rejected(api.post("hours_confirm", body), "stale_write")
    assert api.snapshot() == before


@pytest.mark.parametrize("foreign_member", (True, False))
def test_single_part_reads_preserve_cross_part_group_diagnostics_and_write_guard(stage_api, foreign_member):
    from core.errors import ValidationError

    api = stage_api
    api.prepare("source")
    if foreign_member:
        api.execute(
            "INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,ext_days,ext_group_id) "
            "VALUES ('PROC-003',20,'PROC-EX','热处理','external','PROC-S',3.25,'PROC-G')"
        )
    else:
        api.execute(
            "INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days,supplier_id) "
            "VALUES ('FOREIGN-G','PROC-003',20,20,'merged',6.75,'PROC-S')"
        )
        api.execute("UPDATE PartOperations SET ext_group_id='FOREIGN-G' WHERE part_no=? AND seq=20", (PART,))
    detail = api.detail()["data"]
    assert not detail["workflow"]["ready"]
    assert detail["workflow"]["source"]["state"] != "confirmed"
    external = next(row for row in detail["operations"] if row["sequence"] == 20)
    assert "external_group_part_mismatch" in {row["code"] for row in external["issues"]}
    before = api.snapshot()
    rejected(api.preview("source_confirm", api.source()), "group_invalid", 422)
    with api.database() as conn, pytest.raises(ValidationError):
        with TransactionManager(conn).transaction(begin_immediate=True):
            record_confirmation(conn, PART, "source", confirmed_at=CONFIRMED_AT)
    assert api.snapshot() == before


def test_merged_group_ignores_retained_member_days_in_current_diagnostics(stage_api):
    from core.services.workbench.master.overview import MasterOverviewService

    api = stage_api
    api.prepare()
    api.confirm("hours_confirm", api.hours())
    # 合并组成员保留着并组前的逐序周期（表约束内的真实旧值），当前诊断和展示都只认整组周期。
    api.execute("UPDATE PartOperations SET ext_days=9.5 WHERE part_no=? AND source='external'", (PART,))
    entity = api.detail()["data"]
    assert entity["workflow"]["ready"]
    operation = next(row for row in entity["operations"] if row["source"] == "external")
    assert operation["external_days_source"] == "group" and not operation["issues"]
    assert api.rows("PartOperations", "part_no=? AND source='external'", (PART,))[0]["ext_days"] == 9.5
    path = "/api/workbench/v1/entities/batch/" + api.ref("batch", "PROC-B")
    assert success(api.client.get(path))["data"]["template"]["complete"]
    with api.database() as conn:
        overview = MasterOverviewService(conn)
        with overview.read_snapshot(as_of=datetime.now()) as scope:
            route = next(row for row in scope.entities if row["domain"] == "route" and row["business_code"] == PART)
            assert not route["issues"]
            retained = next(row for row in route["fields"] if "保留的逐序周期" in row["label"])
            assert retained["value"] == 9.5 and not retained["checked"]


def _synced_merged_batch(api, request_key):
    api.prepare()
    api.confirm("hours_confirm", api.hours())
    path = BASE + "/entities/batch/" + api.ref("batch", "PROC-B")
    detail = success(api.client.get(path))
    preview = success(
        api.client.post(path + "/sync-preview", json={"input": {}, "snapshot_ref": detail["meta"]["snapshot_ref"]})
    )["data"]
    synced = success(
        api.client.post(
            path + "/sync-confirm",
            json={
                "request_key": request_key,
                "write_token": preview["write_context"]["write_token"],
                "input": {"preview_ref": preview["preview_ref"]},
            },
        )
    )
    assert synced["result"] == "committed"
    return path


def test_batch_detail_ignores_retained_member_days_of_merged_context(unscheduled_stage_api):
    api = unscheduled_stage_api
    path = _synced_merged_batch(api, "merged-retained-member-days")
    api.execute("UPDATE BatchOperations SET ext_days=9.5 WHERE batch_id='PROC-B' AND source='external'")
    (external,) = [row for row in success(api.client.get(path))["data"]["operations"] if row["source"] == "external"]
    assert external["external_group"]["merge_mode"] == "merged" and external["external_group"]["total_days"] == 6.75
    assert external["external_days"] is None and not external["issues"]


# '--5' 和上标 '²' 看着像数字但 int() 不认，同样按文本排在数字工序之后。
@pytest.mark.parametrize("legacy", ["bad", "--5", "²"])
def test_batch_sync_preview_replaces_legacy_non_integer_sequence(unscheduled_stage_api, legacy):
    api = unscheduled_stage_api
    api.prepare()
    api.confirm("hours_confirm", api.hours())
    # 存量旧工序号坏成文本时详情照常展示，从模板更新工序的预检也要能列出替换结果来修复它。
    api.execute("UPDATE BatchOperations SET seq='" + legacy + "' WHERE op_code='STAGE-API-OLD'")
    path = BASE + "/entities/batch/" + api.ref("batch", "PROC-B")
    detail = success(api.client.get(path))
    assert [row["sequence"] for row in detail["data"]["operations"]] == [legacy]
    preview = success(
        api.client.post(path + "/sync-preview", json={"input": {}, "snapshot_ref": detail["meta"]["snapshot_ref"]})
    )["data"]
    assert [(row["sequence"], row["change"]) for row in preview["changes"]] == [
        (10, "added"),
        (20, "added"),
        (30, "added"),
        (legacy, "removed"),
    ]
    assert preview["change_counts"] == {"added": 3, "removed": 1, "updated": 0, "unchanged": 0}


@pytest.mark.parametrize("status_code", ["inactive", "pending_review"])
def test_supplier_service_status_change_invalidates_confirmations_and_surfaces_diagnostics(stage_api, status_code):
    from core.services.workbench.master.overview import MasterOverviewService

    api = stage_api
    api.prepare()
    api.confirm("hours_confirm", api.hours())
    assert api.detail()["data"]["workflow"]["ready"]

    _update_resource_via_api(api, "supplier", "PROC-S", {"fields": {"status": status_code}})

    with api.database() as conn:
        overview = MasterOverviewService(conn)
        with overview.read_snapshot(as_of=datetime.now()) as scope:
            route = next(row for row in scope.entities if row["domain"] == "route" and row["business_code"] == PART)
            assert any(row["rule"] == "operation.supplier" for row in route["issues"])
    entity = api.detail()["data"]
    assert not entity["workflow"]["ready"]
    assert entity["workflow"]["source"]["state"] == "unconfirmed"
    assert entity["workflow"]["hours"]["state"] == "locked"
    external = next(row for row in entity["operations"] if row["source"] == "external")
    assert external["confirmation"]["source"]["state"] == "unconfirmed"
    assert external["confirmation"]["hours"]["state"] == "unconfirmed"
    assert any(row["code"] == "supplier_invalid" for row in external["issues"])
    path = "/api/workbench/v1/entities/batch/" + api.ref("batch", "PROC-B")
    assert not success(api.client.get(path))["data"]["template"]["complete"]


def test_group_preview_command_and_receipt_roundtrip(unscheduled_stage_api):
    api = unscheduled_stage_api
    with api.database() as conn:
        conn.execute(
            "INSERT INTO Suppliers(supplier_id,name,default_days,status) VALUES ('PROC-S2','另一热处理厂',3.25,'active')"
        )
        conn.execute("INSERT INTO WorkbenchSupplierOpTypes(supplier_id,op_type_id) VALUES ('PROC-S2','PROC-EX')")
        conn.execute("UPDATE ExternalGroups SET end_seq=21,supplier_id=NULL WHERE group_id='PROC-G'")
        conn.execute(
            "INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,ext_days,"
            "ext_group_id,setup_hours,unit_hours) VALUES ('PROC-001',21,'PROC-EX','热处理','external','PROC-S2',3.25,'PROC-G',0,0)"
        )
        with TransactionManager(conn).transaction():
            record_confirmation(conn, PART, "route", confirmed_at=CONFIRMED_AT)
    members = [row["ref"] for row in api.detail()["data"]["operations"] if row["sequence"] in (20, 21)]
    before = api.snapshot()
    _field_rejection(api.preview("source_confirm", api.source()), "group_supplier_mismatch",
                     ["operations." + ref + ".supplier_ref" for ref in members])
    assert api.snapshot() == before
    entity = api.detail()["data"]
    assert not entity["workflow"]["ready"]
    assert any(row["code"] == "external_group_supplier_mismatch" for row in entity["external_groups"][0]["issues"])
    path = "/api/workbench/v1/entities/batch/" + api.ref("batch", "PROC-B")
    detail = success(api.client.get(path))
    assert not detail["data"]["template"]["complete"]
    rejected(
        api.client.post(path + "/sync-preview", json={"input": {}, "snapshot_ref": detail["meta"]["snapshot_ref"]}),
        "constraint_conflict",
    )
    api.execute("UPDATE PartOperations SET supplier_id='PROC-S' WHERE part_no=? AND seq=21", (PART,))
    api.confirm("source_confirm", api.source())
    before = api.snapshot()
    payload = edit(api)
    preview = success(api.preview("groups_confirm", payload))
    assert api.snapshot() == before
    assert preview["data"]["changes"][0]["before"]["total_days"] == 6.75
    assert preview["data"]["changes"][0]["after"]["total_days"] == 8.125
    body = api.body("groups_confirm", payload)
    first = success(api.post("groups_confirm", body))
    assert first["data"]["stage"] == "groups"
    assert success(api.post("groups_confirm", body)) == {**first, "replayed": True}
    detail = api.detail()["data"]
    assert detail["external_groups"][0]["total_days"] == 8.125
    assert detail["operations"][1]["external_days_source"] == "group"
    assert detail["workflow"]["source"]["state"] == "confirmed" and not detail["workflow"]["ready"]
    assert api.rows("PartOperations", "part_no=? AND seq=20", (PART,))[0]["ext_days"] == 3.25
    api.confirm("hours_confirm", api.hours())
    assert api.detail()["data"]["workflow"]["ready"]

    part_row = api.rows("Parts", "part_no=?", (PART,))[0]
    assert part_row["workflow_origin"] == "managed"
    assert all(part_row[col] for col in ("route_confirmed_at", "source_confirmed_at", "hours_confirmed_at"))
    op_rows = api.rows("PartOperations", "part_no=? AND status='active'", (PART,))
    assert all(row["source_confirmed_at"] and row["hours_confirmed_at"] for row in op_rows)

    # 通过正规外协段写入口修改周期后再改回原值 8.125：仍保持未确认，必须重新执行 hours_confirm 才恢复 ready。
    api.confirm("groups_confirm", edit(api, days=9.5))
    changed = api.detail()["data"]
    assert not changed["workflow"]["ready"]
    assert changed["workflow"]["hours"]["state"] == "unconfirmed"
    assert all(
        row["confirmation"]["hours"]["state"] == "unconfirmed"
        for row in changed["operations"]
        if row["source"] == "external"
    )
    assert all(
        row["confirmation"]["hours"]["state"] == "confirmed"
        for row in changed["operations"]
        if row["source"] == "internal"
    )
    api.confirm("groups_confirm", edit(api, days=8.125))
    reverted = api.detail()["data"]
    assert reverted["external_groups"][0]["total_days"] == 8.125
    assert not reverted["workflow"]["ready"]
    assert reverted["workflow"]["hours"]["state"] == "unconfirmed"
    api.confirm("hours_confirm", api.hours())
    assert api.detail()["data"]["workflow"]["ready"]

    detail = success(api.client.get(path))
    assert detail["data"]["template"]["complete"]
    preview = success(
        api.client.post(path + "/sync-preview", json={"input": {}, "snapshot_ref": detail["meta"]["snapshot_ref"]})
    )["data"]
    synced = success(
        api.client.post(
            path + "/sync-confirm",
            json={
                "request_key": "supplier-group-sync-merged",
                "write_token": preview["write_context"]["write_token"],
                "input": {"preview_ref": preview["preview_ref"]},
            },
        )
    )
    assert synced["result"] == "committed"
    operations = success(api.client.get(path))["data"]["operations"]
    external = [row for row in operations if row["source"] == "external"]
    assert len(external) == 2 and {row["resources"]["supplier"]["business_code"] for row in external} == {"PROC-S"}
    # 预检的 after 行与确认后的批次工序同形：字段是批次工序的子集，分件号、资源与比较用的 *_ref 逐道一致。
    after = {row["sequence"]: row["after"] for row in preview["changes"] if row["after"] is not None}
    keys = ("piece_id", "resources", "machine_ref", "operator_ref", "supplier_ref", "op_type_ref")
    assert all(set(after[row["sequence"]]) <= set(row) for row in operations)
    assert {row["sequence"]: {key: row[key] for key in keys} for row in operations} == {
        sequence: {key: row[key] for key in keys} for sequence, row in after.items()}

    # separate 组保留默认供应商 PROC-S，但成员工序全部指派给 PROC-S2：
    # 停用 PROC-S 绝不误伤本零件确认；停用成员实际使用的 PROC-S2 才精准回退。
    api.execute("UPDATE ExternalGroups SET merge_mode='separate',total_days=NULL WHERE group_id='PROC-G'")
    source = api.source()
    for row in source["operations"]:
        if row["source"] == "external":
            row["supplier_ref"] = api.ref("supplier", "PROC-S2")
    api.confirm("source_confirm", source)
    api.confirm("hours_confirm", api.hours())
    assert api.detail()["data"]["workflow"]["ready"]

    _update_resource_via_api(api, "supplier", "PROC-S", {"fields": {"status": "inactive"}})
    assert api.detail()["data"]["workflow"]["ready"]
    detail = success(api.client.get(path))
    assert detail["data"]["template"]["complete"]
    success(api.client.post(path + "/sync-preview", json={"input": {}, "snapshot_ref": detail["meta"]["snapshot_ref"]}))

    _update_resource_via_api(api, "supplier", "PROC-S2", {"fields": {"status": "inactive"}})
    assert not api.detail()["data"]["workflow"]["ready"]


def test_hours_import_group_total_days_requires_all_group_members_source_confirmed(stage_api):
    from core.services.workbench.process.file_codec import encode_process_file
    from core.services.workbench.process.files import WorkbenchProcessFileService

    api = stage_api
    api.prepare()
    # 新增同组未确认归属的第 21 道外协工序
    api.execute(
        "INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,ext_days,ext_group_id) "
        "VALUES ('PROC-001',21,'PROC-EX','热处理','external','PROC-S',3.25,'PROC-G')"
    )
    api.execute("UPDATE ExternalGroups SET end_seq=21 WHERE group_id='PROC-G'")
    content = encode_process_file(
        "hours",
        [
            {"business_code": PART, "sequence": 20, "group_total_days": 9.5},
            {"business_code": PART, "sequence": 21},
        ],
        "csv",
    ).content
    with api.database() as conn:
        preview, _ = WorkbenchProcessFileService(conn).preview_import(
            "hours", content, file_format="csv", mode="upsert", target_ref=None
        )
    body = preview.as_dict()
    assert body["summary"]["update"] == 0 and body["summary"]["rejected"] == 2
    assert all(row["result"] == "rejected" for row in body["rows"])
    assert all(any(err["code"] == "stage_not_ready" for err in row["errors"]) for row in body["rows"])
    unchanged_content = encode_process_file(
        "hours",
        [
            {"business_code": PART, "sequence": 20, "group_total_days": 6.75},
            {"business_code": PART, "sequence": 21},
        ],
        "csv",
    ).content
    with api.database() as conn:
        unchanged_preview, _ = WorkbenchProcessFileService(conn).preview_import(
            "hours", unchanged_content, file_format="csv", mode="upsert", target_ref=None
        )
    unchanged_body = unchanged_preview.as_dict()
    assert unchanged_body["summary"]["unchanged"] == 2 and unchanged_body["summary"]["rejected"] == 0
    assert all(row["result"] == "unchanged" and not row["errors"] for row in unchanged_body["rows"])
    # 合并组成员的逐序周期按原值导回不算修改，改成别的值要拒绝，只能改合并周期。
    for days, result in ((3.25, "unchanged"), (7, "rejected")):
        member_content = encode_process_file(
            "hours",
            [{"business_code": PART, "sequence": 21, "external_days": days}],
            "csv",
        ).content
        with api.database() as conn:
            member_preview, _ = WorkbenchProcessFileService(conn).preview_import(
                "hours", member_content, file_format="csv", mode="upsert", target_ref=None
            )
        member_row = member_preview.as_dict()["rows"][0]
        assert member_row["result"] == result
        assert [error["field"] for error in member_row["errors"]] == ([] if result == "unchanged" else ["external_days"])


@pytest.mark.parametrize("value", ["0", "-1", "36500.5", "inf", "nan", "TRUE", "三天"])
def test_hours_import_refuses_group_cycles_outside_the_external_days_range(stage_api, value):
    from core.services.workbench.process.file_codec import encode_process_file
    from core.services.workbench.process.files import WorkbenchProcessFileService

    api = stage_api
    api.prepare()

    def preview(cell):
        # 导出的数值格子带前导撇号写成文本，回导时去掉撇号按原文解析；这里只换最后一格的原文。
        content = encode_process_file("hours", [{"business_code": PART, "sequence": 20, "group_total_days": 1}], "csv").content
        assert content.endswith(b",'1\r\n")
        content = content[:-len(b"1\r\n")] + cell.encode() + b"\r\n"
        with api.database() as conn:
            result, _ = WorkbenchProcessFileService(conn).preview_import(
                "hours", content, file_format="csv", mode="upsert", target_ref=None)
        return result.as_dict()["rows"][0]

    # 工时导入的合并周期与工序确认同一值域：100 年本身收，零、负数、超过 100 年、非数字都整行拒收。
    century = preview("36500")
    assert century["result"] == "update" and century["after"]["group_total_days"] == 36500
    refused = preview(value)
    assert refused["result"] == "rejected" and [error["field"] for error in refused["errors"]] == ["group_total_days"]
    if value in ("0", "-1", "36500.5"):
        assert refused["errors"][0]["message"] == _CYCLE


def _field_rejection(response, code, paths):
    error = rejected(response, code, 422)["error"]
    assert error["fields"] == [{"path": path, "message": error["message"]} for path in paths]
    return error["message"]


_CYCLE = "外协周期必须大于 0 天且不超过 36500 天（100 年）。"


@pytest.mark.parametrize(("sequence", "key", "value", "message"), [
    (10, "setup_hours", "1", "请输入有效的工时，不能留空。"),
    (10, "unit_hours", -1, "工时必须是有限非负数。"),
    (30, "unit_hours", float(1 << 53), "工时超出有效数字范围。"),
])
def test_hours_confirm_rejection_points_at_the_operation_hours_cell(stage_api, sequence, key, value, message):
    api = stage_api
    api.prepare()
    payload = api.hours()
    operation = next(row["ref"] for row in api.detail()["data"]["operations"] if row["sequence"] == sequence)
    next(row for row in payload["operations"] if row["ref"] == operation)[key] = value
    before = api.preserved()
    assert _field_rejection(api.post("hours_confirm", api.body("hours_confirm", payload)), "invalid_input",
                            ["operations." + operation + "." + key]) == message
    assert api.preserved() == before


@pytest.mark.parametrize(("sequence", "field", "value", "message"), [
    (10, "setup_hours", -1, "工时必须是有限非负数。"),
    (20, "external_days", 0, _CYCLE),
    (10, "external_days", -1, "这一列不适用于当前归属或现有外协组，请核对列值。"),
])
def test_hours_import_reports_a_bad_hours_cell_once(stage_api, sequence, field, value, message):
    from core.services.workbench.process.file_codec import encode_process_file
    from core.services.workbench.process.files import WorkbenchProcessFileService

    api = stage_api
    api.prepare()
    content = encode_process_file("hours", [{"business_code": PART, "sequence": sequence, field: value}], "csv").content
    with api.database() as conn:
        preview, _ = WorkbenchProcessFileService(conn).preview_import(
            "hours", content, file_format="csv", mode="upsert", target_ref=None)
    # 值域只由写入准入判一次，拒绝与工序确认同一条；不适用的列只报不适用，解码不再另报一条。
    assert preview.as_dict()["rows"][0]["errors"] == [
        {"row": 2, "field": field, "code": "invalid_input", "message": message}]


def test_hours_confirm_rejections_point_at_member_cycles_group_totals_and_zero_hours(stage_api):
    api = stage_api
    api.prepare()
    operations = {row["sequence"]: row["ref"] for row in api.detail()["data"]["operations"]}
    payload = api.hours()
    group_ref = payload["groups"][0]["ref"]
    payload["groups"][0]["total_days"] = 0
    assert _field_rejection(api.post("hours_confirm", api.body("hours_confirm", payload)), "invalid_input",
                            ["groups." + group_ref + ".total_days"]) == _CYCLE

    # 合并组成员的逐序周期只读：改了指回那道工序的周期格。
    payload = api.hours()
    next(row for row in payload["operations"] if row["ref"] == operations[20])["external_days"] = 9
    _field_rejection(api.post("hours_confirm", api.body("hours_confirm", payload)), "group_cycle_only",
                     ["operations." + operations[20] + ".external_days"])

    # 未确认的零单件工时要先确认：指回每一道零工时工序的单件工时格。
    payload = {**api.hours(), "confirm_zero_unit_hours": False}
    _field_rejection(api.post("hours_confirm", api.body("hours_confirm", payload)),
                     "zero_unit_hours_confirmation_required", ["operations." + operations[30] + ".unit_hours"])

    # 外协段改成逐序后，外协工序的周期不能留空。
    api.execute("UPDATE ExternalGroups SET merge_mode='separate' WHERE group_id='PROC-G'")
    payload = api.hours()
    assert payload["groups"] == []
    next(row for row in payload["operations"] if row["ref"] == operations[20])["external_days"] = None
    assert _field_rejection(api.post("hours_confirm", api.body("hours_confirm", payload)), "external_days_required",
                            ["operations." + operations[20] + ".external_days"]) == "不是合并组的外协工序必须填正数周期，不能留空。"


def test_group_preview_cycle_rejection_keeps_the_submitted_row_position(stage_api):
    api = stage_api
    api.prepare()
    entity = api.detail()["data"]
    internal = next(row["ref"] for row in entity["operations"] if row["sequence"] == 10)
    payload = edit(api)
    # 新段没有编号，规范化后会排到已有段前面；拒绝仍指回提交时的第 2 行。
    payload["groups"].append({"ref": None, "operation_refs": [internal],
                              "supplier_ref": payload["groups"][0]["supplier_ref"], "total_days": 0})
    before = api.preserved()
    assert _field_rejection(api.preview("groups_confirm", payload), "invalid_input", ["groups.1.total_days"]) == _CYCLE
    assert api.preserved() == before
