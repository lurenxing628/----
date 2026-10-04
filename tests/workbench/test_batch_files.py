"""Real first-sheet XLSX bytes, three modes, range exports and atomic receipts."""

import json
import zipfile
from datetime import date
from io import BytesIO

import openpyxl
import pytest

from core.models.workbench_batch_file import FILE_HEADERS, HEADERS
from core.services.workbench.batch.file_codec import write_batch_file
from tests.workbench.batch_support import BASE, assert_error, batch_database, body, detail, list_data, ref_for, state
from tests.workbench.legacy_batch_lineage_copy_support import assert_dashboard_copy_items

_batch_fixture = batch_database


def uploaded(client, rows, mode="overwrite", content=None):
    content = content or write_batch_file(rows, template=True)
    return client.post(BASE + "/import-preview", data={"file": (BytesIO(content), "batch.xlsx"), "mode": mode,
        "scope": json.dumps({}), "snapshot_ref": list_data(client)["meta"]["snapshot_ref"]}, content_type="multipart/form-data")


def confirm(client, document, key="batch-file-confirm-00001"):
    return client.post(BASE + "/import-confirm", json=body(document["write_context"], {"preview_ref": document["preview_ref"]}, key))


def data_rows(response):
    assert response.status_code == 200, response.get_json()
    workbook = openpyxl.load_workbook(BytesIO(response.data), data_only=False)
    try:
        return list(workbook.worksheets[0].iter_rows(values_only=True))
    finally:
        workbook.close()


@pytest.mark.parametrize("mode", ("overwrite", "append"))
def test_modes_preserve_existing_empty_columns_and_no_automatic_operations(batch_client, mode):
    client = batch_client
    before = state(client)
    response = uploaded(client, [["FREE-001", "P1", 5, None, None, None, None, "changed"],
                                 ["NEW-XLSX", "P1", 3, "2028-02-29", "急件", "未齐套", None, "import"]], mode)
    assert response.status_code == 200, response.get_json()
    document = response.get_json()["data"]
    assert document["can_confirm"] and state(client) == before
    response = confirm(client, document)
    assert response.status_code == 200, response.get_json()
    record = detail(client)["data"]
    assert record["fields"]["remark"] == ("changed" if mode == "overwrite" else "keep-hidden")
    assert record["fields"]["ready_status"] == "no" and record["fields"]["priority"] == "normal"
    new = detail(client, ref_for(client, key="NEW-XLSX"))["data"]
    assert new["operations"] == [] and new["fields"]["due_date"] == "2028-02-29"
    after = state(client)
    assert after[0] == before[0]
    assert_dashboard_copy_items(before[1], after[1], 1)
    for table in before[1]:
        if table not in ("Batches", "WorkbenchEntityRefs", "WorkbenchCommandReceipts", "WorkbenchDashboardItems"):
            assert after[1][table] == before[1][table], table
    saved = state(client)
    replay = confirm(client, document)
    assert replay.get_json()["replayed"] and state(client) == saved


def test_replace_shows_entire_deletion_set_and_blocks_planned_fact(batch_client):
    client = batch_client
    before = state(client)
    response = uploaded(client, [["NEW-XLSX", "P1", 3, None, "普通", "齐套", None, None]], "replace")
    document = response.get_json()["data"]
    assert document["can_confirm"] is False and document["write_context"] is None
    assert {row["before"]["business_code"] for row in document["deleted"]} == {"B1", "FREE-001"}
    assert any(row["errors"] for row in document["deleted"]) and state(client) == before


def test_replace_unreferenced_is_atomic_and_new_identity(batch_client):
    client, conn = batch_client, batch_client.batch_conn
    conn.execute("DELETE FROM Schedule")
    conn.execute("DELETE FROM BatchMaterials")
    conn.commit()
    old_ref = ref_for(client)
    document = uploaded(client, [["FREE-001", "P1", 3, None, "普通", "齐套", None, None]], "replace").get_json()["data"]
    assert document["can_confirm"]
    response = confirm(client, document)
    assert response.status_code == 200, response.get_json()
    assert list_data(client)["data"]["page"]["total"] == 1 and ref_for(client) != old_ref
    assert not detail(client)["data"]["operations"]


@pytest.mark.parametrize("row", [[1, "P1", 3, None, None, None, None, None], ["NEW", "P1", 0, None, None, None, None, None],
                                 ["NEW", "P1", 2, "2026-02-29", None, None, None, None], ["NEW", "missing", 2, None, None, None, None, None]])
def test_invalid_file_rows_never_write(batch_client, row):
    before = state(batch_client)
    response = uploaded(batch_client, [row])
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["data"]["can_confirm"] is False
    assert state(batch_client) == before


def test_template_bytes_and_selected_export_preserve_text_and_scope(batch_client):
    client = batch_client
    before = state(client)
    template = client.get(BASE + "/template")
    assert tuple(data_rows(template)[0]) == FILE_HEADERS
    assert state(client) == before
    conn = client.batch_conn
    conn.execute("UPDATE Batches SET remark='=FORMULA_NOT_EXECUTED' WHERE batch_id='FREE-001'")
    conn.commit()
    result = list_data(client, size=1)
    response = client.post(BASE + "/export-preview", json={"selection": "selected", "refs": [ref_for(client)],
                          "scope": {"size": 1, "snapshot_ref": result["meta"]["snapshot_ref"]}})
    assert response.status_code == 200, response.get_json()
    export = client.get(BASE + "/export", query_string={"export_ref": response.get_json()["data"]["export_ref"]})
    rows = data_rows(export)
    assert len(rows) == 2 and rows[1][0] == "FREE-001" and rows[1][7] == "=FORMULA_NOT_EXECUTED"
    workbook = openpyxl.load_workbook(BytesIO(export.data), data_only=False)
    sheet = workbook.active
    assert sheet is not None
    assert sheet["H2"].data_type == "s"
    workbook.close()
    assert export.headers["Cache-Control"] == "no-store" and export.headers["X-Workbench-Row-Count"] == "1"


def test_file_confirm_stale_rolls_back_and_duplicate_rejected(batch_client):
    client = batch_client
    rows = [["NEW", "P1", 2, None, None, None, None, None]]
    duplicate = uploaded(client, rows * 2).get_json()["data"]
    assert not duplicate["can_confirm"]
    document = uploaded(client, rows).get_json()["data"]
    client.batch_conn.execute("UPDATE Materials SET stock_qty=0")
    client.batch_conn.commit()
    before = state(client)
    assert_error(confirm(client, document), "stale_write")
    assert state(client) == before


def test_import_write_token_binds_the_preview_ref_and_is_issued_after_the_read_slot(batch_client, monkeypatch):
    from web.routes.workbench import batch_files, read_budget

    client = batch_client
    original_issue, original_validate, original_save = batch_files.issue_write_context, batch_files.validate_write_context, batch_files.save_preview
    calls = []

    def issue(subject, actions, snapshot):
        calls.append(("issue", sorted(snapshot), read_budget.BATCH_READ_SLOTS._available))
        return original_issue(subject, actions, snapshot)

    def validate(token, subject, action, snapshot):
        calls.append(("validate", sorted(snapshot), None))
        return original_validate(token, subject, action, snapshot)

    def save(*args):
        calls.append(("save", None, read_budget.BATCH_READ_SLOTS._available))
        return original_save(*args)

    monkeypatch.setattr(batch_files, "issue_write_context", issue)
    monkeypatch.setattr(batch_files, "validate_write_context", validate)
    monkeypatch.setattr(batch_files, "save_preview", save)
    first = uploaded(client, [["FREE-001", "P1", 5, None, None, None, None, "first"]]).get_json()["data"]
    second = uploaded(client, [["FREE-001", "P1", 5, None, None, None, None, "second"]]).get_json()["data"]
    # Both tokens are issued once the shared batch read slot is free again, and the write token never
    # serializes the document (every row carries its whole batch); the preview ref names it instead.
    assert calls == [("save", None, 1), ("issue", ["fingerprint", "preview_ref"], 1)] * 2
    before = state(client)
    crossed = client.post(BASE + "/import-confirm", json=body(first["write_context"], {"preview_ref": second["preview_ref"]},
                                                               "batch-file-crossed-0001"))
    assert_error(crossed, "stale_write")
    assert state(client) == before
    assert confirm(client, second).status_code == 200
    assert calls[-1] == ("validate", ["fingerprint", "preview_ref"], None)
    assert detail(client)["data"]["fields"]["remark"] == "second"


def test_first_sheet_only_formulas_and_bool_quantities(batch_client):
    client = batch_client
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(HEADERS)
    sheet.append(["FIRST", "P1", 3, None, None, None, None, None])
    second = workbook.create_sheet("ignored")
    second.append(["not a batch sheet"])
    content = BytesIO()
    workbook.save(content)
    document = uploaded(client, [], content=content.getvalue()).get_json()["data"]
    assert document["can_confirm"] and document["count"] == 1
    assert document["warnings"][0]["code"] == "first_sheet_only"
    for value in (True, "=1+1"):
        sheet["C2"] = value
        content = BytesIO()
        workbook.save(content)
        before = state(client)
        document = uploaded(client, [], content=content.getvalue()).get_json()["data"]
        assert not document["can_confirm"] and state(client) == before
    workbook.close()


def test_corrupt_xlsx_is_known_rejection_not_unknown_commit(batch_client):
    before = state(batch_client)
    assert_error(uploaded(batch_client, [], content=b"invalid file"), "invalid_input")
    assert state(batch_client) == before
    content = BytesIO()
    with zipfile.ZipFile(content, "w") as archive:
        archive.writestr("[Content_Types].xml", b"<invalid xml")
    assert_error(uploaded(batch_client, [], content=content.getvalue()), "invalid_input")
    assert state(batch_client) == before


def test_filtered_export_shows_effective_readiness_and_original_roundtrip_value(batch_client, monkeypatch):
    from core.services.workbench.batch import projection

    current_day = [date(2026, 10, 3)]
    class CurrentDay(date):
        @classmethod
        def today(cls):
            return current_day[0]

    monkeypatch.setattr(projection, "date", CurrentDay)
    client, conn = batch_client, batch_client.batch_conn
    conn.execute("INSERT INTO BatchMaterialReviews(requirement_id,batch_quantity) VALUES(51,17)")
    conn.execute("INSERT INTO BatchMaterialArrivals(requirement_id,arrival_date,quantity) VALUES(51,'2026-10-04',16.5)")
    conn.commit()
    assert list_data(client, ready_status="yes")["data"]["entities"] == []
    current_day[0] = date(2026, 10, 4)
    filtered = list_data(client, ready_status="yes")
    assert [row["business_code"] for row in filtered["data"]["entities"]] == ["B1"]
    response = client.post(BASE + "/export-preview", json={"selection": "filtered", "scope": {
        "ready_status": "yes", "snapshot_ref": filtered["meta"]["snapshot_ref"]}})
    assert response.status_code == 200, response.get_json()
    exported = client.get(BASE + "/export", query_string={"export_ref": response.get_json()["data"]["export_ref"]})
    rows = data_rows(exported)
    assert tuple(rows[0]) == FILE_HEADERS
    assert rows[1][0] == "B1"
    assert rows[1][rows[0].index("维护齐套标记")] == "未齐套"
    assert rows[1][rows[0].index("当前有效齐套（只读）")] == "齐套"
    original = state(client)
    preview = uploaded(client, [], content=exported.data).get_json()["data"]
    assert preview["can_confirm"], preview
    saved = confirm(client, preview, key="effective-ready-roundtrip-01")
    assert saved.status_code == 200 and saved.get_json()["result"] == "unchanged", saved.get_json()
    assert state(client)[1]["Batches"] == original[1]["Batches"]
    assert conn.execute("SELECT ready_status FROM Batches WHERE batch_id='B1'").fetchone()[0] == "no"
    workbook = openpyxl.load_workbook(BytesIO(exported.data))
    sheet = workbook.worksheets[0]
    sheet.cell(2, FILE_HEADERS.index("当前有效齐套（只读）") + 1, '=IF(1=1,"齐套","未齐套")')
    modified = BytesIO()
    workbook.save(modified)
    ignored = uploaded(client, [], content=modified.getvalue()).get_json()["data"]
    # 只读列不导入，其余各格和导出时一样，这一行判为不变，维护齐套标记仍是 no。
    assert ignored["can_confirm"] and ignored["rows"][0]["action"] == "unchanged" and ignored["rows"][0]["input"] is None
    sheet.cell(2, FILE_HEADERS.index("维护齐套标记") + 1, "齐套")
    modified = BytesIO()
    workbook.save(modified)
    rejected = uploaded(client, [], content=modified.getvalue()).get_json()["data"]
    assert not rejected["can_confirm"]
    assert "齐套按物料需求计算" in rejected["rows"][0]["errors"][0]
    workbook.close()


def test_legacy_ready_header_remains_writable_and_duplicate_aliases_are_rejected(batch_client):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(HEADERS)
    sheet.append(["FREE-001", "P1", 5, None, "普通", "齐套", None, "legacy header"])
    output = BytesIO()
    workbook.save(output)
    preview = uploaded(batch_client, [], content=output.getvalue()).get_json()["data"]
    assert preview["can_confirm"] and preview["rows"][0]["input"]["fields"]["ready_status"] == "yes"
    sheet.cell(1, 9, "维护齐套标记")
    output = BytesIO()
    workbook.save(output)
    assert_error(uploaded(batch_client, [], content=output.getvalue()), "invalid_input")
    workbook.close()


def test_export_projects_once_in_the_shared_read_slot_and_writes_after_release(batch_client, monkeypatch):
    import sqlite3

    from core.services.workbench.batch.files import WorkbenchBatchFileService
    from core.services.workbench.batch.projection import BatchProjection
    from core.services.workbench.batch.queries import WorkbenchBatchQueryService
    from web.routes.workbench import read_budget

    client, conn = batch_client, batch_client.batch_conn
    conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('FREE-002','P1',2),('FREE-003','P1',3)")
    conn.commit()
    filtered = list_data(client)
    response = client.post(BASE + "/export-preview", json={"selection": "filtered", "scope": {"snapshot_ref": filtered["meta"]["snapshot_ref"]}})
    assert response.status_code == 200, response.get_json()
    count = response.get_json()["data"]["count"]
    assert count == 4
    original_init, original_export, original_slot = BatchProjection.__init__, WorkbenchBatchFileService.export, read_budget.BATCH_READ_SLOTS.slot
    original_details = WorkbenchBatchQueryService.details
    projected, written, slots = [], [], []

    def details(reader, refs):
        # Template status, materials and every entity come from the captured facts only.
        conn.set_authorizer(lambda *_args: sqlite3.SQLITE_DENY)
        try:
            return original_details(reader, refs)
        finally:
            conn.set_authorizer(None)

    def project(projection, facts):
        # Built once for the whole file, after the SQLite read lock was released.
        assert not conn.in_transaction
        projected.append(read_budget.BATCH_READ_SLOTS._available)
        original_init(projection, facts)

    def export(entities):
        written.append((len(entities), read_budget.BATCH_READ_SLOTS._available, conn.in_transaction))
        return original_export(entities)

    def slot():
        slots.append(True)
        return original_slot()

    monkeypatch.setattr(BatchProjection, "__init__", project)
    monkeypatch.setattr(WorkbenchBatchQueryService, "details", details)
    monkeypatch.setattr(WorkbenchBatchFileService, "export", staticmethod(export))
    monkeypatch.setattr(read_budget.BATCH_READ_SLOTS, "slot", slot)
    exported = client.get(BASE + "/export", query_string={"export_ref": response.get_json()["data"]["export_ref"]})
    rows = data_rows(exported)
    assert sorted(row[0] for row in rows[1:]) == ["B1", "FREE-001", "FREE-002", "FREE-003"]
    assert projected == [0] and slots == [True]
    assert written == [(count, 1, False)]


# 旧数据：带时间的交期/齐套日期、斜杠日期、旧英文优先级与齐套写法、备注首尾空格。
LEGACY_BATCHES = (("B-TIME", "2026-10-12 00:00:00", "normal", "yes", "2026-10-01 08:00:00", "带时间的日期"),
                  ("B-SLASH", "2026/10/12", "high", "是", None, " 前后空格 "),
                  ("B-EN", None, "URGENT", "YES", None, ""))


def _legacy_export(client):
    from tests.workbench.identity_metadata_support import insert_row

    conn = client.batch_conn
    for code, due, priority, ready, ready_date, remark in LEGACY_BATCHES:
        insert_row(conn, "Batches", dict(batch_id=code, part_no="P1", quantity=3, part_name="x", status="pending", due_date=due,
                                         priority=priority, ready_status=ready, ready_date=ready_date, remark=remark))
    conn.commit()
    listed = list_data(client, size=20)
    refs = [ref_for(client, key=row[0]) for row in LEGACY_BATCHES]
    approved = client.post(BASE + "/export-preview", json={"selection": "selected", "refs": refs,
                           "scope": {"size": 20, "snapshot_ref": listed["meta"]["snapshot_ref"]}})
    assert approved.status_code == 200, approved.get_json()
    exported = client.get(BASE + "/export", query_string={"export_ref": approved.get_json()["data"]["export_ref"]})
    assert exported.status_code == 200
    return exported.data


def test_legacy_values_round_trip_unchanged_and_are_never_normalized(batch_client):
    client = batch_client
    content = _legacy_export(client)
    before = state(client)
    document = uploaded(client, [], content=content).get_json()["data"]
    assert document["can_confirm"], document
    assert [(row["business_code"], row["action"], row["errors"]) for row in document["rows"]] == [
        (row[0], "unchanged", []) for row in LEGACY_BATCHES]
    saved = confirm(client, document, key="legacy-batch-roundtrip-01")
    assert saved.status_code == 200 and saved.get_json()["result"] == "unchanged", saved.get_json()
    assert state(client)[1]["Batches"] == before[1]["Batches"]


def test_legacy_row_edit_writes_only_changed_cell_and_new_values_are_still_checked(batch_client):
    client = batch_client
    workbook = openpyxl.load_workbook(BytesIO(_legacy_export(client)))
    sheet = workbook.worksheets[0]
    line = next(row[0].row for row in sheet.iter_rows(min_row=2) if row[0].value == "B-SLASH")
    sheet.cell(line, FILE_HEADERS.index("备注") + 1, " 新备注 ")
    output = BytesIO()
    workbook.save(output)
    document = uploaded(client, [], content=output.getvalue()).get_json()["data"]
    row = next(item for item in document["rows"] if item["business_code"] == "B-SLASH")
    # 只写真正改了的备注；旧优先级 high、斜杠交期没动，既不校验也不写回。
    assert document["can_confirm"] and row["action"] == "update" and row["input"] == {"fields": {"remark": "新备注"}}
    sheet.cell(line, FILE_HEADERS.index("优先级") + 1, "很急")
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    document = uploaded(client, [], content=output.getvalue()).get_json()["data"]
    row = next(item for item in document["rows"] if item["business_code"] == "B-SLASH")
    assert not document["can_confirm"] and row["action"] == "rejected" and "优先级" in row["errors"][0]
