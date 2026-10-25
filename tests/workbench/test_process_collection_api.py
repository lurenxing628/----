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
