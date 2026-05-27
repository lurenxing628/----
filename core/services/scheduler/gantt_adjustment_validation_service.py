from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.infrastructure.errors import ValidationError
from core.models.schedule_adjustment import DRAFT_STATUS_EDITING
from data.repositories import BatchRepository, MachineDowntimeRepository, ScheduleAdjustmentRepository

from .calendar_service import CalendarService
from .gantt_adjustment_projection import (
    AdjustmentIssue,
    AdjustmentPlanRow,
    build_adjusted_plan_rows,
    find_due_date_warnings,
    find_precedence_violations,
    find_resource_conflicts,
    result_message,
    result_status,
)
from .schedule_plan_query_service import SchedulePlanQueryService


@dataclass(frozen=True)
class GanttAdjustmentEvaluation:
    draft: Any
    changes: Sequence[Any]
    plan_resolution: Any
    adjusted_rows: Sequence[AdjustmentPlanRow]
    issues: Sequence[AdjustmentIssue]
    status: str

    @property
    def can_apply(self) -> bool:
        return self.status != "blocked"

    def to_response(self) -> Dict[str, Any]:
        return {
            "draft_id": self.draft.draft_id,
            "base_version": self.draft.base_version,
            "base_plan_role": self.draft.base_plan_role,
            "status": self.status,
            "can_apply": self.can_apply,
            "message": result_message(self.status),
            "issue_count": len(self.issues),
            "issues": [issue.to_dict() for issue in self.issues],
        }


class GanttAdjustmentValidationService:
    """甘特图 Draft 调整校验服务：只读正式排产，返回内存试算结果。"""

    def __init__(self, conn, logger=None):
        self.conn = conn
        self.logger = logger
        self.draft_repo = ScheduleAdjustmentRepository(conn, logger=logger)
        self.batch_repo = BatchRepository(conn, logger=logger)
        self.downtime_repo = MachineDowntimeRepository(conn, logger=logger)
        self.plan_service = SchedulePlanQueryService(conn, logger=logger)
        self.calendar_service = CalendarService(conn, logger=logger)

    def validate_draft(
        self,
        *,
        draft_id: Any,
        expected_base_version: Optional[Any] = None,
        expected_base_plan_role: Optional[Any] = None,
    ) -> Dict[str, Any]:
        return self.evaluate_draft(
            draft_id=draft_id,
            expected_base_version=expected_base_version,
            expected_base_plan_role=expected_base_plan_role,
        ).to_response()

    def evaluate_draft(
        self,
        *,
        draft_id: Any,
        expected_base_version: Optional[Any] = None,
        expected_base_plan_role: Optional[Any] = None,
        allowed_statuses: Tuple[str, ...] = (DRAFT_STATUS_EDITING,),
    ) -> GanttAdjustmentEvaluation:
        draft_key = _required_text(draft_id, field="draft_id", label="草稿编号")
        draft = self.draft_repo.get_draft(draft_key)
        if draft is None:
            raise ValidationError("调整草稿不存在。", field="draft_id")
        if draft.status not in allowed_statuses:
            raise ValidationError(_status_error_message(allowed_statuses), field="draft_id")
        _check_expected_base(draft.base_version, draft.base_plan_role, expected_base_version, expected_base_plan_role)

        changes = self.draft_repo.list_changes(draft.draft_id)
        try:
            resolution = self.plan_service.resolve_existing_plan(draft.base_version, draft.base_plan_role)
        except ValueError as exc:
            raise ValidationError(str(exc), field="base_plan_role") from exc
        base_rows = self.plan_service.list_plan_detail_rows_all_for_resolution(
            version=draft.base_version,
            source_table=resolution.source_table,
            candidate_id=resolution.candidate_id,
        )
        adjusted_rows = build_adjusted_plan_rows(base_rows, changes)
        issues = self._collect_issues(adjusted_rows)
        status = result_status(issues)
        return GanttAdjustmentEvaluation(
            draft=draft,
            changes=changes,
            plan_resolution=resolution,
            adjusted_rows=adjusted_rows,
            issues=issues,
            status=status,
        )

    def _collect_issues(self, rows: Sequence[AdjustmentPlanRow]) -> List[AdjustmentIssue]:
        issues: List[AdjustmentIssue] = []
        issues.extend(find_resource_conflicts(rows))
        issues.extend(find_precedence_violations(rows))
        issues.extend(self._calendar_issues(rows))
        issues.extend(self._downtime_issues(rows))
        issues.extend(find_due_date_warnings(rows))
        issues.extend(self._material_warnings(rows))
        return issues

    def _calendar_issues(self, rows: Sequence[AdjustmentPlanRow]) -> List[AdjustmentIssue]:
        issues: List[AdjustmentIssue] = []
        for row in rows:
            policy = self.calendar_service.policy_for_datetime(row.start, operator_id=row.operator_id)
            window_start, window_end = policy.work_window()
            if policy.shift_hours <= 0 or not policy.is_priority_allowed(row.priority):
                issues.append(_issue("blocker", "calendar_unavailable", row, "目标时间所在日期不可排产。"))
            elif row.start < window_start or row.end > window_end:
                issues.append(_issue("blocker", "calendar_window", row, "目标时间不在允许排产的班次时间内。"))
        return issues

    def _downtime_issues(self, rows: Sequence[AdjustmentPlanRow]) -> List[AdjustmentIssue]:
        issues: List[AdjustmentIssue] = []
        for row in rows:
            if not row.machine_id:
                continue
            if self.downtime_repo.has_overlap(
                row.machine_id,
                row.start.strftime("%Y-%m-%d %H:%M:%S"),
                row.end.strftime("%Y-%m-%d %H:%M:%S"),
            ):
                issues.append(_issue("blocker", "machine_downtime", row, f"设备 {row.machine_id} 在目标时间段有停机记录。"))
        return issues

    def _material_warnings(self, rows: Sequence[AdjustmentPlanRow]) -> List[AdjustmentIssue]:
        batch_ids = sorted({row.batch_id for row in rows if row.batch_id})
        if not batch_ids:
            return []
        status_by_batch = self.batch_repo.list_ready_status_by_batch_ids(batch_ids)
        issues: List[AdjustmentIssue] = []
        for row in rows:
            ready = status_by_batch.get(row.batch_id)
            if ready is None or ready == "":
                issues.append(_issue("warning", "material_status_missing", row, f"批次 {row.batch_id} 没有找到物料齐套状态。"))
                continue
            if ready in ("no", "partial"):
                issues.append(_issue("warning", "material_not_ready", row, f"批次 {row.batch_id} 物料齐套状态是 {ready}。"))
        return issues


def _issue(severity: str, code: str, row: AdjustmentPlanRow, message: str) -> AdjustmentIssue:
    return AdjustmentIssue(severity=severity, code=code, op_id=row.op_id, message=message)


def _required_text(value: Any, *, field: str, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValidationError(f"{label}不能为空。", field=field)
    return text


def _check_expected_base(
    actual_version: int,
    actual_role: str,
    expected_version: Optional[Any],
    expected_role: Optional[Any],
) -> None:
    if expected_version is not None and str(expected_version).strip() != str(actual_version):
        raise ValidationError("页面草稿的调整依据版本已变化，请刷新后重试。", field="base_version")
    if expected_role is not None and str(expected_role).strip() != actual_role:
        raise ValidationError("页面草稿的调整依据方案已变化，请刷新后重试。", field="base_plan_role")


def _status_error_message(allowed_statuses: Sequence[str]) -> str:
    if tuple(allowed_statuses) == (DRAFT_STATUS_EDITING,):
        return "只有编辑中的调整草稿才能校验。"
    return "调整草稿当前状态不能执行本次操作。"
