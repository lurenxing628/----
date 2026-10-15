"""Current workbench report calculations consume an already selected plan."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, BinaryIO, Callable, ClassVar, Dict, Optional

from core.errors import AppError, ErrorCode, ValidationError
from core.models.report_export import ReportExport, ReportExportDecision
from core.services.capacity.resource_utilization_metrics import METRIC_VERSION
from core.services.common.degradation import DegradationCollector
from core.services.common.plan_query import SchedulePlanQueryService, SchedulePlanResolution
from data.repositories import MachineDowntimeRepository

from . import calculations
from .date_range_limits import ensure_report_date_range_within_limit
from .report_context_filters import filter_downtime_rows_for_report_context
from .report_degradation import report_degradation_payload
from .utilization_calendars import resource_calendars
from .values.number_parsing import parse_report_nonnegative_int


class ReportEngine:
    """Calculate current reports; workbench owns plan selection and exports."""

    XLSX_CONTENT_TYPE: ClassVar[str] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    EXPORT_DIRECT_MAX_ROWS: ClassVar[int] = 2000
    EXPORT_STREAM_MAX_ROWS: ClassVar[int] = 20000

    def __init__(self, conn, logger=None):
        self.conn = conn
        self.logger = logger
        self.machine_downtime_repo = MachineDowntimeRepository(conn, logger=logger)
        self.plan_query_service = SchedulePlanQueryService(conn, logger=logger)

    def _fetch_overdue_base_rows_for_plan(self, resolution: SchedulePlanResolution):
        return self.plan_query_service.list_plan_overdue_base_rows_for_resolution(
            version=resolution.version, source_table=resolution.source_table,
            candidate_id=resolution.candidate_id, scenario_id=resolution.scenario_id,
        )

    def _list_plan_rows_between(self, resolution, start_time, end_time):
        return self.plan_query_service.list_plan_detail_rows_between_for_resolution(
            version=resolution.version, source_table=resolution.source_table,
            candidate_id=resolution.candidate_id, scenario_id=resolution.scenario_id,
            effective_plan_role=resolution.selected_role, start_time=start_time, end_time=end_time,
        )


    def _export_nonnegative_int(self, value: Any, *, field: str, default: Optional[int] = None) -> int:
        return parse_report_nonnegative_int(
            value,
            field=field,
            label=field,
            source_label="导出配置",
            blank_default=int(default or 0),
        )

    def _build_export_decision(self, estimated_rows: int) -> ReportExportDecision:
        rows = self._export_nonnegative_int(estimated_rows, field="导出行数")
        direct_max = self._export_nonnegative_int(
            getattr(self, "EXPORT_DIRECT_MAX_ROWS", 0),
            field="直接导出行数上限",
        )
        stream_max = self._export_nonnegative_int(
            getattr(self, "EXPORT_STREAM_MAX_ROWS", direct_max),
            field="流式导出行数上限",
            default=direct_max,
        )
        if stream_max < direct_max:
            raise ValidationError("流式导出行数上限不能小于直接导出行数上限。", field="流式导出行数上限")

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

    def _parse_limited_report_date_range(
        self,
        start_date: Any,
        end_date: Any,
        *,
        start_field: str = "start_date",
        end_field: str = "end_date",
        limit_field: str = "date_range",
    ):
        sd = calculations.parse_date(start_date, field=start_field)
        ed = calculations.parse_date(end_date, field=end_field)
        if ed < sd:
            raise ValidationError("结束日期不能早于开始日期", field=end_field)
        ensure_report_date_range_within_limit(sd, ed, field=limit_field)
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

        calendars = resource_calendars(self.conn, schedule_rows, start_dt, end_dt_excl)
        degradation_collector = DegradationCollector()
        machine_rows, operator_rows = calculations.compute_utilization(
            schedule_rows=schedule_rows,
            start_dt=start_dt,
            end_dt_excl=end_dt_excl,
            calendars=calendars,
            degradation_collector=degradation_collector,
        )
        degradation = report_degradation_payload(degradation_collector)
        capacities = {row["capacity_hours"] for row in machine_rows + operator_rows}

        return {
            "version": resolution.version,
            "start_date": sd.isoformat(),
            "end_date": ed.isoformat(),
            "capacity_hours_per_resource": next(iter(capacities)) if len(capacities) == 1 else None,
            "metric_version": METRIC_VERSION, "metric_source": "planned",
            "window_start": start_dt.isoformat(), "window_end": end_dt_excl.isoformat(),
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
        downtime_rows = filter_downtime_rows_for_report_context(
            downtime_rows,
            sch_rows,
            degradation_collector=degradation_collector,
        )

        machines = calculations.compute_downtime_impact(
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
