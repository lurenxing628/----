from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, BinaryIO, Callable, ClassVar, Dict, List, Optional

from core.infrastructure.errors import AppError, ErrorCode, ValidationError
from core.models.schedule_plan_role import ROLE_ADOPTED
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
    plan_role_label,
)
from data.repositories import ScheduleHistoryRepository, ScheduleRepository

from . import calculations, queries
from .exporters import (
    export_downtime_impact_xlsx,
    export_execution_review_xlsx,
    export_overdue_xlsx,
    export_utilization_xlsx,
)


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
        self.plan_query_service = SchedulePlanQueryService(conn, logger=logger)
        self.delay_diagnosis_service = ScheduleDelayDiagnosisService(conn, logger=logger)
        self.execution_feedback_service = OperationExecutionFeedbackService(conn, logger=logger)
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

    def _resolve_plan(
        self,
        version: int,
        plan_role: Optional[str],
        scenario_id: Optional[str] = None,
    ) -> SchedulePlanResolution:
        try:
            return self.plan_query_service.resolve_plan_view(int(version), plan_role, scenario_id)
        except ValueError as exc:
            raise ValidationError(str(exc), field="scenario_id" if scenario_id else "plan_role") from exc

    def resolve_plan_context(
        self,
        version: int,
        plan_role: Optional[str] = None,
        scenario_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._resolve_plan(version, plan_role, scenario_id).to_dict()

    def _get_plan_time_span(self, version: int, plan_role: Optional[str], scenario_id: Optional[str] = None):
        try:
            return self.plan_query_service.get_plan_time_span_for_view(int(version), plan_role, scenario_id)
        except ValueError as exc:
            raise ValidationError(str(exc), field="scenario_id" if scenario_id else "plan_role") from exc

    def _list_plan_rows_between(
        self,
        *,
        version: int,
        plan_role: Optional[str],
        scenario_id: Optional[str] = None,
        start_time: str,
        end_time: str,
    ):
        try:
            return self.plan_query_service.list_plan_detail_rows_between_for_view(
                version=int(version),
                role=plan_role,
                scenario_id=scenario_id,
                start_time=start_time,
                end_time=end_time,
            )
        except ValueError as exc:
            raise ValidationError(str(exc), field="scenario_id" if scenario_id else "plan_role") from exc

    def _list_plan_rows_all(
        self,
        *,
        version: int,
        plan_role: Optional[str],
        scenario_id: Optional[str] = None,
    ):
        try:
            resolution = self._resolve_plan(version, plan_role, scenario_id)
            return self.plan_query_service.list_plan_detail_rows_all_for_resolution(
                version=int(version),
                source_table=resolution.source_table,
                candidate_id=resolution.candidate_id,
                scenario_id=resolution.scenario_id,
            )
        except ValueError as exc:
            raise ValidationError(str(exc), field="scenario_id" if scenario_id else "plan_role") from exc

    def _plan_meta(self, resolution: SchedulePlanResolution) -> Dict[str, Any]:
        return {
            "plan_role": resolution.selected_role,
            "plan_role_label": plan_role_label(resolution.selected_role),
            "requested_plan_role": resolution.requested_role,
            "requested_plan_role_label": plan_role_label(resolution.requested_role),
            "scenario_id": resolution.scenario_id,
            "scenario_name": resolution.scenario_name,
            "is_scenario_preview": bool(resolution.is_scenario_preview),
            "plan_resolution": resolution.to_dict(),
        }

    def _filename_plan_label(self, resolution: SchedulePlanResolution) -> str:
        label = resolution.scenario_display_name or plan_role_label(resolution.selected_role)
        for old, new in (("/", "-"), ("\\", "-"), (":", "-"), ("*", ""), ("?", ""), ('"', ""), ("<", ""), (">", ""), ("|", "-")):
            label = label.replace(old, new)
        return label.strip() or plan_role_label(resolution.selected_role)

    def _public_plan_label(self, resolution: SchedulePlanResolution) -> str:
        if resolution.is_scenario_preview:
            return resolution.scenario_display_name
        identity = resolution.plan_identity
        if identity is not None:
            return identity.user_label or identity.label or plan_role_label(resolution.selected_role)
        return plan_role_label(resolution.selected_role)

    def _scenario_export_summary_rows(
        self,
        resolution: SchedulePlanResolution,
        *,
        date_range: Optional[str] = None,
    ) -> List[List[Any]]:
        if not resolution.is_scenario_preview:
            return []
        rows: List[List[Any]] = [
            ["导出类型", "模拟方案预览"],
            ["提示", "这是模拟方案预览，正式计划还没有改变。"],
            ["模拟方案", resolution.scenario_display_name],
            ["预览依据版本", f"v{int(resolution.version)}"],
            ["预览依据方案", plan_role_label(resolution.selected_role)],
        ]
        if date_range:
            rows.append(["查询日期", date_range])
        rows.append(["导出时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
        return rows

    def version_date_range(
        self,
        version: int,
        plan_role: Optional[str] = None,
        scenario_id: Optional[str] = None,
    ) -> Dict[str, Any]:
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
            "plan_role": "adopted",
            "plan_role_label": plan_role_label("adopted"),
            "plan_resolution": None,
        }
        if v <= 0:
            return out

        resolution = self._resolve_plan(v, plan_role, scenario_id)
        out.update(self._plan_meta(resolution))

        span = self._get_plan_time_span(v, plan_role, scenario_id)
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
    # 计划和现场实际复盘
    # -------------------------
    def _execution_review_date_bounds(self, date_from: Any = None, date_to: Any = None) -> Dict[str, Any]:
        raw_from = str(date_from or "").strip()
        raw_to = str(date_to or "").strip()
        if not raw_from and not raw_to:
            return {
                "date_from": "",
                "date_to": "",
                "start_time": None,
                "end_time": None,
                "date_range_label": "全部日期",
            }
        if not raw_from or not raw_to:
            raise ValidationError("开始日期和结束日期要一起填写。", field="date_from")
        start_date = calculations.parse_date(raw_from, field="date_from")
        end_date = calculations.parse_date(raw_to, field="date_to")
        if end_date < start_date:
            raise ValidationError("结束日期不能早于开始日期。", field="date_to")
        start_dt = datetime(start_date.year, start_date.month, start_date.day, 0, 0, 0)
        end_dt_excl = datetime(end_date.year, end_date.month, end_date.day, 0, 0, 0) + timedelta(days=1)
        return {
            "date_from": start_date.isoformat(),
            "date_to": end_date.isoformat(),
            "start_time": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": end_dt_excl.strftime("%Y-%m-%d %H:%M:%S"),
            "date_range_label": f"{start_date.isoformat()} 至 {end_date.isoformat()}",
        }

    def execution_review(
        self,
        version: int,
        *,
        date_from: Any = None,
        date_to: Any = None,
        batch_id: Any = None,
    ) -> Dict[str, Any]:
        v = int(version or 0)
        resolution = self._resolve_plan(v, ROLE_ADOPTED, None)
        date_bounds = self._execution_review_date_bounds(date_from, date_to)
        if date_bounds["start_time"] and date_bounds["end_time"]:
            plan_rows = self._list_plan_rows_between(
                version=v,
                plan_role=ROLE_ADOPTED,
                scenario_id=None,
                start_time=str(date_bounds["start_time"]),
                end_time=str(date_bounds["end_time"]),
            )
        else:
            plan_rows = self._list_plan_rows_all(version=v, plan_role=ROLE_ADOPTED, scenario_id=None)

        batch_filter = str(batch_id or "").strip()
        if batch_filter:
            plan_rows = [row for row in plan_rows if str((row or {}).get("batch_id") or "").strip() == batch_filter]

        op_ids = [int((row or {}).get("op_id") or 0) for row in plan_rows if int((row or {}).get("op_id") or 0) > 0]
        states = self.execution_feedback_service.get_execution_state(op_ids)
        rows = [self._execution_review_row(dict(row or {}), states.get(int((row or {}).get("op_id") or 0))) for row in plan_rows]
        return {
            "version": v,
            "plan_label": plan_role_label(ROLE_ADOPTED),
            "plan_role": ROLE_ADOPTED,
            "plan_resolution": resolution.to_dict(),
            "date_from": date_bounds["date_from"],
            "date_to": date_bounds["date_to"],
            "date_range_label": date_bounds["date_range_label"],
            "batch_id": batch_filter,
            "batch_filter_label": batch_filter or "全部批次",
            "rows": rows,
            "count": len(rows),
        }

    def export_execution_review_xlsx(
        self,
        version: int,
        *,
        date_from: Any = None,
        date_to: Any = None,
        batch_id: Any = None,
    ) -> ReportExport:
        rep = self.execution_review(version, date_from=date_from, date_to=date_to, batch_id=batch_id)
        rows = list(rep.get("rows") or [])
        if not rows:
            raise ValidationError("暂无数据，不能导出。请调整版本、日期或批次后再试。", field="导出")
        filename = f"计划和现场实际-正式采用方案-v{int(rep['version'])}.xlsx"
        if rep.get("date_from") and rep.get("date_to"):
            filename = (
                f"计划和现场实际-正式采用方案-v{int(rep['version'])}-"
                f"{rep['date_from']} 至 {rep['date_to']}.xlsx"
            )
        return self._build_xlsx_export(
            report_name="计划和现场实际",
            filename=filename,
            estimated_rows=len(rows),
            build_direct=lambda: export_execution_review_xlsx(
                rows,
                summary_rows=self._execution_review_summary_rows(rep),
            ),
            build_stream=lambda: export_execution_review_xlsx(
                rows,
                summary_rows=self._execution_review_summary_rows(rep),
                write_only=True,
            ),
        )

    def _execution_review_summary_rows(self, rep: Dict[str, Any]) -> List[List[Any]]:
        return [
            ["报表", "计划和现场实际"],
            ["计划版本", f"v{int(rep.get('version') or 0)}"],
            ["方案", str(rep.get("plan_label") or "正式采用方案")],
            ["查询日期", str(rep.get("date_range_label") or "全部日期")],
            ["批次", str(rep.get("batch_filter_label") or "全部批次")],
            ["导出时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        ]

    def _execution_review_row(self, row: Dict[str, Any], state) -> Dict[str, Any]:
        has_feedback = bool(getattr(state, "last_event_id", None))
        has_exception = bool(getattr(state, "latest_exception_event_id", None))
        planned_start = self._display_time(row.get("start_time"))
        planned_end = self._display_time(row.get("end_time"))
        actual_start = getattr(state, "actual_start_time", None) if state is not None else None
        actual_end = getattr(state, "actual_end_time", None) if state is not None else None
        return {
            "batch_id_label": str(row.get("batch_id") or ""),
            "operation_label": self._operation_label(row),
            "planned_start_time_label": planned_start,
            "actual_start_time_label": self._actual_value_label(actual_start, has_feedback),
            "start_deviation_label": self._deviation_label(row.get("start_time"), actual_start, has_feedback),
            "planned_end_time_label": planned_end,
            "actual_end_time_label": self._actual_value_label(actual_end, has_feedback),
            "end_deviation_label": self._deviation_label(row.get("end_time"), actual_end, has_feedback),
            "pause_duration_label": self._pause_duration_label(getattr(state, "pause_duration_minutes", 0.0), has_feedback),
            "exception_reason_label": self._exception_value_label(
                getattr(state, "latest_exception_reason_label", None),
                has_feedback,
                has_exception,
            ),
            "exception_severity_label": self._exception_value_label(
                getattr(state, "latest_exception_severity_label", None),
                has_feedback,
                has_exception,
            ),
            "exception_impact_minutes_label": self._exception_value_label(
                getattr(state, "latest_exception_impact_minutes_label", None),
                has_feedback,
                has_exception,
            ),
            "exception_affected_machine_label": self._exception_value_label(
                getattr(state, "latest_exception_affected_machine_label", None),
                has_feedback,
                has_exception,
                empty_text="未填写影响设备",
            ),
            "exception_affected_operator_label": self._exception_value_label(
                getattr(state, "latest_exception_affected_operator_label", None),
                has_feedback,
                has_exception,
                empty_text="未填写影响人员",
            ),
            "exception_handling_status_label": self._exception_value_label(
                getattr(state, "latest_exception_handling_status_label", None),
                has_feedback,
                has_exception,
            ),
            "exception_suggest_reschedule_label": self._exception_value_label(
                getattr(state, "latest_exception_suggest_reschedule_label", None),
                has_feedback,
                has_exception,
            ),
            "planned_resource_label": self._planned_resource_label(row),
            "actual_resource_label": self._actual_resource_label(state, has_feedback),
            "feedback_status_label": getattr(state, "current_status_label", None) if has_feedback else "暂无现场反馈",
        }

    @staticmethod
    def _display_time(value: Any) -> str:
        text = str(value or "").strip()
        return text or "未填写计划时间"

    @staticmethod
    def _actual_value_label(value: Any, has_feedback: bool) -> str:
        text = str(value or "").strip()
        if text:
            return text
        return "暂无现场反馈" if not has_feedback else "未填写实际时间"

    @staticmethod
    def _operation_label(row: Dict[str, Any]) -> str:
        op_name = str(row.get("op_type_name") or "").strip()
        op_code = str(row.get("op_code") or "").strip()
        if op_name and op_code:
            return f"{op_code} / {op_name}"
        return op_name or op_code or "未命名工序"

    @staticmethod
    def _planned_resource_label(row: Dict[str, Any]) -> str:
        machine = str(row.get("machine_name") or row.get("machine_id") or "").strip()
        operator = str(row.get("operator_name") or row.get("operator_id") or "").strip()
        if machine and operator:
            return f"{machine} / {operator}"
        if machine:
            return f"{machine} / 未安排人员"
        if operator:
            return f"未安排设备 / {operator}"
        return "未安排计划资源"

    @staticmethod
    def _actual_resource_label(state, has_feedback: bool) -> str:
        if not has_feedback:
            return "暂无现场反馈"
        machine = str(getattr(state, "actual_machine_label", None) or "").strip()
        operator = str(getattr(state, "actual_operator_label", None) or "").strip()
        if machine and operator:
            return f"{machine} / {operator}"
        if machine:
            return f"{machine} / 未填写实际人员"
        if operator:
            return f"未填写实际设备 / {operator}"
        return "未填写实际资源"

    @staticmethod
    def _pause_duration_label(value: Any, has_feedback: bool) -> str:
        if not has_feedback:
            return "暂无现场反馈"
        try:
            minutes = float(value or 0.0)
        except (TypeError, ValueError):
            minutes = 0.0
        if minutes.is_integer():
            return f"{int(minutes)} 分钟"
        return f"{round(minutes, 2)} 分钟"

    @staticmethod
    def _exception_value_label(value: Any, has_feedback: bool, has_exception: bool, *, empty_text: str = "暂无异常") -> str:
        if not has_feedback:
            return "暂无现场反馈"
        if not has_exception:
            return "暂无异常"
        text = str(value or "").strip()
        return text or empty_text

    def _deviation_label(self, planned: Any, actual: Any, has_feedback: bool) -> str:
        if not has_feedback or not str(actual or "").strip():
            return "暂无现场反馈"
        planned_dt = calculations.parse_dt(planned)
        actual_dt = calculations.parse_dt(actual)
        if planned_dt is None or actual_dt is None:
            return "时间格式无法比较"
        minutes = round((actual_dt - planned_dt).total_seconds() / 60.0)
        if minutes == 0:
            return "准点"
        if minutes > 0:
            return f"晚了 {int(minutes)} 分钟"
        return f"提前 {abs(int(minutes))} 分钟"

    # -------------------------
    # 1) 超期清单
    # -------------------------
    def _fetch_overdue_base_rows_for_plan(
        self,
        version: int,
        plan_role: Optional[str],
        scenario_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        resolution = self._resolve_plan(version, plan_role, scenario_id)
        return self.plan_query_service.list_plan_overdue_base_rows_for_resolution(
            version=int(version),
            source_table=resolution.source_table,
            candidate_id=resolution.candidate_id,
            scenario_id=resolution.scenario_id,
        )

    def overdue_batches(
        self,
        version: int,
        plan_role: Optional[str] = None,
        scenario_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        v = int(version or 0)
        resolution = self._resolve_plan(v, plan_role, scenario_id)
        rows = self._fetch_overdue_base_rows_for_plan(v, plan_role, scenario_id)
        scheduled, unscheduled, as_of = calculations.compute_overdue_buckets(rows)
        items = list(scheduled) + list(unscheduled)
        return {
            "version": v,
            **self._plan_meta(resolution),
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

    def overdue_delay_diagnosis_context(
        self,
        version: int,
        plan_role: Optional[str] = None,
        scenario_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        resolution = self._resolve_plan(int(version), plan_role, scenario_id)
        report = self.delay_diagnosis_service.diagnose_resolved_plan_overdue(
            version=int(version),
            resolution=resolution,
        )
        return build_delay_diagnosis_page_context(report)

    def _overdue_diagnosis_export_rows(
        self,
        *,
        version: int,
        resolution: SchedulePlanResolution,
    ) -> List[Dict[str, Any]]:
        diagnosis_report = self.delay_diagnosis_service.diagnose_resolved_plan_overdue(
            version=int(version),
            resolution=resolution,
        )
        return build_delay_diagnosis_export_rows(
            diagnosis_report,
            filters={"version": int(version), "plan_label": self._public_plan_label(resolution)},
        )

    def export_overdue_xlsx(
        self,
        version: int,
        plan_role: Optional[str] = None,
        scenario_id: Optional[str] = None,
    ) -> ReportExport:
        rep = self.overdue_batches(version, plan_role=plan_role, scenario_id=scenario_id)
        items = list(rep.get("items") or [])
        if not items:
            raise ValidationError("当前版本没有可导出的超期结果，请换一个排产版本后再试。", field="导出")
        resolution = self._resolve_plan(int(rep["version"]), plan_role, scenario_id)
        def build_overdue_export(*, write_only: bool = False):
            diagnosis_rows = self._overdue_diagnosis_export_rows(version=int(rep["version"]), resolution=resolution)
            return export_overdue_xlsx(
                items,
                diagnosis_rows=diagnosis_rows,
                summary_rows=self._scenario_export_summary_rows(resolution),
                write_only=write_only,
            )

        return self._build_xlsx_export(
            report_name="超期清单",
            filename=f"超期清单_{self._filename_plan_label(resolution)}_v{int(rep['version'])}.xlsx",
            estimated_rows=len(items),
            build_direct=lambda: build_overdue_export(),
            build_stream=lambda: build_overdue_export(write_only=True),
        )

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
    ) -> Dict[str, Any]:
        v = int(version or 0)
        resolution = self._resolve_plan(v, plan_role, scenario_id)
        sd = calculations.parse_date(start_date, field="start_date")
        ed = calculations.parse_date(end_date, field="end_date")
        if ed < sd:
            raise ValidationError("结束日期不能早于开始日期", field="end_date")

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
        )

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
            **self._plan_meta(resolution),
            "start_date": sd.isoformat(),
            "end_date": ed.isoformat(),
            "capacity_hours_per_resource": round(float(cap_hours), 2),
            "machines": machine_rows,
            "operators": operator_rows,
        }

    def export_utilization_xlsx(
        self,
        version: int,
        start_date: Any,
        end_date: Any,
        plan_role: Optional[str] = None,
        scenario_id: Optional[str] = None,
    ) -> ReportExport:
        rep = self.utilization(version, start_date, end_date, plan_role=plan_role, scenario_id=scenario_id)
        machines = list(rep.get("machines") or [])
        operators = list(rep.get("operators") or [])
        if not machines and not operators:
            raise ValidationError("暂无数据，不能导出。请调整版本或日期范围后再试。", field="导出")
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
                ),
            ),
            build_stream=lambda: export_utilization_xlsx(
                machines,
                operators,
                summary_rows=self._scenario_export_summary_rows(
                    resolution,
                    date_range=f"{rep['start_date']} 至 {rep['end_date']}",
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
    ) -> Dict[str, Any]:
        v = int(version or 0)
        resolution = self._resolve_plan(v, plan_role, scenario_id)
        sd = calculations.parse_date(start_date, field="start_date")
        ed = calculations.parse_date(end_date, field="end_date")
        if ed < sd:
            raise ValidationError("结束日期不能早于开始日期", field="end_date")

        start_dt = datetime(sd.year, sd.month, sd.day, 0, 0, 0)
        end_dt_excl = datetime(ed.year, ed.month, ed.day, 0, 0, 0) + timedelta(days=1)
        start_s = start_dt.strftime("%Y-%m-%d %H:%M:%S")
        end_s = end_dt_excl.strftime("%Y-%m-%d %H:%M:%S")

        downtime_rows = queries.fetch_downtime_rows(self.conn, start_s, end_s)
        sch_rows = self._list_plan_rows_between(
            version=v,
            plan_role=plan_role,
            scenario_id=scenario_id,
            start_time=start_s,
            end_time=end_s,
        )

        machines = calculations.compute_downtime_impact(
            downtime_rows=downtime_rows,
            schedule_rows=sch_rows,
            start_dt=start_dt,
            end_dt_excl=end_dt_excl,
        )

        return {
            "version": v,
            **self._plan_meta(resolution),
            "start_date": sd.isoformat(),
            "end_date": ed.isoformat(),
            "machines": machines,
        }

    def export_downtime_impact_xlsx(
        self,
        version: int,
        start_date: Any,
        end_date: Any,
        plan_role: Optional[str] = None,
        scenario_id: Optional[str] = None,
    ) -> ReportExport:
        rep = self.downtime_impact(version, start_date, end_date, plan_role=plan_role, scenario_id=scenario_id)
        machines = list(rep.get("machines") or [])
        if not machines:
            raise ValidationError("暂无数据，不能导出。请调整版本或日期范围后再试。", field="导出")
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
                ),
            ),
            build_stream=lambda: export_downtime_impact_xlsx(
                machines,
                summary_rows=self._scenario_export_summary_rows(
                    resolution,
                    date_range=f"{rep['start_date']} 至 {rep['end_date']}",
                ),
                write_only=True,
            ),
        )
