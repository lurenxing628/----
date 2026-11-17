"""Batch two-stage SQL pagination keeps whole-scope decisions and bounds operation assembly to the page."""

from datetime import datetime
from io import BytesIO

from openpyxl import load_workbook

from core.models import workbench_batch_query as batch_query
from core.models.workbench_batch_query import batch_scope
from core.models.workbench_execution import ExecutionProjection
from core.services.workbench.batch.projection import BatchProjection
from core.services.workbench.batch.queries import WorkbenchBatchQueryService
from tests.workbench.batch_support import BASE, batch_database
from tests.workbench.identity_metadata_support import insert_row

_batch_fixture = batch_database


def page_batches(conn):
    for code, quantity, due, ready in (
        ("PAGE-A", 3, None, "yes"),
        ("PAGE-B", 2, "2026-10-15", "yes"),
        ("PAGE-C", 2, "2026-10-16", "no"),
        ("PAGE-D", 7, "2026-10-14", "partial"),
    ):
        insert_row(conn, "Batches", {"batch_id": code, "part_no": "P1", "part_name": "retained name",
            "quantity": quantity, "due_date": due, "priority": "normal", "ready_status": ready, "status": "pending"})
        if code != "PAGE-A":
            insert_row(conn, "BatchOperations", {"op_code": code + "_01", "batch_id": code, "seq": 1,
                "op_type_id": "OT1", "op_type_name": "turning", "source": "internal", "setup_hours": 0,
                "unit_hours": 0, "machine_id": None if code == "PAGE-C" else "M1",
                "operator_id": None if code == "PAGE-C" else "O1", "status": "completed" if code == "PAGE-D" else "pending"})
    conn.commit()


def test_summary_keeps_complete_entity_values_and_whole_scope_pagination(batch_client, monkeypatch):
    conn = batch_client.batch_conn
    page_batches(conn)
    reader = WorkbenchBatchQueryService(conn, as_of=datetime.now())
    with reader.facts.detached_read_snapshot() as baseline_snap:
        facts = baseline_snap.load()
        projection = BatchProjection(facts)
        full = {row["batch_id"]: projection.entity(row) for row in facts["Batches"] if row["batch_id"].startswith("PAGE-")}

    scope = batch_scope({"query": "PAGE-", "sort": "quantity", "size": 1})
    expanded, serialize = [], ExecutionProjection.to_dict

    def capture(row):
        expanded.append(row.operation_ref)
        return serialize(row)

    monkeypatch.setattr(ExecutionProjection, "to_dict", capture)
    order = ["PAGE-B", "PAGE-C", "PAGE-A", "PAGE-D"]
    for number, code in enumerate(order, 1):
        page_query = dict(scope, page=number)
        data, _ = reader.read_page(page_query)
        assert data["page"]["total"] == 4 and data["page"]["pages"] == 4
        assert data["metrics"] == {"scope": "filtered", "total": 4, "completed": 1}
        assert data["entities"] == [{key: value for key, value in full[code].items() if key != "operations"}]

    assert [row["business_code"] for row in reader.read_page(dict(scope, size=10, focus="gaps"))[0]["entities"]] == ["PAGE-C", "PAGE-A", "PAGE-D"]
    assert [row["business_code"] for row in reader.read_page(dict(scope, size=10, focus="unready"))[0]["entities"]] == ["PAGE-C", "PAGE-D"]
    assert [row["business_code"] for row in reader.read_page(dict(scope, size=10, status="completed"))[0]["entities"]] == ["PAGE-D"]
    assert [row["business_code"] for row in reader.read_page(dict(scope, size=10, sort="due_date", direction="desc"))[0]["entities"]] == ["PAGE-A", "PAGE-C", "PAGE-B", "PAGE-D"]
    selection, _ = reader.read_selection(scope)
    assert selection == {"refs": [full[code]["ref"] for code in order], "count": 4}
    assert expanded == []

    with reader.facts.detached_read_snapshot(mode="single_template", target_ref=full["PAGE-B"]["ref"]) as detail_snap:
        actual = reader.detail(detail_snap, full["PAGE-B"]["ref"])
        assert {key: value for key, value in actual.items() if key not in ("materials", "template")} == full["PAGE-B"]
        assert expanded == [full["PAGE-B"]["operations"][0]["ref"]]


def test_blank_stored_due_date_sorts_as_text_instead_of_failing(batch_client):
    conn = batch_client.batch_conn
    page_batches(conn)
    insert_row(conn, "Batches", {"batch_id": "PAGE-E", "part_no": "P1", "part_name": "retained name",
        "quantity": 1, "due_date": "", "priority": "normal", "ready_status": "yes", "status": "pending"})
    conn.commit()
    scope = batch_scope({"query": "PAGE-", "sort": "due_date", "size": 10})
    response = batch_client.post(BASE + "/query", json=scope)
    assert response.status_code == 200, response.get_json()
    assert [row["business_code"] for row in response.get_json()["data"]["entities"]] == ["PAGE-E", "PAGE-D", "PAGE-B", "PAGE-C", "PAGE-A"]


def test_priority_status_and_readiness_sort_and_facets_follow_business_order(batch_client):
    conn = batch_client.batch_conn
    page_batches(conn)
    # 字母序与业务序在这三列上都不同；PAGE-D 的工序已完工，派生状态是 completed。
    for code, priority, status in (("PAGE-A", "normal", "cancelled"), ("PAGE-B", "urgent", "scheduled"),
                                   ("PAGE-C", "critical", "pending"), ("PAGE-D", "normal", "pending")):
        conn.execute("UPDATE Batches SET priority=?, status=? WHERE batch_id=?", (priority, status, code))
    conn.commit()
    reader = WorkbenchBatchQueryService(conn, as_of=datetime.now())
    # 列筛选齐套会走候选集的 Python 排序，不带它走 SQL 分页排序：两条路必须排出同一个顺序。
    python_path = {"ready_status": ["yes", "partial", "no"]}
    # 降序时同序号的批次仍按批次号升序（PAGE-A、PAGE-D 都是普通）。
    for field, ascending, descending in (
        ("priority", ["PAGE-C", "PAGE-B", "PAGE-A", "PAGE-D"], ["PAGE-A", "PAGE-D", "PAGE-B", "PAGE-C"]),
        ("status", ["PAGE-C", "PAGE-B", "PAGE-D", "PAGE-A"], ["PAGE-A", "PAGE-D", "PAGE-B", "PAGE-C"]),
    ):
        for filters in ({}, python_path):
            scope = batch_scope({"query": "PAGE-", "sort": field, "size": 10, "column_filters": filters})
            for direction, expected in (("asc", ascending), ("desc", descending)):
                entities = reader.read_page(dict(scope, direction=direction))[0]["entities"]
                assert [row["business_code"] for row in entities] == expected, (field, filters, direction)
    scope = batch_scope({"query": "PAGE-", "sort": "ready_status", "size": 10})
    assert [row["business_code"] for row in reader.read_page(scope)[0]["entities"]] == ["PAGE-A", "PAGE-B", "PAGE-D", "PAGE-C"]
    for field, values in (("priority", ["critical", "urgent", "normal"]),
                          ("status", ["pending", "scheduled", "completed", "cancelled"]),
                          ("ready_status", ["yes", "partial", "no"])):
        assert reader.read_facets(batch_scope({"query": "PAGE-"}), field)[0]["values"] == values


def test_filtered_selection_facets_and_export_use_two_stage_summaries(batch_client, monkeypatch):
    page_batches(batch_client.batch_conn)

    def no_details(_row):
        raise AssertionError("A batch list, selection, facet or basic export must not expand operation DTOs.")

    summarized_batches = []
    original_op_summary = BatchProjection.operation_summary

    def track_op_summary(self, batch, row):
        summarized_batches.append(batch["batch_id"])
        return original_op_summary(self, batch, row)

    monkeypatch.setattr(ExecutionProjection, "to_dict", no_details)
    monkeypatch.setattr(BatchProjection, "operation_summary", track_op_summary)
    scope = batch_scope({"query": "PAGE-", "size": 1, "column_filters": {"quantity": [2]}})
    response = batch_client.post(BASE + "/query", json=scope)
    assert response.status_code == 200, response.get_json()
    # Two-stage SQL pagination only assembles the 1 batch on page 1 ("PAGE-B"), skipping unshown "PAGE-C".
    assert summarized_batches == ["PAGE-B"]
    listed = response.get_json()
    assert listed["data"]["page"]["total"] == 2
    assert listed["data"]["entities"][0]["business_code"] == "PAGE-B"
    assert "operations" not in listed["data"]["entities"][0]
    scope["snapshot_ref"] = listed["meta"]["snapshot_ref"]
    summarized_batches.clear()
    selected = batch_client.post(BASE + "/selection", json=scope).get_json()
    assert selected["data"]["count"] == 2
    facet = batch_client.post(BASE + "/facets", json={"scope": scope, "field": "quantity"}).get_json()
    assert facet["data"]["values"] == [2, 3, 7]
    preview = batch_client.post(BASE + "/export-preview", json={"scope": scope, "selection": "filtered"}).get_json()
    assert preview["data"]["count"] == 2
    # Stage-1 selection/facets/export-preview never invoke stage-2 BatchProjection.operation_summary.
    assert summarized_batches == []
    exported = batch_client.get(BASE + "/export", query_string={"export_ref": preview["data"]["export_ref"]})
    assert exported.status_code == 200 and exported.headers["X-Workbench-Row-Count"] == "2"
    assert summarized_batches == ["PAGE-B", "PAGE-C"]
    workbook = load_workbook(BytesIO(exported.data), read_only=True, data_only=True)
    try:
        rows = list(workbook["批次信息"].iter_rows(values_only=True))
        assert [row[0] for row in rows[1:]] == ["PAGE-B", "PAGE-C"]
        assert [row[2] for row in rows[1:]] == [2, 2]
    finally:
        workbook.close()


def test_sql_pushdown_preserves_float_unicode_decimal_readiness_and_json_each_scale(batch_client, monkeypatch):
    # 批次数量由 Batches 的 CHECK 定为正整数：5.0 按 INTEGER 亲和存成 5，0 与负数写不进库。
    conn = batch_client.batch_conn
    insert_row(conn, "Parts", {"part_no": "P-UNICODE", "part_name": "Straße Welle"})
    insert_row(conn, "Parts", {"part_no": "P-UNUSED", "part_name": "unused catalog part"})
    for code, part_no, qty, priority in (
        ("PUSH-ONE", "P1", 1, "normal"),
        ("PUSH-FLOAT5", "P-UNICODE", 5.0, "urgent"),
    ):
        insert_row(
            conn,
            "Batches",
            {
                "batch_id": code,
                "part_no": part_no,
                "part_name": "part",
                "quantity": qty,
                "due_date": "2026-10-20",
                "priority": priority,
                "ready_status": "yes",
                "status": "pending",
            },
        )
    conn.execute("UPDATE Materials SET status='active' WHERE material_id='MAT1'")
    conn.execute(
        "INSERT INTO BatchMaterials(id, batch_id, material_id, required_qty, available_qty, ready_status) "
        "VALUES (8801, 'PUSH-ONE', 'MAT1', 0.3, 0.1, 'no')"
    )
    conn.execute("INSERT INTO BatchMaterialReviews(requirement_id, batch_quantity) VALUES (8801, 1)")
    conn.execute(
        "INSERT INTO BatchMaterialArrivals(requirement_id, arrival_date, quantity) "
        "VALUES (8801, '2020-01-01', 0.2)"
    )
    conn.commit()

    # 1) quantity=[1] and quantity=[5.0] push down exact integers; 0.1 + 0.2 Decimal arrival covers 0.3 -> ready_status='yes'.
    one_resp = batch_client.post(
        BASE + "/query",
        json={"query": "PUSH-", "ready_status": "yes", "column_filters": {"quantity": [1]}},
    )
    assert one_resp.status_code == 200
    assert [row["business_code"] for row in one_resp.get_json()["data"]["entities"]] == ["PUSH-ONE"]

    float_resp = batch_client.post(BASE + "/query", json={"column_filters": {"quantity": [5.0]}})
    assert float_resp.status_code == 200
    float_codes = {row["business_code"] for row in float_resp.get_json()["data"]["entities"]}
    assert {"FREE-001", "PUSH-FLOAT5"} <= float_codes

    # 2) aps_casefold matches Python .casefold() ('ß' <-> 'SS') and stage-2 loads only page Parts.
    reader = WorkbenchBatchQueryService(conn, as_of=datetime.now())
    unicode_query = batch_scope({"query": "STRASSE"})
    captured_parts = []
    orig_closure = reader.facts.repo.closure_batch_tables

    def spy_closure(target_refs, **kwargs):
        res = orig_closure(target_refs, **kwargs)
        captured_parts.extend(row["part_no"] for row in res["Parts"])
        return res

    monkeypatch.setattr(reader.facts.repo, "closure_batch_tables", spy_closure)
    matched, _ = reader.read_page(unicode_query)
    assert [row["business_code"] for row in matched["entities"]] == ["PUSH-FLOAT5"]
    assert captured_parts == ["P-UNICODE"]
    choices = batch_client.get(BASE + "/choices").get_json()["data"]
    assert {"P1", "P-UNICODE", "P-UNUSED"} <= {row["business_code"] for row in choices["parts"]}

    # 3) >1000 items in column_filters / batch_ids bind via json_each(?) without hitting SQLite's 999 parameter limit.
    large_codes = [f"ABSENT-{idx:04d}" for idx in range(1250)] + ["PUSH-ONE", "PUSH-FLOAT5"]
    large_resp = batch_client.post(
        BASE + "/query",
        json={
            "batch_ids": large_codes,
            "column_filters": {"business_code": large_codes, "priority": ["normal", "urgent"]},
        },
    )
    assert large_resp.status_code == 200, large_resp.get_json()
    assert [row["business_code"] for row in large_resp.get_json()["data"]["entities"]] == ["PUSH-FLOAT5", "PUSH-ONE"]
    # One locator past the bound is refused with the bound in the message, not truncated.
    monkeypatch.setattr(batch_query, "MAX_WINDOW_BATCHES", len(large_codes) - 1)
    refused = batch_client.post(BASE + "/query", json={"batch_ids": large_codes})
    assert refused.status_code == 400 and refused.get_json()["error"]["code"] == "invalid_input"
    assert refused.get_json()["error"]["message"] == "一次最多选 1251 个批次，请缩小范围后重试。"


def test_read_page_and_detached_snapshot_project_execution_outside_sqlite_transaction(batch_client, monkeypatch):
    from core.services.workbench.batch import execution as execution_mod
    from core.services.workbench.batch import facts as facts_mod

    conn = batch_client.batch_conn
    page_batches(conn)
    reader = WorkbenchBatchQueryService(conn, as_of=datetime.now())
    observed = []
    original_project = execution_mod.project_execution_snapshot

    def verify_outside_tx(raw):
        assert conn.in_transaction is False
        observed.append(len(raw["facts"]["operations"]))
        return original_project(raw)

    monkeypatch.setattr(execution_mod, "project_execution_snapshot", verify_outside_tx)
    monkeypatch.setattr(facts_mod, "project_execution_snapshot", verify_outside_tx)

    plain_page, _ = reader.read_page(batch_scope({"query": "PAGE-", "size": 2}))
    assert [row["business_code"] for row in plain_page["entities"]] == ["PAGE-A", "PAGE-B"]
    unready_page, _ = reader.read_page(batch_scope({"query": "PAGE-", "focus": "unready", "size": 2}))
    assert [row["business_code"] for row in unready_page["entities"]] == ["PAGE-C", "PAGE-D"]
    target_ref = plain_page["entities"][1]["ref"]
    with reader.facts.detached_read_snapshot(mode="single_template", target_ref=target_ref) as snap:
        assert conn.in_transaction is False
        det = reader.detail(snap, target_ref)
        assert det["business_code"] == "PAGE-B"
    assert observed == [1, 2, 1]
