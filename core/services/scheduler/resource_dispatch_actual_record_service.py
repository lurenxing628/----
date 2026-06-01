from __future__ import annotations

import hashlib
import io
from dataclasses import replace
from typing import Any, Dict, List, Mapping, Optional, Sequence

from core.infrastructure.errors import AppError, ErrorCode, ValidationError
from core.models.operation_execution_labels import REASON_LABELS, SEVERITY_LABELS
from core.models.operation_execution_state import OperationExecutionState
from core.models.schedule_plan_role import ROLE_ADOPTED, SOURCE_SCHEDULE
from data.repositories.batch_operation_repo import BatchOperationRepository
from data.repositories.schedule_repo import ScheduleRepository

from .operation_execution_feedback_service import ExecutionFeedbackContext, OperationExecutionFeedbackService
from .resource_dispatch_actual_excel import build_actual_template_workbook, read_actual_workbook_rows
from .resource_dispatch_actual_import import ResourceDispatchActualImportPreviewer, preview_payload, preview_token
from .resource_dispatch_actual_records import (
    PausePlan,
    PreviewResult,
    TaskPlan,
    TaskRef,
    datetime_text,
    feedback_person,
    normalize_choice,
    ordered_pauses,
    parse_datetime_or_error,
    parse_int_or_error,
    planned_event_count,
    resource_label,
    task_code_from_parts,
    task_display_name,
    text,
)
from .resource_dispatch_execution_service import ResourceDispatchExecutionService
from .resource_dispatch_task_ids import public_task_id


class ResourceDispatchActualRecordService:
    def __init__(self, conn, logger=None, op_logger=None, *, execution_service=None, feedback_service=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        # 可注入已装配好的 execution/feedback 服务，避免同一请求里重复构造；不注入时自行构造，
        # 保证本服务可独立使用、不反向依赖 web 装配层。
        self.execution_service = execution_service or ResourceDispatchExecutionService(
            conn, logger=logger, op_logger=op_logger
        )
        self.feedback_service = feedback_service or OperationExecutionFeedbackService(
            conn, logger=logger, op_logger=op_logger
        )
        self.previewer = ResourceDispatchActualImportPreviewer(self.feedback_service)
        self.schedule_repo = ScheduleRepository(conn, logger=logger)
        self.batch_operation_repo = BatchOperationRepository(conn, logger=logger)

    def build_template_workbook(self, **query_kwargs: Any) -> io.BytesIO:
        context = self._execution_context_for_write(**query_kwargs)
        return build_actual_template_workbook(self._task_refs_from_context(context))

    def preview_import_workbook(self, file_bytes: bytes, **query_kwargs: Any) -> Dict[str, Any]:
        raw_rows = read_actual_workbook_rows(file_bytes)
        preview = self._preview_raw_rows(raw_rows, **query_kwargs)
        token = preview_token(preview.raw_rows, query_kwargs)
        return preview_payload(preview, preview_token=token)

    def import_workbook(self, file_bytes: bytes, **query_kwargs: Any) -> Dict[str, Any]:
        raw_rows = read_actual_workbook_rows(file_bytes)
        preview = self._preview_raw_rows(raw_rows, **query_kwargs)
        if not preview.summary.get("can_confirm"):
            raise ValidationError(
                "导入失败，Excel 里还有错误，请修改后再导入。",
                field="file",
                details={
                    "reason": "actual_import_validation_failed",
                    "summary": preview.summary,
                    "rows": preview.rows,
                },
            )
        return self._write_preview(preview, import_token=preview_token(preview.raw_rows, query_kwargs))

    def confirm_import(self, rows: Sequence[Mapping[str, Any]], preview_token_value: Any, **query_kwargs: Any) -> Dict[str, Any]:
        raw_rows = [dict(row) for row in rows or []]
        preview = self._preview_raw_rows(raw_rows, **query_kwargs)
        expected_token = preview_token(preview.raw_rows, query_kwargs)
        if text(preview_token_value) != expected_token:
            raise ValidationError("导入内容已经变化，请重新上传 Excel 并检查后再确认导入。", field="preview_token")
        if not preview.summary.get("can_confirm"):
            raise ValidationError("导入预览还有错误，请先修改 Excel 后重新上传检查。", field="file")
        return self._write_preview(preview, import_token=expected_token)

    def _write_preview(self, preview: PreviewResult, *, import_token: str) -> Dict[str, Any]:
        written = 0
        skipped = int(preview.summary.get("skip_count") or 0)
        with self.feedback_service.tx_manager.transaction(begin_immediate=True):
            for plan in preview.task_plans:
                if planned_event_count(plan) <= 0:
                    continue
                result = self._apply_task_plan(plan, import_token=import_token)
                written += int(result.get("written") or 0)
                skipped += int(result.get("skipped") or 0)
        return {
            "success": True,
            "message": self._import_result_message(written, skipped),
            "summary": {
                "added_events": written,
                "skipped_events": skipped,
                "conflict_rows": 0,
                "error_rows": 0,
            },
        }

    def _import_result_message(self, written: int, skipped: int) -> str:
        if skipped > 0:
            return f"导入完成：新增 {written} 条现场记录；{skipped} 行没有填写实际情况，已忽略。"
        return f"导入完成：新增 {written} 条现场记录。"

    def record_actual_situation(self, context: ExecutionFeedbackContext, payload: Mapping[str, Any]) -> Dict[str, Any]:
        self._ensure_context_can_write(context)
        task = self._task_ref_from_feedback_context(context)
        plan = self._task_plan_from_actual_payload(task, payload, row_number=1)
        token = text(payload.get("idempotency_key")) or self._manual_plan_token(plan)
        messages: List[str] = []
        if not self._plan_is_full_replay(plan, token):
            self.previewer.validator.validate_task_plan(plan, messages)
            if messages:
                raise ValidationError(messages[0], field="actual_record", details={"messages": messages})
        with self.feedback_service.tx_manager.transaction(begin_immediate=True):
            return self._apply_task_plan(plan, import_token=token)

    def _preview_raw_rows(self, raw_rows: Sequence[Mapping[str, Any]], **query_kwargs: Any):
        context = self._execution_context_for_write(**query_kwargs)
        return self.previewer.preview(raw_rows, self._task_refs_from_context(context))

    def _execution_context_for_write(self, **query_kwargs: Any) -> Dict[str, Any]:
        context = self.execution_service.get_execution_context(**query_kwargs)
        identity = context.get("plan_identity") if isinstance(context, dict) else {}
        if not bool((identity or {}).get("can_write_feedback")):
            raise AppError(ErrorCode.SCHEDULE_CONFLICT, "当前不是最新正式采用方案，不能填写现场记录。", details={"reason": "not_current_official_plan", "can_retry": False})
        return context

    def _ensure_context_can_write(self, context: ExecutionFeedbackContext) -> None:
        is_official_schedule = (
            text(context.requested_plan_role) == ROLE_ADOPTED
            and text(context.effective_plan_role) == ROLE_ADOPTED
            and text(context.source_table) == SOURCE_SCHEDULE
            and not text(context.scenario_id)
        )
        if not is_official_schedule:
            raise AppError(ErrorCode.SCHEDULE_CONFLICT, "当前不是最新正式采用方案，不能填写现场记录。", details={"reason": "not_current_official_plan", "can_retry": False})
        self._execution_context_for_write(
            version=context.schedule_version,
            plan_role=context.requested_plan_role,
            scenario_id=context.scenario_id,
        )

    def _task_refs_from_context(self, context: Mapping[str, Any]) -> List[TaskRef]:
        states_value = context.get("states")
        states = states_value if isinstance(states_value, dict) else {}
        out: List[TaskRef] = []
        seen = set()
        for row in context.get("rows") or []:
            if not isinstance(row, Mapping):
                continue
            task = self._task_ref_from_row(row, states, context=context)
            if task.op_id <= 0 or task.op_id in seen:
                continue
            seen.add(task.op_id)
            out.append(task)
        return out

    def _task_ref_from_row(
        self,
        row: Mapping[str, Any],
        states: Mapping[int, OperationExecutionState],
        *,
        context: Mapping[str, Any],
    ) -> TaskRef:
        op_id = int(row.get("op_id") or 0)
        schedule_id = int(row.get("schedule_id") or 0)
        batch_id = text(row.get("batch_id"))
        op_name = task_display_name(row)
        planned_machine_label = resource_label(row, "planned_machine") or resource_label(row, "machine") or "-"
        planned_operator_label = resource_label(row, "planned_operator") or resource_label(row, "operator") or "-"
        state = states.get(op_id) or OperationExecutionState(op_id=op_id, batch_id=batch_id)
        return TaskRef(
            task_code=task_code_from_parts(
                batch_id=batch_id,
                op_name=op_name,
                planned_start_time=row.get("start_time"),
                planned_machine_label=planned_machine_label,
                public_task_id=public_task_id(row),
            ),
            schedule_version=self._schedule_version_from_context(context, row, schedule_id),
            schedule_id=schedule_id,
            op_id=op_id,
            batch_id=batch_id,
            op_name=op_name,
            planned_machine_id=text(row.get("machine_id") or row.get("planned_machine_id")),
            planned_machine_label=planned_machine_label,
            planned_operator_id=text(row.get("operator_id") or row.get("planned_operator_id")),
            planned_operator_label=planned_operator_label,
            state=state,
            expected_state_revision=state.state_revision,
        )

    def _schedule_version_from_context(self, context: Mapping[str, Any], row: Mapping[str, Any], schedule_id: int) -> int:
        plan_identity = context.get("plan_identity") if isinstance(context.get("plan_identity"), Mapping) else {}
        schedule_version = int((plan_identity or {}).get("version") or row.get("version") or 0)
        if schedule_version > 0:
            return schedule_version
        schedule = self.schedule_repo.get(schedule_id)
        return int(getattr(schedule, "version", 0) or 0) if schedule is not None else 0

    def _task_ref_from_feedback_context(self, context: ExecutionFeedbackContext) -> TaskRef:
        schedule = self.schedule_repo.get(int(context.schedule_id))
        batch_op = self.batch_operation_repo.get(int(context.op_id))
        if schedule is None or batch_op is None:
            raise AppError(ErrorCode.NOT_FOUND, "当前任务不存在，请刷新后重试。", details={"reason": "not_found"})
        state = self.feedback_service.get_execution_state([int(context.op_id)]).get(int(context.op_id))
        batch_id = text(getattr(batch_op, "batch_id", None) or context.batch_id)
        op_name = text(getattr(batch_op, "op_code", None)) or f"工序{text(getattr(batch_op, 'seq', None))}"
        machine_id = text(getattr(schedule, "machine_id", None))
        operator_id = text(getattr(schedule, "operator_id", None))
        return TaskRef(
            task_code=task_code_from_parts(
                batch_id=batch_id,
                op_name=op_name,
                planned_start_time=getattr(schedule, "start_time", ""),
                planned_machine_label=machine_id,
                public_task_id=public_task_id(
                    {
                        "schedule_id": getattr(schedule, "id", None),
                        "op_id": getattr(schedule, "op_id", None),
                        "op_code": op_name,
                        "batch_id": batch_id,
                        "start_time": getattr(schedule, "start_time", ""),
                        "end_time": getattr(schedule, "end_time", ""),
                        "machine_id": machine_id,
                        "operator_id": operator_id,
                    }
                ),
            ),
            schedule_version=int(context.schedule_version),
            schedule_id=int(context.schedule_id),
            op_id=int(context.op_id),
            batch_id=batch_id,
            op_name=op_name,
            planned_machine_id=machine_id,
            planned_machine_label=machine_id,
            planned_operator_id=operator_id,
            planned_operator_label=operator_id,
            state=state or OperationExecutionState(op_id=int(context.op_id), batch_id=batch_id),
            expected_state_revision=text(context.expected_state_revision),
        )

    def _task_plan_from_actual_payload(self, task: TaskRef, payload: Mapping[str, Any], *, row_number: int) -> TaskPlan:
        messages: List[str] = []
        plan = TaskPlan(
            task=task,
            row_number=row_number,
            actual_start_time=parse_datetime_or_error(payload.get("actual_start_time"), field_label="实际开工时间", messages=messages),
            actual_finish_time=parse_datetime_or_error(payload.get("actual_finish_time"), field_label="实际完工时间", messages=messages),
            quantity_done=payload.get("quantity_done"),
            quantity_scrapped=payload.get("quantity_scrapped"),
            exception_time=parse_datetime_or_error(payload.get("exception_time"), field_label="异常时间", messages=messages),
            exception_reason_code=normalize_choice(
                payload.get("exception_reason") or payload.get("reason_code"),
                REASON_LABELS,
                field_label="异常原因",
                messages=messages,
            ),
            exception_severity=normalize_choice(
                payload.get("exception_severity") or payload.get("severity"),
                SEVERITY_LABELS,
                field_label="异常严重程度",
                messages=messages,
            ),
            exception_remark=text(payload.get("exception_remark") or payload.get("reason_detail") or payload.get("remark")) or None,
            feedback_person=feedback_person(payload.get("feedback_person") or payload.get("created_by")),
            remark=text(payload.get("remark")) or None,
            pauses=[],
        )
        pause = self._pause_plan_from_payload(payload, row_number=row_number, messages=messages)
        if pause is not None:
            plan.pauses = [pause]
        if messages:
            raise ValidationError(messages[0], field="actual_record", details={"messages": messages})
        return plan

    def _pause_plan_from_payload(self, payload: Mapping[str, Any], *, row_number: int, messages: List[str]) -> Optional[PausePlan]:
        start = parse_datetime_or_error(payload.get("pause_start_time"), field_label="暂停开始时间", messages=messages)
        end = parse_datetime_or_error(payload.get("pause_end_time"), field_label="暂停结束时间", messages=messages)
        duration = parse_int_or_error(payload.get("pause_duration_minutes"), field_label="暂停时长分钟", messages=messages)
        reason_code = normalize_choice(
            payload.get("pause_reason") or payload.get("pause_reason_code"),
            REASON_LABELS,
            field_label="暂停原因",
            messages=messages,
        )
        remark = text(payload.get("pause_remark"))
        if not any([start, end, duration is not None, reason_code, remark]):
            return None
        return self.previewer.pause_plan_from_values(
            row_number=row_number,
            start=start,
            end=end,
            duration_minutes=duration,
            reason_code=reason_code,
            remark=remark,
            feedback_person_value=payload.get("feedback_person") or payload.get("created_by"),
            messages=messages,
        )

    def _apply_task_plan(self, plan: TaskPlan, *, import_token: Optional[str]) -> Dict[str, Any]:
        current_state = self.feedback_service.get_execution_state([plan.task.op_id])[plan.task.op_id]
        context = ExecutionFeedbackContext(
            schedule_version=plan.task.schedule_version,
            schedule_id=plan.task.schedule_id,
            op_id=plan.task.op_id,
            batch_id=plan.task.batch_id,
            expected_state_revision=plan.task.expected_state_revision or current_state.state_revision,
            created_by=plan.feedback_person,
            idempotency_key=self._idempotency_key(import_token, plan.task.task_code, "actual", plan.row_number),
        )
        written = 0
        result: Optional[Any] = None
        if plan.actual_start_time:
            result = self.feedback_service.start_operation(
                context,
                event_time=plan.actual_start_time,
                operator_id=plan.task.planned_operator_id,
                machine_id=plan.task.planned_machine_id,
                remark=plan.remark,
            )
            written += 1
            context = self._next_context(context, self._revision_for_next_event(result), import_token, plan, "after-start")
            current_state = result.state
        else:
            context = replace(context, expected_state_revision=current_state.state_revision)
        if current_state.current_status == "not_started" and not plan.actual_start_time:
            raise ValidationError("填写暂停、异常或完工前，请先填写实际开工。", field="actual_start_time")
        for index, pause in enumerate(ordered_pauses(plan)):
            result = self._apply_pause(context, plan, pause, import_token, index)
            written += 2
            context = replace(context, expected_state_revision=self._revision_for_next_event(result))
            current_state = result.state
        if plan.exception_time:
            context = replace(context, created_by=plan.feedback_person, idempotency_key=self._idempotency_key(import_token, plan.task.task_code, "exception", plan.row_number))
            result = self.feedback_service.report_exception(
                context,
                event_time=plan.exception_time,
                reason_code=plan.exception_reason_code,
                severity=plan.exception_severity,
                remark=plan.exception_remark,
                reason_detail=plan.exception_remark,
            )
            written += 1
            context = replace(context, expected_state_revision=result.state_revision)
        if plan.actual_finish_time:
            context = replace(context, created_by=plan.feedback_person, idempotency_key=self._idempotency_key(import_token, plan.task.task_code, "finish", plan.row_number))
            result = self.feedback_service.finish_operation(
                context,
                event_time=plan.actual_finish_time,
                quantity_done=plan.quantity_done,
                quantity_scrapped=plan.quantity_scrapped,
                remark=plan.remark,
            )
            written += 1
        if result is None:
            state = self.feedback_service.get_execution_state([plan.task.op_id])[plan.task.op_id]
            return {"written": written, "skipped": 1, "state": state, "result": None}
        return {"written": written, "skipped": 0, "state": result.state, "result": result}

    def _revision_for_next_event(self, result: Any) -> str:
        if not bool(getattr(result, "idempotency_reused", False)):
            return str(result.state_revision)
        event = getattr(result, "event", None)
        if event is None:
            return str(result.state_revision)
        op_id = int(getattr(event, "op_id", 0) or 0)
        event_id = int(getattr(event, "id", 0) or 0)
        events = self.feedback_service.list_execution_events(op_id)
        for index, item in enumerate(events, start=1):
            if int(getattr(item, "id", 0) or 0) == event_id:
                return f"{op_id}:{index}:{event_id}"
        raise AppError(ErrorCode.NOT_FOUND, "现场记录已写入但没有读回，请刷新后重试。", details={"reason": "event_not_found"})

    def _plan_is_full_replay(self, plan: TaskPlan, import_token: Optional[str]) -> bool:
        """判断这次提交是不是“同一份内容的完全重放”。

        只有当这个 plan 要写的每一个事件都已经按相同幂等 key 写过时，才视为纯重放并跳过
        高层校验。只要有任何一个事件是新的（key 不存在），就必须跑完整校验——否则客户端复用
        同一个 idempotency_key 提交了新内容时，新增部分会逃过完工早于开工、暂停冲突等跨字段校验。
        """
        if not import_token:
            return False
        keys = self._plan_idempotency_keys(plan, import_token)
        if not keys:
            return False
        return all(
            self.feedback_service.event_repo.get_by_idempotency_key(key) is not None
            for key in keys
        )

    def _plan_idempotency_keys(self, plan: TaskPlan, import_token: str) -> List[str]:
        keys: List[str] = []
        if plan.actual_start_time:
            keys.append(self._idempotency_key(import_token, plan.task.task_code, "actual", plan.row_number))
        for index, pause in enumerate(ordered_pauses(plan)):
            keys.append(self._idempotency_key(import_token, plan.task.task_code, f"pause-{index}", pause.row_number))
            keys.append(self._idempotency_key(import_token, plan.task.task_code, f"resume-{index}", pause.row_number))
        if plan.exception_time:
            keys.append(self._idempotency_key(import_token, plan.task.task_code, "exception", plan.row_number))
        if plan.actual_finish_time:
            keys.append(self._idempotency_key(import_token, plan.task.task_code, "finish", plan.row_number))
        return keys

    def _apply_pause(
        self,
        context: ExecutionFeedbackContext,
        plan: TaskPlan,
        pause: PausePlan,
        import_token: Optional[str],
        index: int,
    ) -> Any:
        context = replace(
            context,
            created_by=pause.feedback_person,
            idempotency_key=self._idempotency_key(import_token, plan.task.task_code, f"pause-{index}", pause.row_number),
        )
        pause_result = self.feedback_service.pause_operation(
            context,
            event_time=pause.start_time,
            reason_code=pause.reason_code,
            remark=pause.remark,
        )
        context = replace(
            context,
            expected_state_revision=self._revision_for_next_event(pause_result),
            idempotency_key=self._idempotency_key(import_token, plan.task.task_code, f"resume-{index}", pause.row_number),
        )
        return self.feedback_service.resume_operation(context, event_time=pause.end_time, remark=pause.remark)

    def _next_context(
        self,
        context: ExecutionFeedbackContext,
        revision: str,
        import_token: Optional[str],
        plan: TaskPlan,
        action: str,
    ) -> ExecutionFeedbackContext:
        return replace(
            context,
            expected_state_revision=revision,
            idempotency_key=self._idempotency_key(import_token, plan.task.task_code, action, plan.row_number),
        )

    def _idempotency_key(self, import_token: Optional[str], task_code: str, action: str, row_number: int) -> str:
        base = import_token or "manual"
        raw = f"resource-dispatch-actual:{base}:{task_code}:{action}:{row_number}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        return f"resource-dispatch-actual-{digest}"

    def _manual_plan_token(self, plan: TaskPlan) -> str:
        parts = [
            plan.task.task_code,
            self._token_time("start", plan.actual_start_time),
            self._token_time("finish", plan.actual_finish_time),
            f"done:{text(plan.quantity_done)}",
            f"scrapped:{text(plan.quantity_scrapped)}",
            self._token_time("exception", plan.exception_time),
            f"exception_reason:{text(plan.exception_reason_code)}",
            f"exception_severity:{text(plan.exception_severity)}",
            f"exception_remark:{text(plan.exception_remark)}",
            f"remark:{text(plan.remark)}",
        ]
        for index, pause in enumerate(ordered_pauses(plan)):
            parts.extend(
                [
                    f"pause:{index}",
                    self._token_time("pause_start", pause.start_time),
                    self._token_time("pause_end", pause.end_time),
                    f"pause_reason:{text(pause.reason_code)}",
                    f"pause_remark:{text(pause.remark)}",
                ]
            )
        raw = "|".join(parts)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        return f"manual-{digest}"

    def _token_time(self, label: str, value: Any) -> str:
        if not text(value):
            return f"{label}:"
        return f"{label}:{datetime_text(value, field_label=label)}"


__all__ = ["ResourceDispatchActualRecordService"]
