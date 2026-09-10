"""Whole-cell filters, all business columns and stable domain projections."""

import re
from dataclasses import replace

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_material_query import MaterialPageRequest
from core.models.workbench_resource_query import ResourcePageRequest
from tests.workbench.resource_table_support import (
    COLUMNS,
    VIEWS,
    conditions,
    facet_key,
    oracle_cell,
    query_for,
    reader,
    stored_state,
    table_database,
)


@pytest.mark.parametrize("kind,category", VIEWS)
def test_empty_filter_scope_is_backward_compatible(kind, category):
    old = query_for(kind, category).scope()
    assert "column_filters" not in old
    assert query_for(kind, category, column_filters={}).scope() == old
    expected = {"kind", "query", "status", "size", "sort", "direction"} | ({"category"} if kind != "material" else set())
    assert set(old) == expected


@pytest.mark.parametrize("kind,category", VIEWS)
@pytest.mark.parametrize("sort", ["business_code", "label", "status"])
def test_unfiltered_export_selection_keeps_exact_legacy_get_sort(table_conn, kind, category, sort):
    service, query = reader(table_conn, kind), query_for(kind, category, sort=sort, size=200, direction="desc")
    with service.read_snapshot():
        records, _ = service.page(query)
        assert service.matching_keys(query) == [record.entity["business_code"] for record in records]


@pytest.mark.parametrize("patch", [None, [], {"id": {"mode": "include", "values": []}},
    {"spec": {"mode": "unknown", "values": []}}, {"spec": {"mode": "include", "values": ["f" * 48]}},
    {"spec": {"mode": "include", "values": ["F" * 64]}}, {"spec": {"mode": "include", "values": [None]}},
    {"spec": {"mode": "include", "values": ["f" * 64, "f" * 64]}},
    {"spec": {"mode": "include", "values": "f" * 64}}, {"spec": {"mode": "include", "values": [], "extra": 1}}])
def test_invalid_filter_contract_is_rejected(patch):
    with pytest.raises(WorkbenchCommandRejected) as error:
        MaterialPageRequest(column_filters=patch)
    assert error.value.code == "invalid_input"


def test_fifty_thousand_unique_keys_are_supported_without_silent_truncation():
    keys = [f"{number:064x}" for number in range(50001)]
    query = MaterialPageRequest(column_filters=conditions("spec", keys[:50000]))
    assert query.scope()["column_filters"]["spec"]["values"] == keys[:50000]
    with pytest.raises(WorkbenchCommandRejected):
        MaterialPageRequest(column_filters=conditions("spec", keys))
    with pytest.raises(WorkbenchCommandRejected):
        ResourcePageRequest("machine_group", column_filters=conditions("label", []))
    assert ResourcePageRequest("machine_group", sort="status").scope()["sort"] == "status"


@pytest.mark.parametrize("kind,category,column", [(kind, category, column) for (kind, category), columns in COLUMNS.items() for column in columns])
@pytest.mark.parametrize("direction", ["asc", "desc"])
def test_every_business_column_sorts_by_real_values_with_code_ties(table_conn, kind, category, column, direction):
    service = reader(table_conn, kind)
    base = query_for(kind, category, size=200)
    before = stored_state(table_conn)
    with service.read_snapshot():
        records, _ = service.page(base)
        expected = sorted((record.entity for record in records), key=lambda row: row["business_code"])
        expected.sort(key=lambda row: oracle_cell(row, column), reverse=direction == "desc")
        query = replace(base, sort=column, direction=direction, column_filters=conditions("business_code", [], "exclude"), size=2)
        keys = service.matching_keys(query)
        assert keys == [row["business_code"] for row in expected]
        rows = service.matching_rows(query)
        assert isinstance(rows, list) and [row["business_code"] for row in rows] == keys
        actual = []
        for number in range(1, (len(keys) + 1) // 2 + 1):
            page_records, page = service.page(replace(query, number=number))
            actual.extend(record.entity["business_code"] for record in page_records)
            assert page["total"] == len(keys)
            for record in page_records:
                assert service.detail(record.identity.ref).entity == record.entity
                if kind != "material":
                    assert service.domain.snapshot(record.identity) == record.state
        assert actual == keys
    assert stored_state(table_conn) == before


def test_include_empty_exclude_empty_multicolumn_and_per_column_or(table_conn):
    service = reader(table_conn, "material")
    base = MaterialPageRequest(size=1)
    with service.read_snapshot():
        round_key = facet_key(service, base, "spec", "Round")
        active_key = facet_key(service, base, "status", "启用")
        inactive_key = facet_key(service, base, "status", "停用")
        assert service.page(replace(base, column_filters=conditions("spec", [])))[1]["total"] == 0
        assert service.page(replace(base, column_filters=conditions("spec", [], "exclude")))[1]["total"] == 5
        filters = {**conditions("spec", [round_key]), **conditions("status", [active_key, inactive_key])}
        query = replace(base, column_filters=filters)
        assert service.matching_keys(query) == ["MAT1", "MAT4"]
        assert service.page(query)[1]["total"] == 2
        assert service.metrics(query)["counts"] == {"total": 2, "active": 2, "inactive": 0, "unknown": 0, "stock_unknown": 0}
        assert service.matching_keys(replace(base, column_filters=conditions("spec", [round_key], "exclude"))) == ["MAT2", "MAT3"]


@pytest.mark.parametrize("kind,column,full,partial,expected", [
    ("operator", "skill_refs", "Type A、Type B", "Type A", ["OFF", "LEAVE", "UNAUTH", "UNKNOWN"]),
    ("supplier", "op_type_refs", "Type X、Type Y", "Type X", ["S2", "S3", "S4", "S5"]),
])
def test_relation_facets_compare_entire_combinations_not_any_member(table_conn, kind, column, full, partial, expected):
    service, base = reader(table_conn, kind), query_for(kind)
    with service.read_snapshot():
        options = service.facets(base, column)["options"]
        assert all(re.fullmatch(r"[a-f0-9]{64}", row["key"]) for row in options)
        key = next(row["key"] for row in options if row["label"] == partial)
        assert service.matching_keys(replace(base, column_filters=conditions(column, [key]))) == sorted(expected)
        full_key = next(row["key"] for row in options if row["label"] == full)
        assert service.matching_keys(replace(base, column_filters=conditions(column, [full_key]))) == ["OK" if kind == "operator" else "S1"]
        assert all("ref" not in row and "entity_key" not in row for row in options)


def test_null_zero_empty_and_different_units_have_distinct_business_cells(table_conn):
    service, query = reader(table_conn, "material"), MaterialPageRequest()
    with service.read_snapshot():
        quantities = service.facets(query, "stock_qty")["options"]
        assert [row["label"] for row in quantities] == ["未知", "0 kg", "0 pcs", "2 pcs", "10 kg"]
        assert len({row["key"] for row in quantities}) == 5
        specs = service.facets(query, "spec")["options"]
        assert {row["label"]: row["count"] for row in specs} == {"未知": 1, "（空白）": 1, "Round": 3}
        assert sum(row["count"] for row in service.facets(query, "status")["options"]) == 5


def test_facet_values_ignore_all_column_filters_but_keep_toolbar_scope(table_conn):
    service = reader(table_conn, "material")
    query = MaterialPageRequest(query="Alpha", status=None, size=1)
    with service.read_snapshot():
        expected = service.facets(query, "spec")
        filtered = replace(query, column_filters=conditions("label", []))
        assert service.facets(filtered, "spec") == expected
        assert expected["row_count"] == 3 and expected["page"]["total"] == 3
        result = service.facets(filtered, "spec", "rou", size=1)
        assert result["page"]["total"] == 1 and result["options"][0]["label"] == "Round"
        assert service.facets(query, "spec", "absent")["page"] == {"number": 1, "size": 100, "total": 0, "pages": 1}


@pytest.mark.parametrize("kind,category", VIEWS)
def test_facets_filter_full_metrics_before_page(table_conn, kind, category):
    service, query = reader(table_conn, kind), query_for(kind, category, size=1)
    with service.read_snapshot():
        options = service.facets(query, "business_code")["options"]
        chosen = options[-2:]
        filtered = replace(query, column_filters=conditions("business_code", [row["key"] for row in chosen]))
        records, page = service.page(filtered)
        assert len(records) == 1 and page["total"] == 2
        assert service.metrics(filtered)["counts"]["total"] == 2
        assert service.matching_keys(filtered) == sorted(row["label"] for row in chosen)


@pytest.mark.parametrize("category,column", [("external", "available_machines"), ("internal", "default_merge_mode"), (None, "available_operators")])
def test_category_specific_columns_cannot_change_scope_silently(category, column):
    with pytest.raises(WorkbenchCommandRejected):
        ResourcePageRequest("op_type", category=category, sort=column)
    with pytest.raises(WorkbenchCommandRejected):
        ResourcePageRequest("op_type", category=category, column_filters=conditions(column, []))


@pytest.mark.parametrize("kind,category,ref_kind,code", [
    ("material", None, "material", "MAT5"), ("op_type", "internal", "op_type", "A"),
    ("machine", None, "machine_group", "G1"), ("operator", None, "shift_profile", "H1"), ("supplier", None, "op_type", "X")])
def test_missing_refs_fail_before_facet_or_filtered_paging_without_repairs(table_conn, kind, category, ref_kind, code):
    table_conn.execute("DELETE FROM WorkbenchEntityRefs WHERE kind=? AND entity_key=?", (ref_kind, code))
    table_conn.commit()
    before = stored_state(table_conn)
    service, query = reader(table_conn, kind), query_for(kind, category, size=1)
    with pytest.raises(WorkbenchCommandRejected, match="永久引用"):
        with service.read_snapshot():
            service.facets(query, "label")
    assert stored_state(table_conn) == before


def test_unavailable_qualification_is_unknown_not_zero_and_invalid_binding_is_visible(table_conn):
    table_conn.execute("UPDATE OperatorSkill SET op_type_id='X' WHERE operator_id='OK' AND op_type_id='B'")
    table_conn.execute("UPDATE Machines SET op_type_id='X' WHERE machine_id='A4'")
    table_conn.commit()
    service = reader(table_conn, "op_type")
    with service.read_snapshot():
        facet = service.facets(ResourcePageRequest("op_type", category="internal"), "available_operators")
        assert [(row["label"], row["count"]) for row in facet["options"]] == [("无法核实", 3)]
    service = reader(table_conn, "machine")
    with service.read_snapshot():
        query = ResourcePageRequest("machine", sort="op_type_ref")
        rows, _ = service.page(query)
        bad = next(row.entity for row in rows if row.identity.entity_key == "A4")
        assert bad["relationships"]["op_type"]["label"] == "Type X"
        assert any(issue["code"] == "machine_work_type_invalid" for issue in bad["issues"])
