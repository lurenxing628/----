from __future__ import annotations

import io
import re
from dataclasses import replace
from typing import Any, Dict, List, Mapping, Optional, Sequence

from core.errors import AppError, ErrorCode, ValidationError
from core.models.content import same
from core.models.operation_execution_labels import REASON_LABELS, SEVERITY_LABELS
from core.models.operation_execution_scope import operation_execution_scope_from_event
from core.models.operation_execution_state import OperationExecutionState
from core.models.schedule_plan_role import ROLE_ADOPTED, SOURCE_SCHEDULE
from core.services.common.plan_query import SchedulePlanQueryService
from core.services.common.plan_task_identity import public_task_id
from core.services.scheduler.execution.operation_execution_scope_read import (
    events_for_task_ref,
    state_for_feedback_context,
    state_for_task_ref,
)
from core.services.scheduler.operation_execution_feedback_service import (
    ExecutionFeedbackContext,
    OperationExecutionFeedbackService,
)
from data.repositories.batch_operation_repo import BatchOperationRepository
from data.repositories.schedule_repo import ScheduleRepository

from .actual_excel import build_actual_template_workbook, read_actual_workbook_rows
from .actual_import import ResourceDispatchActualImportPreviewer, preview_payload, preview_token
from .actual_records import (
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
    plan_identity_from_context,
    planned_event_count,
    resource_label,
    task_code_from_parts,
    task_display_name,
    text,
)
from .actual_tokens import idempotency_key, manual_plan_token
from .execution_service import ResourceDispatchExecutionService


def _not_current_official_plan_error() -> AppError:
    details = {"reason": "not_current_official_plan", "can_retry": False}
    return AppError(
        ErrorCode.SCHEDULE_CONFLICT,
        "当前不是最新正式采用方案，不能填写现场记录。",
        details=details,
    )


class ResourceDispatchActualRecordService:
    def __init__(self, conn, logger=None, op_logger=None, *, execution_service=None, feedback_service=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.execution_service = execution_service or ResourceDispatchExecutionService(
            conn,
            logger=logger,
            op_logger=op_logger,
        )
        self.feedback_service = feedback_service or OperationExecutionFeedbackService(
            conn,
            logger=logger,
            op_logger=op_logger,
        )
        self.previewer = ResourceDispatchActualImportPreviewer(
            self.feedback_service, replay_checker=self._import_plan_is_full_replay)
        self.schedule_repo = ScheduleRepository(conn, logger=logger)
        self.batch_operation_repo = BatchOperationRepository(conn, logger=logger)
        self.plan_query_service = getattr(self.execution_service, "plan_query_service", None) or SchedulePlanQueryService(conn, logger=logger)

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
        return self._write_preview(preview)

    def confirm_import(self, rows: Sequence[Mapping[str, Any]], preview_token_value: Any, **query_kwargs: Any) -> Dict[str, Any]:
        raw_rows = [dict(row) for row in rows or []]
        preview = self._preview_raw_rows(raw_rows, **query_kwargs)
        expected_token = preview_token(preview.raw_rows, query_kwargs)
        if not same(preview_token_value, expected_token):
            raise ValidationError("导入内容已经变化，请重新上传 Excel 并检查后再确认导入。", field="preview_token")
        if not preview.summary.get("can_confirm"):
            raise ValidationError("导入预览还有错误，请先修改 Excel 后重新上传检查。", field="file")
        return self._write_preview(preview)

    def _write_preview(self, preview: PreviewResult) -> Dict[str, Any]:
        written = 0
        skipped = int(preview.summary.get("skip_count") or 0)
        with self.feedback_service.tx_manager.transaction(begin_immediate=True):
            for plan in preview.task_plans:
                if planned_event_count(plan) <= 0:
                    continue
                import_token = "import:" + manual_plan_token(plan)
                if self._plan_is_full_replay(plan, import_token):
                    revision = self._first_replay_revision(plan, import_token)
                    plan = replace(plan, task=replace(plan.task, expected_state_revision=revision))
                    import_token = "import:" + manual_plan_token(plan)
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
        token = self._submission_token(payload, plan)
        messages: List[str] = []
        if not self._plan_is_full_replay(plan, token):
            self.previewer.validator.validate_task_plan(plan, messages)
            if messages:
                raise ValidationError(messages[0], field="actual_record", details={"messages": messages})
        with self.feedback_service.tx_manager.transaction(begin_immediate=True):
            return self._apply_task_plan(plan, import_token=token)

    def actual_payload_replay_state_revision(self, context: ExecutionFeedbackContext, payload: Mapping[str, Any]) -> Optional[str]:
        task = self._task_ref_from_feedback_context(context)
        plan = self._task_plan_from_actual_payload(task, payload, row_number=1)
        token = self._submission_token(payload, plan)
        if not self._plan_is_full_replay(plan, token):
            return None
        return self._first_replay_revision(plan, token)

    @staticmethod
    def _submission_token(payload: Mapping[str, Any], plan: TaskPlan) -> str:
        value = payload.get("idempotency_key")
        if value is None or (type(value) is str and not value.strip()):
            return manual_plan_token(plan)
        if type(value) is not str:
            raise ValidationError("重复提交标记格式不正确，请刷新任务后再提交。", field="idempotency_key")
        return "client:" + value.strip()

    def _import_plan_is_full_replay(self, plan: TaskPlan) -> bool:
        return self._plan_is_full_replay(plan, "import:" + manual_plan_token(plan))

    def _first_replay_revision(self, plan: TaskPlan, token: str) -> str:
        for key in self._plan_idempotency_keys(plan, token):
            event = self.feedback_service.get_event_by_idempotency_key(key)
            if event is not None:
                revision = getattr(event, "previous_state_revision", None)
                if type(revision) is str and revision:
                    return revision
        raise AppError(ErrorCode.NOT_FOUND, "原现场提交的状态版本缺失，请核对保存记录。", details={"reason": "event_revision_missing"})

    def _preview_raw_rows(self, raw_rows: Sequence[Mapping[str, Any]], **query_kwargs: Any):
        context = self._execution_context_for_write(**query_kwargs)
        return self.previewer.preview(raw_rows, self._task_refs_from_context(context))

    def _execution_context_for_write(self, **query_kwargs: Any) -> Dict[str, Any]:
        context = self.execution_service.get_execution_context(**query_kwargs)
        identity = context.get("plan_identity") if isinstance(context, dict) else {}
        if not bool((identity or {}).get("can_write_feedback")):
            raise _not_current_official_plan_error()
        return context

    def _ensure_context_can_write(self, context: ExecutionFeedbackContext) -> None:
        is_official_schedule = (
            text(context.requested_plan_role) == ROLE_ADOPTED
            and text(context.effective_plan_role) == ROLE_ADOPTED
            and text(context.source_table) == SOURCE_SCHEDULE
            and not text(context.scenario_id)
        )
        if not is_official_schedule:
            raise _not_current_official_plan_error()
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
        identity = plan_identity_from_context(context)
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
            schedule_version=int(identity["version"]),
            schedule_id=schedule_id,
            op_id=op_id,
            batch_id=batch_id,
            requested_plan_role=str(identity["requested_plan_role"]),
            source_table=str(identity["source_table"]),
            effective_plan_role=str(identity["effective_plan_role"]),
            scenario_id=identity["scenario_id"],
            op_name=op_name,
            planned_machine_id=text(row.get("machine_id") or row.get("planned_machine_id")),
            planned_machine_label=planned_machine_label,
            planned_operator_id=text(row.get("operator_id") or row.get("planned_operator_id")),
            planned_operator_label=planned_operator_label,
            state=state,
            expected_state_revision=state.state_revision,
        )

    def _task_ref_from_feedback_context(self, context: ExecutionFeedbackContext) -> TaskRef:
        schedule = self.schedule_repo.get(int(context.schedule_id))
        batch_op = self.batch_operation_repo.get(int(context.op_id))
        if schedule is None or batch_op is None:
            raise AppError(ErrorCode.NOT_FOUND, "当前任务不存在，请刷新后重试。", details={"reason": "not_found"})
        state = state_for_feedback_context(self.feedback_service, context)
        batch_id = text(getattr(batch_op, "batch_id", None) or context.batch_id)
        op_name = text(getattr(batch_op, "op_code", None)) or f"工序{text(getattr(batch_op, 'seq', None))}"
        machine_id = text(getattr(schedule, "machine_id", None))
        operator_id = text(getattr(schedule, "operator_id", None))
        source_row = {
            "schedule_id": getattr(schedule, "id", None), "op_id": getattr(schedule, "op_id", None),
            "op_code": op_name, "batch_id": batch_id,
            "start_time": getattr(schedule, "start_time", ""), "end_time": getattr(schedule, "end_time", ""),
            "machine_id": machine_id, "operator_id": operator_id,
        }
        task_id = self.plan_query_service.task_id_for_row(source_row,
            version=int(context.schedule_version), source_table=text(context.source_table),
            candidate_id=None, scenario_id=text(context.scenario_id) or None,
            effective_plan_role=text(context.effective_plan_role))
        return TaskRef(
            task_code=task_code_from_parts(
                batch_id=batch_id,
                op_name=op_name,
                planned_start_time=getattr(schedule, "start_time", ""),
                planned_machine_label=machine_id,
                public_task_id=task_id,
            ),
            schedule_version=int(context.schedule_version),
            schedule_id=int(context.schedule_id),
            op_id=int(context.op_id),
            batch_id=batch_id,
            requested_plan_role=text(context.requested_plan_role),
            source_table=text(context.source_table),
            effective_plan_role=text(context.effective_plan_role),
            scenario_id=text(context.scenario_id) or None,
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
        current_state = state_for_task_ref(self.feedback_service, plan.task)
        event_keys = self._event_keys(plan, import_token)
        context = ExecutionFeedbackContext(
            schedule_version=plan.task.schedule_version,
            schedule_id=plan.task.schedule_id,
            op_id=plan.task.op_id,
            batch_id=plan.task.batch_id,
            expected_state_revision=text(plan.task.expected_state_revision),
            created_by=plan.feedback_person,
            idempotency_key=event_keys.get("actual") or idempotency_key(
                import_token, self._task_event_identity(plan.task), "actual", plan.row_number),
            requested_plan_role=plan.task.requested_plan_role,
            source_table=plan.task.source_table,
            effective_plan_role=plan.task.effective_plan_role,
            scenario_id=plan.task.scenario_id,
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
            written += int(not result.idempotency_reused)
            context = replace(context, expected_state_revision=self._revision_for_next_event(result))
            current_state = result.state
        if current_state.current_status == "not_started" and not plan.actual_start_time:
            raise ValidationError("填写暂停、异常或完工前，请先填写实际开工。", field="actual_start_time")
        for index, pause in enumerate(ordered_pauses(plan)):
            pause_result, result = self._apply_pause(context, pause, index, event_keys)
            written += int(not pause_result.idempotency_reused) + int(not result.idempotency_reused)
            context = replace(context, expected_state_revision=self._revision_for_next_event(result))
            current_state = result.state
        if plan.exception_time:
            context = replace(
                context,
                created_by=plan.feedback_person,
                idempotency_key=event_keys["exception"],
            )
            result = self.feedback_service.report_exception(
                context,
                event_time=plan.exception_time,
                reason_code=plan.exception_reason_code,
                severity=plan.exception_severity,
                remark=plan.exception_remark,
                reason_detail=plan.exception_remark,
            )
            written += int(not result.idempotency_reused)
            context = replace(context, expected_state_revision=self._revision_for_next_event(result))
        if plan.actual_finish_time:
            context = replace(
                context,
                created_by=plan.feedback_person,
                idempotency_key=event_keys["finish"],
            )
            result = self.feedback_service.finish_operation(
                context,
                event_time=plan.actual_finish_time,
                quantity_done=plan.quantity_done,
                quantity_scrapped=plan.quantity_scrapped,
                remark=plan.remark,
            )
            written += int(not result.idempotency_reused)
        if result is None:
            state = state_for_task_ref(self.feedback_service, plan.task)
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
        events = self.feedback_service.list_execution_events_for_scope(operation_execution_scope_from_event(event))
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
        return all(self.feedback_service.has_event_by_idempotency_key(key) for key in keys)

    def _plan_idempotency_keys(self, plan: TaskPlan, import_token: str) -> List[str]:
        return list(self._event_keys(plan, import_token).values())

    @staticmethod
    def _task_event_identity(task: TaskRef) -> Dict[str, Any]:
        return {key: getattr(task, key) for key in (
            "schedule_version", "schedule_id", "op_id", "batch_id", "source_table", "effective_plan_role", "scenario_id")}

    def _event_keys(self, plan: TaskPlan, import_token: Optional[str]) -> Dict[str, str]:
        """Restore original keys from persisted events without recomputing them."""
        slots = []
        if plan.actual_start_time:
            slots.append(("actual", "start", plan.actual_start_time, plan.row_number))
        for index, pause in enumerate(ordered_pauses(plan)):
            slots.append((f"pause-{index}", "pause", pause.start_time, pause.row_number))
            slots.append((f"resume-{index}", "resume", pause.end_time, pause.row_number))
        if plan.exception_time:
            slots.append(("exception", "exception", plan.exception_time, plan.row_number))
        if plan.actual_finish_time:
            slots.append(("finish", "finish", plan.actual_finish_time, plan.row_number))
        identity = self._task_event_identity(plan.task)
        keys = {slot: idempotency_key(import_token, identity, slot, row_number)
                for slot, _, _, row_number in slots}
        if not slots or str(import_token or "").startswith("client:"):
            return keys
        source = "import:manual:" if str(import_token or "").startswith("import:manual:") else "manual:"
        if not str(import_token or "").startswith(source):
            return keys
        if all(self.feedback_service.has_event_by_idempotency_key(key) for key in keys.values()):
            return keys
        events = events_for_task_ref(self.feedback_service, plan.task)
        restored = []
        first_slot, first_type, first_time, first_row = slots[0]
        for index, event in enumerate(events):
            if not self._matches_event_slot(event, first_type, first_time):
                continue
            revision = getattr(event, "previous_state_revision", None)
            if type(revision) is not str or not revision:
                continue
            original_token = source + revision
            if same(getattr(event, "idempotency_key", None),
                    idempotency_key(original_token, identity, first_slot, first_row)):
                restored.append({slot: idempotency_key(original_token, identity, slot, row_number)
                                 for slot, _, _, row_number in slots})
                continue
            # Legacy digests retain no submission field. A complete contiguous
            # saved event chain and its original revisions establish a replay.
            group = events[index:index + len(slots)]
            if len(group) != len(slots) or any(
                re.fullmatch(r"resource-dispatch-actual-[0-9a-f]{16}", text(item.idempotency_key)) is None
                or not self._matches_event_slot(item, slot[1], slot[2])
                for item, slot in zip(group, slots)
            ):
                continue
            if any(not same(item.previous_state_revision,
                            f"{plan.task.op_id}:{index + offset}:{group[offset - 1].id}")
                   for offset, item in enumerate(group) if offset > 0):
                continue
            final_revision = f"{plan.task.op_id}:{index + len(group)}:{group[-1].id}"
            if not (same(plan.task.expected_state_revision, revision)
                    or (index + len(group) == len(events) and same(plan.task.expected_state_revision, final_revision))):
                continue
            restored.append({slot[0]: item.idempotency_key for item, slot in zip(group, slots)})
        if len(restored) > 1:
            raise AppError(ErrorCode.SCHEDULE_CONFLICT, "原现场事件存在多个对应记录，请核对保存记录。",
                           details={"reason": "actual_event_identity_ambiguous"})
        return restored[0] if restored else keys

    @staticmethod
    def _matches_event_slot(event: Any, event_type: str, event_time: str) -> bool:
        return (same(getattr(event, "event_type", None), event_type)
                and same(datetime_text(getattr(event, "event_time", None), field_label="现场记录时间"), event_time))

    def _apply_pause(
        self,
        context: ExecutionFeedbackContext,
        pause: PausePlan,
        index: int,
        event_keys: Mapping[str, str],
    ) -> Any:
        context = replace(
            context,
            created_by=pause.feedback_person,
            idempotency_key=event_keys[f"pause-{index}"],
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
            idempotency_key=event_keys[f"resume-{index}"],
        )
        resume_result = self.feedback_service.resume_operation(context, event_time=pause.end_time, remark=pause.remark)
        return pause_result, resume_result

__all__ = ["ResourceDispatchActualRecordService"]
