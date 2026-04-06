from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from core.services.scheduler import GanttService


@dataclass
class GanttQuery:
    view: str = "machine"
    week_start: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    offset_weeks: int = 0
    version: Optional[int] = None
    include_history: bool = False


class GanttDesktopDataProvider:
    """
    桌面端数据提供器（只读）。

    作用：
    - 统一封装 GanttService 调用；
    - 输出与 Web 同构的 gantt_contract JSON（dict）。
    """

    def __init__(self, service: GanttService):
        self._service = service

    def fetch_contract(self, query: Optional[GanttQuery] = None) -> Dict[str, Any]:
        q = query or GanttQuery()
        return self._service.get_gantt_tasks(
            view=q.view,
            week_start=q.week_start,
            offset_weeks=int(q.offset_weeks),
            start_date=q.start_date,
            end_date=q.end_date,
            version=q.version,
            include_history=bool(q.include_history),
        )

