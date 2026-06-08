from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Protocol, cast

from core.infrastructure.errors import ValidationError
from core.models.operation_execution_scope import OperationExecutionScope
from core.models.resource_identity import ResourceIdentity, build_resource_identity
from core.models.schedule_plan_role import ROLE_ADOPTED, SOURCE_SCHEDULE
from core.services.scheduler.schedule_plan_query_service import plan_role_label

from . import calculations
from .exporters import export_execution_review_xlsx
from .report_number_parsing import parse_report_float, parse_report_int


def _finite_number(value: Any, *, field: str, label: str, default: float = 0.0) -> float:
    return parse_report_float(value, field=field, label=label, source_label="现场反馈数据", blank_default=default)


def _operation_id(value: Any) -> int:
    return parse_report_int(value, field="op_id", label="工序编号", source_label="计划数据", blank_default=0)


def _schedule_id(value: Any) -> int:
    return parse_report_int(value, field="schedule_id", label="排程记录编号", source_label="计划数据", blank_default=0)


def _schedule_version(value: Any) -> int:
    return parse_report_int(value, field="version", label="排产版本", source_label="计划数据", blank_default=0)


def _execution_scope(row: Dict[str, Any], op_id: int) -> OperationExecutionScope:
    schedule_id = _schedule_id(row.get("schedule_id"))
    version = _schedule_version(row.get("version"))
    batch_id = str(row.get("batch_id") or "").strip()
    missing = []
    if op_id <= 0:
        missing.append("op_id")
    if schedule_id <= 0:
        missing.append("schedule_id")
    if version <= 0:
        missing.append("version")
    if not batch_id:
        missing.append("batch_id")
    if missing:
        raise ValidationError(
            "计划数据缺少现场执行身份字段，不能生成计划和现场实际复盘。",
            field=missing[0],
            details={"missing_fields": missing},
        )
    # 现场复盘只认正式 schedule/adopted 身份；读侧硬钉与 OperationExecutionEvents 的 v19 CHECK 同向。
    return OperationExecutionScope.from_values(
        schedule_version=version,
        schedule_id=schedule_id,
        op_id=op_id,
        batch_id=batch_id,
        source_table=SOURCE_SCHEDULE,
        effective_plan_role=ROLE_ADOPTED,
    )


def _plan_identity_label(plan_resolution: Dict[str, Any]) -> str:
    identity = plan_resolution.get("plan_identity") if isinstance(plan_resolution, dict) else None
    identity_dict = identity if isinstance(identity, dict) else {}
    return str(identity_dict.get("user_label") or identity_dict.get("label") or plan_role_label(ROLE_ADOPTED))


def _filename_part(value: Any) -> str:
    text = str(value or "").strip() or plan_role_label(ROLE_ADOPTED)
    for char in '\\/:*?"<>|':
        text = text.replace(char, "_")
    return text


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
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        batch_id: Optional[str] = None,
    ) -> Any:
        ...

    def _list_plan_rows_all(
        self,
        *,
        version: int,
        plan_role: Optional[str],
        scenario_id: Optional[str],
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        batch_id: Optional[str] = None,
    ) -> Any:
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

    def _execution_review_plan_rows(
        self,
        *,
        version: int,
        date_bounds: Dict[str, Any],
        batch_filter: str,
        resource_type: Any = None,
        resource_id: Any = None,
    ):
        host = cast(_ExecutionReviewHost, self)
        if date_bounds["start_time"] and date_bounds["end_time"]:
            # 复盘报表不接收可变 plan_role/scenario_id；候选和模拟方案只在入口处可见拦截。
            plan_rows = host._list_plan_rows_between(
                version=version,
                plan_role=ROLE_ADOPTED,
                scenario_id=None,
                start_time=str(date_bounds["start_time"]),
                end_time=str(date_bounds["end_time"]),
                resource_type=str(resource_type or "").strip(),
                resource_id=str(resource_id or "").strip(),
                batch_id=batch_filter,
            )
        else:
            # 无日期筛选时同样硬钉正式 adopted/null，不能把对比方案当现场事实复盘来源。
            plan_rows = host._list_plan_rows_all(
                version=version,
                plan_role=ROLE_ADOPTED,
                scenario_id=None,
                resource_type=str(resource_type or "").strip(),
                resource_id=str(resource_id or "").strip(),
                batch_id=batch_filter,
            )
        return plan_rows

    def _execution_review_rows(self, plan_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        host = cast(_ExecutionReviewHost, self)
        rows_with_scopes = [
            (dict(row or {}), _execution_scope(dict(row or {}), _operation_id((row or {}).get("op_id"))))
            for row in plan_rows
        ]
        scopes = [scope for _row, scope in rows_with_scopes]
        states = host.execution_feedback_service.get_execution_state_for_scopes(scopes)
        return [self._execution_review_row(row, states.get(scope)) for row, scope in rows_with_scopes]

    def execution_review(
        self,
        version: int,
        *,
        date_from: Any = None,
        date_to: Any = None,
        batch_id: Any = None,
        resource_type: Any = None,
        resource_id: Any = None,
    ) -> Dict[str, Any]:
        host = cast(_ExecutionReviewHost, self)
        v = int(version or 0)
        # 先按正式 adopted/null 解析身份，再进入复盘计算，避免下游读路径被查询参数放宽。
        resolution = host._resolve_plan(v, ROLE_ADOPTED, None)
        date_bounds = self._execution_review_date_bounds(date_from, date_to)
        plan_resolution = resolution.to_dict()
        batch_filter = str(batch_id or "").strip()
        plan_rows = self._execution_review_plan_rows(
            version=v,
            date_bounds=date_bounds,
            batch_filter=batch_filter,
            resource_type=resource_type,
            resource_id=resource_id,
        )
        rows = self._execution_review_rows(list(plan_rows or []))
        return {
            "version": v,
            "plan_label": _plan_identity_label(plan_resolution),
            # 返回给页面/导出层的身份也硬钉 adopted，和上面的读路径保持同一条防线。
            "plan_role": ROLE_ADOPTED,
            "plan_resolution": plan_resolution,
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
        resource_type: Any = None,
        resource_id: Any = None,
    ) -> Any:
        rep = self.execution_review(
            version,
            date_from=date_from,
            date_to=date_to,
            batch_id=batch_id,
            resource_type=resource_type,
            resource_id=resource_id,
        )
        rows = list(rep.get("rows") or [])
        if not rows:
            raise ValidationError("暂无数据，不能导出。请调整版本、日期或批次后再试。", field="导出")
        plan_label = _filename_part(rep.get("plan_label"))
        filename = f"计划和现场实际-{plan_label}-v{int(rep['version'])}.xlsx"
        if rep.get("date_from") and rep.get("date_to"):
            filename = (
                f"计划和现场实际-{plan_label}-v{int(rep['version'])}-"
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
            "exception_affected_machine_identity_label": affected_machine_label,
            "exception_affected_machine_export_label": affected_machine_label,
            "exception_affected_operator_label": affected_operator_label,
            "exception_affected_operator_identity_label": affected_operator_label,
            "exception_affected_operator_export_label": affected_operator_label,
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
            "planned_resource_identity_label": planned_resource["display_label"],
            "planned_resource_export_label": planned_resource["display_label"],
            "planned_machine_id": str(row.get("machine_id") or ""),
            "planned_machine_name": str(row.get("machine_name") or ""),
            "planned_operator_id": str(row.get("operator_id") or ""),
            "planned_operator_name": str(row.get("operator_name") or ""),
            "actual_resource_label": actual_resource["display_label"],
            "actual_resource_identity_label": actual_resource["display_label"],
            "actual_resource_export_label": actual_resource["display_label"],
            "feedback_status_label": getattr(state, "current_status_label", None) if has_feedback else "暂无现场反馈",
        }

    @staticmethod
    def _display_time(value: Any) -> str:
        # 计划时间保持 ISO 文本口径：页面同一行的实际时间和 Excel 导出共享本标签，
        # 不做中文友好化转换，避免页面/导出口径分叉（2026-06-05 复审回退）。
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
        if machine_display and operator_display:
            display = f"{machine_display} / {operator_display}"
        elif machine_display:
            display = f"{machine_display} / 未安排人员"
        elif operator_display:
            display = f"未安排设备 / {operator_display}"
        else:
            display = empty_label
        return {"display_label": display, "identity_label": display, "export_label": display}

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
        minutes = _finite_number(value, field="pause_duration_minutes", label="暂停时长")
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
