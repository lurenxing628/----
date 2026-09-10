"""Validated material query scope, independent of HTTP and persistence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_resource_table_query import normalize_column_filters, table_columns


@dataclass(frozen=True)
class MaterialPageRequest:
    query: str = ""
    status: Optional[str] = None
    number: int = 1
    size: int = 20
    sort: str = "business_code"
    direction: str = "asc"
    column_filters: Dict = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.query, str) or len(self.query) > 200:
            raise WorkbenchCommandRejected("invalid_input", "搜索内容必须是200字以内的文字。", 400)
        if self.status not in (None, "active", "inactive"):
            raise WorkbenchCommandRejected("invalid_input", "物料状态筛选不正确。", 400)
        if type(self.number) is not int or not 1 <= self.number <= 1_000_000:
            raise WorkbenchCommandRejected("invalid_input", "页码必须是1至1000000之间的整数。", 400)
        if type(self.size) is not int or not 1 <= self.size <= 200:
            raise WorkbenchCommandRejected("invalid_input", "每页条数必须是1至200之间的整数。", 400)
        if self.sort not in table_columns("material") or self.direction not in ("asc", "desc"):
            raise WorkbenchCommandRejected("invalid_input", "排序条件不正确。", 400)
        object.__setattr__(self, "column_filters", normalize_column_filters(self.column_filters, "material"))

    def scope(self):
        # Page number varies within a snapshot; filter, order and page size do not.
        return {"kind": "material", "query": self.query, "status": self.status,
                "size": self.size, "sort": self.sort, "direction": self.direction,
                **({"column_filters": self.column_filters} if self.column_filters else {})}
