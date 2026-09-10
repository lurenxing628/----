"""L2/L3 facet and filtered-page work stays batched; bulk selection is one scan."""

from dataclasses import replace

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.resource_table_cells import text_cell
from core.services.workbench.resource_table_index import ResourceTableIndex
from tests.workbench.resource_table_support import (
    conditions,
    measured_read,
    query_for,
    reader,
    seed_scale,
    stored_state,
    table_database,
)


@pytest.mark.parametrize("kind", ["material", "machine", "operator", "supplier"])
def test_two_thousand_and_ten_thousand_facet_filter_page_scale(table_conn, kind, record_property):
    service = reader(table_conn, kind)
    query = query_for(kind, query="Scale", size=200)
    results = []
    for start, amount, count in ((0, 2000, 2000), (2000, 8000, 10000)):
        seed_scale(table_conn, start, amount)
        before = stored_state(table_conn)
        with measured_read(table_conn) as measured:
            with service.read_snapshot():
                facet = service.facets(query, "business_code", size=100)
                selected = service.facet_selection(query, "business_code", size=100)
                assert facet["page"]["total"] == facet["row_count"] == count
                assert len(facet["options"]) == 100 and selected["total"] == count
                assert len(selected["keys"]) == count
                filtered = replace(query, column_filters=conditions("business_code", selected["keys"][::2]), number=2)
                records, page = service.page(filtered)
                assert len(records) == 200 and page["total"] == count // 2
                assert service.metrics(filtered)["counts"]["total"] == count // 2
                assert len(service.matching_rows(filtered)) == count // 2
        selects = sum(sql.lstrip().upper().startswith(("SELECT", "WITH")) for sql in measured["statements"])
        assert selects < 80
        assert stored_state(table_conn) == before
        results.append({"rows": count, "selects": selects, "vm_steps": measured["vm_steps"], "seconds": measured["seconds"]})
    assert results[1]["vm_steps"] < max(1000, results[0]["vm_steps"]) * 8
    record_property(kind + "_table_scale", results)


def test_bulk_value_selection_explicitly_rejects_more_than_fifty_thousand():
    codes = [f"B{index:05d}" for index in range(50001)]
    cells = {code: {"business_code": text_cell(code)} for code in codes}
    index = ResourceTableIndex(dict.fromkeys(codes), cells)
    query = query_for("material")
    with pytest.raises(WorkbenchCommandRejected) as error:
        index.facet_selection(query, "business_code")
    assert error.value.code == "capacity_exceeded" and error.value.status == 413
    result = index.facet_selection(query, "business_code", "B0")
    assert result["total"] == 10000 and len(set(result["keys"])) == 10000


@pytest.mark.parametrize("category,sort", [("internal", "available_operators"), ("external", "default_merge_mode")])
def test_work_type_l2_l3_facets_and_filtered_business_sort(table_conn, category, sort, record_property):
    service = reader(table_conn, "op_type")
    query = query_for("op_type", category, query="Scale", size=200, sort=sort)
    results = []
    for start, amount, count in ((0, 2000, 2000), (2000, 8000, 10000)):
        table_conn.executemany("INSERT INTO OpTypes(op_type_id,name,category) VALUES (?,?,?)", [
            (f"T{index:05d}", f"Scale {index:05d}", category) for index in range(start, start + amount)])
        table_conn.commit()
        before = stored_state(table_conn)
        with measured_read(table_conn) as measured:
            with service.read_snapshot():
                facet = service.facets(query, "business_code", size=100)
                selected = service.facet_selection(query, "business_code", size=100)
                assert facet["page"]["total"] == count and selected["total"] == count
                filtered = replace(query, column_filters=conditions("business_code", selected["keys"][::2]), number=2)
                rows, page = service.page(filtered)
                assert len(rows) == 200 and page["total"] == count // 2
                assert service.metrics(filtered)["counts"]["total"] == count // 2
                assert len(service.matching_rows(filtered)) == count // 2
        selects = sum(sql.lstrip().upper().startswith(("SELECT", "WITH")) for sql in measured["statements"])
        assert selects < 80 and stored_state(table_conn) == before
        results.append({"rows": count, "selects": selects, "vm_steps": measured["vm_steps"], "seconds": measured["seconds"]})
    assert results[1]["vm_steps"] < max(1000, results[0]["vm_steps"]) * 8
    record_property(category + "_table_scale", results)
