"""Collection requests bind real snapshots and retain explicit cross-page refs."""

import pytest

from tests.workbench.process_collection_api_support import (
    COLLECTION,
    CREATE,
    LIST,
    browser_contract,
    collection_api_fixture,
    conditions,
    enforce_readonly,
    expire,
    rejected,
    seed_table_rows,
    success,
)

_fixture = collection_api_fixture


@pytest.mark.parametrize("route", [None, "", "  \r\n ", "not a parsed route", CREATE["route_raw"]])
def test_create_context_real_command_and_managed_workflow_preserve_existing_rows(collection_api, route):
    api = collection_api
    before = api.snapshot()
    body = api.create_body({**CREATE, "route_raw": route})
    assert api.snapshot() == before
    first = success(api.send("create", body))
    browser_contract("receipt", first, intent={"kind": "process", "action": "create", "ref": None, "input": body["input"]})
    ref = first["data"]["entity_ref"]
    part = api.rows("Parts", "part_no=?", (CREATE["business_code"],))[0]
    assert part["route_raw"] == route and part["route_parsed"] == "no" and part["remark"] == "note"
    detail = success(api.client.get(LIST + "/" + ref))["data"]
    assert detail["operations"] == [] and detail["workflow"] == first["data"]["workflow"]
    assert detail["workflow"]["origin"] == "managed" and detail["workflow"]["stage"] == "route"
    assert not detail["workflow"]["ready"]
    after = api.snapshot()
    assert after[0] == before[0]
    for table in before[1].keys() - {"Parts", "WorkbenchEntityRefs", "WorkbenchProcessWorkflow", "WorkbenchCommandReceipts"}:
        assert after[1][table] == before[1][table], table
    assert len(api.rows("WorkbenchCommandReceipts")) == 1


@pytest.mark.parametrize("advanced", [False, True])
def test_delete_cross_page_explicit_refs_survive_filter_and_match_actual_js_contract(collection_api, monkeypatch, advanced):
    api = collection_api
    codes = seed_table_rows(api, 43)
    first = api.listing({"query": "TABLE-"}, size=20)
    third = api.listing({"query": "TABLE-"}, size=20, page=3, snapshot_ref=first["meta"]["snapshot_ref"])
    refs = [third["data"]["entities"][-1]["ref"], first["data"]["entities"][0]["ref"], api.ref(code="PROC-003")]
    scope = {"query": "does not match selected refs", "stage": "ready"}
    if advanced:
        scope.update(sort=[{"field": "operation_count", "direction": "desc"}], column_filters=conditions("label", []))
    body = api.bound(refs, scope, size=1)
    before = api.snapshot()
    with monkeypatch.context() as patch:
        seen = enforce_readonly(patch)
        raw = success(api.send("bulk-preview", body))
    assert seen and api.snapshot() == before
    preview = raw["data"]
    assert [row["entity_ref"] for row in preview["rows"]] == refs
    assert preview["summary"]["delete"] == 3 and preview["summary"]["rejected"] == 0
    assert all("expected" not in row and "input" not in row for row in preview["rows"])
    browser_contract("delete", raw, body)
    command = {"request_key": "api-cross-page-delete", "write_token": preview["write_context"]["write_token"],
               "input": {"preview_ref": preview["preview_ref"]}}
    result = success(api.send("bulk-confirm", command))
    browser_contract("receipt", result, intent={"kind": "process_bulk", "action": "confirm", "ref": preview["preview_ref"]}, refs=refs)
    assert [row["entity_ref"] for row in result["data"]["rows"]] == refs
    assert result["data"]["deleted_count"] == 3
    remaining = {row["part_no"] for row in api.rows("Parts")}
    assert not remaining.intersection({codes[0], codes[-1], "PROC-003"})
    assert set(codes[1:-1]) <= remaining
    for table in ("Batches", "BatchOperations", "Schedule", "Suppliers", "ExternalGroups"):
        assert api.snapshot()[1][table] == before[1][table]


@pytest.mark.parametrize("snapshot", [None, "", "unknown"])
def test_preview_requires_a_nonempty_original_list_snapshot(collection_api, snapshot):
    api = collection_api
    body = api.bound([api.ref(code="PROC-002")])
    body["snapshot_ref"] = snapshot
    before = api.snapshot()
    rejected(api.send("bulk-preview", body), "snapshot_stale")
    assert api.snapshot() == before


@pytest.mark.parametrize("change", ["query", "sort", "filter", "page_size", "detail_token", "data", "expired"])
def test_preview_cannot_rebind_changed_scope_or_stale_list_snapshot(collection_api, change):
    api = collection_api
    body = api.bound([api.ref(code="PROC-002")], {"sort": [], "column_filters": {}})
    if change == "query":
        body["scope"]["query"] = "PROC-001"
    elif change == "sort":
        body["scope"]["sort"] = [{"field": "stage", "direction": "desc"}]
    elif change == "filter":
        body["scope"]["column_filters"] = conditions("label", [])
    elif change == "page_size":
        body["page_size"] = 1
    elif change == "detail_token":
        body["snapshot_ref"] = api.detail()["meta"]["snapshot_ref"]
    elif change == "data":
        api.execute("UPDATE Parts SET remark='changed' WHERE part_no='PROC-002'")
    else:
        expire(api, "workbench-read-v1", body["snapshot_ref"])
    before = api.snapshot()
    rejected(api.send("bulk-preview", body), "snapshot_stale")
    assert api.snapshot() == before


@pytest.mark.parametrize("scope", [None, [], {"page": 2}, {"size": 1}, {"kind": "part"}, {"column_filters": None}])
def test_preview_scope_shape_is_never_repaired_or_expanded(collection_api, scope):
    api = collection_api
    body = api.bound([api.ref(code="PROC-002")])
    body["scope"] = scope
    before = api.snapshot()
    response = api.send("bulk-preview", body)
    assert response.status_code in (400, 422), response.get_json()
    assert response.get_json()["error"]["code"] == "invalid_input"
    assert response.get_json()["committed"] is False
    assert api.snapshot() == before


@pytest.mark.parametrize("bad", [None, [], ["PROC-002"], ["A" * 48], ["f" * 48, "f" * 48]])
def test_invalid_or_duplicate_explicit_refs_reject_before_preview(collection_api, bad):
    body = collection_api.bound([collection_api.ref(code="PROC-002")])
    body["refs"] = bad
    before = collection_api.snapshot()
    rejected(collection_api.send("bulk-preview", body), "invalid_input", 422)
    assert collection_api.snapshot() == before


@pytest.mark.parametrize("blocked", ["batch", "missing", "wrong_kind"])
def test_rejected_row_blocks_all_rows_even_with_issued_write_token(collection_api, blocked):
    api = collection_api
    other = api.ref() if blocked == "batch" else "f" * 48 if blocked == "missing" else api.ref("op_type", "PROC-IN")
    request = api.bound([api.ref(code="PROC-002"), other])
    before = api.snapshot()
    raw = success(api.send("bulk-preview", request))
    browser_contract("delete", raw, request)
    data = raw["data"]
    assert data["summary"]["delete"] == data["summary"]["rejected"] == 1
    assert not data["can_confirm"] and not data["write_context"]["capabilities"]["process_bulk.confirm"]
    body = {"request_key": "api-rejected-delete", "write_token": data["write_context"]["write_token"],
            "input": {"preview_ref": data["preview_ref"]}}
    rejected(api.send("bulk-confirm", body), "constraint_conflict")
    assert api.snapshot() == before


@pytest.mark.parametrize("action", ["create", "bulk-preview", "bulk-confirm"])
@pytest.mark.parametrize("raw", ['[]', 'null', '{', '{"input":{},"input":{}}', '{"scope":{"query":"a","query":"b"}}'])
def test_duplicate_and_malformed_json_never_write(collection_api, action, raw):
    before = collection_api.snapshot()
    rejected(collection_api.client.post(COLLECTION + action, data=raw, content_type="application/json"), "invalid_input", 400)
    assert collection_api.snapshot() == before


@pytest.mark.parametrize("field", ["business_code", "label", "route_raw", "remark"])
@pytest.mark.parametrize("value", [True, 1, [], {}, "\ud800"])
def test_create_rejects_nontext_and_unstorable_input(collection_api, field, value):
    api = collection_api
    body = api.create_body({**CREATE, field: value})
    before = api.snapshot()
    rejected(api.send("create", body), "invalid_input", 422)
    assert api.snapshot() == before
