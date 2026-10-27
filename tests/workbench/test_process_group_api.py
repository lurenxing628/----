"""Outsourcing-stage preview, confirmation and receipt replay."""

import json

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.content import content_text
from core.services.process.workflow_state import record_confirmation
from tests.workbench.process_stage_api_support import BASE, PART, rejected, seed_stage_scale, stage_api_fixture, success

_api_fixture = stage_api_fixture


def edit(api, days=8.125):
    entity = api.detail()["data"]
    return {"groups": [{"ref": entity["external_groups"][0]["ref"],
                        "operation_refs": [row["ref"] for row in entity["operations"] if row["source"] == "external"],
                        "supplier_ref": entity["operations"][1]["supplier_ref"], "total_days": days}],
            "discard_group_refs": []}


@pytest.mark.parametrize("action", ("route_confirm", "source_confirm", "hours_confirm", "groups_confirm"))
def test_single_part_write_context_ignores_unrelated_template_changes(stage_api, action):
    api = stage_api
    api.prepare()
    payload = {"route_confirm": lambda: {"route": api.route(), "discard_group_refs": []},
               "source_confirm": api.source, "hours_confirm": api.hours,
               "groups_confirm": lambda: edit(api)}[action]()
    body = api.body(action, payload)
    with api.database() as conn:
        seed_stage_scale(conn, "UNRELATED", 3)
    assert success(api.post(action, body))["result"] in ("committed", "unchanged")


def test_single_part_write_context_keeps_hidden_deleted_template_facts(stage_api):
    api = stage_api
    api.prepare()
    api.execute("INSERT INTO PartOperations(part_no,seq,op_type_name,source,status,private_stage_note) "
                "VALUES (?,40,'历史工序','internal','deleted','保留的历史资料')", (PART,))
    body = api.body("hours_confirm", api.hours())
    api.execute("UPDATE PartOperations SET private_stage_note='历史资料已变更' WHERE part_no=? AND seq=40", (PART,))
    before = api.snapshot()
    rejected(api.post("hours_confirm", body), "stale_write")
    assert api.snapshot() == before


@pytest.mark.parametrize("foreign_member", (True, False))
def test_single_part_reads_preserve_cross_part_group_diagnostics_and_write_guard(stage_api, foreign_member):
    from core.errors import ValidationError
    from core.infrastructure.transaction import TransactionManager
    from core.services.process.workflow_state import record_confirmation

    api = stage_api
    api.prepare()
    if foreign_member:
        api.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,ext_days,ext_group_id) "
                    "VALUES ('PROC-003',20,'PROC-EX','热处理','external','PROC-S',3.25,'PROC-G')")
    else:
        api.execute("INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days,supplier_id) "
                    "VALUES ('FOREIGN-G','PROC-003',20,20,'merged',6.75,'PROC-S')")
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
            record_confirmation(conn, PART, "source")
    assert api.snapshot() == before


@pytest.mark.parametrize("shared_catalog", (False, True))
@pytest.mark.parametrize("stored_seq", (b"\x15", "第二道"))
def test_cross_part_group_members_with_mixed_seq_storage_sort_like_sqlite(stage_api, stored_seq, shared_catalog):
    from core.errors import ValidationError
    from data.repositories.workbench_process_workflow_repo import WorkbenchProcessWorkflowRepository

    api = stage_api
    api.prepare()
    # 同一外部零件的两道成员：一道整数序号，一道是存成 BLOB/文本的坏序号。
    for seq in (20, stored_seq):
        api.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,ext_days,ext_group_id) "
                    "VALUES ('PROC-003',?,'PROC-EX','热处理','external','PROC-S',3.25,'PROC-G')", (seq,))
    before = api.snapshot()
    with api.database() as conn:
        repo = WorkbenchProcessWorkflowRepository(conn)
        expected = [tuple(row) for row in conn.execute(
            "SELECT part_no,seq,id FROM PartOperations WHERE status='active' AND (part_no=? OR ext_group_id IN ("
            "SELECT group_id FROM ExternalGroups WHERE part_no=? UNION SELECT ext_group_id FROM PartOperations "
            "WHERE status='active' AND part_no=? AND ext_group_id IS NOT NULL)) ORDER BY part_no,seq,id", (PART,) * 3)]
        merged = repo.active_operations(PART, include_related_groups=True)
        assert [(row["part_no"], row["seq"], row["id"]) for row in merged] == expected
        assert stored_seq in [row["seq"] for row in merged]
        cross_part_by_group = None
        if shared_catalog:
            cross_part_by_group = {}
            for op in repo.active_operations():
                if op["ext_group_id"] is not None:
                    cross_part_by_group.setdefault(op["ext_group_id"], []).append(op)
        # 合并排序不再因混合存储类抛 TypeError，坏外协组照常按资料不合法拒绝确认。
        with pytest.raises(ValidationError):
            with TransactionManager(conn).transaction(begin_immediate=True):
                record_confirmation(conn, PART, "source", cross_part_by_group=cross_part_by_group)
    assert api.snapshot() == before


def test_route_confirmation_replaces_the_parts_old_members_in_the_shared_group_index(stage_api):
    """多零件路线文件共用跨件分组索引：换路线后旧工序所在分组里该零件的旧成员清掉（新工序已不在该组），
    新分组加入新成员，别的零件的成员原样保留。"""
    from data.repositories.workbench_process_workflow_repo import WorkbenchProcessWorkflowRepository

    api = stage_api
    api.prepare()
    api.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,ext_days,ext_group_id) "
                "VALUES ('PROC-003',20,'PROC-EX','热处理','external','PROC-S',3.25,'PROC-G')")
    with api.database() as conn:
        repo = WorkbenchProcessWorkflowRepository(conn)
        cross_part_by_group = {}
        for op in repo.active_operations():
            if op["ext_group_id"] is not None:
                cross_part_by_group.setdefault(op["ext_group_id"], []).append(op)
        old_operations = repo.active_operations(PART, include_related_groups=False)
        assert [(op["part_no"], op["seq"]) for op in cross_part_by_group["PROC-G"]] == [(PART, 20), ("PROC-003", 20)]
        # 新路线里第 20 道改归新分组 PROC-G2，原分组 PROC-G 里不再有本零件的工序。
        conn.execute("INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days,supplier_id) "
                     "VALUES ('PROC-G2',?,20,20,'merged',6.75,'PROC-S')", (PART,))
        conn.execute("UPDATE PartOperations SET ext_group_id='PROC-G2' WHERE part_no=? AND seq=20", (PART,))
        with TransactionManager(conn).transaction():
            record_confirmation(conn, PART, "route", cross_part_by_group=cross_part_by_group,
                                old_operations=old_operations)
    members = {gid: [(op["part_no"], op["seq"]) for op in items] for gid, items in cross_part_by_group.items()}
    assert members["PROC-G"] == [("PROC-003", 20)]
    assert members["PROC-G2"] == [(PART, 20)]


def test_merged_group_ignores_retained_member_days_in_current_diagnostics(stage_api):
    from core.services.workbench.master.overview import MasterOverviewService

    api = stage_api
    api.prepare()
    api.confirm("hours_confirm", api.hours())
    api.execute("UPDATE PartOperations SET ext_days='old invalid cycle' WHERE part_no=? AND source='external'", (PART,))
    entity = api.detail()["data"]
    assert entity["workflow"]["ready"]
    operation = next(row for row in entity["operations"] if row["source"] == "external")
    assert operation["external_days_source"] == "group" and not operation["issues"]
    assert api.rows("PartOperations", "part_no=? AND source='external'", (PART,))[0]["ext_days"] == "old invalid cycle"
    path = "/api/workbench/v1/entities/batch/" + api.ref("batch", "PROC-B")
    assert success(api.client.get(path))["data"]["template"]["complete"]
    with api.database() as conn:
        overview = MasterOverviewService(conn)
        with overview.read_snapshot():
            route = next(row for row in overview.entities if row["domain"] == "route" and row["business_code"] == PART)
            assert not route["issues"]
            retained = next(row for row in route["fields"] if "保留的逐序周期" in row["label"])
            assert retained["value"] == "old invalid cycle" and not retained["checked"]


@pytest.mark.parametrize("retained", ("old invalid cycle", b"\x01"))
def test_merged_group_retained_member_days_are_neither_exported_nor_imported(stage_api, retained):
    from core.services.workbench.process.file_codec import decode_process_file, encode_process_file
    from core.services.workbench.process.files import WorkbenchProcessFileService
    from tests.workbench.process_file_api_support import FileAPI

    api = stage_api
    api.prepare()
    api.confirm("hours_confirm", api.hours())
    api.execute("UPDATE PartOperations SET ext_days=? WHERE part_no=? AND seq=20", (retained, PART))
    target = api.ref()
    _, _, download = FileAPI(api.client).export("hours", target=target, selection="explicit", refs=[target])
    exported, _ = decode_process_file("hours", download.data, "csv")
    member = next(row["values"] for row in exported if row["values"]["sequence"] == 20)
    # 合并组只导出整段周期；保留的逐序旧周期不生效，坏旧值也不挡导出。
    assert "external_days" not in member and member["group_total_days"] == 6.75

    def preview(rows):
        content = encode_process_file("hours", rows, "csv").content
        with api.database() as conn:
            result, _ = WorkbenchProcessFileService(conn).preview_import("hours", content, file_format="csv")
        return result.as_dict()["rows"]

    assert all(row["result"] == "unchanged" and not row["errors"] for row in preview([row["values"] for row in exported]))
    # 逐序周期留空（\N）不写入也不算修改；填任何值都比不上不合法的旧值，只能改合并周期。
    for days, result in ((None, "unchanged"), (7, "rejected")):
        member_row, = preview([{"business_code": PART, "sequence": 20, "external_days": days}])
        assert member_row["result"] == result
        assert [error["field"] for error in member_row["errors"]] == ([] if days is None else ["external_days"])
    assert api.rows("PartOperations", "part_no=? AND seq=20", (PART,))[0]["ext_days"] == retained


def _synced_merged_batch(api, request_key):
    api.execute("DELETE FROM Schedule WHERE op_id IN (SELECT id FROM BatchOperations WHERE batch_id='PROC-B')")
    api.prepare()
    api.confirm("hours_confirm", api.hours())
    path = BASE + "/entities/batch/" + api.ref("batch", "PROC-B")
    detail = success(api.client.get(path))
    preview = success(api.client.post(path + "/sync-preview", json={"input": {}, "snapshot_ref": detail["meta"]["snapshot_ref"]}))["data"]
    synced = success(api.client.post(path + "/sync-confirm", json={"request_key": request_key,
        "write_token": preview["write_context"]["write_token"], "input": {"preview_ref": preview["preview_ref"]}}))
    assert synced["result"] == "committed"
    return path


def test_batch_detail_ignores_retained_member_days_of_merged_context(stage_api):
    api = stage_api
    path = _synced_merged_batch(api, "merged-retained-member-days")
    api.execute("UPDATE BatchOperations SET ext_days='old invalid cycle' WHERE batch_id='PROC-B' AND source='external'")
    external, = [row for row in success(api.client.get(path))["data"]["operations"] if row["source"] == "external"]
    assert external["external_group"]["merge_mode"] == "merged" and external["external_group"]["total_days"] == 6.75
    assert external["external_days"] is None and not external["issues"]


@pytest.mark.parametrize("sequence", ("x20", b"\x14"))
def test_batch_detail_reports_merged_context_with_non_integer_sequence(stage_api, sequence):
    api = stage_api
    path = _synced_merged_batch(api, "merged-non-integer-sequence")
    # 存量合并外协工序号混入非整数时，按分组范围不一致诊断，不在区间比较里抛 TypeError。
    api.execute("UPDATE BatchExternalContexts SET sequence=? WHERE operation_id=(SELECT MAX(id) FROM BatchOperations "
                "WHERE batch_id='PROC-B' AND source='external')", (sequence,))
    api.execute("UPDATE BatchOperations SET seq=? WHERE id=(SELECT MAX(id) FROM BatchOperations "
                "WHERE batch_id='PROC-B' AND source='external')", (sequence,))
    operations = success(api.client.get(path))["data"]["operations"]
    broken, = [row for row in operations if row["source"] == "external"]
    assert [item["code"] for item in broken["issues"]] == ["external_context_invalid"]
    assert "外协分组范围与本工序不一致" in broken["issues"][0]["message"]


# '--5' 和上标 '²' 看着像数字但 int() 不认，同样按文本排在数字工序之后。
@pytest.mark.parametrize("legacy", ["bad", "--5", "²"])
def test_batch_sync_preview_replaces_legacy_non_integer_sequence(stage_api, legacy):
    api = stage_api
    api.execute("DELETE FROM Schedule WHERE op_id IN (SELECT id FROM BatchOperations WHERE batch_id='PROC-B')")
    api.prepare()
    api.confirm("hours_confirm", api.hours())
    # 存量旧工序号坏成文本时详情照常展示，从模板更新工序的预检也要能列出替换结果来修复它。
    api.execute("UPDATE BatchOperations SET seq='" + legacy + "' WHERE op_code='STAGE-API-OLD'")
    path = BASE + "/entities/batch/" + api.ref("batch", "PROC-B")
    detail = success(api.client.get(path))
    assert [row["sequence"] for row in detail["data"]["operations"]] == [legacy]
    preview = success(api.client.post(path + "/sync-preview", json={"input": {}, "snapshot_ref": detail["meta"]["snapshot_ref"]}))["data"]
    assert [(row["sequence"], row["change"]) for row in preview["changes"]] == [(10, "added"), (20, "added"), (30, "added"), (legacy, "removed")]
    assert preview["change_counts"] == {"added": 3, "removed": 1, "updated": 0, "unchanged": 0}


@pytest.mark.parametrize("change, expected_rule, expected_detail_code", [
    ("UPDATE Suppliers SET status='inactive' WHERE supplier_id='PROC-S'", "operation.supplier", "supplier_invalid"),
    ("INSERT OR REPLACE INTO WorkbenchSupplierProfiles(supplier_id,inactive_reason) VALUES ('PROC-S','pending_review')", "operation.supplier", "supplier_invalid"),
    ("UPDATE ExternalGroups SET supplier_id='PROC-S2' WHERE group_id='PROC-G'", "group.supplier", "external_group_supplier_mismatch"),
])
def test_source_diagnostics_reject_supplier_and_group_drift(stage_api, change, expected_rule, expected_detail_code):
    from core.services.workbench.master.overview import MasterOverviewService

    api = stage_api
    api.prepare()
    api.confirm("hours_confirm", api.hours())
    api.execute("INSERT INTO Suppliers(supplier_id,name,default_days,status) VALUES ('PROC-S2','另一个供应商',3.25,'active')")
    api.execute("INSERT INTO WorkbenchSupplierOpTypes(supplier_id,op_type_id) VALUES ('PROC-S2','PROC-EX')")
    api.execute(change)
    with api.database() as conn:
        overview = MasterOverviewService(conn)
        with overview.read_snapshot():
            route = next(row for row in overview.entities if row["domain"] == "route" and row["business_code"] == PART)
            assert any(row["rule"] == expected_rule for row in route["issues"])
    entity = api.detail()["data"]
    assert not entity["workflow"]["ready"]
    external = next(row for row in entity["operations"] if row["source"] == "external")
    assert any(row["code"] == expected_detail_code for row in external["issues"])
    path = "/api/workbench/v1/entities/batch/" + api.ref("batch", "PROC-B")
    assert not success(api.client.get(path))["data"]["template"]["complete"]


def test_group_preview_command_and_receipt_roundtrip(stage_api):
    api = stage_api
    with api.database() as conn:
        conn.execute("INSERT INTO Suppliers(supplier_id,name,default_days,status) VALUES ('PROC-S2','另一热处理厂',3.25,'active')")
        conn.execute("INSERT INTO WorkbenchSupplierOpTypes(supplier_id,op_type_id) VALUES ('PROC-S2','PROC-EX')")
        conn.execute("UPDATE ExternalGroups SET end_seq=21,supplier_id=NULL WHERE group_id='PROC-G'")
        conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,ext_days,"
                     "ext_group_id,setup_hours,unit_hours) VALUES ('PROC-001',21,'PROC-EX','热处理','external','PROC-S2',3.25,'PROC-G',0,0)")
        conn.execute("DELETE FROM Schedule WHERE op_id IN (SELECT id FROM BatchOperations WHERE batch_id='PROC-B')")
        with TransactionManager(conn).transaction():
            record_confirmation(conn, PART, "route")
    before = api.snapshot()
    rejected(api.preview("source_confirm", api.source()), "group_supplier_mismatch", 422)
    assert api.snapshot() == before
    entity = api.detail()["data"]
    assert not entity["workflow"]["ready"]
    assert any(row["code"] == "external_group_supplier_mismatch" for row in entity["external_groups"][0]["issues"])
    path = "/api/workbench/v1/entities/batch/" + api.ref("batch", "PROC-B")
    detail = success(api.client.get(path))
    assert not detail["data"]["template"]["complete"]
    rejected(api.client.post(path + "/sync-preview", json={"input": {}, "snapshot_ref": detail["meta"]["snapshot_ref"]}),
             "constraint_conflict")
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
    part_ref = api.ref()
    confirmations = api.rows("WorkbenchProcessOperationConfirmations", "part_ref=?", (part_ref,))
    stored = api.rows("WorkbenchProcessWorkflow", "part_ref=?", (part_ref,))[0]
    assert all(row["signature"] is None and row["content_json"] for row in confirmations)
    assert all(stored[stage + "_signature"] is None and stored[stage + "_content_json"] for stage in ("route", "source", "hours"))
    source_document = json.loads(stored["source_content_json"])
    group_ref = detail["external_groups"][0]["ref"]
    assert len(source_document[3]) == 1 and len(source_document[3][group_ref]["members"]) == 2
    external_refs = {row["ref"] for row in api.detail()["data"]["operations"] if row["source"] == "external"}
    source_row = next(row for row in confirmations if row["stage"] == "source" and row["operation_ref"] in external_refs)
    local_document = json.loads(source_row["content_json"])
    assert "members" not in local_document[2][8]
    assert local_document[2][7]["capable"] is True
    local_document[2][7]["capable"] = 1
    api.execute("UPDATE WorkbenchProcessOperationConfirmations SET content_json=? WHERE operation_ref=? AND stage='source'",
                (content_text(local_document), source_row["operation_ref"]))
    changed = api.detail()["data"]
    assert not changed["workflow"]["ready"]
    assert next(row for row in changed["operations"] if row["ref"] == source_row["operation_ref"])["confirmation"]["source"]["state"] == "unconfirmed"
    api.confirm("source_confirm", api.source())
    assert api.detail()["data"]["workflow"]["ready"]
    # A shared membership change affects the group's operations, not an unrelated internal operation.
    api.execute("UPDATE PartOperations SET ext_group_id=NULL WHERE part_no=? AND seq=21", (PART,))
    changed = api.detail()["data"]
    assert not changed["workflow"]["ready"]
    assert all(row["confirmation"]["source"]["state"] == "unconfirmed" for row in changed["operations"] if row["ref"] in external_refs)
    assert all(row["confirmation"]["source"]["state"] == "confirmed" for row in changed["operations"] if row["source"] == "internal")
    api.execute("UPDATE PartOperations SET ext_group_id='PROC-G' WHERE part_no=? AND seq=21", (PART,))
    assert api.detail()["data"]["workflow"]["ready"]
    # Old markers preserve the actual historical record while current facts require a new confirmation.
    legacy_marker, legacy_stamp, legacy_person = "a" * 64, "2001-02-03T04:05:06Z", "原确认人"
    business = api.preserved()
    with api.database() as conn:
        for stage in ("route", "source", "hours"):
            conn.execute("UPDATE WorkbenchProcessWorkflow SET " + stage + "_signature=?," + stage + "_content_json=NULL,"
                         + stage + "_confirmed_at=?," + stage + "_confirmed_by=? WHERE part_ref=?",
                         (legacy_marker, legacy_stamp, legacy_person, part_ref))
        conn.execute("UPDATE WorkbenchProcessOperationConfirmations SET signature=?,content_json=NULL,confirmed_at=?,confirmed_by=? WHERE part_ref=?",
                     (legacy_marker, legacy_stamp, legacy_person, part_ref))
    old_rows = api.snapshot()
    historical = api.detail()["data"]
    assert historical["workflow"]["route"]["state"] == "unconfirmed" and not historical["workflow"]["ready"]
    for stage in ("route", "source", "hours"):
        current = historical["workflow"][stage]
        assert current["content_state"] == "missing_original" and "重新确认" in current["reason"]
        assert current["history"] == {"confirmed_at": legacy_stamp, "confirmed_by": legacy_person}
        assert current["confirmed_at"] is None and current["confirmed_by"] is None
    assert all(row["confirmation"]["source"]["content_state"] == "missing_original" for row in historical["operations"] if row["status"] == "active")
    assert api.snapshot() == old_rows
    rejected(api.preview("source_confirm", api.source()), "stage_locked")
    with api.database() as conn:
        with TransactionManager(conn).transaction():
            record_confirmation(conn, PART, "route")
    api.confirm("source_confirm", api.source())
    api.confirm("hours_confirm", api.hours())
    assert api.detail()["data"]["workflow"]["ready"] and api.preserved() == business
    stored = api.rows("WorkbenchProcessWorkflow", "part_ref=?", (part_ref,))[0]
    assert all(stored[stage + "_signature"] == legacy_marker and stored[stage + "_content_json"]
               and stored[stage + "_confirmed_at"] != legacy_stamp for stage in ("route", "source", "hours"))
    assert all(row["signature"] == legacy_marker and row["content_json"] and row["confirmed_at"] != legacy_stamp
               for row in api.rows("WorkbenchProcessOperationConfirmations", "part_ref=?", (part_ref,)))
    detail = success(api.client.get(path))
    assert detail["data"]["template"]["complete"]
    preview = success(api.client.post(path + "/sync-preview", json={"input": {}, "snapshot_ref": detail["meta"]["snapshot_ref"]}))["data"]
    synced = success(api.client.post(path + "/sync-confirm", json={"request_key": "supplier-group-sync-merged",
        "write_token": preview["write_context"]["write_token"], "input": {"preview_ref": preview["preview_ref"]}}))
    assert synced["result"] == "committed"
    external = [row for row in success(api.client.get(path))["data"]["operations"] if row["source"] == "external"]
    assert len(external) == 2 and {row["resources"]["supplier"]["business_code"] for row in external} == {"PROC-S"}
    # The same route may keep an old default supplier while its separate work
    # is assigned elsewhere. Only the actual members' qualification matters.
    api.execute("UPDATE ExternalGroups SET merge_mode='separate',total_days=NULL WHERE group_id='PROC-G'")
    source = api.source()
    for row in source["operations"]:
        if row["source"] == "external":
            row["supplier_ref"] = api.ref("supplier", "PROC-S2")
    api.confirm("source_confirm", source)
    api.confirm("hours_confirm", api.hours())
    assert api.detail()["data"]["workflow"]["ready"]
    api.execute("UPDATE Suppliers SET status='inactive' WHERE supplier_id='PROC-S'")
    assert api.detail()["data"]["workflow"]["ready"]
    detail = success(api.client.get(path))
    assert detail["data"]["template"]["complete"]
    success(api.client.post(path + "/sync-preview", json={"input": {}, "snapshot_ref": detail["meta"]["snapshot_ref"]}))
    api.execute("UPDATE Suppliers SET status='inactive' WHERE supplier_id='PROC-S2'")
    assert not api.detail()["data"]["workflow"]["ready"]


def test_hours_import_group_total_days_requires_all_group_members_source_confirmed(stage_api):
    from core.services.workbench.process.file_codec import encode_process_file
    from core.services.workbench.process.files import WorkbenchProcessFileService

    api = stage_api
    api.prepare()
    api.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,ext_days,ext_group_id) "
                "VALUES ('PROC-001',21,'PROC-EX','热处理','external','PROC-S',3.25,'PROC-G')")
    api.execute("UPDATE ExternalGroups SET end_seq=21 WHERE group_id='PROC-G'")
    with api.database() as conn:
        with TransactionManager(conn).transaction():
            record_confirmation(conn, PART, "route")
    api.confirm("source_confirm", api.source())
    second_ref = next(row["ref"] for row in api.detail()["data"]["operations"] if row["sequence"] == 21)
    api.execute("DELETE FROM WorkbenchProcessOperationConfirmations WHERE operation_ref=? AND stage='source'", (second_ref,))
    content = encode_process_file("hours", [
        {"business_code": PART, "sequence": 20, "group_total_days": 9.5},
        {"business_code": PART, "sequence": 21},
    ], "csv").content
    with api.database() as conn:
        preview, _ = WorkbenchProcessFileService(conn).preview_import("hours", content, file_format="csv")
    body = preview.as_dict()
    assert body["summary"]["update"] == 0 and body["summary"]["rejected"] == 2
    assert all(row["result"] == "rejected" for row in body["rows"])
    assert all(any(err["code"] == "stage_not_ready" for err in row["errors"]) for row in body["rows"])
    unchanged_content = encode_process_file("hours", [
        {"business_code": PART, "sequence": 20, "group_total_days": 6.75},
        {"business_code": PART, "sequence": 21},
    ], "csv").content
    with api.database() as conn:
        unchanged_preview, _ = WorkbenchProcessFileService(conn).preview_import("hours", unchanged_content, file_format="csv")
    unchanged_body = unchanged_preview.as_dict()
    assert unchanged_body["summary"]["unchanged"] == 2 and unchanged_body["summary"]["rejected"] == 0
    assert all(row["result"] == "unchanged" and not row["errors"] for row in unchanged_body["rows"])
    # 合并组成员的逐序周期按原值导回不算修改，改成别的值要拒绝，只能改合并周期。
    for days, result in ((3.25, "unchanged"), (7, "rejected")):
        member_content = encode_process_file("hours", [
            {"business_code": PART, "sequence": 21, "external_days": days},
        ], "csv").content
        with api.database() as conn:
            member_preview, _ = WorkbenchProcessFileService(conn).preview_import("hours", member_content, file_format="csv")
        member_row = member_preview.as_dict()["rows"][0]
        assert member_row["result"] == result
        assert [error["field"] for error in member_row["errors"]] == ([] if result == "unchanged" else ["external_days"])
