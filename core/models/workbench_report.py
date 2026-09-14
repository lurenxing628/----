"""Strict report cohorts; pagination never changes the export cohort."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import date
from typing import Optional

from core.models.workbench_command import WorkbenchCommandRejected

TOPICS = ("delivery", "records", "machines", "people", "quality")
FOCUSES = ("all", "unreported", "unclosed", "late_open", "finish_late", "complete", "data_gaps")
MAX_REPORT_OPERATIONS = 10000
MAX_REPORT_EVENTS = 20000


def reject(message):
    raise WorkbenchCommandRejected("invalid_input", message, 400)


def reference(value):
    if value is not None and (type(value) is not str or re.fullmatch(r"[0-9a-f]{48}", value) is None):
        reject("这条记录已失效，请刷新后重新选择。")


def _validate_finish_dates(start: Optional[str], end: Optional[str]) -> None:
    if (start is None) != (end is None):
        reject("计划完工起止日期必须一起填写。")
    if start is not None and end is not None:
        try:
            if any(type(value) is not str or re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None for value in (start, end)):
                raise ValueError("date format")
            sd, ed = date.fromisoformat(start), date.fromisoformat(end)
            if ed < sd:
                raise ValueError("date order")
        except ValueError as exc:
            raise WorkbenchCommandRejected("invalid_input", "计划完工日期无效或结束早于开始。", 400) from exc


@dataclass(frozen=True)
class ReportScope:
    source: str = "production"
    plan_ref: Optional[str] = None
    plan_finish_date_from: Optional[str] = None
    plan_finish_date_to: Optional[str] = None
    batch_ref: Optional[str] = None
    resource_type: Optional[str] = None
    resource_ref: Optional[str] = None
    query: str = ""
    focus: str = "all"

    def __post_init__(self):
        if self.source != "production":
            reject("此入口只读取真实数据，不以演示数据替代。")
        reference(self.plan_ref)
        reference(self.batch_ref)
        if self.resource_ref != "unassigned":
            reference(self.resource_ref)
        if self.resource_type not in (None, "machine", "operator"):
            reject("资源类型只能是设备或人员。")
        if self.resource_ref and not self.resource_type:
            reject("选了设备或人员，就要同时选类型。")
        if self.focus not in FOCUSES or type(self.query) is not str or len(self.query) > 200:
            reject("分析范围或搜索文字无效。")
        _validate_finish_dates(self.plan_finish_date_from, self.plan_finish_date_to)

    def scope(self):
        return {"kind": "execution_analysis", **asdict(self)}


@dataclass(frozen=True)
class ReportPage:
    number: int = 1
    size: int = 20
    sort: str = "batch_label"
    direction: str = "asc"

    def __post_init__(self):
        if type(self.number) is not int or not 1 <= self.number <= 100000:
            reject("页码必须是正整数。")
        if type(self.size) is not int or self.size not in (10, 20, 50):
            reject("每页数量只能是 10、20 或 50。")
        if self.direction not in ("asc", "desc"):
            reject("排序方向无效。")

    def apply(self, rows, allowed):
        if self.sort not in allowed:
            reject("这个报表不支持按这一列排序。")
        known = [row for row in rows if row.get(self.sort) is not None]
        unknown = [row for row in rows if row.get(self.sort) is None]
        ordered = sorted(known, key=lambda row: row[self.sort], reverse=self.direction == "desc") + unknown
        pages = max(1, (len(rows) + self.size - 1) // self.size)
        if self.number > pages:
            reject("页码超出当前范围，请明确选择有效页码。")
        start = (self.number - 1) * self.size
        return ordered, ordered[start:start + self.size], {
            "number": self.number, "size": self.size, "total": len(rows), "pages": pages,
            "sort": [{"field": self.sort, "direction": self.direction}],
        }
