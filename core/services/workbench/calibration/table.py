"""Typed full-snapshot calibration filters and facets, never current-page filtering."""

from core.models.enums import SOURCE_TYPE_LABELS
from core.models.workbench_calibration import TABLE_COLUMNS
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.facts.table_cells import number_cell, text_cell
from core.services.workbench.facts.table_index import ResourceTableIndex

#: 模板工序归属还没确认（存储为空）时，校准行的来源记作 unknown。
SOURCE_LABELS = {**SOURCE_TYPE_LABELS, "unknown": "未确认"}


def cells(row):
    return {"part_no": text_cell(row["part_no"] + " · " + row["part_name"]),
            "operation_label": text_cell(str(row["sequence"]) + " · " + row["operation_label"] + " · " +
                SOURCE_LABELS[row["source"]]),
            "old_unit_hours": number_cell(row["old_unit_hours"], missing="未填写"),
            "suggested_unit_hours": number_cell(row["suggested_unit_hours"], missing="暂无建议"),
            "sample_count": number_cell(row["sample_count"]),
            "absolute_deviation_percent": number_cell(row["deviation_percent"], "%", missing="未计算"),
            "status": text_cell("数据不足" if row["status"] == "insufficient_data" else "已有建议")}


def filter_rows(rows, rules, *, cell_cache):
    if not rules:
        return rows
    filters = [(key, rule["mode"], set(rule["values"])) for key, rule in rules.items()]
    selected = []
    for row in rows:
        values = cells(row)
        if cell_cache is not None:
            cell_cache[row["suggestion_ref"]] = values
        if all((values[key].key in keys) == (mode == "include") for key, mode, keys in filters):
            selected.append(row)
    return selected


def validate_facet(column, search, number, size):
    if column not in TABLE_COLUMNS or type(search) is not str or len(search) > 200 or "\x00" in search:
        raise WorkbenchCommandRejected("invalid_input", "筛选的列或搜索内容填写不对，列表没有变化。", 400)
    if type(number) is not int or not 1 <= number <= 1000000 or type(size) is not int or not 1 <= size <= 200:
        raise WorkbenchCommandRejected("invalid_input", "页码或每页数量填写不对，列表没有变化。", 400)


def facet_data(rows, column, search, number, size, *, selection, cell_cache):
    """``rows`` already pass every other column's filter; facets count them."""
    indexed = {row["suggestion_ref"]: row for row in rows}
    indexed_cells = {ref: cell_cache[ref] for ref in indexed} if cell_cache else {ref: cells(row) for ref, row in indexed.items()}
    index = ResourceTableIndex(indexed, indexed_cells)
    return index.facet_selection(column, search) if selection else index.facets(column, search, number, size)
