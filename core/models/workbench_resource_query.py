"""Bounded resource pages with filters that match their real domain fields."""

from dataclasses import dataclass, field
from typing import Dict, Optional

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_resource_table_query import normalize_column_filters, table_columns

RESOURCE_KINDS = ("op_type", "machine", "operator", "supplier", "machine_group", "shift_profile")


@dataclass(frozen=True)
class ResourcePageRequest:
    kind: str
    query: str = ""
    status: Optional[str] = None
    category: Optional[str] = None
    number: int = 1
    size: int = 20
    sort: str = "business_code"
    direction: str = "asc"
    column_filters: Dict = field(default_factory=dict)

    def __post_init__(self):
        if self.kind not in RESOURCE_KINDS or type(self.query) is not str or len(self.query) > 200:
            raise WorkbenchCommandRejected("invalid_input", "资源类型或搜索条件不正确。", 400)
        statuses = {"op_type": (None,), "machine": (None, "active", "maintain", "inactive", "unknown"),
                    "operator": (None, "active", "leave", "inactive", "unknown"),
                    "supplier": (None, "active", "pending_review", "inactive", "unknown")}
        if self.status not in statuses.get(self.kind, (None, "active", "inactive", "unknown")):
            raise WorkbenchCommandRejected("invalid_input", "资源状态筛选不正确。", 400)
        if self.category not in ((None, "internal", "external") if self.kind == "op_type" else (None,)):
            raise WorkbenchCommandRejected("invalid_input", "当前资源不支持此归属筛选。", 400)
        if type(self.number) is not int or not 1 <= self.number <= 1000000 or type(self.size) is not int or not 1 <= self.size <= 200:
            raise WorkbenchCommandRejected("invalid_input", "页码或每页条数不正确，每页最多200条。", 400)
        sorts = ("business_code", "label", "status") + table_columns(self.kind, self.category)
        if self.sort not in sorts or self.direction not in ("asc", "desc"):
            raise WorkbenchCommandRejected("invalid_input", "资源排序条件不正确。", 400)
        object.__setattr__(self, "column_filters", normalize_column_filters(self.column_filters, self.kind, self.category))

    def scope(self):
        return {"kind": self.kind, "query": self.query, "status": self.status, "category": self.category,
                "size": self.size, "sort": self.sort, "direction": self.direction,
                **({"column_filters": self.column_filters} if self.column_filters else {})}
