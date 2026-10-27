"""Current workbench report calculations consume an already selected plan."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, BinaryIO, Callable, ClassVar, Dict

from core.models.report_export import ReportExport, ReportExportDecision
from core.services.capacity.resource_utilization_metrics import METRIC_VERSION
from core.services.common.plan_query import SchedulePlanQueryService, SchedulePlanResolution
from core.shared.degradation import DegradationCollector
from data.repositories import MachineDowntimeRepository

from .date_range_limits import ensure_report_date_range_within_limit
from .downtime_impact import compute_downtime_impact
from .report_degradation import report_degradation_payload
from .utilization import group_utilization_rows, utilization_from_groups
from .utilization_calendars import resource_calendars_for_ids, resource_ids_from_groups


class ReportEngine:
    """Calculate current reports; workbench owns plan selection and exports."""

    XLSX_CONTENT_TYPE: ClassVar[str] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    EXPORT_DIRECT_MAX_ROWS: ClassVar[int] = 2000
    EXPORT_STREAM_MAX_ROWS: ClassVar[int] = 20000

    def __init__(self, conn, logger=None):
        self.conn = conn
        self.machine_downtime_repo = MachineDowntimeRepository(conn, logger=logger)
        self.plan_query_service = SchedulePlanQueryService(conn, logger=logger)

    def _fetch_overdue_base_rows_for_plan(self, resolution: SchedulePlanResolution):
        return self.plan_query_service.list_plan_overdue_base_rows_for_resolution(
            version=resolution.version, source_table=resolution.source_table,
        )

    def _list_plan_rows_between(self, resolution, start_time, end_time):
        return self.plan_query_service.list_plan_detail_rows_between_for_resolution(
            version=resolution.version, source_table=resolution.source_table,
            start_time=start_time, end_time=end_time,
        )


    def _build_export_decision(self, estimated_rows: int) -> ReportExportDecision:
        if estimated_rows <= self.EXPORT_DIRECT_MAX_ROWS:
            return ReportExportDecision(mode="direct", estimated_rows=estimated_rows)
        if estimated_rows <= self.EXPORT_STREAM_MAX_ROWS:
            return ReportExportDecision(mode="stream", estimated_rows=estimated_rows)
        return ReportExportDecision(mode="reject_need_async", estimated_rows=estimated_rows)

    def _build_xlsx_export(
        self,
        *,
        filename: str,
        decision: ReportExportDecision,
        build_direct: Callable[[], BinaryIO],
        build_stream: Callable[[], BinaryIO],
    ) -> ReportExport:
        data = build_stream() if decision.mode == "stream" else build_direct()
        return ReportExport(
            filename=filename,
            content_type=self.XLSX_CONTENT_TYPE,
            data=data,
            mode=decision.mode,
            estimated_rows=decision.estimated_rows,
        )

    def _parse_limited_report_date_range(self, start_date: str, end_date: str):
        sd, ed = date.fromisoformat(start_date), date.fromisoformat(end_date)
        ensure_report_date_range_within_limit(sd, ed, field="date_range")
        return sd, ed

    def utilization(
        self,
        resolution: SchedulePlanResolution,
        start_date: Any,
        end_date: Any,
    ) -> Dict[str, Any]:
        sd, ed = self._parse_limited_report_date_range(start_date, end_date)

        start_dt = datetime(sd.year, sd.month, sd.day, 0, 0, 0)
        end_dt_excl = datetime(ed.year, ed.month, ed.day, 0, 0, 0) + timedelta(days=1)
        start_s = start_dt.strftime("%Y-%m-%d %H:%M:%S")
        end_s = end_dt_excl.strftime("%Y-%m-%d %H:%M:%S")

        schedule_rows = self._list_plan_rows_between(resolution, start_s, end_s)

        degradation_collector = DegradationCollector()
        groups = group_utilization_rows(schedule_rows, start_dt, end_dt_excl, degradation_collector)
        calendars = resource_calendars_for_ids(self.conn, resource_ids_from_groups(groups), start_dt, end_dt_excl)
        machine_rows, operator_rows = utilization_from_groups(
            groups,
            start_dt=start_dt,
            end_dt_excl=end_dt_excl,
            calendars=calendars,
            degradation_collector=degradation_collector,
        )
        degradation = report_degradation_payload(degradation_collector)

        return {
            "version": resolution.version,
            "start_date": sd.isoformat(),
            "end_date": ed.isoformat(),
            "metric_version": METRIC_VERSION,
            "metric_source": "planned",
            "machines": machine_rows,
            "operators": operator_rows,
            **degradation,
        }

    def downtime_impact(
        self,
        resolution: SchedulePlanResolution,
        start_date: Any,
        end_date: Any,
    ) -> Dict[str, Any]:
        sd, ed = self._parse_limited_report_date_range(start_date, end_date)

        start_dt = datetime(sd.year, sd.month, sd.day, 0, 0, 0)
        end_dt_excl = datetime(ed.year, ed.month, ed.day, 0, 0, 0) + timedelta(days=1)
        start_s = start_dt.strftime("%Y-%m-%d %H:%M:%S")
        end_s = end_dt_excl.strftime("%Y-%m-%d %H:%M:%S")

        downtime_rows = self.machine_downtime_repo.list_active_overlaps_with_machine_names(start_s, end_s)
        sch_rows = self._list_plan_rows_between(resolution, start_s, end_s)
        degradation_collector = DegradationCollector()
        machines = compute_downtime_impact(
            downtime_rows=downtime_rows,
            schedule_rows=sch_rows,
            start_dt=start_dt,
            end_dt_excl=end_dt_excl,
            degradation_collector=degradation_collector,
        )
        degradation = report_degradation_payload(degradation_collector)

        return {
            "version": resolution.version,
            "start_date": sd.isoformat(),
            "end_date": ed.isoformat(),
            "machines": machines,
            **degradation,
        }
