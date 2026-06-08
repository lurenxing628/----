from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any, Dict, List, Optional, Sequence

from core.infrastructure.errors import AppError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.operation_execution_event import (
    EXECUTION_ACTION_REPORT_EXCEPTION,
    EXECUTION_EVENT_EXCEPTION,
    EXECUTION_EVENT_FINISH,
    EXECUTION_EVENT_PAUSE,
    EXECUTION_EVENT_START,
    OperationExecutionEvent,
    validate_operation_execution_event_transition,
)
from core.models.operation_execution_scope import OperationExecutionScope
from core.models.operation_execution_state import OperationExecutionState
from core.models.schedule_plan_role import ROLE_ADOPTED, SOURCE_SCHEDULE
from core.shared.field_labels import display_field_label
from data.repositories.batch_operation_repo import BatchOperationRepository
from data.repositories.machine_repo import MachineRepository
from data.repositories.operation_execution_event_repo import OperationExecutionEventRepo
from data.repositories.operator_repo import OperatorRepository
from data.repositories.schedule_repo import ScheduleRepository

from .operation_execution_feedback_actions import OperationExecutionFeedbackActionsMixin
from .operation_execution_feedback_support import (
    _ACTION_PAYLOAD_FIELDS,
    _REPORTED_STATUS_BY_ACTION,
    ExecutionFeedbackContext,
    ExecutionFeedbackResult,
    _conflict,
    _event_public_tuple,
    _invalid_field_value,
    _non_negative_int,
    _normalize_feedback_datetime,
    _optional_int,
    _optional_non_negative_int,
    _optional_text,
    _parse_feedback_datetime,
    _positive_int,
    _required_non_negative_int,
    _required_text,
    _scope_for_context,
    _state_for_context,
    _text,
    _validate_known_value,
)
from .operation_execution_labels import (
    HANDLING_STATUS_LABELS,
    REASON_LABELS,
    SEVERITY_LABELS,
    action_to_event_type,
    event_type_to_action,
    execution_action_label,
    public_execution_remark,
)
from .schedule_plan_query_service import SchedulePlanQueryService


class OperationExecutionFeedbackService(OperationExecutionFeedbackActionsMixin):
    def __init__(self, conn: sqlite3.Connection, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.tx_manager = TransactionManager(conn)
        self.event_repo = OperationExecutionEventRepo(conn, logger=logger)
        self.schedule_repo = ScheduleRepository(conn, logger=logger)
        self.batch_operation_repo = BatchOperationRepository(conn, logger=logger)
        self.machine_repo = MachineRepository(conn, logger=logger)
        self.operator_repo = OperatorRepository(conn, logger=logger)
        self.plan_query_service = SchedulePlanQueryService(conn, logger=logger)

    def get_execution_state(self, op_ids: Sequence[int]) -> Dict[int, OperationExecutionState]:
        raise ValidationError("现场执行状态必须按完整计划身份读取，不能只按 op_id 聚合。", field="operation_execution_scope")

    def get_execution_state_for_scopes(self, scopes: Sequence[OperationExecutionScope]) -> Dict[OperationExecutionScope, OperationExecutionState]:
        return self.event_repo.aggregate_states_by_scopes(scopes)

    def list_execution_events_for_scope(self, scope: OperationExecutionScope) -> List[OperationExecutionEvent]:
        return self.event_repo.list_events_by_scope(scope)

    def get_event_by_idempotency_key(self, idempotency_key: str) -> Optional[OperationExecutionEvent]:
        return self.event_repo.get_by_idempotency_key(idempotency_key)

    def has_event_by_idempotency_key(self, idempotency_key: str) -> bool:
        return self.get_event_by_idempotency_key(idempotency_key) is not None

    def list_execution_events(self, op_id: int) -> List[OperationExecutionEvent]:
        raise ValidationError("现场执行事件必须按完整计划身份读取，不能只按 op_id 查询。", field="operation_execution_scope")

    def record_event(self, context: ExecutionFeedbackContext, *, action: str, **payload: Any) -> ExecutionFeedbackResult:
        normalized_context = self._normalize_context(context)
        normalized_action = self._normalize_action(action)
        normalized_payload = self._normalize_payload(normalized_action, payload)
        fingerprint = self._request_fingerprint(normalized_context, normalized_action, normalized_payload)

        existing = self.event_repo.get_by_idempotency_key(normalized_context.idempotency_key)
        if existing is not None:
            return self._resolve_idempotent_existing(
                existing,
                context=normalized_context,
                action=normalized_action,
                payload=normalized_payload,
                fingerprint=fingerprint,
            )

        with self.tx_manager.transaction(begin_immediate=True):
            existing = self.event_repo.get_by_idempotency_key(normalized_context.idempotency_key)
            if existing is not None:
                return self._resolve_idempotent_existing(
                    existing,
                    context=normalized_context,
                    action=normalized_action,
                    payload=normalized_payload,
                    fingerprint=fingerprint,
                )
            schedule, batch_op = self._load_current_official_schedule(normalized_context)
            current_state = _state_for_context(self.event_repo, normalized_context)
            if current_state.state_revision != normalized_context.expected_state_revision:
                raise _conflict(
                    "stale_state_revision",
                    details={
                        "expected_state_revision": normalized_context.expected_state_revision,
                        "current_state_revision": current_state.state_revision,
                    },
                )
            self._validate_state_transition(current_state, normalized_action)
            self._validate_event_time_sequence(current_state, normalized_action, normalized_payload.get("event_time"))
            self._validate_payload_against_plan(
                action=normalized_action,
                payload=normalized_payload,
                schedule=schedule,
            )
            event_payload = self._build_event_payload(
                context=normalized_context,
                schedule=schedule,
                batch_id=str(batch_op.batch_id or ""),
                action=normalized_action,
                payload=normalized_payload,
                fingerprint=fingerprint,
            )
            try:
                event = self.event_repo.insert_event(event_payload)
            except AppError as exc:
                return self._handle_unique_insert_error(
                    exc,
                    context=normalized_context,
                    action=normalized_action,
                    payload=normalized_payload,
                    fingerprint=fingerprint,
                )
            state = _state_for_context(self.event_repo, normalized_context)
            return ExecutionFeedbackResult(
                event=event,
                state=state,
                idempotency_reused=False,
                state_revision=state.state_revision,
            )

    def _validate_state_transition(self, state: OperationExecutionState, action: str) -> None:
        current_status = state.current_status
        try:
            validate_operation_execution_event_transition(
                current_status=current_status,
                event_type=action_to_event_type(action),
            )
        except ValueError as exc:
            raise _conflict(
                "invalid_state_transition",
                details={
                    "current_status": current_status,
                    "current_status_label": state.current_status_label,
                    "action": action,
                    "action_label": execution_action_label(action),
                },
            ) from exc

    def _handle_unique_insert_error(
        self,
        exc: AppError,
        *,
        context: ExecutionFeedbackContext,
        action: str,
        payload: Dict[str, Any],
        fingerprint: str,
    ) -> ExecutionFeedbackResult:
        if exc.code != ErrorCode.DUPLICATE_ENTRY:
            raise exc
        existing = self.event_repo.get_by_idempotency_key(context.idempotency_key)
        if existing is not None:
            return self._resolve_idempotent_existing(
                existing,
                context=context,
                action=action,
                payload=payload,
                fingerprint=fingerprint,
            )
        current_revision = self.event_repo.state_revision_for_scope(_scope_for_context(context))
        raise _conflict(
            "stale_state_revision",
            details={
                "expected_state_revision": context.expected_state_revision,
                "current_state_revision": current_revision,
            },
        )

    def _resolve_idempotent_existing(
        self,
        existing: OperationExecutionEvent,
        *,
        context: ExecutionFeedbackContext,
        action: str,
        payload: Dict[str, Any],
        fingerprint: str,
    ) -> ExecutionFeedbackResult:
        schedule, batch_op = self._load_current_official_schedule(context)
        expected_event = OperationExecutionEvent.from_row(
            self._build_event_payload(
                context=context,
                schedule=schedule,
                batch_id=str(batch_op.batch_id or ""),
                action=action,
                payload=payload,
                fingerprint=fingerprint,
            )
        )
        if existing.request_fingerprint != fingerprint or _event_public_tuple(existing) != _event_public_tuple(expected_event):
            raise _conflict("idempotency_conflict")
        state = _state_for_context(self.event_repo, context)
        return ExecutionFeedbackResult(
            event=existing,
            state=state,
            idempotency_reused=True,
            state_revision=state.state_revision,
        )

    def _normalize_context(self, context: ExecutionFeedbackContext) -> ExecutionFeedbackContext:
        schedule_version = _positive_int(context.schedule_version, "schedule_version")
        schedule_id = _positive_int(context.schedule_id, "schedule_id")
        op_id = _positive_int(context.op_id, "op_id")
        batch_id = _required_text(context.batch_id, "batch_id")
        created_by = _optional_text(context.created_by) or "未填写反馈人"
        idempotency_key = _required_text(context.idempotency_key, "idempotency_key")
        expected_state_revision = _required_text(context.expected_state_revision, "expected_state_revision")
        requested_plan_role = _required_text(context.requested_plan_role, "requested_plan_role")
        source_table = _required_text(context.source_table, "source_table")
        effective_plan_role = _required_text(context.effective_plan_role, "effective_plan_role")
        return ExecutionFeedbackContext(
            schedule_version=schedule_version,
            schedule_id=schedule_id,
            op_id=op_id,
            batch_id=batch_id,
            expected_state_revision=expected_state_revision,
            created_by=created_by,
            idempotency_key=idempotency_key,
            requested_plan_role=requested_plan_role,
            source_table=source_table,
            effective_plan_role=effective_plan_role,
            scenario_id=_optional_text(context.scenario_id),
        )

    def _normalize_action(self, action: Any) -> str:
        text = _text(action)
        normalized = event_type_to_action(action_to_event_type(text))
        if normalized not in _REPORTED_STATUS_BY_ACTION:
            raise ValidationError(
                "现场反馈操作不正确，请刷新后重试。",
                field="action",
                details={"reason": "invalid_field_value", "action": text, "action_label": execution_action_label(text)},
            )
        return normalized

    def _normalize_payload(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        out = {field: payload.get(field) for field in _ACTION_PAYLOAD_FIELDS}
        out["event_time"] = _normalize_feedback_datetime(_required_text(out.get("event_time"), "event_time"))
        out["actual_machine_id"] = _optional_text(out.get("actual_machine_id"))
        out["actual_operator_id"] = _optional_text(out.get("actual_operator_id"))
        out["reason_code"] = _optional_text(out.get("reason_code"))
        out["reason_detail"] = _optional_text(out.get("reason_detail"))
        out["severity"] = _optional_text(out.get("severity"))
        out["affected_machine_id"] = _optional_text(out.get("affected_machine_id"))
        out["affected_operator_id"] = _optional_text(out.get("affected_operator_id"))
        out["handling_status"] = _optional_text(out.get("handling_status"))
        out["suggest_reschedule"] = self._normalize_suggest_reschedule(out.get("suggest_reschedule"))
        internal_tokens = {
            action,
            action_to_event_type(action),
            out.get("reason_code"),
            out.get("severity"),
            out.get("handling_status"),
        }
        out["remark"] = public_execution_remark(out.get("remark"), internal_tokens=internal_tokens) or None
        out["reason_detail"] = public_execution_remark(out.get("reason_detail"), internal_tokens=internal_tokens) or None
        if action in (EXECUTION_EVENT_PAUSE, EXECUTION_ACTION_REPORT_EXCEPTION):
            out["reason_code"] = _required_text(out.get("reason_code"), "reason_code")
            if not out.get("remark") and out.get("reason_detail"):
                out["remark"] = out.get("reason_detail")
            if not (_optional_text(out.get("reason_detail")) or _optional_text(out.get("remark"))):
                _required_text(out.get("remark"), "remark")
        if action == EXECUTION_ACTION_REPORT_EXCEPTION:
            out["severity"] = _required_text(out.get("severity"), "severity")
        _validate_known_value(out.get("reason_code"), "reason_code", REASON_LABELS)
        _validate_known_value(out.get("severity"), "severity", SEVERITY_LABELS)
        _validate_known_value(out.get("handling_status"), "handling_status", HANDLING_STATUS_LABELS)
        if action == EXECUTION_EVENT_FINISH:
            out["quantity_done"] = _required_non_negative_int(out.get("quantity_done"), "quantity_done")
            out["quantity_scrapped"] = (
                0 if out.get("quantity_scrapped") is None or _text(out.get("quantity_scrapped")) == ""
                else _non_negative_int(out.get("quantity_scrapped"), "quantity_scrapped")
            )
        else:
            out["quantity_done"] = _optional_int(out.get("quantity_done"), "quantity_done")
            out["quantity_scrapped"] = _optional_int(out.get("quantity_scrapped"), "quantity_scrapped")
        out["impact_minutes"] = _optional_non_negative_int(out.get("impact_minutes"), "impact_minutes")
        if action == EXECUTION_EVENT_START:
            _required_text(out.get("actual_operator_id"), "operator_id")
            _required_text(out.get("actual_machine_id"), "machine_id")
        return out

    def _normalize_suggest_reschedule(self, value: Any) -> int:
        if value is None or _text(value) == "":
            return 0
        text = _text(value).lower()
        if text in ("yes", "true", "1"):
            return 1
        if text in ("no", "false", "0"):
            return 0
        raise ValidationError(
            f"{display_field_label('suggest_reschedule')}填写不正确，请检查后重试。",
            field="suggest_reschedule",
            details={
                "reason": "invalid_field_value",
                "field": "suggest_reschedule",
                "field_label": display_field_label("suggest_reschedule"),
            },
        )

    def _request_fingerprint(
        self,
        context: ExecutionFeedbackContext,
        action: str,
        payload: Dict[str, Any],
    ) -> str:
        raw = {
            "context": {
                "schedule_version": int(context.schedule_version),
                "schedule_id": int(context.schedule_id),
                "op_id": int(context.op_id),
                "batch_id": context.batch_id,
                "expected_state_revision": context.expected_state_revision,
                "created_by": context.created_by,
                "requested_plan_role": context.requested_plan_role,
                "source_table": context.source_table,
                "effective_plan_role": context.effective_plan_role,
                "scenario_id": context.scenario_id,
            },
            "action": action,
            "payload": payload,
        }
        text = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    # 现场事实写闸在这里：只有当前正式 schedule/adopted、无 scenario，且 plan_identity 允许回写时才继续。
    def _load_current_official_schedule(self, context: ExecutionFeedbackContext):
        if (
            context.requested_plan_role != ROLE_ADOPTED
            or context.effective_plan_role != ROLE_ADOPTED
            or context.source_table != SOURCE_SCHEDULE
            or context.scenario_id is not None
        ):
            raise _conflict("not_current_official_plan")
        resolution = self.plan_query_service.resolve_plan_view(
            int(context.schedule_version),
            context.requested_plan_role,
            context.scenario_id,
        )
        plan_identity = resolution.plan_identity
        if plan_identity is None or not bool(plan_identity.can_write_feedback):
            raise _conflict("not_current_official_plan")
        schedule = self.schedule_repo.get(context.schedule_id)
        if schedule is None:
            raise AppError(ErrorCode.NOT_FOUND, "排程记录不存在，请刷新后重试。", details={"reason": "not_found"})
        batch_op = self.batch_operation_repo.get(context.op_id)
        if batch_op is None:
            raise AppError(ErrorCode.NOT_FOUND, "工序记录不存在，请刷新后重试。", details={"reason": "not_found"})
        schedule_mismatch = (
            int(schedule.version) != int(context.schedule_version)
            or int(schedule.id or 0) != int(context.schedule_id)
            or int(schedule.op_id or 0) != int(context.op_id)
            or _text(batch_op.batch_id) != context.batch_id
        )
        if schedule_mismatch:
            raise _conflict("schedule_mismatch")
        return schedule, batch_op

    def _validate_event_time_sequence(self, state: OperationExecutionState, action: str, event_time: Any) -> None:
        event_dt = _parse_feedback_datetime(event_time)
        last_event_time = _optional_text(state.last_event_time)
        if last_event_time:
            last_event_dt = _parse_feedback_datetime(last_event_time)
            if event_dt < last_event_dt:
                raise _conflict(
                    "invalid_state_transition",
                    details={
                        "current_status": state.current_status,
                        "current_status_label": state.current_status_label,
                        "action": action,
                        "action_label": execution_action_label(action),
                    },
                    message="反馈时间不能早于上一条现场反馈时间，请刷新后重试。",
                )
        if action == EXECUTION_EVENT_FINISH and state.actual_start_time:
            start_dt = _parse_feedback_datetime(state.actual_start_time)
            if event_dt < start_dt:
                raise _conflict(
                    "invalid_state_transition",
                    details={
                        "current_status": state.current_status,
                        "current_status_label": state.current_status_label,
                        "action": action,
                        "action_label": execution_action_label(action),
                    },
                    message="完工时间不能早于实际开工时间，请检查后再提交。",
                )

    def _validate_payload_against_plan(self, *, action: str, payload: Dict[str, Any], schedule: Any) -> None:
        if action == EXECUTION_EVENT_START:
            self._validate_start_payload_against_plan(payload=payload, schedule=schedule)
            return
        if action == EXECUTION_ACTION_REPORT_EXCEPTION:
            self._validate_exception_payload_against_plan(payload=payload)

    def _validate_start_payload_against_plan(self, *, payload: Dict[str, Any], schedule: Any) -> None:
        operator_id = _required_text(payload.get("actual_operator_id"), "operator_id")
        machine_id = _required_text(payload.get("actual_machine_id"), "machine_id")
        if not self.operator_repo.exists(operator_id):
            raise _invalid_field_value("operator_id", "请选择有效的操作人员。")
        if not self.machine_repo.exists(machine_id):
            raise _invalid_field_value("machine_id", "请选择有效的设备。")
        planned_machine_id = _text(getattr(schedule, "machine_id", ""))
        if not planned_machine_id or machine_id != planned_machine_id:
            raise _invalid_field_value("machine_id", "请选择当前正式排程记录里的设备。")

    def _validate_exception_payload_against_plan(self, *, payload: Dict[str, Any]) -> None:
        affected_machine_id = _optional_text(payload.get("affected_machine_id"))
        affected_operator_id = _optional_text(payload.get("affected_operator_id"))
        if affected_machine_id and not self.machine_repo.exists(affected_machine_id):
            raise _invalid_field_value("affected_machine_id", "请选择有效的影响设备。")
        if affected_operator_id and not self.operator_repo.exists(affected_operator_id):
            raise _invalid_field_value("affected_operator_id", "请选择有效的影响人员。")

    def _build_event_payload(
        self,
        *,
        context: ExecutionFeedbackContext,
        schedule: Any,
        batch_id: str,
        action: str,
        payload: Dict[str, Any],
        fingerprint: str,
    ) -> Dict[str, Any]:
        event_type = action_to_event_type(action)
        return {
            "schedule_version": context.schedule_version,
            "schedule_id": context.schedule_id,
            "op_id": context.op_id,
            "batch_id": batch_id,
            # 写入前最终消毒：现场事件永远落到正式 schedule/adopted/no-scenario 身份。
            "source_table": SOURCE_SCHEDULE,
            "effective_plan_role": ROLE_ADOPTED,
            "scenario_id": None,
            "event_type": event_type,
            "reported_status": _REPORTED_STATUS_BY_ACTION[action],
            "event_time": payload.get("event_time"),
            "actual_machine_id": payload.get("actual_machine_id"),
            "actual_operator_id": payload.get("actual_operator_id"),
            "quantity_done": payload.get("quantity_done"),
            "quantity_scrapped": payload.get("quantity_scrapped"),
            "reason_code": payload.get("reason_code"),
            "reason_detail": payload.get("reason_detail"),
            "severity": payload.get("severity"),
            "impact_minutes": payload.get("impact_minutes"),
            "affected_machine_id": payload.get("affected_machine_id"),
            "affected_operator_id": payload.get("affected_operator_id"),
            "handling_status": payload.get("handling_status"),
            "suggest_reschedule": payload.get("suggest_reschedule"),
            "remark": payload.get("remark"),
            "created_by": context.created_by,
            "idempotency_key": context.idempotency_key,
            "request_fingerprint": fingerprint,
            "previous_state_revision": context.expected_state_revision,
        }

__all__ = ("ExecutionFeedbackContext", "ExecutionFeedbackResult", "OperationExecutionFeedbackService")
