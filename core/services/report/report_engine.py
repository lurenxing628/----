from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, BinaryIO, Callable, ClassVar, Dict, List

from core.infrastructure.errors import AppError, ErrorCode, ValidationError
from core.services.scheduler.calendar_service import CalendarService
from data.repositories import ScheduleHistoryRepository, ScheduleRepository

from . import calculations, queries
from .exporters import export_downtime_impact_xlsx, export_overdue_xlsx, export_utilization_xlsx


@dataclass
class ReportExport:
    filename: str
    content_type: str
    data: BinaryIO
    mode: str = "direct"
    estimated_rows: int = 0


@dataclass(frozen=True)
class ReportExportDecision:
    mode: str
    estimated_rows: int


class ReportEngine:
    """
    报表引擎（基于现有 DB 表直接汇总）。
    - queries：取数
    - calculations：指标计算
    - exporters：导出渲染（xlsx）
    """

    XLSX_CONTENT_TYPE: ClassVar[str] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    EXPORT_DIRECT_MAX_ROWS: ClassVar[int] = 2000
    EXPORT_STREAM_MAX_ROWS: ClassVar[int] = 20000

    def __init__(self, conn, logger=None):
        self.conn = conn
        self.logger = logger
        self.schedule_repo = ScheduleRepository(conn, logger=logger)
        self.history_repo = ScheduleHistoryRepository(conn, logger=logger)
        self.calendar = CalendarService(conn, logger=logger)

    def _sanitize_export_threshold(self, value: Any, *, default: int) -> int:
        try:
            parsed = int(value)
        except Exception:
            parsed = int(default)
        return max(0, parsed)

    def _build_export_decision(self, estimated_rows: int) -> ReportExportDecision:
        rows = max(0, int(estimated_rows or 0))
        direct_max = self._sanitize_export_threshold(getattr(self, "EXPORT_DIRECT_MAX_ROWS", 0), default=0)
        stream_max = self._sanitize_export_threshold(
            getattr(self, "EXPORT_STREAM_MAX_ROWS", direct_max),
            default=direct_max,
        )
        if stream_max < direct_max:
            stream_max = direct_max

        if rows <= direct_max:
            return ReportExportDecision(mode="direct", estimated_rows=rows)
        if rows <= stream_max:
            return ReportExportDecision(mode="stream", estimated_rows=rows)
        return ReportExportDecision(mode="reject_need_async", estimated_rows=rows)

    def _raise_export_need_async(self, *, report_name: str, decision: ReportExportDecision) -> None:
        raise AppError(
            code=ErrorCode.VALIDATION_ERROR,
            message=f"{report_name}导出范围过大（预估 {int(decision.estimated_rows)} 行），请缩小范围后重试，或改走后台导出。",
            details={
                "field": "导出范围",
                "mode": decision.mode,
                "estimated_rows": int(decision.estimated_rows),
                "report_name": report_name,
            },
        )

    def _build_xlsx_export(
        self,
        *,
        report_name: str,
        filename: str,
        estimated_rows: int,
        build_direct: Callable[[], BinaryIO],
        build_stream: Callable[[], BinaryIO],
    ) -> ReportExport:
        decision = self._build_export_decision(estimated_rows)
        if decision.mode == "reject_need_async":
            self._raise_export_need_async(report_name=report_name, decision=decision)
        data = build_stream() if decision.mode == "stream" else build_direct()
        return ReportExport(
            filename=filename,
            content_type=self.XLSX_CONTENT_TYPE,
            data=data,
            mode=decision.mode,
            estimated_rows=decision.estimated_rows,
        )

    # -------------------------
    # Version helpers
    # -------------------------
    def list_versions(self, limit: int = 30) -> List[Dict[str, Any]]:
        return list(self.history_repo.list_versions(limit=int(limit)))

    def latest_version(self) -> int:
        return int(self.history_repo.get_latest_version() or 0)

    def version_date_range(self, version: int) -> Dict[str, Any]:
        """
        返回指定版本的排程日期范围（用于报表默认筛选）。
        """
        v = int(version or 0)
        out: Dict[str, Any] = {
            "version": v,
            "start_time": None,
            "end_time": None,
            "start_date": None,
            "end_date": None,
            "has_data": False,
        }
        if v <= 0:
            return out

        span = self.schedule_repo.get_version_time_span(v)
        if not span:
            return out

        start_time = span.get("start_time")
        end_time = span.get("end_time")
        start_dt = calculations.parse_dt(start_time)
        end_dt = calculations.parse_dt(end_time)
        if not start_dt or not end_dt:
            return out

        out["start_time"] = str(start_time)
        out["end_time"] = str(end_time)
        out["start_date"] = start_dt.date().isoformat()
        out["end_date"] = end_dt.date().isoformat()
        out["has_data"] = True
        return out

    # -------------------------
    # 1) 超期清单
    # -------------------------
    def overdue_batches(self, version: int) -> Dict[str, Any]:
        v = int(version or 0)
        rows = queries.fetch_overdue_base_rows(self.conn, v)
        scheduled, unscheduled, as_of = calculations.compute_overdue_buckets(rows)
        items = list(scheduled) + list(unscheduled)
        return {
            "version": v,
            "count": len(items),
            "scheduled_count": len(scheduled),
            "unscheduled_count": len(unscheduled),
            "as_of_time": as_of,
            # 兼容旧页面：items 仍保留（已排程在前、未排程在后）
            "items": items,
            # 新增分桶输出
            "scheduled_items": list(scheduled),
            "unscheduled_items": list(unscheduled),
        }

    def export_overdue_xlsx(self, version: int) -> ReportExport:
        rep = self.overdue_batches(version)
        items = list(rep.get("items") or [])
        if not items:
            raise ValidationError("当前版本没有可导出的超期结果，请换一个排产版本后再试。", field="导出")
        return self._build_xlsx_export(
            report_name="超期清单",
            filename=f"超期清单_v{int(rep['version'])}.xlsx",
            estimated_rows=len(items),
            build_direct=lambda: export_overdue_xlsx(items),
            build_stream=lambda: export_overdue_xlsx(items, write_only=True),
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
        machines = list(rep.get("machines") or [])
        operators = list(rep.get("operators") or [])
        if not machines and not operators:
            raise ValidationError("暂无数据，不能导出。请调整版本或日期范围后再试。", field="导出")
        return self._build_xlsx_export(
            report_name="资源负荷与利用率",
            filename=f"资源负荷与利用率_v{int(rep['version'])}_{rep['start_date']}_to_{rep['end_date']}.xlsx",
            estimated_rows=len(machines) + len(operators),
            build_direct=lambda: export_utilization_xlsx(machines, operators),
            build_stream=lambda: export_utilization_xlsx(machines, operators, write_only=True),
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
        machines = list(rep.get("machines") or [])
        if not machines:
            raise ValidationError("暂无数据，不能导出。请调整版本或日期范围后再试。", field="导出")
        return self._build_xlsx_export(
            report_name="停机影响统计",
            filename=f"停机影响统计_v{int(rep['version'])}_{rep['start_date']}_to_{rep['end_date']}.xlsx",
            estimated_rows=len(machines),
            build_direct=lambda: export_downtime_impact_xlsx(machines),
            build_stream=lambda: export_downtime_impact_xlsx(machines, write_only=True),
        )
