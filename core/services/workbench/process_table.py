"""Pure table calculations over one caller-owned projected process snapshot."""

from typing import Dict

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_process_table_query import PROCESS_STAGES, validate_process_facet_request
from core.models.workbench_resource_table_query import MAX_FACET_KEYS

from .resource_table_cells import TableCell, number_cell, text_cell
from .resource_table_index import ResourceTableIndex

_STAGE_LABELS = dict(zip(PROCESS_STAGES, ("待导入路线", "待定归属", "待填工时", "已就绪")))


def process_table_cells(entity):
    workflow = entity["workflow"]
    stage = workflow["stage"]
    if stage not in PROCESS_STAGES or workflow["ready"] is not (stage == "ready"):
        raise WorkbenchCommandRejected("storage_failure", "工艺阶段记录前后不一致，系统不猜确认状态。请刷新重试；仍不行请联系维护人员。", 500)
    if stage == "ready" and workflow["origin"] != "managed":
        raise WorkbenchCommandRejected("storage_failure", "这条历史遗留工艺没有单独确认过，不能算已就绪。请到基础资料逐道工序确认。", 500)
    cell = text_cell(_STAGE_LABELS[stage])
    return {"business_code": text_cell(entity["business_code"]), "label": text_cell(entity["label"]),
            "operation_count": number_cell(entity["relationships"]["operation_count"]),
            "stage": TableCell(cell.key, cell.label, (1, PROCESS_STAGES.index(stage)))}


class ProcessTable:
    """No repository or connection: pass all project_part entities from one snapshot.

    Rebuild after a facts/workflow snapshot changes; do not mutate the input while
    using this table. matching_rows is the complete, ordered export selection.
    """

    def __init__(self, entities):
        self.rows, self.cells = {}, {}
        self.search_text = {}
        for entity in entities:
            ref = entity["ref"]
            if ref in self.rows:
                raise WorkbenchCommandRejected("storage_failure", "读到的工艺数据里有重复零件。请刷新重试；仍不行请联系维护人员。", 500)
            self.rows[ref] = entity
            self.cells[ref] = process_table_cells(entity)
            self.search_text[ref] = tuple(str(value).casefold() for value in (
                entity["business_code"], entity["label"], entity["fields"]["route_raw"]) if value is not None)

    def _matching_refs(self, query, exclude_column=None):
        filters = [(column, rule["mode"], set(rule["values"])) for column, rule in query.column_filters.items()
                   if column != exclude_column]
        needle = query.query.casefold()
        return [ref for ref, row in self.rows.items()
                if (not needle or any(needle in value for value in self.search_text[ref]))
                and (query.stage is None or row["workflow"]["stage"] == query.stage)
                and all((self.cells[ref][column].key in values) == (mode == "include")
                        for column, mode, values in filters)]

    def matching_rows(self, query):
        """Filter and sort the entire snapshot; query.number/size do not limit it."""
        refs = self._matching_refs(query)
        refs.sort(key=lambda ref: (self.cells[ref]["business_code"].order, ref))
        # Stable passes from lowest to highest priority preserve the ASC tie break.
        for item in reversed(query.ordering()):
            column = item["field"]
            refs.sort(key=lambda ref: self.cells[ref][column].order, reverse=item["direction"] == "desc")
        return [self.rows[ref] for ref in refs]

    def page(self, query):
        rows = self.matching_rows(query)
        counts: Dict[str, int] = dict.fromkeys(PROCESS_STAGES, 0)
        for row in rows:
            counts[row["workflow"]["stage"]] += 1
        counts["total"] = len(rows)
        start = (query.number - 1) * query.size
        return {"entities": rows[start:start + query.size], "page": {
            "number": query.number, "size": query.size, "total": len(rows),
            "pages": max(1, (len(rows) + query.size - 1) // query.size), "sort": query.ordering()},
            "metrics": {"scope": "filtered", "counts": counts}}

    def _facet_options(self, query, column, search):
        refs = self._matching_refs(query, exclude_column=column)
        index = ResourceTableIndex({ref: self.rows[ref] for ref in refs}, self.cells)
        return index._options(column, search), len(refs)

    def facets(self, query, column, search="", number=1, size=100):
        validate_process_facet_request(column, search, number, size)
        options, row_count = self._facet_options(query, column, search)
        total = len(options)
        pages = max(1, (total + size - 1) // size)
        if number > pages:
            raise WorkbenchCommandRejected("snapshot_stale", "翻页位置已失效，请回到第 1 页重新查询。")
        values = [{key: row[key] for key in ("key", "label", "count")}
                  for row in options[(number - 1) * size:number * size]]
        # Keep ResourceTableFilterModel's envelope; process_facet_scope binds the
        # effective toolbar scope, including every column except this one.
        return {"column": column, "basis": "toolbar_scope", "options": values, "row_count": row_count,
                "page": {"number": number, "size": size, "total": total, "pages": pages}}

    def facet_selection(self, query, column, search="", size=100):
        validate_process_facet_request(column, search, 1, size)
        options, _ = self._facet_options(query, column, search)
        if len(options) > MAX_FACET_KEYS:
            raise WorkbenchCommandRejected("capacity_exceeded", "搜索命中的不同值超过 50000 个，没有返回结果，也不会只给一部分。请缩小范围后重试。", 413)
        keys = [row["key"] for row in options]
        return {"column": column, "basis": "toolbar_scope", "keys": keys, "total": len(keys)}
