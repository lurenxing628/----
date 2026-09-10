"""Pure list/export/facet contracts over the same complete projected snapshot."""

import json
from copy import deepcopy
from dataclasses import replace
from time import perf_counter
from typing import Any, Dict

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.models.workbench_process_query import ProcessPageRequest
from core.models.workbench_process_table_query import (
    PROCESS_TABLE_COLUMNS,
    ProcessTablePageRequest,
    process_facet_scope,
    process_table_request,
    process_table_scope,
    unique_process_table_object,
)
from core.models.workbench_resource_table_query import MAX_FACET_KEYS, normalize_column_filters
from core.services.process.workflow_state import record_confirmation
from core.services.workbench.process_queries import WorkbenchProcessQueryService
from core.services.workbench.process_table import ProcessTable, process_table_cells
from core.services.workbench.resource_table_cells import number_cell, text_cell
from tests.workbench.process_query_support import process_read_database, stored
from tests.workbench.process_table_support import (
    LONG_NAME,
    conditions,
    facet_key,
    oracle_order,
    part_entity,
    projected_parts,
    refs,
    small_entities,
)


@pytest.mark.parametrize("scope", [None, [], {"id": 1}, {"ops": []}, {"kind": "part"}, {"number": 2},
                                    {"snapshot_ref": "token"}, {"page": 1, "number": 1}])
def test_list_scope_rejects_unknown_fields(scope):
    with pytest.raises(WorkbenchCommandRejected) as error:
        process_table_request(scope)
    assert error.value.code == "invalid_input"


@pytest.mark.parametrize("patch", [{"query": None}, {"query": "a" * 201}, {"stage": "done"}, {"stage": []},
    {"number": True}, {"number": 0}, {"number": 1000001}, {"size": False}, {"size": 0}, {"size": 201}, {"size": 1.5}])
def test_page_contract_retains_existing_process_limits(patch):
    for model in (ProcessPageRequest, ProcessTablePageRequest):
        with pytest.raises(WorkbenchCommandRejected) as error:
            model(**patch)
        assert error.value.code == "invalid_input" and error.value.status == 400


@pytest.mark.parametrize("size", [20, 50, 100, 200])
def test_page_size_and_number_are_not_action_export_limits(size):
    query = process_table_request({"page": 1000000, "size": size})
    assert query.size == size and query.number == 1000000
    assert "number" not in query.scope()
    for field in ("page", "size", "number", "ref", "limit", "ops"):
        with pytest.raises(WorkbenchCommandRejected):
            process_table_scope({field: size})


@pytest.mark.parametrize("value", [None, [], {"operation_id": {}}, {"label": None},
    {"label": {"mode": "contains", "values": []}}, {"label": {"mode": [], "values": []}},
    {"label": {"mode": "include", "values": [None]}}, {"label": {"mode": "include", "values": "a" * 64}},
    {"label": {"mode": "include", "values": ["a" * 48]}}, {"label": {"mode": "include", "values": ["A" * 64]}},
    {"label": {"mode": "include", "values": ["a" * 64, "a" * 64]}},
    {"label": {"mode": "include", "values": [], "op": "eq"}}])
def test_column_filters_reject_invalid_operations_values_and_duplicates(value):
    with pytest.raises(WorkbenchCommandRejected) as error:
        ProcessTablePageRequest(column_filters=value)
    assert error.value.code == "invalid_input"


@pytest.mark.parametrize("value,direction", [(None, "asc"), ("id", "asc"), ("label", "DESC"),
    ({}, "asc"), ([{"field": "id", "direction": "asc"}], "asc"),
    ([{"field": "label", "direction": "none"}], "asc"),
    ([{"field": [], "direction": "asc"}], "asc"), ([{"field": "label"}], "asc"),
    ([{"field": "label", "direction": "asc", "extra": True}], "asc"),
    ([{"field": "label", "direction": "asc"}] * 2, "asc"),
    ([{"field": "label", "direction": "asc"}] * 5, "asc"), ([], "desc")])
def test_sort_model_rejects_unknown_duplicate_and_ambiguous_operations(value, direction):
    with pytest.raises(WorkbenchCommandRejected) as error:
        ProcessTablePageRequest(sort=value, direction=direction)
    assert error.value.code == "invalid_input"


@pytest.mark.parametrize("raw", ['{"query":"a","query":"b"}',
    '{"column_filters":{"label":{"mode":"include","mode":"exclude","values":[]}}}',
    '{"sort":[{"field":"label","field":"stage","direction":"asc"}]}'])
def test_duplicate_json_fields_are_rejected_before_scope_parsing(raw):
    with pytest.raises(WorkbenchCommandRejected, match="重复字段"):
        json.loads(raw, object_pairs_hook=unique_process_table_object)


def test_normalization_is_stable_idempotent_detached_and_uses_existing_filter_contract():
    filters = {**conditions("stage", ["b" * 64, "a" * 64]), **conditions("label", ["c" * 64])}
    raw = {"query": "中文", "stage": "source", "sort": "label", "direction": "desc", "column_filters": filters}
    before = deepcopy(raw)
    assert json.loads(json.dumps(raw), object_pairs_hook=unique_process_table_object) == raw
    query = process_table_request(raw)
    action = process_table_scope(raw)
    assert action["sort"] == [{"field": "label", "direction": "desc"}]
    assert list(action["column_filters"]) == ["label", "stage"]
    assert action["column_filters"]["stage"]["values"] == ["a" * 64, "b" * 64]
    assert action == process_table_scope(action)
    assert process_table_request(action).scope() == query.scope()
    assert input_fingerprint(query.scope()) == input_fingerprint(replace(query, number=7).scope())
    common = conditions("label", ["b" * 64, "a" * 64])
    assert ProcessTablePageRequest(column_filters=common).column_filters == normalize_column_filters(common, "material")
    assert raw == before
    filters["label"]["values"].clear()
    action["column_filters"]["label"]["values"].clear()
    assert query.column_filters["label"]["values"] == ["c" * 64]
    assert ProcessTablePageRequest().scope() == ProcessTablePageRequest(column_filters={}).scope()


def test_combination_filter_and_per_column_or_include_exclude_empty():
    table = ProcessTable(small_entities())
    label = facet_key(table, "label", "轴套")
    zero, two = (facet_key(table, "operation_count", value) for value in ("0", "2"))
    base = ProcessTablePageRequest(size=1)
    combined = replace(base, column_filters={**conditions("label", [label]), **conditions("operation_count", [zero, two])})
    assert refs(table.matching_rows(combined)) == [f"{index:048x}" for index in (2, 3)]
    assert table.page(combined)["page"]["total"] == 2
    assert table.page(combined)["metrics"]["counts"] == {"route": 0, "source": 2, "hours": 0, "ready": 0, "total": 2}
    assert table.matching_rows(replace(base, column_filters=conditions("label", []))) == []
    assert len(table.matching_rows(replace(base, column_filters=conditions("label", [], "exclude")))) == 8
    assert len(table.matching_rows(replace(combined, column_filters=conditions("label", [label], "exclude")))) == 5


@pytest.mark.parametrize("column", PROCESS_TABLE_COLUMNS)
@pytest.mark.parametrize("direction", ["asc", "desc"])
def test_all_columns_sort_before_page_with_stable_code_and_ref_ties(column, direction):
    entities = small_entities()
    entities.append(part_entity(20, code="P-00002", count=2))
    table = ProcessTable(entities)
    expected = sorted(entities, key=lambda row: (row["business_code"], row["ref"]))
    expected.sort(key=lambda row: oracle_order(row, column), reverse=direction == "desc")
    query = ProcessTablePageRequest(sort=column, direction=direction, size=2, number=2)
    assert refs(table.matching_rows(query)) == refs(expected)
    assert refs(table.page(query)["entities"]) == refs(expected[2:4])
    assert refs(ProcessTable(list(reversed(entities))).matching_rows(query)) == refs(expected)


def test_three_state_sort_clear_and_four_key_priority():
    entities = small_entities()
    table = ProcessTable(entities)
    orders = [refs(table.matching_rows(ProcessTablePageRequest(sort=value))) for value in (
        [{"field": "operation_count", "direction": "asc"}], [{"field": "operation_count", "direction": "desc"}], [])]
    assert len(set(tuple(value) for value in orders)) == 3
    assert orders[2] == refs(sorted(entities, key=lambda row: row["business_code"]))
    sort = [{"field": "stage", "direction": "asc"}, {"field": "operation_count", "direction": "desc"},
            {"field": "label", "direction": "desc"}, {"field": "business_code", "direction": "desc"}]
    expected = sorted(entities, key=lambda row: (row["business_code"], row["ref"]))
    for item in reversed(sort):
        expected.sort(key=lambda row: oracle_order(row, item["field"]), reverse=item["direction"] == "desc")
    query = ProcessTablePageRequest(sort=sort)
    assert refs(table.matching_rows(query)) == refs(expected)
    sort.clear()
    assert len(query.ordering()) == 4
    assert table.page(ProcessTablePageRequest(sort=[]))["page"]["sort"] == []


def test_null_empty_zero_chinese_long_names_and_literal_search_are_not_lost():
    entities = small_entities()
    unknown = part_entity(9, label="unknown count")
    unknown["relationships"]["operation_count"] = None
    table = ProcessTable(entities + [unknown, part_entity(10, label="literal %_", route_raw=None)])
    query = ProcessTablePageRequest()
    keys = [facet_key(table, "label", label) for label in ("未知", "（空白）", "0", LONG_NAME.strip())]
    assert len(set(keys)) == 4
    assert facet_key(table, "operation_count", "0") == number_cell(0).key
    assert facet_key(table, "operation_count", "未知") == number_cell(None).key
    assert number_cell(0).key != number_cell(None).key
    assert facet_key(table, "label", LONG_NAME.strip()) == text_cell(LONG_NAME).key
    assert table.facets(query, "label", "长名称")["options"][0]["label"] == LONG_NAME.strip()
    selected = table.matching_rows(replace(query, column_filters=conditions("label", [keys[-1]])))
    assert len(selected) == 1 and selected[0]["label"] == LONG_NAME
    for search, expected in (("aBc", [7]), ("onlyroutetoken", [7]), ("%_", [10]), ("中文长名称", [6]), ("0", list(range(1, 11)))):
        assert refs(table.matching_rows(replace(query, query=search))) == [f"{index:048x}" for index in expected]


def test_facets_keep_other_columns_and_toolbar_but_exclude_own_column():
    table = ProcessTable(small_entities())
    two = facet_key(table, "operation_count", "2")
    base = ProcessTablePageRequest(query="P-", column_filters={**conditions("operation_count", [two]), **conditions("label", [])}, size=1)
    assert table.page(base)["page"]["total"] == 0
    facet = table.facets(base, "label", size=200)
    assert facet["row_count"] == 2 and facet["page"]["total"] == 1
    assert facet["options"][0]["label"] == "轴套" and facet["options"][0]["count"] == 2
    assert table.facets(base, "operation_count")["row_count"] == 0
    assert table.facets(replace(base, stage="ready"), "label")["row_count"] == 0
    assert table.facets(replace(base, number=99, sort="label", direction="desc"), "label", size=200) == facet
    signature = process_facet_scope(base, "label", size=200)
    assert signature == process_facet_scope(replace(base, column_filters=conditions("operation_count", [two])), "label", size=200)
    assert signature != process_facet_scope(replace(base, column_filters={}), "label", size=200)
    assert signature != process_facet_scope(replace(base, stage="ready"), "label", size=200)
    assert table.facet_selection(base, "label")["keys"] == [facet["options"][0]["key"]]


@pytest.mark.parametrize("size", [20, 50, 100])
def test_every_page_concatenates_to_complete_action_export_selection(size):
    table = ProcessTable([part_entity(index, count=index % 7, stage="ready" if index % 3 else "source")
                          for index in range(257)])
    scope = {"query": "P-", "column_filters": conditions("operation_count", [number_cell(0).key], "exclude"),
             "sort": [{"field": "stage", "direction": "desc"}, {"field": "operation_count", "direction": "desc"}]}
    query = process_table_request(dict(scope, page=3, size=size))
    export_query = process_table_request(process_table_scope(scope))
    expected = table.matching_rows(export_query)
    assert len(expected) == 220 and export_query.size == 20
    pages = table.page(query)["page"]["pages"]
    actual = []
    for number in range(1, pages + 1):
        data = table.page(replace(query, number=number))
        actual.extend(data["entities"])
        assert data["metrics"]["counts"]["total"] == len(expected)
    assert refs(actual) == refs(expected) == refs(table.matching_rows(query))
    assert len(set(refs(actual))) == len(actual)
    assert table.page(replace(query, number=pages + 1))["entities"] == []


@pytest.mark.parametrize("patch", [{"column": "id"}, {"column": []}, {"search": None}, {"search": "x" * 201},
    {"number": False}, {"number": 0}, {"number": 1000001}, {"size": True}, {"size": 201}, {"size": 0}])
def test_invalid_facet_inputs_are_explicitly_rejected(patch):
    table = ProcessTable(small_entities())
    request: Dict[str, Any] = {"column": "label"}
    request.update(patch)
    with pytest.raises(WorkbenchCommandRejected) as error:
        table.facets(ProcessTablePageRequest(), **request)
    assert error.value.code == "invalid_input"


def test_facet_pagination_counts_selection_all_values_and_stale_page():
    table = ProcessTable([part_entity(index, label=f"零件{index:04d}") for index in range(503)]
                         + [part_entity(index + 1000, label="零件0000") for index in range(7)])
    query = ProcessTablePageRequest(size=20, number=3)
    pages = [table.facets(query, "label", size=200, number=number) for number in (1, 2, 3)]
    assert [len(page["options"]) for page in pages] == [200, 200, 103]
    assert all(page["page"]["total"] == 503 and page["row_count"] == 510 for page in pages)
    assert sum(option["count"] for page in pages for option in page["options"]) == 510
    selected = table.facet_selection(query, "label", size=1)
    assert selected["total"] == 503
    assert selected["keys"] == [option["key"] for page in pages for option in page["options"]]
    assert pages[0]["options"][0]["count"] == 8
    for column in PROCESS_TABLE_COLUMNS:
        assert table.facets(query, column, "no-match")["page"]["total"] == 0
        assert table.facets(query, column, "no-match")["row_count"] == 510
    with pytest.raises(WorkbenchCommandRejected) as error:
        table.facets(query, "label", size=200, number=4)
    assert error.value.code == "snapshot_stale"


def test_fifty_thousand_selection_keys_are_complete_and_excess_is_rejected():
    keys = [f"{index:064x}" for index in range(MAX_FACET_KEYS + 1)]
    assert len(ProcessTablePageRequest(column_filters=conditions("label", keys[:-1])).column_filters["label"]["values"]) == MAX_FACET_KEYS
    with pytest.raises(WorkbenchCommandRejected):
        ProcessTablePageRequest(column_filters=conditions("label", keys))
    table = ProcessTable([part_entity(index, label=f"name-{index:05d}", count=0) for index in range(MAX_FACET_KEYS + 1)])
    query = ProcessTablePageRequest(column_filters=conditions("business_code", [text_cell("P-50000").key], "exclude"))
    assert table.facet_selection(query, "label")["total"] == MAX_FACET_KEYS
    with pytest.raises(WorkbenchCommandRejected) as error:
        table.facet_selection(ProcessTablePageRequest(), "label")
    assert error.value.code == "capacity_exceeded" and error.value.status == 413
    assert table.facets(ProcessTablePageRequest(), "label", size=200)["page"]["total"] == MAX_FACET_KEYS + 1


def test_projected_legacy_and_invalidated_stages_share_facts_without_new_database_reads(process_read_conn):
    conn = process_read_conn
    with TransactionManager(conn).transaction():
        for stage in ("route", "source", "hours"):
            record_confirmation(conn, "PROC-001", stage)
    for sql, stage in ((None, "ready"), ("UPDATE PartOperations SET unit_hours=2 WHERE part_no='PROC-001' AND seq=30", "hours"),
                       ("UPDATE Suppliers SET status='inactive' WHERE supplier_id='PROC-S'", "source"),
                       ("UPDATE PartOperations SET status='deleted' WHERE part_no='PROC-001' AND seq=10", "route")):
        if sql:
            conn.execute(sql)
            conn.commit()
        before, changes = stored(conn), conn.total_changes
        reader = WorkbenchProcessQueryService(conn)
        with reader.read_snapshot():
            entities = projected_parts(reader.facts())
            snapshot = deepcopy(entities)
            statements = []
            conn.set_trace_callback(statements.append)
            try:
                table = ProcessTable(entities)
                query = ProcessTablePageRequest(stage=stage, size=1)
                assert "PROC-001" in [row["business_code"] for row in table.matching_rows(query)]
                assert table.page(query)["metrics"]["counts"][stage] >= 1
                assert sum(row["count"] for row in table.facets(query, "stage")["options"]) == table.page(query)["page"]["total"]
                assert table.facet_selection(query, "business_code")["total"] == table.page(query)["page"]["total"]
            finally:
                conn.set_trace_callback(None)
            assert statements == [] and entities == snapshot
            assert all(not row["workflow"]["ready"] for row in entities if row["workflow"]["origin"] == "legacy")
            deleted = next(row for row in entities if row["business_code"] == "PROC-004")
            assert deleted["workflow"]["stage"] == "route" and deleted["relationships"]["operation_count"] == 0
        assert stored(conn) == before and conn.total_changes == changes


@pytest.mark.parametrize("patch", [{"stage": "unexpected"}, {"stage": "ready"}, {"ready": True},
                                     {"stage": "ready", "ready": True, "origin": "legacy"}])
def test_inconsistent_stage_projection_is_not_inferred_or_hidden(patch):
    entity = part_entity(1)
    entity["workflow"].update(patch)
    with pytest.raises(WorkbenchCommandRejected) as error:
        process_table_cells(entity)
    assert error.value.code == "storage_failure"


def test_duplicate_identity_is_not_silently_overwritten_and_empty_table_is_valid():
    entity = part_entity(1)
    with pytest.raises(WorkbenchCommandRejected, match="重复零件引用"):
        ProcessTable([entity, entity])
    table, query = ProcessTable([]), ProcessTablePageRequest()
    assert table.page(query)["metrics"]["counts"]["total"] == 0
    assert table.page(query)["page"]["pages"] == 1
    assert table.facets(query, "label")["row_count"] == 0
    assert table.facet_selection(query, "label")["keys"] == []


def test_ten_thousand_parts_offpage_export_order_facets_and_measured_scale(record_property):
    entities = [part_entity(index, label=LONG_NAME + str(index), count=index % 11, stage="hours" if index % 2 else "source")
                for index in range(10000)]
    before = deepcopy(entities)
    started = perf_counter()
    table = ProcessTable(entities)
    built = perf_counter()
    query = ProcessTablePageRequest(query="中文长名称", column_filters=conditions("stage", [text_cell("待填工时").key]),
        sort=[{"field": "operation_count", "direction": "desc"}, {"field": "label", "direction": "asc"}], number=9)
    exported = table.matching_rows(query)
    matched = perf_counter()
    page = table.page(query)
    paged = perf_counter()
    facet = table.facets(query, "label", size=200)
    selection = table.facet_selection(query, "label")
    finished = perf_counter()
    expected = [row for row in entities if int(row["ref"], 16) % 2]
    expected.sort(key=lambda row: (-row["relationships"]["operation_count"], row["label"], row["business_code"], row["ref"]))
    assert refs(exported) == refs(expected) and len(exported) == 5000
    assert refs(page["entities"]) == refs(expected[160:180]) and page["page"]["total"] == 5000
    assert facet["page"]["total"] == selection["total"] == 5000 and len(facet["options"]) == 200
    assert len(set(selection["keys"])) == 5000 and facet["row_count"] == 5000
    assert entities == before
    measurements = {"parts": 10000, "matched": len(exported), "new_database_queries": 0,
        "index_seconds": built - started, "filter_sort_seconds": matched - built,
        "page_seconds": paged - matched, "facet_and_selection_seconds": finished - paged,
        "total_seconds": finished - started}
    record_property("process_table_scale", measurements)
    print("process_table_scale=" + json.dumps(measurements, sort_keys=True))
