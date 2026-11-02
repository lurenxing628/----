"""Process table scopes using the existing resource column-filter vocabulary."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_process_query import PROCESS_STAGES, PROCESS_TABLE_COLUMNS
from core.models.workbench_resource_table_query import normalize_table_column_filters

MAX_PROCESS_SORT_KEYS = len(PROCESS_TABLE_COLUMNS)
_SCOPE_FIELDS = {"query", "stage", "sort", "direction", "column_filters"}
# The list and facet routes decode their JSON arguments strictly and share this duplicate-key text.
DUPLICATE_QUERY_MESSAGE = "查询条件里有重复的项，请重新选择。"


def normalize_process_column_filters(value):
    return normalize_table_column_filters(
        value, PROCESS_TABLE_COLUMNS, invalid_column_message="工艺列表的筛选列不正确，请重新选择筛选条件。"
    )


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
    """The one process list request: sort is a column with direction, or a list of up to four keys."""

    query: str = ""
    stage: Optional[str] = None
    number: int = 1
    size: int = 20
    sort: Union[str, List[Dict[str, str]]] = "business_code"
    direction: str = "asc"
    column_filters: Dict = field(default_factory=dict)
    _ordering: List[Dict[str, str]] = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        if not isinstance(self.query, str) or len(self.query) > 200:
            raise WorkbenchCommandRejected("invalid_input", "搜索内容必须是200字以内的文字。", 400)
        if self.stage not in (None, *PROCESS_STAGES):
            raise WorkbenchCommandRejected("invalid_input", "工艺阶段筛选不正确。", 400)
        if type(self.number) is not int or not 1 <= self.number <= 1_000_000:
            raise WorkbenchCommandRejected("invalid_input", "页码必须是1至1000000之间的整数。", 400)
        if type(self.size) is not int or not 1 <= self.size <= 200:
            raise WorkbenchCommandRejected("invalid_input", "每页条数必须是1至200之间的整数。", 400)
        ordering = normalize_process_sort(self.sort, self.direction)
        object.__setattr__(self, "_ordering", ordering)
        if type(self.sort) is list:
            object.__setattr__(self, "sort", ordering)
        object.__setattr__(self, "column_filters", normalize_process_column_filters(self.column_filters))

    def ordering(self):
        """An empty list clears header sorting; the stable identity tie remains."""
        return self._ordering

    def scope(self):
        return {"kind": "part", "query": self.query, "stage": self.stage, "size": self.size,
                "sort": self.ordering(),
                **({"column_filters": self.column_filters} if self.column_filters else {})}


def process_table_request(value):
    """Parse a list scope; transport owns snapshot_ref and duplicate-key decoding."""
    if type(value) is not dict or set(value) - (_SCOPE_FIELDS | {"page", "size"}):
        raise WorkbenchCommandRejected("invalid_input", "工艺列表的查询条件含有不支持的项，请刷新页面后重试。", 400)
    fields = dict(value)
    if "page" in fields:
        fields["number"] = fields.pop("page")
    return ProcessTablePageRequest(**fields)


def process_scope_request(value, *, size=20):
    """An action/export scope (no page number) as the viewed list's request; size is that list's page size."""
    if type(value) is not dict or set(value) - _SCOPE_FIELDS:
        raise WorkbenchCommandRejected("invalid_input", "工艺动作范围只接受搜索、阶段、排序和列筛选，不接受分页。", 400)
    return ProcessTablePageRequest(**value, size=size)


def wire_process_scope(request):
    """A validated request's scope as its wire dictionary, without kind or page size."""
    return {key: item for key, item in request.scope().items() if key not in ("kind", "size")}


def validate_process_facet_request(column, search, number, size):
    if column not in PROCESS_TABLE_COLUMNS:
        raise WorkbenchCommandRejected("invalid_input", "该工艺列不支持选项查询。", 400)
    if type(search) is not str or len(search) > 200:
        raise WorkbenchCommandRejected("invalid_input", "筛选值搜索最多200字。", 400)
    if type(number) is not int or not 1 <= number <= 1000000 or type(size) is not int or not 1 <= size <= 200:
        raise WorkbenchCommandRejected("invalid_input", "筛选值页码或条数不正确，每页最多200条。", 400)


def process_facet_scope(query, column, search="", size=100):
    """Bind facets to toolbar AND other columns, never the queried column itself; arguments are already validated."""
    filters = {key: value for key, value in query.column_filters.items() if key != column}
    scope = {"kind": "part", "query": query.query, "stage": query.stage,
             **({"column_filters": filters} if filters else {})}
    return {"kind": "process_table_facets", "scope": scope, "column": column, "query": search, "size": size}
