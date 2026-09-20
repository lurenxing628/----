"""Whole-cell AND/OR filtering and toolbar-only distincts, independent of SQL."""

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_resource_table_query import MAX_FACET_KEYS, table_query_required, validate_facet_request


class ResourceTableIndex:
    def __init__(self, rows, cells, legacy_values=None):
        self.rows, self.cells = rows, cells
        self.legacy_values = legacy_values

    def matching_keys(self, query):
        filters = [(column, condition["mode"], set(condition["values"])) for column, condition in query.column_filters.items()]
        keys = [code for code in self.rows if all(
            (self.cells[code][column].key in values) == (mode == "include") for column, mode, values in filters)]
        # Stable two-pass ordering retains business-code ASC for equal cell values in either direction.
        keys.sort()
        keys.sort(key=lambda code: self._order(code, query), reverse=query.direction == "desc")
        return keys

    def _order(self, code, query):
        if self.legacy_values is not None and not table_query_required(query):
            value = self.legacy_values[code][query.sort]
            return (0, "") if value is None else (1, value)
        return self.cells[code][query.sort].order

    def page(self, query):
        keys = self.matching_keys(query)
        start = (query.number - 1) * query.size
        return [self.rows[code] for code in keys[start:start + query.size]], len(keys)

    def _options(self, column, search):
        options = {}
        for code in self.rows:
            cell = self.cells[code][column]
            if cell.key not in options:
                options[cell.key] = {"key": cell.key, "label": cell.label, "count": 0, "order": cell.order}
            options[cell.key]["count"] += 1
        needle = search.casefold()
        selected = [value for value in options.values() if needle in value["label"].casefold()]
        selected.sort(key=lambda value: (value["order"], value["label"], value["key"]))
        return selected

    def facets(self, query, column, search="", number=1, size=100):
        validate_facet_request(query, column, search, number, size)
        selected = self._options(column, search)
        total = len(selected)
        pages = max(1, (total + size - 1) // size)
        if number > pages:
            raise WorkbenchCommandRejected("snapshot_stale", "筛选值页码已超出当前范围，请刷新。")
        values = [{key: row[key] for key in ("key", "label", "count")} for row in selected[(number - 1) * size:number * size]]
        return {"column": column, "basis": "toolbar_scope", "options": values, "row_count": len(self.rows),
                "page": {"number": number, "size": size, "total": total, "pages": pages}}

    def facet_selection(self, query, column, search="", size=100):
        validate_facet_request(query, column, search, 1, size)
        options = self._options(column, search)
        if len(options) > MAX_FACET_KEYS:
            raise WorkbenchCommandRejected("capacity_exceeded", "搜索命中的不同值超过50000个，请缩小范围后重试；未截断结果。", 413)
        keys = [row["key"] for row in options]
        return {"column": column, "basis": "toolbar_scope", "keys": keys, "total": len(keys)}
