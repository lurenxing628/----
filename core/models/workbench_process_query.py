"""Validated process list scope; confirmation state is not a browser preference."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.models.workbench_command import WorkbenchCommandRejected

PROCESS_TABLE_COLUMNS = ("business_code", "label", "operation_count", "stage")
PROCESS_STAGES = ("route", "source", "hours", "ready")


def normalize_process_page_base(query: str, stage: Optional[str], number: int, size: int) -> None:
    if not isinstance(query, str) or len(query) > 200:
        raise WorkbenchCommandRejected("invalid_input", "搜索内容必须是200字以内的文字。", 400)
    if stage not in (None, *PROCESS_STAGES):
        raise WorkbenchCommandRejected("invalid_input", "工艺阶段筛选不正确。", 400)
    if type(number) is not int or not 1 <= number <= 1_000_000:
        raise WorkbenchCommandRejected("invalid_input", "页码必须是1至1000000之间的整数。", 400)
    if type(size) is not int or not 1 <= size <= 200:
        raise WorkbenchCommandRejected("invalid_input", "每页条数必须是1至200之间的整数。", 400)


@dataclass(frozen=True)
class ProcessPageRequest:
    query: str = ""
    stage: Optional[str] = None
    number: int = 1
    size: int = 20
    sort: str = "business_code"
    direction: str = "asc"
    column_filters: Dict = field(default_factory=dict, init=False, repr=False, compare=False)

    def __post_init__(self):
        normalize_process_page_base(self.query, self.stage, self.number, self.size)
        if self.sort not in PROCESS_TABLE_COLUMNS or self.direction not in ("asc", "desc"):
            raise WorkbenchCommandRejected("invalid_input", "工艺排序条件不正确。", 400)

    def ordering(self) -> List[Dict[str, str]]:
        return [{"field": self.sort, "direction": self.direction}]

    def scope(self):
        return {"kind": "part", "query": self.query, "stage": self.stage, "size": self.size,
                "sort": self.sort, "direction": self.direction}
