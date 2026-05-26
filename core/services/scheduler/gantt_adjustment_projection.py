from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.infrastructure.errors import ValidationError
from core.models.schedule_adjustment import ScheduleAdjustmentChange
from core.shared.strict_parse import parse_optional_datetime, parse_required_datetime
from data.repositories.schedule_rows import ScheduleDetailRow


@dataclass(frozen=True)
class AdjustmentIssue:
    severity: str
    code: str
    message: str
    op_id: Optional[int] = None
    related_op_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"severity": self.severity, "code": self.code, "message": self.message}
        if self.op_id is not None:
            payload["op_id"] = self.op_id
        if self.related_op_id is not None:
            payload["related_op_id"] = self.related_op_id
        return payload


@dataclass
class AdjustmentPlanRow:
    schedule_id: int
    op_id: int
    batch_id: str
    piece_id: str
    seq: int
    start: datetime
    end: datetime
    machine_id: Optional[str]
    operator_id: Optional[str]
    due_date: Optional[str]
    priority: Optional[str]
    lock_status: Optional[str]
    is_changed: bool = False


def build_adjusted_plan_rows(
    base_rows: Sequence[ScheduleDetailRow],
    changes: Sequence[ScheduleAdjustmentChange],
) -> List[AdjustmentPlanRow]:
    rows_by_op = {int(row.get("op_id") or 0): _plan_row(row) for row in base_rows}
    for change in changes:
        row = rows_by_op.get(int(change.op_id))
        if row is None:
            raise ValidationError("草稿调整指向的工序不在调整依据方案里。", field="op_id")
        _apply_change(row, change)
    return list(rows_by_op.values())


def find_resource_conflicts(rows: Sequence[AdjustmentPlanRow]) -> List[AdjustmentIssue]:
    issues: List[AdjustmentIssue] = []
    for field, label, code in (
        ("machine_id", "设备", "machine_overlap"),
        ("operator_id", "人员", "operator_overlap"),
    ):
        for left, right in _overlap_pairs(rows, field):
            resource_id = getattr(left, field)
            issues.append(
                AdjustmentIssue(
                    severity="blocker",
                    code=code,
                    op_id=left.op_id,
                    related_op_id=right.op_id,
                    message=f"{label} {resource_id} 在目标时间段已经有其他工序。",
                )
            )
    return issues


def find_precedence_violations(rows: Sequence[AdjustmentPlanRow]) -> List[AdjustmentIssue]:
    issues: List[AdjustmentIssue] = []
    grouped: Dict[Tuple[str, str], List[AdjustmentPlanRow]] = {}
    for row in rows:
        grouped.setdefault((row.batch_id, row.piece_id), []).append(row)
    for group_rows in grouped.values():
        ordered = sorted(group_rows, key=lambda item: item.seq)
        for prev, current in zip(ordered, ordered[1:]):
            if prev.end > current.start:
                issues.append(
                    AdjustmentIssue(
                        severity="blocker",
                        code="precedence_violation",
                        op_id=current.op_id,
                        related_op_id=prev.op_id,
                        message="后一道工序开始时间早于前一道工序结束时间。",
                    )
                )
    return issues


def find_due_date_warnings(rows: Sequence[AdjustmentPlanRow]) -> List[AdjustmentIssue]:
    latest_by_batch: Dict[str, AdjustmentPlanRow] = {}
    for row in rows:
        if not row.due_date:
            continue
        current = latest_by_batch.get(row.batch_id)
        if current is None or row.end > current.end:
            latest_by_batch[row.batch_id] = row
    issues: List[AdjustmentIssue] = []
    for row in latest_by_batch.values():
        due_limit = parse_required_datetime(row.due_date, field="交期") + timedelta(days=1)
        if row.end >= due_limit:
            issues.append(
                AdjustmentIssue(
                    severity="warning",
                    code="due_date_risk",
                    op_id=row.op_id,
                    message=f"批次 {row.batch_id} 调整后可能超过交期 {row.due_date}。",
                )
            )
    return issues


def result_status(issues: Sequence[AdjustmentIssue]) -> str:
    if any(issue.severity == "blocker" for issue in issues):
        return "blocked"
    if issues:
        return "warning"
    return "valid"


def result_message(status: str) -> str:
    if status == "blocked":
        return "这个调整暂时不能放，请先处理下面的冲突。"
    if status == "warning":
        return "这个调整可以试算，但存在需要确认的影响，正式计划还没有改变。"
    return "这个调整可以放到目标位置，正式计划还没有改变。"


def _plan_row(row: ScheduleDetailRow) -> AdjustmentPlanRow:
    start = parse_required_datetime(row.get("start_time"), field="开始时间")
    end = parse_required_datetime(row.get("end_time"), field="结束时间")
    if end <= start:
        raise ValidationError("调整依据方案中存在结束时间不晚于开始时间的工序。", field="end_time")
    return AdjustmentPlanRow(
        schedule_id=int(row.get("schedule_id") or 0),
        op_id=int(row.get("op_id") or 0),
        batch_id=str(row.get("batch_id") or ""),
        piece_id=str(row.get("piece_id") or ""),
        seq=int(row.get("seq") or 0),
        start=start,
        end=end,
        machine_id=_text_or_none(row.get("machine_id")),
        operator_id=_text_or_none(row.get("operator_id")),
        due_date=_text_or_none(row.get("due_date")),
        priority=_text_or_none(row.get("priority")),
        lock_status=_text_or_none(row.get("lock_status")),
    )


def _apply_change(row: AdjustmentPlanRow, change: ScheduleAdjustmentChange) -> None:
    new_start = parse_optional_datetime(change.to_start, field="调整后开始时间") or row.start
    new_end = parse_optional_datetime(change.to_end, field="调整后结束时间") or row.end
    if new_end <= new_start:
        raise ValidationError("调整后结束时间必须晚于开始时间。", field="to_end")
    row.start = new_start
    row.end = new_end
    row.is_changed = True
    if change.to_machine_id is not None:
        row.machine_id = _text_or_none(change.to_machine_id)
        row.is_changed = True
    if change.to_operator_id is not None:
        row.operator_id = _text_or_none(change.to_operator_id)
        row.is_changed = True


def _overlap_pairs(rows: Sequence[AdjustmentPlanRow], field: str) -> List[Tuple[AdjustmentPlanRow, AdjustmentPlanRow]]:
    by_resource: Dict[str, List[AdjustmentPlanRow]] = {}
    for row in rows:
        value = getattr(row, field)
        if value:
            by_resource.setdefault(str(value), []).append(row)
    pairs: List[Tuple[AdjustmentPlanRow, AdjustmentPlanRow]] = []
    for group_rows in by_resource.values():
        ordered = sorted(group_rows, key=lambda item: item.start)
        for index, left in enumerate(ordered):
            for right in ordered[index + 1 :]:
                if right.start >= left.end:
                    break
                if left.op_id != right.op_id:
                    pairs.append((left, right))
    return pairs


def _text_or_none(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None
