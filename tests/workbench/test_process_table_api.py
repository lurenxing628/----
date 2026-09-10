"""Process table HTTP scopes, cross-column facets and complete large selections."""

from time import perf_counter

import pytest

from tests.workbench.process_collection_api_support import (
    LIST,
    TABLE,
    browser_contract,
    collection_api_fixture,
    conditions,
    enforce_readonly,
    expire,
    rejected,
    seed_table_rows,
    transport,
)

_fixture = collection_api_fixture


@pytest.mark.parametrize("sort,direction", [
    ("label", "desc"), ([], "asc"),
    ([{"field": "stage", "direction": "asc"}, {"field": "operation_count", "direction": "desc"},
      {"field": "label", "direction": "desc"}, {"field": "business_code", "direction": "asc"}], "asc"),
])
def test_advanced_sort_filter_metrics_and_pagination_match_browser(collection_api, monkeypatch, sort, direction):
    api = collection_api
    before = api.snapshot()
    seen = enforce_readonly(monkeypatch)
    options = api.facet("business_code")["data"]["options"]
    keys = [row["key"] for row in options if row["label"] != "PROC-%_"]
    scope = {"query": "PROC-", "sort": sort, "direction": direction,
             "column_filters": conditions("business_code", keys)}
    expected = api.listing(scope, size=200)["data"]["entities"]
    # Independent fixture ordering, not a second call to the table implementation.
    codes = {"PROC-001": ("\u8f74\u5957", 3, 1), "PROC-002": ("\u7a7a\u8def\u7ebf", 0, 0),
             "PROC-003": ("\u672a\u5f52\u7c7b", 1, 1), "PROC-004": ("\u53ea\u6709\u5386\u53f2\u5de5\u5e8f", 0, 0)}
    ordered = sorted(codes)
    ordering = [{"field": sort, "direction": direction}] if isinstance(sort, str) else sort
    for item in reversed(ordering):
        field = item["field"]
        ordered.sort(key=lambda code: code if field == "business_code" else codes[code][
            {"label": 0, "operation_count": 1, "stage": 2}[field]], reverse=item["direction"] == "desc")
    assert [row["business_code"] for row in expected] == ordered
    first = api.listing(scope, size=2)
    token = first["meta"]["snapshot_ref"]
    second = api.listing(scope, page=2, size=2, snapshot_ref=token)
    assert first["data"]["entities"] + second["data"]["entities"] == expected
    assert first["data"]["metrics"]["counts"] == {"total": 4, "route": 2, "source": 2, "hours": 0, "ready": 0}
    for number, result in ((1, first), (2, second)):
        browser_contract("list", result, {**scope, "page": number, "size": 2})
        assert result["data"]["capabilities"]["create"] is True
        assert result["data"]["capabilities"]["delete"] is True
        assert result["data"]["create_context"]["capabilities"] == {"process.create": True}
    assert seen and api.snapshot() == before


def test_facets_keep_other_columns_and_ignore_only_own_filter_order_and_list_page(collection_api, monkeypatch):
    api = collection_api
    seen = enforce_readonly(monkeypatch)
    before = api.snapshot()
    counts = api.facet("operation_count")["data"]["options"]
    zero = next(row["key"] for row in counts if row["label"] == "0")
    scope = {"query": "PROC-", "column_filters": {**conditions("operation_count", [zero]), **conditions("label", [])}}
    assert api.listing(scope)["data"]["page"]["total"] == 0
    first = api.facet(scope=scope, size=1)
    assert first["data"]["row_count"] == first["data"]["page"]["total"] == 3
    assert api.facet("operation_count", scope)["data"]["row_count"] == 0
    changed = {**scope, "page": 200, "size": 200, "sort": [{"field": "label", "direction": "desc"}],
               "column_filters": conditions("operation_count", [zero])}
    token = first["meta"]["snapshot_ref"]
    pages = [first] + [api.facet(scope=changed, size=1, page=n, snapshot_ref=token) for n in (2, 3)]
    selected = api.facet(scope=changed, selection=True, size=1, snapshot_ref=token)
    assert selected["data"]["keys"] == [page["data"]["options"][0]["key"] for page in pages]
    assert selected["data"]["total"] == 3
    for number, page in enumerate(pages, 1):
        browser_contract("facets", page, {"column": "label", "page": number, "size": 1, "snapshot_ref": token})
    browser_contract("selection", selected, {"column": "label", "snapshot_ref": token, "expected_total": 3})
    assert api.facet(scope={**scope, "stage": "source"})["data"]["row_count"] == 0
    assert seen and api.snapshot() == before


@pytest.mark.parametrize("change", ["column", "query", "size", "toolbar", "other_filter", "list_token", "expired", "unknown"])
def test_facet_selection_rejects_mixed_or_expired_context(collection_api, change):
    api = collection_api
    params = {"size": 1, "snapshot_ref": api.facet(size=1)["meta"]["snapshot_ref"]}
    column, scope = "label", {}
    if change == "column":
        column = "business_code"
    elif change in ("query", "size"):
        params[change] = "Name" if change == "query" else 2
    elif change == "toolbar":
        scope = {"stage": "source"}
    elif change == "other_filter":
        scope = {"column_filters": conditions("operation_count", [])}
    elif change == "list_token":
        params["snapshot_ref"] = api.listing()["meta"]["snapshot_ref"]
    elif change == "expired":
        expire(api, "workbench-read-v1", params["snapshot_ref"])
    else:
        params["snapshot_ref"] = "x" * 32
    before = api.snapshot()
    rejected(api.facet_response(column, scope, selection=True, **params), "snapshot_stale")
    assert api.snapshot() == before


@pytest.mark.parametrize("sql", [
    "UPDATE Parts SET part_name='Changed' WHERE part_no='PROC-002'",
    "UPDATE PartOperations SET unit_hours=9 WHERE part_no='PROC-001' AND seq=10",
    "UPDATE ExternalGroups SET total_days=9 WHERE group_id='PROC-G'",
    "UPDATE Suppliers SET default_days=9 WHERE supplier_id='PROC-S'",
    "DELETE FROM WorkbenchSupplierOpTypes WHERE supplier_id='PROC-S'",
])
def test_real_fact_changes_stale_both_advanced_pages_and_facets(collection_api, sql):
    api = collection_api
    scope = {"column_filters": conditions("label", [], "exclude")}
    listing = api.listing(scope, size=1)
    facet = api.facet(scope=scope, size=1)
    api.execute(sql)
    before = api.snapshot()
    rejected(api.client.get(LIST, query_string=transport({**scope, "size": 1, "page": 2,
             "snapshot_ref": listing["meta"]["snapshot_ref"]})), "snapshot_stale")
    rejected(api.facet_response(scope=scope, selection=True, size=1, snapshot_ref=facet["meta"]["snapshot_ref"]), "snapshot_stale")
    assert api.snapshot() == before


@pytest.mark.parametrize("query", [
    "sort=[", 'sort=[{"field":"label","field":"stage","direction":"asc"}]',
    'column_filters={"label":{"mode":"include","mode":"exclude","values":[]}}',
    "sort=[]&direction=desc", "column_filters=null", "column_filters={}&column_filters={}",
    'sort=[{"field":[],"direction":"asc"}]', 'sort={}', 'column_filters={"label":{"mode":"include","values":["x"]}}',
])
def test_invalid_advanced_list_json_is_rejected_without_writes(collection_api, query):
    before = collection_api.snapshot()
    rejected(collection_api.client.get(LIST + "?" + query), "invalid_input", 400)
    assert collection_api.snapshot() == before


@pytest.mark.parametrize("query", ['scope={', 'scope={"query":"a","query":"b"}', 'scope=[]',
    'scope={"column_filters":null}', "page=0", "page=1000001", "size=201", "page=1&page=2", "unknown=1"])
def test_invalid_facet_parameters_fail_closed(collection_api, query):
    rejected(collection_api.client.get(TABLE + "facets/label?" + query), "invalid_input", 400)


def test_missing_snapshot_and_out_of_range_pages_are_not_empty_success(collection_api):
    api = collection_api
    rejected(api.facet_response(page=2), "snapshot_stale")
    rejected(api.facet_response(selection=True), "snapshot_stale")
    facet = api.facet(size=200)
    rejected(api.facet_response(size=200, page=2, snapshot_ref=facet["meta"]["snapshot_ref"]), "snapshot_stale")
    rejected(api.facet_response(selection=True, page=2, snapshot_ref=facet["meta"]["snapshot_ref"]), "invalid_input", 400)
    listing = api.listing(sort=[])
    rejected(api.client.get(LIST, query_string={"sort": "[]", "page": 2,
             "snapshot_ref": listing["meta"]["snapshot_ref"]}), "snapshot_stale")
    assert api.facet(query="not found")["data"]["page"]["total"] == 0


def test_real_http_ten_thousand_keys_roundtrip_without_truncation(collection_api, monkeypatch, record_property):
    api = collection_api
    codes = seed_table_rows(api, 10000)
    before = api.snapshot()
    seen = enforce_readonly(monkeypatch)
    start = perf_counter()
    scope = {"query": "OnlyRouteToken"}
    facet = api.facet(scope=scope, query="Name", size=100)
    selected = api.facet(scope=scope, query="Name", size=100, selection=True, snapshot_ref=facet["meta"]["snapshot_ref"])
    assert facet["data"]["page"]["total"] == 10000 and len(facet["data"]["options"]) == 100
    keys = selected["data"]["keys"]
    assert selected["data"]["total"] == len(set(keys)) == len(keys) == 10000
    scope.update(column_filters=conditions("label", keys), sort=[{"field": "label", "direction": "desc"}])
    first = api.listing(scope, size=200)
    last = api.listing(scope, size=200, page=50, snapshot_ref=first["meta"]["snapshot_ref"])
    assert first["data"]["page"]["total"] == last["data"]["page"]["total"] == 10000
    assert [row["business_code"] for row in first["data"]["entities"]] == list(reversed(codes))[:200]
    assert [row["business_code"] for row in last["data"]["entities"]] == list(reversed(codes))[-200:]
    browser_contract("selection", selected, {"column": "label", "expected_total": 10000})
    elapsed = perf_counter() - start
    record_property("process_table_api_10000_seconds", elapsed)
    print("process_table_api_10000_seconds=" + str(elapsed))
    assert len(seen) == 4 and api.snapshot() == before
