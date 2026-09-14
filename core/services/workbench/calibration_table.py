"""Typed full-snapshot calibration filters and facets, never current-page filtering."""

from core.models.workbench_calibration import TABLE_COLUMNS
from core.models.workbench_command import WorkbenchCommandRejected

from .resource_table_cells import number_cell, text_cell
from .resource_table_index import ResourceTableIndex


def cells(row):
    return {"part_no": text_cell(row["part_no"] + " · " + row["part_name"]),
            "operation_label": text_cell(str(row["sequence"]) + " · " + row["operation_label"] + " · " +
                {"internal": "自制", "external": "外协", "unknown": "未确认", None: "未确认"}[row["source"]]),
            "old_unit_hours": number_cell(row["old_unit_hours"], missing="未填写"),
            "suggested_unit_hours": number_cell(row["suggested_unit_hours"], missing="暂无建议"),
            "sample_count": number_cell(row["sample_count"]),
            "absolute_deviation_percent": number_cell(row["deviation_percent"], "%", missing="未计算"),
            "status": text_cell("数据不足" if row["status"] == "insufficient_data" else "待复核")}


def filter_rows(rows, rules):
    if not rules:
        return rows
    filters = [(key, rule["mode"], set(rule["values"])) for key, rule in rules.items()]
    selected = []
    for row in rows:
        values = cells(row)
        if all((values[key].key in keys) == (mode == "include") for key, mode, keys in filters):
            selected.append(row)
    return selected


def validate_facet(column, search, number, size):
    if column not in TABLE_COLUMNS or type(search) is not str or len(search) > 200 or "\x00" in search:
        raise WorkbenchCommandRejected("invalid_input", "筛选的列或搜索内容填写不对，列表没有变化。", 400)
    if type(number) is not int or not 1 <= number <= 1000000 or type(size) is not int or not 1 <= size <= 200:
        raise WorkbenchCommandRejected("invalid_input", "页码或每页数量填写不对，列表没有变化。", 400)


def facet_data(rows, column, search, number, size, *, selection=False):
    validate_facet(column, search, number, size)
    indexed = {row["suggestion_ref"]: row for row in rows}
    if len(indexed) != len(rows):
        raise WorkbenchCommandRejected("projection_invalid", "同一个模板在筛选结果里出现了多次。数据可能已更新，请刷新后重试。")
    options = ResourceTableIndex(indexed, {ref: cells(row) for ref, row in indexed.items()})._options(column, search)
    if selection:
        return {"column": column, "basis": "toolbar_scope", "keys": [row["key"] for row in options], "total": len(options)}
    pages = max(1, (len(options) + size - 1) // size)
    if number > pages:
        raise WorkbenchCommandRejected("snapshot_stale", "翻页位置已失效，请回到第 1 页重新查询。")
    return {"column": column, "basis": "toolbar_scope", "row_count": len(rows),
            "options": [{key: row[key] for key in ("key", "label", "count")} for row in options[(number - 1) * size:number * size]],
            "page": {"number": number, "size": size, "total": len(options), "pages": pages}}
