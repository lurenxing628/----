from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, BinaryIO, Callable, ClassVar, Dict, Iterable, List, Optional

from core.infrastructure.errors import AppError, ErrorCode, ValidationError
from core.services.common.degradation import DegradationCollector
from core.services.report.delay_diagnosis_presentation import (
    build_delay_diagnosis_export_rows,
    build_delay_diagnosis_page_context,
)
from core.services.scheduler.calendar_service import CalendarService
from core.services.scheduler.operation_execution_feedback_service import OperationExecutionFeedbackService
from core.services.scheduler.schedule_delay_diagnosis_service import ScheduleDelayDiagnosisService
from core.services.scheduler.schedule_plan_query_service import (
    SchedulePlanQueryService,
    SchedulePlanResolution,
)
from data.repositories import MachineDowntimeRepository, ScheduleHistoryRepository, ScheduleRepository

from . import calculations
from .date_range_limits import ensure_report_date_range_within_limit
from .execution_review import ExecutionReviewMixin
from .exporters import (
    export_downtime_impact_xlsx,
    export_overdue_xlsx,
    export_utilization_xlsx,
)
from .report_context_filters import filter_downtime_rows_for_report_context, normalize_report_resource_filter
from .report_degradation import report_degradation_payload
from .report_number_parsing import parse_report_nonnegative_int
from .report_plan_helpers import ReportPlanMixin


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


class ReportEngine(ReportPlanMixin, ExecutionReviewMixin):
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
        self.machine_downtime_repo = MachineDowntimeRepository(conn, logger=logger)
        self.plan_query_service = SchedulePlanQueryService(conn, logger=logger)
        self.delay_diagnosis_service = ScheduleDelayDiagnosisService(conn, logger=logger)
        self.execution_feedback_service = OperationExecutionFeedbackService(conn, logger=logger)
        self.calendar = CalendarService(conn, logger=logger)

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

    def _raise_empty_export(self, rep: Dict[str, Any]) -> None:
        bad_time_count = int(rep.get("report_bad_time_skipped_count") or 0)
        if bad_time_count > 0:
            degradation_message = str(rep.get("report_degradation_message") or "").strip()
            prefix = degradation_message or f"已过滤 {bad_time_count} 条开始或结束时间写法不对的记录。"
            raise ValidationError(
                f"{prefix} 当前没有可导出的有效数据，不能导出。请先修正这些时间后再试。",
                field="导出",
            )
        raise ValidationError("暂无数据，不能导出。请调整版本或日期范围后再试。", field="导出")

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
    # 1) 超期清单
    # -------------------------
    def _fetch_overdue_base_rows_for_plan(
        self,
        version: int,
        plan_role: Optional[str],
        scenario_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        batch_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        resolution = self._resolve_plan(version, plan_role, scenario_id)
        resource_type, resource_id = normalize_report_resource_filter(resource_type, resource_id)
        return self.plan_query_service.list_plan_overdue_base_rows_for_resolution(
            version=int(version),
            source_table=resolution.source_table,
            candidate_id=resolution.candidate_id,
            scenario_id=resolution.scenario_id,
            resource_type=resource_type,
            resource_id=resource_id,
            batch_id=batch_id,
        )

    def overdue_batches(
        self,
        version: int,
        plan_role: Optional[str] = None,
        scenario_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        batch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        v = int(version or 0)
        resource_type, resource_id = normalize_report_resource_filter(resource_type, resource_id)
        resolution = self._resolve_plan(v, plan_role, scenario_id)
        rows = self._fetch_overdue_base_rows_for_plan(
            v,
            plan_role,
            scenario_id,
            resource_type=resource_type,
            resource_id=resource_id,
            batch_id=batch_id,
        )
        scheduled, unscheduled, invalid_time, as_of = calculations.compute_overdue_bucket_groups(rows)
        invalid_due_items = [item for item in invalid_time if item.get("bucket") == "due_date_invalid"]
        schedule_time_invalid_items = [item for item in invalid_time if item.get("bucket") != "due_date_invalid"]
        items = list(scheduled) + list(invalid_time) + list(unscheduled)
        # 诚实计数覆盖所有批次：混合批次（有有效完成时间但夹带坏时间行）的坏行也要计入，
        # 不能只数“排程时间异常”桶，否则会重新制造“部分坏数据被静默吞掉”的问题。
        invalid_time_count, invalid_time_samples = calculations.collect_bad_time_rows(rows)
        invalid_due_count = len(invalid_due_items)
        degradation_messages = []
        if invalid_time_count > 0:
            degradation_messages.append(
                f"有 {invalid_time_count} 条排程记录的计划完成时间写法不对，已从相关批次的逾期与跨度计算中剔除；"
                f"完全没有有效完成时间的批次按“排程时间异常”单列。"
            )
        if invalid_due_count > 0:
            degradation_messages.append(f"有 {invalid_due_count} 个批次的交期写法不对，已按“交期写法异常”单列。")
        degradation_counters = {}
        if invalid_time_count > 0:
            degradation_counters["bad_time_row_skipped"] = invalid_time_count
        if invalid_due_count > 0:
            degradation_counters["bad_due_date"] = invalid_due_count
        degradation = {
            "report_degraded": bool(degradation_messages),
            "report_degradation_events": [],
            "report_degradation_counters": degradation_counters,
            "report_degradation_samples": invalid_time_samples[:3],
            "report_degradation_message": " ".join(degradation_messages),
            "report_bad_time_skipped_count": invalid_time_count,
            "report_degradation_count_label": "计划完成时间写法不对的排程记录数",
            "report_degradation_sample_label": "时间异常记录样例",
            "report_invalid_due_count": invalid_due_count,
        }
        return {
            "version": v,
            **self._plan_meta(resolution),
            "count": len(items),
            "scheduled_count": len(scheduled),
            "unscheduled_count": len(unscheduled),
            "invalid_time_count": len(schedule_time_invalid_items),
            "invalid_due_count": invalid_due_count,
            "as_of_time": as_of,
            **degradation,
            # 兼容旧页面：items 仍保留（已排程在前、未排程在后）
            "items": items,
            # 新增分桶输出
            "scheduled_items": list(scheduled),
            "invalid_time_items": list(invalid_time),
            "unscheduled_items": list(unscheduled),
        }

    def overdue_delay_diagnosis_context(
        self,
        version: int,
        plan_role: Optional[str] = None,
        scenario_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        batch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        resource_type, resource_id = normalize_report_resource_filter(resource_type, resource_id)
        resolution = self._resolve_plan(int(version), plan_role, scenario_id)
        report = self.delay_diagnosis_service.diagnose_resolved_plan_overdue(
            version=int(version),
            resolution=resolution,
            resource_type=resource_type,
            resource_id=resource_id,
            batch_id=batch_id,
        )
        return build_delay_diagnosis_page_context(report)

    def _overdue_diagnosis_export_rows(
        self,
        *,
        version: int,
        resolution: SchedulePlanResolution,
        batch_ids: Optional[Iterable[Any]] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        batch_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        resource_type, resource_id = normalize_report_resource_filter(resource_type, resource_id)
        diagnosis_report = self.delay_diagnosis_service.diagnose_resolved_plan_overdue(
            version=int(version),
            resolution=resolution,
            resource_type=resource_type,
            resource_id=resource_id,
            batch_id=batch_id,
        )
        return build_delay_diagnosis_export_rows(
            diagnosis_report,
            filters={"version": int(version), "plan_label": self._public_plan_label(resolution)},
            allowed_batch_ids=batch_ids,
        )

    def export_overdue_xlsx(
        self,
        version: int,
        plan_role: Optional[str] = None,
        scenario_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        batch_id: Optional[str] = None,
    ) -> ReportExport:
        overdue_kwargs: Dict[str, Any] = {"plan_role": plan_role, "scenario_id": scenario_id}
        if resource_type or resource_id:
            overdue_kwargs.update({"resource_type": resource_type, "resource_id": resource_id})
        if batch_id:
            overdue_kwargs["batch_id"] = batch_id
        rep = self.overdue_batches(version, **overdue_kwargs)
        items = list(rep.get("items") or [])
        if not items:
            raise ValidationError("当前版本没有可导出的超期结果，请换一个排产版本后再试。", field="导出")
        resolution = self._resolve_plan(int(rep["version"]), plan_role, scenario_id)
        exported_batch_ids = [item.get("batch_id") for item in items]
        def build_overdue_export(*, write_only: bool = False):
            diagnosis_rows = self._overdue_diagnosis_export_rows(
                version=int(rep["version"]),
                resolution=resolution,
                batch_ids=exported_batch_ids,
                resource_type=resource_type,
                resource_id=resource_id,
                batch_id=batch_id,
            )
            return export_overdue_xlsx(
                items,
                diagnosis_rows=diagnosis_rows,
                summary_rows=self._scenario_export_summary_rows(resolution, degradation=rep),
                write_only=write_only,
            )

        return self._build_xlsx_export(
            report_name="超期清单",
            filename=f"超期清单_{self._filename_plan_label(resolution)}_v{int(rep['version'])}.xlsx",
            estimated_rows=len(items),
            build_direct=lambda: build_overdue_export(),
            build_stream=lambda: build_overdue_export(write_only=True),
        )

    def _parse_limited_report_date_range(
        self,
        start_date: Any,
        end_date: Any,
        *,
        start_field: str = "start_date",
        end_field: str = "end_date",
        limit_field: str = "date_range",
        enforce_date_range_limit: bool = True,
    ):
        sd = calculations.parse_date(start_date, field=start_field)
        ed = calculations.parse_date(end_date, field=end_field)
        if ed < sd:
            raise ValidationError("结束日期不能早于开始日期", field=end_field)
        if enforce_date_range_limit:
            ensure_report_date_range_within_limit(sd, ed, field=limit_field)
        return sd, ed

    # -------------------------
    # 2) 资源负荷/利用率
    # -------------------------
    def utilization(
        self,
        version: int,
        start_date: Any,
        end_date: Any,
        plan_role: Optional[str] = None,
        scenario_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        batch_id: Optional[str] = None,
        enforce_date_range_limit: bool = True,
    ) -> Dict[str, Any]:
        v = int(version or 0)
        resource_type, resource_id = normalize_report_resource_filter(resource_type, resource_id)
        resolution = self._resolve_plan(v, plan_role, scenario_id)
        sd, ed = self._parse_limited_report_date_range(
            start_date,
            end_date,
            enforce_date_range_limit=enforce_date_range_limit,
        )

        start_dt = datetime(sd.year, sd.month, sd.day, 0, 0, 0)
        end_dt_excl = datetime(ed.year, ed.month, ed.day, 0, 0, 0) + timedelta(days=1)
        start_s = start_dt.strftime("%Y-%m-%d %H:%M:%S")
        end_s = end_dt_excl.strftime("%Y-%m-%d %H:%M:%S")

        schedule_rows = self._list_plan_rows_between(
            version=v,
            plan_role=plan_role,
            scenario_id=scenario_id,
            start_time=start_s,
            end_time=end_s,
            resource_type=resource_type,
            resource_id=resource_id,
            batch_id=batch_id,
        )

        cap_hours = calculations.capacity_hours(self.calendar, sd, ed)
        if cap_hours <= 0:
            cap_hours = 0.0

        degradation_collector = DegradationCollector()
        machine_rows, operator_rows = calculations.compute_utilization(
            schedule_rows=schedule_rows,
            start_dt=start_dt,
            end_dt_excl=end_dt_excl,
            cap_hours=float(cap_hours),
            degradation_collector=degradation_collector,
        )
        degradation = report_degradation_payload(degradation_collector)

        return {
            "version": v,
            **self._plan_meta(resolution),
            "start_date": sd.isoformat(),
            "end_date": ed.isoformat(),
            "capacity_hours_per_resource": round(float(cap_hours), 2),
            "machines": machine_rows,
            "operators": operator_rows,
            **degradation,
        }

    def export_utilization_xlsx(
        self,
        version: int,
        start_date: Any,
        end_date: Any,
        plan_role: Optional[str] = None,
        scenario_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        batch_id: Optional[str] = None,
        enforce_date_range_limit: bool = True,
    ) -> ReportExport:
        utilization_kwargs: Dict[str, Any] = {"plan_role": plan_role, "scenario_id": scenario_id}
        if resource_type or resource_id:
            utilization_kwargs.update({"resource_type": resource_type, "resource_id": resource_id})
        if batch_id:
            utilization_kwargs["batch_id"] = batch_id
        if enforce_date_range_limit:
            self._parse_limited_report_date_range(start_date, end_date)
        else:
            utilization_kwargs["enforce_date_range_limit"] = False
        rep = self.utilization(version, start_date, end_date, **utilization_kwargs)
        machines = list(rep.get("machines") or [])
        operators = list(rep.get("operators") or [])
        if not machines and not operators:
            self._raise_empty_export(rep)
        resolution = self._resolve_plan(int(rep["version"]), plan_role, scenario_id)
        return self._build_xlsx_export(
            report_name="资源负荷与利用率",
            filename=f"资源负荷与利用率_{self._filename_plan_label(resolution)}_v{int(rep['version'])}_{rep['start_date']}至{rep['end_date']}.xlsx",
            estimated_rows=len(machines) + len(operators),
            build_direct=lambda: export_utilization_xlsx(
                machines,
                operators,
                summary_rows=self._scenario_export_summary_rows(
                    resolution,
                    date_range=f"{rep['start_date']} 至 {rep['end_date']}",
                    degradation=rep,
                ),
            ),
            build_stream=lambda: export_utilization_xlsx(
                machines,
                operators,
                summary_rows=self._scenario_export_summary_rows(
                    resolution,
                    date_range=f"{rep['start_date']} 至 {rep['end_date']}",
                    degradation=rep,
                ),
                write_only=True,
            ),
        )

    # -------------------------
    # 3) 停机影响统计
    # -------------------------
    def downtime_impact(
        self,
        version: int,
        start_date: Any,
        end_date: Any,
        plan_role: Optional[str] = None,
        scenario_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        batch_id: Optional[str] = None,
        enforce_date_range_limit: bool = True,
    ) -> Dict[str, Any]:
        v = int(version or 0)
        resource_type, resource_id = normalize_report_resource_filter(resource_type, resource_id)
        resolution = self._resolve_plan(v, plan_role, scenario_id)
        sd, ed = self._parse_limited_report_date_range(
            start_date,
            end_date,
            enforce_date_range_limit=enforce_date_range_limit,
        )

        start_dt = datetime(sd.year, sd.month, sd.day, 0, 0, 0)
        end_dt_excl = datetime(ed.year, ed.month, ed.day, 0, 0, 0) + timedelta(days=1)
        start_s = start_dt.strftime("%Y-%m-%d %H:%M:%S")
        end_s = end_dt_excl.strftime("%Y-%m-%d %H:%M:%S")

        downtime_rows = self.machine_downtime_repo.list_active_overlaps_with_machine_names(start_s, end_s)
        sch_rows = self._list_plan_rows_between(
            version=v,
            plan_role=plan_role,
            scenario_id=scenario_id,
            start_time=start_s,
            end_time=end_s,
            resource_type=resource_type,
            resource_id=resource_id,
            batch_id=batch_id,
        )
        degradation_collector = DegradationCollector()
        downtime_rows = filter_downtime_rows_for_report_context(
            downtime_rows,
            sch_rows,
            resource_type=resource_type,
            resource_id=resource_id,
            batch_id=batch_id,
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
            "version": v,
            **self._plan_meta(resolution),
            "start_date": sd.isoformat(),
            "end_date": ed.isoformat(),
            "machines": machines,
            **degradation,
        }

    def export_downtime_impact_xlsx(
        self,
        version: int,
        start_date: Any,
        end_date: Any,
        plan_role: Optional[str] = None,
        scenario_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        batch_id: Optional[str] = None,
        enforce_date_range_limit: bool = True,
    ) -> ReportExport:
        downtime_kwargs: Dict[str, Any] = {"plan_role": plan_role, "scenario_id": scenario_id}
        if resource_type or resource_id:
            downtime_kwargs.update({"resource_type": resource_type, "resource_id": resource_id})
        if batch_id:
            downtime_kwargs["batch_id"] = batch_id
        if enforce_date_range_limit:
            self._parse_limited_report_date_range(start_date, end_date)
        else:
            downtime_kwargs["enforce_date_range_limit"] = False
        rep = self.downtime_impact(version, start_date, end_date, **downtime_kwargs)
        machines = list(rep.get("machines") or [])
        if not machines:
            self._raise_empty_export(rep)
        resolution = self._resolve_plan(int(rep["version"]), plan_role, scenario_id)
        return self._build_xlsx_export(
            report_name="停机影响统计",
            filename=f"停机影响统计_{self._filename_plan_label(resolution)}_v{int(rep['version'])}_{rep['start_date']}至{rep['end_date']}.xlsx",
            estimated_rows=len(machines),
            build_direct=lambda: export_downtime_impact_xlsx(
                machines,
                summary_rows=self._scenario_export_summary_rows(
                    resolution,
                    date_range=f"{rep['start_date']} 至 {rep['end_date']}",
                    degradation=rep,
                ),
            ),
            build_stream=lambda: export_downtime_impact_xlsx(
                machines,
                summary_rows=self._scenario_export_summary_rows(
                    resolution,
                    date_range=f"{rep['start_date']} 至 {rep['end_date']}",
                    degradation=rep,
                ),
                write_only=True,
            ),
        )
