"""Validated process list scope; confirmation state is not a browser preference."""

from dataclasses import dataclass
from typing import Optional

from core.models.workbench_command import WorkbenchCommandRejected


@dataclass(frozen=True)
class ProcessPageRequest:
    query: str = ""
    stage: Optional[str] = None
    number: int = 1
    size: int = 20
    sort: str = "business_code"
    direction: str = "asc"

    def __post_init__(self):
        if not isinstance(self.query, str) or len(self.query) > 200:
            raise WorkbenchCommandRejected("invalid_input", "搜索内容必须是200字以内的文字。", 400)
        if self.stage not in (None, "route", "source", "hours", "ready"):
            raise WorkbenchCommandRejected("invalid_input", "工艺阶段筛选不正确。", 400)
        if type(self.number) is not int or not 1 <= self.number <= 1_000_000:
            raise WorkbenchCommandRejected("invalid_input", "页码必须是1至1000000之间的整数。", 400)
        if type(self.size) is not int or not 1 <= self.size <= 200:
            raise WorkbenchCommandRejected("invalid_input", "每页条数必须是1至200之间的整数。", 400)
        if self.sort not in ("business_code", "label", "operation_count", "stage") or self.direction not in ("asc", "desc"):
            raise WorkbenchCommandRejected("invalid_input", "工艺排序条件不正确。", 400)

    def scope(self):
        return {"kind": "part", "query": self.query, "stage": self.stage, "size": self.size,
                "sort": self.sort, "direction": self.direction}
