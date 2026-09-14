"""Process table scopes using the existing resource column-filter vocabulary."""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_process_query import ProcessPageRequest
from core.models.workbench_resource_table_query import MAX_FACET_KEYS

PROCESS_TABLE_COLUMNS = ("business_code", "label", "operation_count", "stage")
PROCESS_STAGES = ("route", "source", "hours", "ready")
MAX_PROCESS_SORT_KEYS = len(PROCESS_TABLE_COLUMNS)
_SCOPE_FIELDS = {"query", "stage", "sort", "direction", "column_filters"}


def unique_process_table_object(pairs):
    """Use as json.loads object_pairs_hook before duplicate JSON keys are lost."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise WorkbenchCommandRejected("invalid_input", "查询条件里有重复的项，请重新选择。", 400)
        result[key] = value
    return result


def normalize_process_column_filters(value):
    if type(value) is not dict or set(value) - set(PROCESS_TABLE_COLUMNS):
        raise WorkbenchCommandRejected("invalid_input", "工艺列表的筛选列不正确，请重新选择筛选条件。", 400)
    result = {}
    for column, condition in value.items():
        if type(condition) is not dict or set(condition) != {"mode", "values"}:
            raise WorkbenchCommandRejected("invalid_input", "列筛选必须包含mode和values。", 400)
        values = condition["values"]
        if condition["mode"] not in ("include", "exclude") or type(values) is not list or len(values) > MAX_FACET_KEYS:
            raise WorkbenchCommandRejected("invalid_input", "列筛选方式不对，每列最多 50000 个值。", 400)
        if any(type(key) is not str or re.fullmatch(r"[0-9a-f]{64}", key) is None for key in values) or len(set(values)) != len(values):
            raise WorkbenchCommandRejected("invalid_input", "筛选值不对或有重复，请重新选择筛选条件。", 400)
        result[column] = {"mode": condition["mode"], "values": sorted(values)}
    return {column: result[column] for column in sorted(result)}


def normalize_process_sort(value, direction="asc"):
    if direction not in ("asc", "desc"):
        raise WorkbenchCommandRejected("invalid_input", "工艺排序方向不正确。", 400)
    if type(value) is str:
        value = [{"field": value, "direction": direction}]
    elif direction != "asc":
        raise WorkbenchCommandRejected("invalid_input", "多键排序不能再指定整体排序方向。", 400)
    if type(value) is not list or len(value) > MAX_PROCESS_SORT_KEYS:
        raise WorkbenchCommandRejected("invalid_input", "工艺排序必须是列名或最多四项的排序列表。", 400)
    result, seen = [], set()
    for item in value:
        if type(item) is not dict or set(item) != {"field", "direction"}:
            raise WorkbenchCommandRejected("invalid_input", "排序项必须包含field和direction。", 400)
        column = item["field"]
        if column not in PROCESS_TABLE_COLUMNS or item["direction"] not in ("asc", "desc") or column in seen:
            raise WorkbenchCommandRejected("invalid_input", "排序列、方向不正确或存在重复列。", 400)
        seen.add(column)
        result.append(dict(item))
    return result


@dataclass(frozen=True)
class ProcessTablePageRequest:
    query: str = ""
    stage: Optional[str] = None
    number: int = 1
    size: int = 20
    sort: Union[str, List[Dict[str, str]]] = "business_code"
    direction: str = "asc"
    column_filters: Dict = field(default_factory=dict)

    def __post_init__(self):
        ProcessPageRequest(query=self.query, stage=self.stage, number=self.number, size=self.size)
        ordering = normalize_process_sort(self.sort, self.direction)
        if type(self.sort) is list:
            object.__setattr__(self, "sort", ordering)
        object.__setattr__(self, "column_filters", normalize_process_column_filters(self.column_filters))

    def ordering(self):
        """An empty list clears header sorting; the stable identity tie remains."""
        return normalize_process_sort(self.sort, self.direction)

    def scope(self):
        return {"kind": "part", "query": self.query, "stage": self.stage, "size": self.size,
                "sort": self.ordering(),
                **({"column_filters": normalize_process_column_filters(self.column_filters)} if self.column_filters else {})}


def process_table_request(value):
    """Parse a list scope; transport owns snapshot_ref and duplicate-key decoding."""
    if type(value) is not dict or set(value) - (_SCOPE_FIELDS | {"page", "size"}):
        raise WorkbenchCommandRejected("invalid_input", "工艺列表的查询条件含有不支持的项，请刷新页面后重试。", 400)
    fields = dict(value)
    if "page" in fields:
        fields["number"] = fields.pop("page")
    return ProcessTablePageRequest(**fields)


def process_table_scope(value):
    """Normalize an action/export scope, explicitly excluding page and page size."""
    if type(value) is not dict or set(value) - _SCOPE_FIELDS:
        raise WorkbenchCommandRejected("invalid_input", "工艺动作范围只接受搜索、阶段、排序和列筛选，不接受分页。", 400)
    return {key: item for key, item in process_table_request(value).scope().items() if key not in ("kind", "size")}


def validate_process_facet_request(column, search, number, size):
    if column not in PROCESS_TABLE_COLUMNS:
        raise WorkbenchCommandRejected("invalid_input", "该工艺列不支持选项查询。", 400)
    if type(search) is not str or len(search) > 200:
        raise WorkbenchCommandRejected("invalid_input", "筛选值搜索最多200字。", 400)
    if type(number) is not int or not 1 <= number <= 1000000 or type(size) is not int or not 1 <= size <= 200:
        raise WorkbenchCommandRejected("invalid_input", "筛选值页码或条数不正确，每页最多200条。", 400)


def process_facet_scope(query, column, search="", size=100):
    """Bind facets to toolbar AND other columns, never the queried column itself."""
    validate_process_facet_request(column, search, 1, size)
    filters = {key: value for key, value in query.column_filters.items() if key != column}
    scope = {"kind": "part", "query": query.query, "stage": query.stage,
             **({"column_filters": normalize_process_column_filters(filters)} if filters else {})}
    return {"kind": "process_table_facets", "scope": scope, "column": column, "query": search, "size": size}
