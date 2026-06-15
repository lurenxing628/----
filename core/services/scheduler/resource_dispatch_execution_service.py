from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

from core.infrastructure.errors import AppError, ErrorCode, ValidationError
from core.models.operation_execution_scope import parse_positive_execution_int
from core.models.operation_execution_state import OperationExecutionState
from core.models.schedule_plan_role import ROLE_ADOPTED, SOURCE_SCHEDULE
from data.repositories.schedule_repo import ScheduleRepository

from .operation_execution_feedback_service import ExecutionFeedbackContext, OperationExecutionFeedbackService
from .operation_execution_scope_read import states_by_op_id_for_plan_rows
from .resource_dispatch_range import resolve_dispatch_range
from .resource_dispatch_rows import prepare_dispatch_rows
from .resource_dispatch_service import ResourceDispatchService
from .schedule_plan_query_service import SchedulePlanQueryService
from .schedule_result_view_context import normalize_plan_role, plan_role_filter_fields
from .version_resolution import require_selected_version


def _text(value: Any) -> str:
    return str(value or "").strip()


def _positive_int(value: Any) -> Optional[int]:
    # R09 收编:委托唯一收口点 parse_positive_execution_int(严格:bool/小数/非正数均拒),
    # 坏值返回 None 由调用方按"无效"处理——5.9 不再截断成 5 误命中相邻工序。
    try:
        return parse_positive_execution_int(value, "resource_dispatch_execution")
    except ValueError:
        return None


def _context_is_current_official(context: ExecutionFeedbackContext, latest_version: int) -> bool:
    return (
        int(context.schedule_version) == int(latest_version)
        and _text(context.requested_plan_role) == ROLE_ADOPTED
        and _text(context.effective_plan_role) == ROLE_ADOPTED
        and _text(context.source_table) == SOURCE_SCHEDULE
        and not _text(context.scenario_id)
    )


class ResourceDispatchExecutionService:
    """资源派工页现场反馈任务卡读取服务。

    普通资源派工 JSON 会脱敏隐藏 schedule_id / op_id。现场反馈任务卡需要这些
    程序提交字段，所以单独走这个服务，不改变原公开接口。
    """

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.dispatch_service = ResourceDispatchService(conn, logger=logger, op_logger=op_logger)
        self.plan_query_service = SchedulePlanQueryService(conn, logger=logger)
        self.feedback_service = OperationExecutionFeedbackService(conn, logger=logger, op_logger=op_logger)
        self.schedule_repo = ScheduleRepository(conn, logger=logger)

    def get_execution_context(
        self,
        *,
        scope_type: Any = None,
        scope_id: Any = None,
        operator_id: Any = None,
        machine_id: Any = None,
        team_id: Any = None,
        team_axis: Any = None,
        period_preset: Any = None,
        query_date: Any = None,
        start_date: Any = None,
        end_date: Any = None,
        version: Any = None,
        plan_role: Any = None,
        scenario_id: Any = None,
        batch_id: Any = None,
    ) -> Dict[str, Any]:
        normalized_scope_type = self.dispatch_service._normalize_scope_type(scope_type)
        normalized_plan_role = normalize_plan_role(plan_role)
        normalized_scenario_id = self.dispatch_service._text(scenario_id)
        latest_version = self.dispatch_service._latest_version()
        view_context = self.dispatch_service._resolve_result_view_context(
            version=version,
            plan_role=normalized_plan_role,
            scenario_id=normalized_scenario_id,
            latest_version=latest_version,
        )
        version_resolution = view_context.version_resolution
        if version_resolution.status == "no_history":
            return self._empty_context(view_context)
        selected_version = require_selected_version(version_resolution)
        plan_role_fields = plan_role_filter_fields(view_context)
        selected_scope_id = self.dispatch_service._resolve_scope_id(
            scope_type=normalized_scope_type,
            scope_id=scope_id,
            operator_id=operator_id,
            machine_id=machine_id,
            team_id=team_id,
        )
        if normalized_scope_type == "team" and not selected_scope_id:
            raise ValidationError("请选择查询对象", field="scope_id")
        dr = resolve_dispatch_range(
            period_preset=period_preset or "week",
            query_date=query_date,
            start_date=start_date,
            end_date=end_date,
        )
        rows = self.plan_query_service.list_plan_dispatch_rows_for_resolution(
            start_time=dr.start_time,
            end_time=dr.end_time,
            version=int(selected_version),
            source_table=str(plan_role_fields.get("source_table") or ""),
            candidate_id=plan_role_fields.get("candidate_id"),
            scenario_id=plan_role_fields.get("scenario_id"),
            scope_type=normalized_scope_type,
            scope_id=selected_scope_id,
            batch_id=batch_id,
        )
        normalized_batch_id = _text(batch_id)
        rows = [
            dict(row)
            for row in rows
            if not normalized_batch_id or _text((row or {}).get("batch_id")) == normalized_batch_id
        ]
        prepared = prepare_dispatch_rows(rows, scope="resource_dispatch.execution")
        states = states_by_op_id_for_plan_rows(self.feedback_service, prepared.value, plan_role_fields)
        return {
            "plan_identity": self._plan_identity(view_context),
            "plan_identity_label": str(plan_role_fields.get("plan_identity_label") or ""),
            "can_write_feedback": bool(plan_role_fields.get("can_write_feedback")),
            "rows": prepared.value,
            "states": states,
            "feedback_write_enabled": bool(plan_role_fields.get("can_write_feedback")),
            "degradation_events": prepared.events,
        }

    def task_card_for_feedback_context(
        self,
        context: ExecutionFeedbackContext,
        state: OperationExecutionState,
        *,
        feedback_write_enabled: bool = True,
    ) -> Dict[str, Any]:
        schedule = self.schedule_repo.get(int(context.schedule_id))
        if schedule is None:
            # N4/O31：排程行缺失是"资源不存在"语义，须 NOT_FOUND 而非字段校验错——与写门禁
            # operation_execution_feedback_service.py 的 schedule 缺失分支同错误类（跨文件对称）。
            raise AppError(
                ErrorCode.NOT_FOUND,
                "现场记录对应的排程行不存在，请刷新后重试。",
                details={"reason": "not_found"},
            )
        rows = self.plan_query_service.list_plan_dispatch_rows_for_resolution(
            version=int(context.schedule_version),
            source_table=_text(context.source_table),
            candidate_id=None,
            scenario_id=_text(context.scenario_id) or None,
            start_time=schedule.start_time,
            end_time=schedule.end_time,
            batch_id=_text(context.batch_id),
            schedule_id=int(context.schedule_id),
            op_id=int(context.op_id),
        )
        row = self._matching_row(rows, context)
        identity = self._plan_identity_from_context(context)
        return {
            "plan_identity": identity,
            "plan_identity_label": str(identity.get("user_label") or ""),
            "can_write_feedback": bool(identity.get("can_write_feedback")),
            "rows": [row],
            "states": {int(context.op_id): state},
            "feedback_write_enabled": feedback_write_enabled,
            "degradation_events": [],
        }

    @staticmethod
    def _op_ids(rows: Sequence[Mapping[str, Any]]) -> List[int]:
        out: List[int] = []
        seen = set()
        for row in rows:
            op_id = _positive_int(row.get("op_id"))
            if op_id is None or op_id in seen:
                continue
            seen.add(op_id)
            out.append(op_id)
        return out

    @staticmethod
    def _matching_row(rows: Sequence[Mapping[str, Any]], context: ExecutionFeedbackContext) -> Dict[str, Any]:
        for row in rows:
            if (
                _positive_int(row.get("schedule_id")) == int(context.schedule_id)
                and _positive_int(row.get("op_id")) == int(context.op_id)
                and _text(row.get("batch_id")) == _text(context.batch_id)
            ):
                return dict(row)
        raise ValidationError("现场记录对应的任务不在当前计划身份里，请刷新后重试。", field="plan_identity")

    def _plan_identity_from_context(self, context: ExecutionFeedbackContext) -> Dict[str, Any]:
        latest_version = self.dispatch_service._latest_version()
        current_official = _context_is_current_official(context, latest_version)
        label = "正式采用方案" if current_official else f"历史或对比方案 v{int(context.schedule_version)}"
        return {
            "version": int(context.schedule_version),
            "requested_plan_role": _text(context.requested_plan_role),
            "effective_plan_role": _text(context.effective_plan_role),
            "source_table": _text(context.source_table),
            "scenario_id": _text(context.scenario_id) or None,
            "user_label": label,
            "can_write_feedback": current_official,
        }

    @staticmethod
    def _plan_identity(view_context: Any) -> Dict[str, Any]:
        plan_resolution = getattr(view_context, "plan_resolution", {}) or {}
        identity = plan_resolution.get("plan_identity") if isinstance(plan_resolution, dict) else None
        return dict(identity or {})

    def _empty_context(self, view_context: Any) -> Dict[str, Any]:
        return {
            "plan_identity": self._plan_identity(view_context),
            "plan_identity_label": "正式采用方案",
            "can_write_feedback": False,
            "rows": [],
            "states": {},
            "feedback_write_enabled": False,
            "degradation_events": [],
        }


__all__ = ["ResourceDispatchExecutionService"]
