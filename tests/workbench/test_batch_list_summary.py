"""Batch summaries keep whole-scope decisions and defer operation DTO expansion."""

from io import BytesIO

from openpyxl import load_workbook

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
    reader = WorkbenchBatchQueryService(conn)
    scope = batch_scope({"query": "PAGE-", "sort": "quantity", "size": 1})
    with reader.facts.detached_read_snapshot(query_filter=scope) as snap:
        facts = snap.load()
        projection = BatchProjection(facts)
        full = {row["batch_id"]: projection.entity(row) for row in facts["Batches"] if row["batch_id"].startswith("PAGE-")}
        expanded, serialize = [], ExecutionProjection.to_dict

        def capture(row):
            expanded.append(row.operation_ref)
            return serialize(row)

        monkeypatch.setattr(ExecutionProjection, "to_dict", capture)
        order = ["PAGE-B", "PAGE-C", "PAGE-A", "PAGE-D"]
        for number, code in enumerate(order, 1):
            data = reader.page(snap, dict(scope, page=number))
            assert data["page"]["total"] == 4 and data["page"]["pages"] == 4
            assert data["metrics"] == {"scope": "filtered", "total": 4, "completed": 1}
            assert data["entities"] == [{key: value for key, value in full[code].items() if key != "operations"}]
        assert [row["business_code"] for row in reader.matched(snap, dict(scope, focus="gaps"))] == ["PAGE-C", "PAGE-A", "PAGE-D"]
        assert [row["business_code"] for row in reader.matched(snap, dict(scope, focus="unready"))] == ["PAGE-C", "PAGE-D"]
        assert [row["business_code"] for row in reader.matched(snap, dict(scope, status="completed"))] == ["PAGE-D"]
        assert [row["business_code"] for row in reader.matched(snap, dict(scope, sort="due_date", direction="desc"))] == ["PAGE-A", "PAGE-C", "PAGE-B", "PAGE-D"]
        selection = reader.selection(snap, scope)
        assert selection == {"refs": [full[code]["ref"] for code in order], "count": 4}
        assert expanded == []
    with reader.facts.detached_read_snapshot(mode="single_template", target_ref=full["PAGE-B"]["ref"]) as detail_snap:
        actual = reader.detail(detail_snap, full["PAGE-B"]["ref"])
        assert {key: value for key, value in actual.items() if key not in ("materials", "template")} == full["PAGE-B"]
        assert expanded == [full["PAGE-B"]["operations"][0]["ref"]]


def test_blank_stored_due_date_and_priority_sort_as_text_instead_of_failing(batch_client):
    conn = batch_client.batch_conn
    page_batches(conn)
    insert_row(conn, "Batches", {"batch_id": "PAGE-E", "part_no": "P1", "part_name": "retained name",
        "quantity": 1, "due_date": "", "priority": "", "ready_status": "yes", "status": "pending"})
    conn.commit()
    for field, expected in (("due_date", ["PAGE-E", "PAGE-D", "PAGE-B", "PAGE-C", "PAGE-A"]),
                            ("priority", ["PAGE-E", "PAGE-A", "PAGE-B", "PAGE-C", "PAGE-D"])):
        scope = batch_scope({"query": "PAGE-", "sort": field, "size": 10})
        response = batch_client.post(BASE + "/query", json=scope)
        assert response.status_code == 200, response.get_json()
        assert [row["business_code"] for row in response.get_json()["data"]["entities"]] == expected


def test_filtered_selection_facets_and_export_use_summaries(batch_client, monkeypatch):
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
    assert set(summarized_batches) == {"PAGE-B", "PAGE-C"}
    listed = response.get_json()
    assert listed["data"]["page"]["total"] == 2
    assert listed["data"]["entities"][0]["business_code"] == "PAGE-B"
    assert "operations" not in listed["data"]["entities"][0]
    scope["snapshot_ref"] = listed["meta"]["snapshot_ref"]
    selected = batch_client.post(BASE + "/selection", json=scope).get_json()
    assert selected["data"]["count"] == 2
    facet = batch_client.post(BASE + "/facets", json={"scope": scope, "field": "quantity"}).get_json()
    assert facet["data"]["values"] == [2, 3, 7]
    preview = batch_client.post(BASE + "/export-preview", json={"scope": scope, "selection": "filtered"}).get_json()
    assert preview["data"]["count"] == 2
    exported = batch_client.get(BASE + "/export", query_string={"export_ref": preview["data"]["export_ref"]})
    assert exported.status_code == 200 and exported.headers["X-Workbench-Row-Count"] == "2"
    workbook = load_workbook(BytesIO(exported.data), read_only=True, data_only=True)
    try:
        rows = list(workbook["批次信息"].iter_rows(values_only=True))
        assert [row[0] for row in rows[1:]] == ["PAGE-B", "PAGE-C"]
        assert [row[2] for row in rows[1:]] == [2, 2]
    finally:
        workbook.close()


def test_sql_pushdown_preserves_zero_float_null_unicode_parts_scoping_and_chunked_bind_budget(batch_client):
    conn = batch_client.batch_conn
    insert_row(conn, "Parts", {"part_no": "P-UNICODE", "part_name": "Straße Welle"})
    insert_row(conn, "Parts", {"part_no": "P-UNUSED", "part_name": "unused catalog part"})
    for code, part_no, qty, priority in (
        ("PUSH-ZERO", "P1", 0, "normal"),
        ("PUSH-FLOAT5", "P-UNICODE", 5.0, "urgent"),
        ("PUSH-BADQTY", "P1", -3, None),
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
    conn.commit()

    # 1) quantity=[0] and quantity=[5.0] push down exact integers without dropping 0 or integral float.
    zero_resp = batch_client.post(BASE + "/query", json={"query": "PUSH-", "column_filters": {"quantity": [0]}})
    assert zero_resp.status_code == 200
    assert [row["business_code"] for row in zero_resp.get_json()["data"]["entities"]] == ["PUSH-ZERO"]

    float_resp = batch_client.post(BASE + "/query", json={"column_filters": {"quantity": [5.0]}})
    assert float_resp.status_code == 200
    float_codes = {row["business_code"] for row in float_resp.get_json()["data"]["entities"]}
    assert {"FREE-001", "PUSH-FLOAT5"} <= float_codes

    # 2) quantity=[None] and priority=[None] preserve NULL / invalid-quantity degraded None rows.
    bad_qty_resp = batch_client.post(BASE + "/query", json={"query": "PUSH-", "column_filters": {"quantity": [None]}})
    assert bad_qty_resp.status_code == 200
    assert [row["business_code"] for row in bad_qty_resp.get_json()["data"]["entities"]] == ["PUSH-BADQTY"]

    null_prio_resp = batch_client.post(BASE + "/query", json={"query": "PUSH-", "column_filters": {"priority": [None]}})
    assert null_prio_resp.status_code == 200
    assert [row["business_code"] for row in null_prio_resp.get_json()["data"]["entities"]] == ["PUSH-BADQTY"]

    # 3) aps_casefold matches Python .casefold() ('ß' <-> 'SS') and page loads only candidate Parts.
    reader = WorkbenchBatchQueryService(conn)
    unicode_query = batch_scope({"query": "STRASSE"})
    with reader.facts.detached_read_snapshot(query_filter=unicode_query) as unicode_scope:
        captured_parts = [row["part_no"] for row in unicode_scope.load()["Parts"]]
        matched = reader.page(unicode_scope, unicode_query)
    assert [row["business_code"] for row in matched["entities"]] == ["PUSH-FLOAT5"]
    assert captured_parts == ["P-UNICODE"]
    choices = batch_client.get(BASE + "/choices").get_json()["data"]
    assert {"P1", "P-UNICODE", "P-UNUSED"} <= {row["business_code"] for row in choices["parts"]}

    # 4) >1000 items in column_filters / batch_ids chunk <= 400 params per SQL without hitting SQLite's 999 limit.
    large_codes = [f"ABSENT-{idx:04d}" for idx in range(1250)] + ["PUSH-ZERO", "PUSH-FLOAT5"]
    executed_sql = []
    conn.set_trace_callback(executed_sql.append)
    try:
        large_resp = batch_client.post(
            BASE + "/query",
            json={
                "batch_ids": large_codes,
                "column_filters": {"business_code": large_codes, "priority": ["normal", "urgent"]},
            },
        )
    finally:
        conn.set_trace_callback(None)
    assert large_resp.status_code == 200, large_resp.get_json()
    assert [row["business_code"] for row in large_resp.get_json()["data"]["entities"]] == ["PUSH-FLOAT5", "PUSH-ZERO"]
    # Trace callback receives expanded SQL; verify chunked Batches rowid queries ran and stayed bounded.
    rowid_queries = [sql for sql in executed_sql if 'SELECT b.rowid AS rowid FROM "Batches"' in sql]
    assert len(rowid_queries) >= 7
    assert all(sql.count(",") <= 405 for sql in rowid_queries)
