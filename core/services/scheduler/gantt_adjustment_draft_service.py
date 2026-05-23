from __future__ import annotations

import uuid
from typing import Any, Optional

from core.infrastructure.errors import ValidationError
from core.models.schedule_adjustment import (
    CHANGE_TYPE_CHANGE_RESOURCE,
    CHANGE_TYPE_MOVE_TIME,
    CHANGE_TYPE_RESIZE_TIME,
    DRAFT_STATUS_DISCARDED,
    DRAFT_STATUS_EDITING,
    VALID_CHANGE_TYPES,
    ScheduleAdjustmentChange,
    ScheduleAdjustmentDraft,
)
from core.models.schedule_plan_role import VALID_PLAN_ROLES
from data.repositories import ScheduleAdjustmentRepository, ScheduleHistoryRepository

from .schedule_plan_query_service import SchedulePlanQueryService


def _text(value: Any) -> str:
    return str(value or "").strip()


def _base_version(value: Any) -> int:
    if value is None or isinstance(value, bool) or isinstance(value, float):
        raise ValidationError("基准版本不正确。", field="base_version")
    try:
        version = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("基准版本不正确。", field="base_version") from exc
    if version <= 0:
        raise ValidationError("基准版本必须大于 0。", field="base_version")
    return version


def _plan_role(value: Any) -> str:
    role = _text(value)
    if not role:
        raise ValidationError("基准方案角色不能为空。", field="base_plan_role")
    if role not in VALID_PLAN_ROLES:
        raise ValidationError("基准方案角色不正确。", field="base_plan_role")
    return role


def _change_type(value: Any) -> str:
    kind = _text(value)
    if kind not in VALID_CHANGE_TYPES:
        raise ValidationError("调整类型不正确。", field="change_type")
    return kind


def _op_id(value: Any) -> int:
    if value is None or isinstance(value, bool) or isinstance(value, float):
        raise ValidationError("工序 ID 不正确。", field="op_id")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("工序 ID 不正确。", field="op_id") from exc
    if number <= 0:
        raise ValidationError("工序 ID 必须大于 0。", field="op_id")
    return number


def _draft_id(value: Any) -> str:
    draft_id = _text(value)
    if not draft_id:
        raise ValidationError("草稿编号不能为空。", field="draft_id")
    return draft_id


class GanttAdjustmentDraftService:
    """甘特图模拟调整 Draft 服务，只写草稿表，不写正式排产版本。"""

    def __init__(self, conn, logger=None):
        self.conn = conn
        self.logger = logger
        self.repo = ScheduleAdjustmentRepository(conn, logger=logger)
        self.history_repo = ScheduleHistoryRepository(conn, logger=logger)
        self.plan_service = SchedulePlanQueryService(conn, logger=logger)

    def create_draft(
        self,
        *,
        base_version: Any,
        base_plan_role: Any,
        created_by: Optional[str] = None,
        reason: Optional[str] = None,
        expires_at: Optional[str] = None,
    ) -> ScheduleAdjustmentDraft:
        version = _base_version(base_version)
        role = _plan_role(base_plan_role)
        self._require_base_plan(base_version=version, base_plan_role=role)
        draft = ScheduleAdjustmentDraft(
            draft_id=self._new_draft_id(),
            base_version=version,
            base_plan_role=role,
            status=DRAFT_STATUS_EDITING,
            created_by=_text(created_by) or None,
            reason=_text(reason) or None,
            expires_at=_text(expires_at) or None,
        )
        with self.conn:
            return self.repo.create_draft(draft)

    def record_time_change(
        self,
        *,
        draft_id: str,
        op_id: Any,
        change_type: str = CHANGE_TYPE_MOVE_TIME,
        schedule_id: Optional[int] = None,
        from_start: Optional[str] = None,
        from_end: Optional[str] = None,
        to_start: Optional[str] = None,
        to_end: Optional[str] = None,
    ) -> ScheduleAdjustmentChange:
        draft_key = self._require_editing_draft(draft_id).draft_id
        kind = _change_type(change_type)
        if kind not in (CHANGE_TYPE_MOVE_TIME, CHANGE_TYPE_RESIZE_TIME):
            raise ValidationError("时间调整只能是移动或改时长。", field="change_type")
        with self.conn:
            return self.repo.create_change(
                ScheduleAdjustmentChange(
                    id=None,
                    draft_id=draft_key,
                    schedule_id=schedule_id,
                    op_id=_op_id(op_id),
                    change_type=kind,
                    from_start=_text(from_start) or None,
                    from_end=_text(from_end) or None,
                    to_start=_text(to_start) or None,
                    to_end=_text(to_end) or None,
                )
            )

    def record_resource_change(
        self,
        *,
        draft_id: str,
        op_id: Any,
        schedule_id: Optional[int] = None,
        from_machine_id: Optional[str] = None,
        to_machine_id: Optional[str] = None,
        from_operator_id: Optional[str] = None,
        to_operator_id: Optional[str] = None,
    ) -> ScheduleAdjustmentChange:
        draft_key = self._require_editing_draft(draft_id).draft_id
        with self.conn:
            return self.repo.create_change(
                ScheduleAdjustmentChange(
                    id=None,
                    draft_id=draft_key,
                    schedule_id=schedule_id,
                    op_id=_op_id(op_id),
                    change_type=CHANGE_TYPE_CHANGE_RESOURCE,
                    from_machine_id=_text(from_machine_id) or None,
                    to_machine_id=_text(to_machine_id) or None,
                    from_operator_id=_text(from_operator_id) or None,
                    to_operator_id=_text(to_operator_id) or None,
                )
            )

    def discard_draft(self, *, draft_id: str, reason: Optional[str] = None) -> ScheduleAdjustmentDraft:
        draft_key = _draft_id(draft_id)
        if self.repo.get_draft(draft_key) is None:
            raise ValidationError("调整草稿不存在。", field="draft_id")
        with self.conn:
            return self.repo.update_draft_status(draft_id=draft_key, status=DRAFT_STATUS_DISCARDED, reason=reason)

    def _new_draft_id(self) -> str:
        return "draft-" + uuid.uuid4().hex[:16]

    def _require_editing_draft(self, draft_id: Any) -> ScheduleAdjustmentDraft:
        draft_key = _draft_id(draft_id)
        draft = self.repo.get_draft(draft_key)
        if draft is None:
            raise ValidationError("调整草稿不存在。", field="draft_id")
        if draft.status != DRAFT_STATUS_EDITING:
            raise ValidationError("只有编辑中的调整草稿才能继续记录调整。", field="draft_id")
        return draft

    def _require_base_plan(self, *, base_version: int, base_plan_role: str) -> None:
        if self.history_repo.get_by_version(base_version) is None:
            raise ValidationError("基准版本不存在，不能创建调整草稿。", field="base_version")
        try:
            self.plan_service.resolve_existing_plan(base_version, base_plan_role)
        except ValueError as exc:
            raise ValidationError(str(exc), field="base_plan_role") from exc
