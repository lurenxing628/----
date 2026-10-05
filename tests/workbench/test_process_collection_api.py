"""Cross-page deletion binds the actual list snapshot and explicit refs."""

import pytest

from tests.workbench.process_collection_api_support import (
    browser_contract,
    collection_api_fixture,
    conditions,
    enforce_readonly,
    seed_table_rows,
    success,
)

_fixture = collection_api_fixture


@pytest.mark.parametrize("advanced", [True])
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
