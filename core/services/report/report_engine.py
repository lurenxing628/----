from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List

from core.infrastructure.errors import ValidationError
from core.services.scheduler.calendar_service import CalendarService
from data.repositories import ScheduleHistoryRepository, ScheduleRepository

from . import calculations, queries
from .exporters import export_downtime_impact_xlsx, export_overdue_xlsx, export_utilization_xlsx


@dataclass
class ReportExport:
    filename: str
    content_type: str
    data: io.BytesIO


class ReportEngine:
    """
    报表引擎（基于现有 DB 表直接汇总）。
    - queries：取数
    - calculations：指标计算
    - exporters：导出渲染（xlsx）
    """

    XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    def __init__(self, conn, logger=None):
        self.conn = conn
        self.logger = logger
        self.schedule_repo = ScheduleRepository(conn, logger=logger)
        self.history_repo = ScheduleHistoryRepository(conn, logger=logger)
        self.calendar = CalendarService(conn, logger=logger)

    # -------------------------
    # Version helpers
    # -------------------------
    def list_versions(self, limit: int = 30) -> List[Dict[str, Any]]:
        return list(self.history_repo.list_versions(limit=int(limit)))

    def latest_version(self) -> int:
        return int(self.history_repo.get_latest_version() or 0)

    # -------------------------
    # 1) 超期清单
    # -------------------------
    def overdue_batches(self, version: int) -> Dict[str, Any]:
        v = int(version or 0)
        rows = queries.fetch_overdue_base_rows(self.conn, v)
        items = calculations.compute_overdue_items(rows)
        return {"version": v, "count": len(items), "items": items}

    def export_overdue_xlsx(self, version: int) -> ReportExport:
        rep = self.overdue_batches(version)
        buf = export_overdue_xlsx(rep["items"])
        return ReportExport(
            filename=f"超期清单_v{int(rep['version'])}.xlsx",
            content_type=self.XLSX_CONTENT_TYPE,
            data=buf,
        )

    # -------------------------
    # 2) 资源负荷/利用率
    # -------------------------
    def utilization(self, version: int, start_date: Any, end_date: Any) -> Dict[str, Any]:
        v = int(version or 0)
        sd = calculations.parse_date(start_date, field="start_date")
        ed = calculations.parse_date(end_date, field="end_date")
        if ed < sd:
            raise ValidationError("结束日期不能早于开始日期", field="end_date")

        start_dt = datetime(sd.year, sd.month, sd.day, 0, 0, 0)
        end_dt_excl = datetime(ed.year, ed.month, ed.day, 0, 0, 0) + timedelta(days=1)
        start_s = start_dt.strftime("%Y-%m-%d %H:%M:%S")
        end_s = end_dt_excl.strftime("%Y-%m-%d %H:%M:%S")

        schedule_rows = self.schedule_repo.list_overlapping_with_details(start_s, end_s, v)

        cap_hours = calculations.capacity_hours(self.calendar, sd, ed)
        if cap_hours <= 0:
            cap_hours = 0.0

        machine_rows, operator_rows = calculations.compute_utilization(
            schedule_rows=schedule_rows,
            start_dt=start_dt,
            end_dt_excl=end_dt_excl,
            cap_hours=float(cap_hours),
        )

        return {
            "version": v,
            "start_date": sd.isoformat(),
            "end_date": ed.isoformat(),
            "capacity_hours_per_resource": round(float(cap_hours), 2),
            "machines": machine_rows,
            "operators": operator_rows,
        }

    def export_utilization_xlsx(self, version: int, start_date: Any, end_date: Any) -> ReportExport:
        rep = self.utilization(version, start_date, end_date)
        buf = export_utilization_xlsx(rep["machines"], rep["operators"])
        return ReportExport(
            filename=f"资源负荷与利用率_v{int(rep['version'])}_{rep['start_date']}_to_{rep['end_date']}.xlsx",
            content_type=self.XLSX_CONTENT_TYPE,
            data=buf,
        )

    # -------------------------
    # 3) 停机影响统计
    # -------------------------
    def downtime_impact(self, version: int, start_date: Any, end_date: Any) -> Dict[str, Any]:
        v = int(version or 0)
        sd = calculations.parse_date(start_date, field="start_date")
        ed = calculations.parse_date(end_date, field="end_date")
        if ed < sd:
            raise ValidationError("结束日期不能早于开始日期", field="end_date")

        start_dt = datetime(sd.year, sd.month, sd.day, 0, 0, 0)
        end_dt_excl = datetime(ed.year, ed.month, ed.day, 0, 0, 0) + timedelta(days=1)
        start_s = start_dt.strftime("%Y-%m-%d %H:%M:%S")
        end_s = end_dt_excl.strftime("%Y-%m-%d %H:%M:%S")

        downtime_rows = queries.fetch_downtime_rows(self.conn, start_s, end_s)
        sch_rows = self.schedule_repo.list_overlapping_with_details(start_s, end_s, v)

        machines = calculations.compute_downtime_impact(
            downtime_rows=downtime_rows,
            schedule_rows=sch_rows,
            start_dt=start_dt,
            end_dt_excl=end_dt_excl,
        )

        return {
            "version": v,
            "start_date": sd.isoformat(),
            "end_date": ed.isoformat(),
            "machines": machines,
        }

    def export_downtime_impact_xlsx(self, version: int, start_date: Any, end_date: Any) -> ReportExport:
        rep = self.downtime_impact(version, start_date, end_date)
        buf = export_downtime_impact_xlsx(rep["machines"])
        return ReportExport(
            filename=f"停机影响统计_v{int(rep['version'])}_{rep['start_date']}_to_{rep['end_date']}.xlsx",
            content_type=self.XLSX_CONTENT_TYPE,
            data=buf,
        )

