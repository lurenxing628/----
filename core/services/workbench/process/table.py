"""Pure table calculations over one caller-owned projected process snapshot."""

from typing import Dict

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_process_query import PROCESS_STAGES
from core.services.workbench.facts.table_cells import TableCell, number_cell, text_cell
from core.services.workbench.facts.table_index import ResourceTableIndex

_STAGE_LABELS = dict(zip(PROCESS_STAGES, ("待导入路线", "待定归属", "待填工时", "已就绪")))


def process_table_cells(entity):
    workflow = entity["workflow"]
    stage = workflow["stage"]
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

    def _facet_index(self, query, column):
        """Facets of a column count the rows passing every other column's filter (process_facet_scope binds that scope)."""
        refs = self._matching_refs(query, exclude_column=column)
        return ResourceTableIndex({ref: self.rows[ref] for ref in refs}, self.cells)

    def facets(self, query, column, search, number, size):
        """``column``/``search``/``number``/``size`` were validated at the request boundary."""
        return self._facet_index(query, column).facets(column, search, number, size)

    def facet_selection(self, query, column, search):
        return self._facet_index(query, column).facet_selection(column, search)
