"""Catalog windows deliberately differ from the analysis finish-date cohort."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

from .workbench_report import ReportScope, reject


@dataclass(frozen=True)
class ReportCatalogScope:
    kind: str
    source: str = "production"
    plan_ref: Optional[str] = None
    window_date_from: Optional[str] = None
    window_date_to: Optional[str] = None
    query: str = ""

    def __post_init__(self):
        if self.kind not in ("overdue", "utilization", "downtime"):
            reject("未知目录报表。")
        ReportScope(source=self.source, plan_ref=self.plan_ref, query=self.query,
                    plan_finish_date_from=self.window_date_from, plan_finish_date_to=self.window_date_to)
        if self.kind == "overdue" and self.window_date_from is not None:
            reject("超期清单按正式计划全部批次统计，不接受时间窗口冒充批次范围。")

    def scope(self):
        return {"selection": "all_plan_batches" if self.kind == "overdue" else "schedule_window_overlap", **asdict(self)}
