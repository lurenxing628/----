from __future__ import annotations

from core.models.enums import (
    BatchPriority,
    BatchStatus,
    CalendarDayType,
    MachineStatus,
    OperatorStatus,
    ReadyStatus,
)


def machine_status_zh(status: str) -> str:
    v = (status or "").strip()
    if v == MachineStatus.ACTIVE.value:
        return "可用"
    if v == MachineStatus.MAINTAIN.value:
        return "维修"
    if v == MachineStatus.INACTIVE.value:
        return "停用"
    return v or "-"


def operator_status_zh(status: str) -> str:
    v = (status or "").strip()
    if v == OperatorStatus.ACTIVE.value:
        return "在岗"
    if v == OperatorStatus.INACTIVE.value:
        return "停用/休假"
    return v or "-"


def day_type_zh(day_type: str) -> str:
    """
    日历类型中文展示：
    - workday：工作日
    - holiday/weekend：假期
    """
    v = (day_type or "").strip()
    if v == CalendarDayType.WORKDAY.value:
        return "工作日"
    if v in (CalendarDayType.HOLIDAY.value, CalendarDayType.WEEKEND.value):
        return "假期"
    return v or "-"


def batch_status_zh(v: str) -> str:
    s = (v or "").strip()
    if s == BatchStatus.PENDING.value:
        return "待排"
    if s == BatchStatus.SCHEDULED.value:
        return "已排"
    if s == BatchStatus.PROCESSING.value:
        return "加工中"
    if s == BatchStatus.COMPLETED.value:
        return "已完成"
    if s == BatchStatus.CANCELLED.value:
        return "已取消"
    return s or "-"


def priority_zh(v: str) -> str:
    s = (v or "").strip()
    if s == BatchPriority.CRITICAL.value:
        return "特急"
    if s == BatchPriority.URGENT.value:
        return "急件"
    return "普通"


def ready_zh(v: str) -> str:
    s = (v or "").strip()
    if s == ReadyStatus.YES.value:
        return "齐套"
    if s == ReadyStatus.PARTIAL.value:
        return "部分齐套"
    return "未齐套"

