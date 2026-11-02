"""Cross-page deletion binds the actual list snapshot and explicit refs."""

import pytest

from tests.workbench.process_collection_api_support import (
    COLLECTION,
    LIST,
    TABLE,
    browser_contract,
    collection_api_fixture,
    conditions,
    enforce_readonly,
    rejected,
    seed_table_rows,
    success,
)

_fixture = collection_api_fixture
_DUPLICATE_QUERY = "查询条件里有重复的项，请重新选择。"
_FACET_UNREADABLE = "筛选内容读不出来，筛选没有变化。请点「清除筛选」后重新选择。"
_LIST_UNREADABLE = "排序或筛选内容读不出来，当前筛选没有变化。请点「清除筛选」后重新选择。"


@pytest.mark.parametrize("raw,message", [
    ('{"refs": [], "refs": [], "scope": {}, "snapshot_ref": "x"}', "删除预检没有执行：提交的内容有重复项。请刷新页面后重新提交。"),
    *[('{"refs": [], "scope": {}, "snapshot_ref": "x", "page_size": ' + literal + "}",
       "删除预检没有执行：提交的内容格式不正确。请刷新页面后重新提交。") for literal in ("NaN", "Infinity", "-Infinity", "1e999")],
    ('{"refs": [], "scope": {}', "删除预检没有执行：提交的内容格式不正确。请刷新页面后重新提交。"),
])
def test_process_body_rejects_duplicate_keys_and_nonfinite_numbers_with_route_texts(collection_api, raw, message):
    response = collection_api.client.post(COLLECTION + "bulk-preview", data=raw, content_type="application/json")
    assert rejected(response, "invalid_input", 400)["error"]["message"] == message


@pytest.mark.parametrize("request_options,code,status,message", [
    ({"query_string": {"x": "1"}, "data": "{}", "content_type": "application/json"}, "invalid_input", 400,
     "删除预检没有执行：提交的内容格式不正确，也不能在网址上附加条件。请刷新页面后重新提交。"),
    ({"data": "{}", "content_type": "text/plain"}, "invalid_input", 400,
     "删除预检没有执行：提交的内容格式不正确，也不能在网址上附加条件。请刷新页面后重新提交。"),
    ({"data": "[]", "content_type": "application/json"}, "invalid_input", 400,
     "删除预检没有执行：提交的内容不完整。请刷新页面后重新提交。"),
    ({"data": " " * (4 * 1024 * 1024 + 1), "content_type": "application/json"}, "capacity_exceeded", 413,
     "删除预检没有执行：一次提交的内容太多，系统没有截断处理。请缩小范围后重新提交。"),
])
def test_process_body_transport_size_and_shape_keep_route_texts(collection_api, request_options, code, status, message):
    response = collection_api.client.post(COLLECTION + "bulk-preview", **request_options)
    assert rejected(response, code, status)["error"]["message"] == message


@pytest.mark.parametrize("path,query,message", [
    (TABLE + "facets/label", {"scope": '{"query": "a", "query": "b"}'}, _DUPLICATE_QUERY),
    (TABLE + "facets/label", {"scope": '{"query": "a", "page": NaN}'}, _FACET_UNREADABLE),
    (TABLE + "facet-selection/label", {"scope": '{"stage": "ready", "size": 1e999}'}, _FACET_UNREADABLE),
    (TABLE + "facets/label", {"scope": '{"query": '}, _FACET_UNREADABLE),
    (LIST, {"column_filters": '{"label": {"mode": "include", "mode": "exclude", "values": []}}'}, _DUPLICATE_QUERY),
    (LIST, {"column_filters": '{"label": {"mode": "include", "values": [Infinity]}}'}, _LIST_UNREADABLE),
    (LIST, {"sort": '[{"field": "label", "field": "stage", "direction": "asc"}]'}, _DUPLICATE_QUERY),
    (LIST, {"sort": '[{"field": "label", "direction": -Infinity}]'}, _LIST_UNREADABLE),
    (LIST, {"column_filters": "{"}, _LIST_UNREADABLE),
])
def test_process_query_json_rejects_duplicate_keys_and_nonfinite_numbers_with_route_texts(collection_api, path, query, message):
    response = collection_api.client.get(path, query_string=query)
    assert rejected(response, "invalid_input", 400)["error"]["message"] == message


@pytest.mark.parametrize("advanced", [True])
def test_delete_cross_page_explicit_refs_survive_filter_and_match_actual_js_contract(collection_api, monkeypatch, advanced, record_property):
    from core.services.workbench.process.queries import WorkbenchProcessQueryService
    from data.repositories.workbench_process_part_facts_repo import WorkbenchProcessPartFactsRepository

    api = collection_api
    codes = seed_table_rows(api, 43)
    original, calls = WorkbenchProcessQueryService.page, []

    def page(reader, query):
        calls.append(query.number)
        return original(reader, query)

    with monkeypatch.context() as patch:
        patch.setattr(WorkbenchProcessQueryService, "page", page)
        third = api.listing({"query": "TABLE-"}, size=20, page=3)
    assert calls == [3] and third["data"]["page"]["number"] == 3
    assert third["data"]["page"]["total"] == 43 and len(third["data"]["entities"]) == 3
    record_property("direct_page", 3)
    record_property("page_query_calls", len(calls))
    record_property("data_fields", sorted(third["data"]))
    token = third["meta"]["snapshot_ref"]
    repeated = api.listing({"query": "TABLE-"}, size=20, page=3, snapshot_ref=token)
    assert repeated["data"] == third["data"] and repeated["meta"].keys() == third["meta"].keys()
    assert repeated["meta"]["request_ref"] != third["meta"]["request_ref"]
    assert all(repeated["meta"][key] == value for key, value in third["meta"].items() if key != "request_ref")
    first = api.listing({"query": "TABLE-"}, size=20, snapshot_ref=token)
    refs = [third["data"]["entities"][-1]["ref"], first["data"]["entities"][0]["ref"], api.ref(code="PROC-003")]
    scope = {"query": "does not match selected refs", "stage": "ready"}
    if advanced:
        scope.update(sort=[{"field": "operation_count", "direction": "desc"}], column_filters=conditions("label", []))
    body = api.bound(refs, scope, size=1)
    before = api.snapshot()
    captured = []
    capture = WorkbenchProcessPartFactsRepository.capture

    def capture_selection(repo, selection):
        captured.append(tuple(selection))
        return capture(repo, selection)

    monkeypatch.setattr(WorkbenchProcessPartFactsRepository, "capture", capture_selection)
    with monkeypatch.context() as patch:
        seen = enforce_readonly(patch)
        raw = success(api.send("bulk-preview", body))
    assert seen and api.snapshot() == before
    preview = raw["data"]
    assert captured == [tuple(refs)]
    assert [row["entity_ref"] for row in preview["rows"]] == refs
    assert preview["summary"]["delete"] == 3 and preview["summary"]["rejected"] == 0
    assert all("expected" not in row and "input" not in row for row in preview["rows"])
    browser_contract("delete", raw, body)
    command = {"request_key": "api-cross-page-delete", "write_token": preview["write_context"]["write_token"],
               "input": {"preview_ref": preview["preview_ref"]}}
    captured.clear()
    result = success(api.send("bulk-confirm", command))
    assert captured == [tuple(refs)]
    browser_contract("receipt", result, intent={"kind": "process_bulk", "action": "confirm", "ref": preview["preview_ref"]}, refs=refs)
    assert [row["entity_ref"] for row in result["data"]["rows"]] == refs
    assert result["data"]["deleted_count"] == 3
    remaining = {row["part_no"] for row in api.rows("Parts")}
    assert not remaining.intersection({codes[0], codes[-1], "PROC-003"})
    assert set(codes[1:-1]) <= remaining
    for table in ("Batches", "BatchOperations", "Schedule", "Suppliers", "ExternalGroups"):
        assert api.snapshot()[1][table] == before[1][table]


@pytest.mark.parametrize("mutation,code,status", [
    ("UPDATE Parts SET part_name='renamed' WHERE part_no='PROC-002'", "stale_write", 409),
    ("INSERT INTO Batches(batch_id,part_no,part_name,quantity,due_date) VALUES ('REG-B','PROC-002','x',1,'2026-12-01')",
     "stale_write", 409),
])
def test_part_delete_confirm_rechecks_current_facts_atomically(collection_api, mutation, code, status):
    command = collection_api.delete_body()
    collection_api.execute(mutation)
    before = collection_api.snapshot()
    rejected(collection_api.send("bulk-confirm", command), code, status)
    assert collection_api.snapshot() == before


def test_part_delete_confirm_refuses_a_preview_with_rejected_rows(collection_api):
    collection_api.execute("INSERT INTO Batches(batch_id,part_no,part_name,quantity,due_date) "
                           "VALUES ('REG-B','PROC-002','x',1,'2026-12-01')")
    command = collection_api.delete_body()
    before = collection_api.snapshot()
    rejected(collection_api.send("bulk-confirm", command), "constraint_conflict", 409)
    assert collection_api.snapshot() == before


def test_single_part_detail_prebinds_before_projection_and_tracks_shared_identity_revisions(collection_api, monkeypatch):
    from core.services.workbench.process.queries import WorkbenchProcessQueryService

    api = collection_api
    with api.database() as conn:
        conn.executemany(
            "INSERT INTO Suppliers(supplier_id,name,default_days,status) VALUES (?,?,3.0,'active')",
            [(f"BULK-SUP-{idx:04d}", f"Bulk Supplier {idx:04d}") for idx in range(1001)],
        )
        conn.commit()

    ref = api.ref(code="PROC-001")
    queries = []
    orig_init = WorkbenchProcessQueryService.__init__

    def traced_init(self, conn, *args, **kwargs):
        conn.set_trace_callback(queries.append)
        orig_init(self, conn, *args, **kwargs)

    monkeypatch.setattr(WorkbenchProcessQueryService, "__init__", traced_init)
    first_detail = success(api.client.get(f"/api/workbench/v1/entities/part/{ref}"))
    token = first_detail["meta"]["snapshot_ref"]
    assert len(first_detail["data"]["operations"]) == 3
    # Valid detail read must not scan all 1,001 suppliers or full OpTypes / WorkbenchOpTypePolicies tables.
    assert not any('SELECT * FROM "Suppliers" ORDER BY rowid' in sql for sql in queries)
    assert not any('SELECT * FROM "OpTypes" ORDER BY rowid' in sql for sql in queries)
    assert not any('SELECT * FROM "WorkbenchOpTypePolicies"' in sql for sql in queries)

    # Advance a shared dictionary table so the token becomes stale.
    with api.database() as conn:
        conn.execute("UPDATE Suppliers SET name='Updated Bulk Supplier' WHERE supplier_id='BULK-SUP-0000'")
        conn.commit()

    queries.clear()
    with monkeypatch.context() as patch:
        patch.setattr(
            WorkbenchProcessQueryService,
            "resolved_detail",
            lambda *a, **kw: pytest.fail("Stale process_detail must reject before resolved_detail projection"),
        )
        stale_res = api.client.get(f"/api/workbench/v1/entities/part/{ref}", query_string={"snapshot_ref": token})
    assert rejected(stale_res, "snapshot_stale", 409)
    assert not any("FROM Suppliers" in sql or 'FROM "Suppliers"' in sql for sql in queries)
    assert not any('FROM "WorkbenchSupplierProfiles"' in sql for sql in queries)
    assert not any('FROM "WorkbenchSupplierOpTypes"' in sql for sql in queries)

    # Missing part ref still returns 404 before snapshot binding.
    missing_res = api.client.get(f"/api/workbench/v1/entities/part/{'f' * 48}", query_string={"snapshot_ref": token})
    assert rejected(missing_res, "entity_not_found", 404)

    # Updating op_type or supplier identity in WorkbenchEntityRefs bumps op_types / suppliers revision and invalidates snapshot.
    for kind, key in (("op_type", "PROC-IN"), ("supplier", "PROC-S")):
        fresh_token = success(api.client.get(f"/api/workbench/v1/entities/part/{ref}"))["meta"]["snapshot_ref"]
        with api.database() as conn:
            conn.execute(
                "UPDATE WorkbenchEntityRefs SET revision = revision + 1 WHERE kind = ? AND entity_key = ?",
                (kind, key),
            )
            conn.commit()
        after_identity_change = api.client.get(
            f"/api/workbench/v1/entities/part/{ref}", query_string={"snapshot_ref": fresh_token}
        )
        assert rejected(after_identity_change, "snapshot_stale", 409)


def test_legacy_padded_part_ref_can_be_deleted_and_raw_facts_skip_workflow_enrichment(collection_api, monkeypatch):
    from core.models.workbench_process_table_query import ProcessTablePageRequest
    from core.services.process import workflow_state
    from core.services.workbench.process import queries as process_queries
    from core.services.workbench.process.file_export import select_export_parts
    from core.services.workbench.process.queries import WorkbenchProcessQueryService
    from tests.workbench.identity_metadata_support import insert_row

    api = collection_api
    with api.database() as conn:
        insert_row(conn, "Parts", dict(part_no=" PAD-PART-1 ", part_name="padded-part"))
        conn.commit()
        padded_ref = conn.execute(
            "SELECT ref FROM WorkbenchEntityRefs WHERE kind='part' AND entity_key=' PAD-PART-1 ' AND active=1"
        ).fetchone()[0]

    preview_doc = success(api.send("bulk-preview", api.bound([padded_ref], {})))["data"]
    assert preview_doc["summary"]["delete"] == 1 and preview_doc["summary"]["rejected"] == 0
    delete_res = api.send(
        "bulk-confirm",
        {
            "request_key": "delete-padded-part-01",
            "write_token": preview_doc["write_context"]["write_token"],
            "input": {"preview_ref": preview_doc["preview_ref"]},
        },
    )
    assert success(delete_res)["result"] == "committed"
    assert rejected(api.client.get(f"/api/workbench/v1/entities/part/{padded_ref}"), "entity_not_found", 404)

    # raw_facts for explicit export and route export must not call workflow_snapshot.
    with api.database() as conn:
        reader = WorkbenchProcessQueryService(conn)
        with monkeypatch.context() as patch:
            patch.setattr(
                process_queries,
                "workflow_snapshot",
                lambda *a, **kw: pytest.fail("Explicit export must use raw_facts without workflow_snapshot"),
            )
            with reader.read_snapshot():
                parts = select_export_parts(reader, [api.ref(code="PROC-001")], ProcessTablePageRequest())
                assert len(parts) == 1

        # Single-part resolved_detail constructs TemplateSourceFacts only once.
        source_calls = []
        orig_build = workflow_state.build_template_source_facts

        def counted_build(*args, **kwargs):
            source_calls.append(True)
            return orig_build(*args, **kwargs)

        with monkeypatch.context() as patch:
            patch.setattr(process_queries, "build_template_source_facts", counted_build)
            with reader.read_snapshot():
                reader.detail(api.ref(code="PROC-001"))
        assert len(source_calls) == 1

    # Pure text route-file preview/import (part_name / remark only, no route change) must not load supplier catalogs.
    with api.database() as conn:
        conn.executemany(
            "INSERT INTO Suppliers(supplier_id,name,default_days,status) VALUES (?,?,3.0,'active')",
            [(f"ROUTE-SUP-{idx:04d}", f"Route Supplier {idx:04d}") for idx in range(50)],
        )
        conn.commit()
        from core.services.workbench.process.files import WorkbenchProcessFileService

        service = WorkbenchProcessFileService(conn)
        csv_bytes = "图号,名称,备注\r\n'PROC-001,'更新后的零件名,'更新后的备注\r\n".encode("utf-8-sig")
        queries = []
        conn.set_trace_callback(queries.append)
        try:
            preview, extra = service.preview_import("route", csv_bytes, file_format="csv", mode="upsert", target_ref=None)
        finally:
            conn.set_trace_callback(None)
        preview_doc = preview.as_dict()
        assert preview_doc["rows"][0]["result"] == "update"
        assert set(preview_doc["rows"][0]["changes"]) == {"label", "remark"}
        assert extra["affected_groups"] == []
        assert not any('SELECT * FROM "Suppliers"' in sql for sql in queries)
        assert not any("WorkbenchSupplierProfiles" in sql for sql in queries)
        assert not any("WorkbenchSupplierOpTypes" in sql for sql in queries)
        assert not any('SELECT * FROM "OpTypes"' in sql for sql in queries)
        assert not any("WorkbenchOpTypePolicies" in sql for sql in queries)
        assert not any("kind IN ('op_type','supplier')" in sql for sql in queries)

    create_req = api.create_body()
    create_queries = []
    orig_reader_init = WorkbenchProcessQueryService.__init__

    def traced_reader_init(self, conn, *args, **kwargs):
        conn.set_trace_callback(create_queries.append)
        orig_reader_init(self, conn, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(WorkbenchProcessQueryService, "__init__", traced_reader_init)
        patch.setattr(
            WorkbenchProcessQueryService,
            "raw_facts",
            lambda *a, **kw: pytest.fail("process_create must not call reader.raw_facts()"),
        )
        created_res = success(api.send("create", create_req))["data"]
        assert created_res["business_code"] == "API-NEW"
        assert any("SELECT 1 FROM Parts WHERE part_no =" in sql for sql in create_queries)
        assert not any('SELECT * FROM "PartOperations"' in sql for sql in create_queries)
        assert not any("ExternalGroups" in sql for sql in create_queries)

        dup_req = api.create_body({"business_code": "PROC-001", "label": "Dup", "route_raw": "", "remark": ""})
        create_queries.clear()
        rejected(api.send("create", dup_req), "constraint_conflict", 409)
        assert any("SELECT 1 FROM Parts WHERE part_no =" in sql for sql in create_queries)
        assert not any("PartOperations" in sql for sql in create_queries)
        assert not any("ExternalGroups" in sql for sql in create_queries)
