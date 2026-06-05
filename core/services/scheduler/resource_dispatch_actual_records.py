from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence

from core.infrastructure.errors import ValidationError
from core.models.operation_execution_state import OperationExecutionState

from .operation_execution_feedback_support import _parse_feedback_datetime

TASK_FEEDBACK_SHEET = "任务反馈"
PAUSE_DETAIL_SHEET = "暂停明细"
UNSPECIFIED_FEEDBACK_PERSON = "未填写反馈人"

TASK_HEADERS = [
    "任务识别码",
    "批次",
    "工序",
    "计划设备",
    "计划人员",
    "实际开工时间",
    "实际完工时间",
    "完成数量",
    "报废数量",
    "异常时间",
    "异常原因",
    "异常严重程度",
    "异常说明",
    "反馈人",
    "备注",
]

PAUSE_HEADERS = [
    "任务识别码",
    "暂停开始时间",
    "暂停结束时间",
    "暂停时长分钟",
    "暂停原因",
    "暂停说明",
    "反馈人",
]

INTERNAL_TEMPLATE_TOKENS = {
    "op_id",
    "schedule_id",
    "state_revision",
    "execution_snapshot_revision",
}


@dataclass
class TaskRef:
    task_code: str
    schedule_version: int
    schedule_id: int
    op_id: int
    batch_id: str
    requested_plan_role: str
    source_table: str
    effective_plan_role: str
    scenario_id: Optional[str]
    op_name: str
    planned_machine_id: str
    planned_machine_label: str
    planned_operator_id: str
    planned_operator_label: str
    state: OperationExecutionState
    expected_state_revision: Optional[str] = None


@dataclass
class PausePlan:
    row_number: int
    start_time: str
    end_time: str
    reason_code: str
    remark: str
    feedback_person: str


@dataclass
class TaskPlan:
    task: TaskRef
    row_number: int
    actual_start_time: Optional[str] = None
    actual_finish_time: Optional[str] = None
    quantity_done: Optional[Any] = None
    quantity_scrapped: Optional[Any] = None
    exception_time: Optional[str] = None
    exception_reason_code: Optional[str] = None
    exception_severity: Optional[str] = None
    exception_remark: Optional[str] = None
    feedback_person: str = UNSPECIFIED_FEEDBACK_PERSON
    remark: Optional[str] = None
    pauses: Optional[List[PausePlan]] = None


@dataclass
class PreviewResult:
    rows: List[Dict[str, Any]]
    raw_rows: List[Dict[str, Any]]
    summary: Dict[str, Any]
    task_plans: List[TaskPlan]


def text(value: Any) -> str:
    return str(value or "").strip()


def plan_identity_from_context(context: Mapping[str, Any]) -> Dict[str, Any]:
    raw_identity = context.get("plan_identity")
    identity: Mapping[str, Any] = raw_identity if isinstance(raw_identity, Mapping) else {}
    missing = [
        field
        for field in ("version", "requested_plan_role", "source_table", "effective_plan_role")
        if not text(identity.get(field))
    ]
    try:
        version = int(identity.get("version") or 0)
    except (TypeError, ValueError):
        version = 0
    if version <= 0 and "version" not in missing:
        missing.append("version")
    if missing:
        raise ValidationError(
            "当前计划身份不完整，请刷新资源排班页面后重试。",
            field="plan_identity",
            details={"missing_fields": missing},
        )
    return {
        "version": version,
        "requested_plan_role": text(identity.get("requested_plan_role")),
        "source_table": text(identity.get("source_table")),
        "effective_plan_role": text(identity.get("effective_plan_role")),
        "scenario_id": text(identity.get("scenario_id")) or None,
    }


def feedback_person(value: Any) -> str:
    return text(value) or UNSPECIFIED_FEEDBACK_PERSON


def datetime_text(value: Any, *, field_label: str) -> str:
    dt = _parse_feedback_datetime(value, field=field_label)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def parse_datetime_or_error(value: Any, *, field_label: str, messages: List[str]) -> Optional[str]:
    if not text(value):
        return None
    try:
        return datetime_text(value, field_label=field_label)
    except ValidationError as exc:
        messages.append(exc.message)
        return None


def parse_int_or_error(value: Any, *, field_label: str, messages: List[str]) -> Optional[int]:
    if value is None or text(value) == "":
        return None
    if isinstance(value, bool):
        messages.append(f"{field_label}填写不正确，请填写整数。")
        return None
    if isinstance(value, float) and not value.is_integer():
        messages.append(f"{field_label}填写不正确，请填写整数。")
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        messages.append(f"{field_label}填写不正确，请填写整数。")
        return None
    if isinstance(value, str) and value.strip() not in (str(parsed), f"+{parsed}"):
        messages.append(f"{field_label}填写不正确，请填写整数。")
        return None
    if parsed < 0:
        messages.append(f"{field_label}不能小于 0。")
        return None
    return parsed


def normalize_choice(value: Any, labels: Mapping[str, str], *, field_label: str, messages: List[str]) -> Optional[str]:
    item = text(value)
    if not item:
        return None
    if item in labels:
        return item
    reverse = {label: code for code, label in labels.items()}
    if item in reverse:
        return reverse[item]
    messages.append(f"{field_label}填写不正确，请按模板里的中文选项填写。")
    return None


def task_display_name(row: Mapping[str, Any]) -> str:
    op_code = text(row.get("op_code"))
    if op_code:
        return op_code
    seq = text(row.get("seq"))
    return f"工序{seq}" if seq else "工序"


def resource_label(row: Mapping[str, Any], prefix: str) -> str:
    return (
        text(row.get(f"{prefix}_display_label"))
        or text(row.get(f"{prefix}_name"))
        or text(row.get(f"{prefix}_label"))
        or text(row.get(f"{prefix}_id"))
    )


def task_code_from_parts(
    *,
    batch_id: str,
    op_name: str,
    planned_start_time: Any,
    planned_machine_label: str,
    public_task_id: str = "",
) -> str:
    start = text(planned_start_time).replace("-", "").replace(":", "").replace(" ", "")
    parts = [batch_id, op_name, start, planned_machine_label]
    if public_task_id:
        parts.append(public_task_id)
    return "-".join(part for part in (text(item) for item in parts) if part)


def status_label(status: str) -> str:
    if status == "ok":
        return "匹配成功"
    if status == "skip":
        return "跳过"
    if status == "conflict":
        return "有冲突"
    return "有错误"


def public_raw_row(row: Mapping[str, Any]) -> Dict[str, Any]:
    return {str(key): value for key, value in dict(row).items() if str(key) not in INTERNAL_TEMPLATE_TOKENS}


def ordered_pauses(plan: TaskPlan) -> List[PausePlan]:
    return sorted(plan.pauses or [], key=lambda item: item.start_time)


def planned_event_count(plan: Optional[TaskPlan]) -> int:
    if plan is None:
        return 0
    count = 0
    if plan.actual_start_time:
        count += 1
    count += len(plan.pauses or []) * 2
    if plan.exception_time:
        count += 1
    if plan.actual_finish_time:
        count += 1
    return count


def row_key(row: Mapping[str, Any]) -> tuple:
    return (text(row.get("sheet")), int(row.get("row_number") or 0))


__all__ = [
    "INTERNAL_TEMPLATE_TOKENS",
    "PAUSE_DETAIL_SHEET",
    "PAUSE_HEADERS",
    "PausePlan",
    "PreviewResult",
    "TASK_FEEDBACK_SHEET",
    "TASK_HEADERS",
    "TaskPlan",
    "TaskRef",
    "UNSPECIFIED_FEEDBACK_PERSON",
    "datetime_text",
    "feedback_person",
    "normalize_choice",
    "ordered_pauses",
    "plan_identity_from_context",
    "parse_datetime_or_error",
    "parse_int_or_error",
    "planned_event_count",
    "public_raw_row",
    "resource_label",
    "row_key",
    "status_label",
    "task_code_from_parts",
    "task_display_name",
    "text",
]
