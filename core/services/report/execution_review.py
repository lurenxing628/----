from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Protocol, cast

from core.infrastructure.errors import ValidationError
from core.models.resource_identity import ResourceIdentity, build_resource_identity
from core.models.schedule_plan_role import ROLE_ADOPTED
from core.services.scheduler.schedule_plan_query_service import plan_role_label

from . import calculations
from .exporters import export_execution_review_xlsx


class _ExecutionReviewHost(Protocol):
    execution_feedback_service: Any

    def _list_plan_rows_between(
        self,
        *,
        version: int,
        plan_role: Optional[str],
        scenario_id: Optional[str],
        start_time: str,
        end_time: str,
    ) -> Any:
        ...

    def _list_plan_rows_all(self, *, version: int, plan_role: Optional[str], scenario_id: Optional[str]) -> Any:
        ...

    def _resolve_plan(self, version: int, plan_role: Optional[str], scenario_id: Optional[str] = None) -> Any:
        ...

    def _build_xlsx_export(
        self,
        *,
        report_name: str,
        filename: str,
        estimated_rows: int,
        build_direct: Callable[[], Any],
        build_stream: Callable[[], Any],
    ) -> Any:
        ...


class ExecutionReviewMixin:
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

    def _execution_review_plan_rows(self, *, version: int, date_bounds: Dict[str, Any], batch_filter: str):
        host = cast(_ExecutionReviewHost, self)
        if date_bounds["start_time"] and date_bounds["end_time"]:
            plan_rows = host._list_plan_rows_between(
                version=version,
                plan_role=ROLE_ADOPTED,
                scenario_id=None,
                start_time=str(date_bounds["start_time"]),
                end_time=str(date_bounds["end_time"]),
            )
        else:
            plan_rows = host._list_plan_rows_all(version=version, plan_role=ROLE_ADOPTED, scenario_id=None)
        if not batch_filter:
            return plan_rows
        return [row for row in plan_rows if str((row or {}).get("batch_id") or "").strip() == batch_filter]

    def _execution_review_rows(self, plan_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        host = cast(_ExecutionReviewHost, self)
        op_ids = [int((row or {}).get("op_id") or 0) for row in plan_rows if int((row or {}).get("op_id") or 0) > 0]
        states = host.execution_feedback_service.get_execution_state(op_ids)
        return [
            self._execution_review_row(dict(row or {}), states.get(int((row or {}).get("op_id") or 0)))
            for row in plan_rows
        ]

    def execution_review(
        self,
        version: int,
        *,
        date_from: Any = None,
        date_to: Any = None,
        batch_id: Any = None,
    ) -> Dict[str, Any]:
        host = cast(_ExecutionReviewHost, self)
        v = int(version or 0)
        resolution = host._resolve_plan(v, ROLE_ADOPTED, None)
        date_bounds = self._execution_review_date_bounds(date_from, date_to)
        batch_filter = str(batch_id or "").strip()
        plan_rows = self._execution_review_plan_rows(
            version=v,
            date_bounds=date_bounds,
            batch_filter=batch_filter,
        )
        rows = self._execution_review_rows(list(plan_rows or []))
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
    ) -> Any:
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
        host = cast(_ExecutionReviewHost, self)
        return host._build_xlsx_export(
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
        planned_resource = self._planned_resource_identity(row)
        actual_resource = self._actual_resource_identity(state, has_feedback)
        affected_machine = self._state_resource_identity(
            state,
            "latest_exception_affected_machine",
            empty_label="未填写影响设备",
        )
        affected_operator = self._state_resource_identity(
            state,
            "latest_exception_affected_operator",
            empty_label="未填写影响人员",
        )
        affected_machine_label = self._exception_value_label(
            affected_machine.display_label,
            has_feedback,
            has_exception,
            empty_text="未填写影响设备",
        )
        affected_operator_label = self._exception_value_label(
            affected_operator.display_label,
            has_feedback,
            has_exception,
            empty_text="未填写影响人员",
        )
        affected_machine_identity_label = (
            self._exception_value_label(
                affected_machine.identity_label,
                has_feedback,
                has_exception,
                empty_text="未填写影响设备",
            )
            if has_feedback and has_exception
            else affected_machine_label
        )
        affected_operator_identity_label = (
            self._exception_value_label(
                affected_operator.identity_label,
                has_feedback,
                has_exception,
                empty_text="未填写影响人员",
            )
            if has_feedback and has_exception
            else affected_operator_label
        )
        affected_machine_export_label = (
            self._resource_export_label(affected_machine, affected_machine_label)
            if has_feedback and has_exception
            else affected_machine_label
        )
        affected_operator_export_label = (
            self._resource_export_label(affected_operator, affected_operator_label)
            if has_feedback and has_exception
            else affected_operator_label
        )
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
            "exception_affected_machine_label": affected_machine_label,
            "exception_affected_machine_identity_label": affected_machine_identity_label,
            "exception_affected_machine_export_label": affected_machine_export_label,
            "exception_affected_operator_label": affected_operator_label,
            "exception_affected_operator_identity_label": affected_operator_identity_label,
            "exception_affected_operator_export_label": affected_operator_export_label,
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
            "planned_resource_label": planned_resource["display_label"],
            "planned_resource_identity_label": planned_resource["identity_label"],
            "planned_resource_export_label": planned_resource["export_label"],
            "actual_resource_label": actual_resource["display_label"],
            "actual_resource_identity_label": actual_resource["identity_label"],
            "actual_resource_export_label": actual_resource["export_label"],
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
    def _resource_pair_payload(machine: ResourceIdentity, operator: ResourceIdentity, *, empty_label: str) -> Dict[str, str]:
        machine_display = machine.display_label
        operator_display = operator.display_label
        machine_identity = machine.identity_label
        operator_identity = operator.identity_label
        if machine_display and operator_display:
            display = f"{machine_display} / {operator_display}"
        elif machine_display:
            display = f"{machine_display} / 未安排人员"
        elif operator_display:
            display = f"未安排设备 / {operator_display}"
        else:
            display = empty_label
        if machine_identity and operator_identity:
            identity = f"{machine_identity} / {operator_identity}"
        elif machine_identity:
            identity = f"{machine_identity} / 未安排人员"
        elif operator_identity:
            identity = f"未安排设备 / {operator_identity}"
        else:
            identity = display
        export = display
        if identity and identity != display:
            export = f"{display}\n完整身份：{identity}"
        return {"display_label": display, "identity_label": identity, "export_label": export}

    @staticmethod
    def _resource_export_label(identity: ResourceIdentity, display_label: str) -> str:
        display = str(display_label or "").strip()
        identity_label = identity.identity_label
        if display and identity_label and identity_label != display:
            return f"{display}\n完整身份：{identity_label}"
        return display or identity_label

    @staticmethod
    def _planned_resource_identity(row: Dict[str, Any]) -> Dict[str, str]:
        machine = build_resource_identity(row.get("machine_id"), row.get("machine_name"))
        operator = build_resource_identity(row.get("operator_id"), row.get("operator_name"))
        return ExecutionReviewMixin._resource_pair_payload(machine, operator, empty_label="未安排计划资源")

    @staticmethod
    def _state_resource_identity(state, prefix: str, *, empty_label: str = "") -> ResourceIdentity:
        return build_resource_identity(
            getattr(state, f"{prefix}_id", None),
            getattr(state, f"{prefix}_name", None),
            display_label=getattr(state, f"{prefix}_display_label", None) or empty_label,
            identity_label=getattr(state, f"{prefix}_identity_label", None) or getattr(state, f"{prefix}_label", None),
        )

    @staticmethod
    def _actual_resource_identity(state, has_feedback: bool) -> Dict[str, str]:
        if not has_feedback:
            return {
                "display_label": "暂无现场反馈",
                "identity_label": "暂无现场反馈",
                "export_label": "暂无现场反馈",
            }
        machine = ExecutionReviewMixin._state_resource_identity(state, "actual_machine")
        operator = ExecutionReviewMixin._state_resource_identity(state, "actual_operator")
        return ExecutionReviewMixin._resource_pair_payload(machine, operator, empty_label="未填写实际资源")

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
