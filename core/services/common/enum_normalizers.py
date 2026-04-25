from __future__ import annotations

from typing import Any

from core.models.enums import (
    BatchPriority,
    CalendarDayType,
    MachineStatus,
    OperatorStatus,
    ReadyStatus,
    SourceType,
    SupplierStatus,
    YesNo,
)
from core.services.common.normalization_matrix import (
    normalize_batch_priority_value,
    normalize_calendar_day_type_value,
    normalize_ready_status_value,
    normalize_skill_level_value,
    normalize_yes_no_narrow_value,
    normalize_yes_no_wide_value,
    skill_level_rank,
)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def normalize_machine_status(value: Any) -> str:
    """
    标准化设备状态（Machines.status）。

    约定（保持既有 Excel/表单口径）：
    - None -> ""
    - 中文别名 -> 标准英文枚举值（active/inactive/maintain）
    - 英文枚举值：大小写不敏感，返回标准小写
    - 其它未知值：原样透传（由调用方决定是否报错）
    """
    v = _text(value)
    if not v:
        return v

    if v in ("可用", "启用", "正常"):
        return MachineStatus.ACTIVE.value
    if v in ("维修", "维护", "维护中", "维修中", "保养"):
        return MachineStatus.MAINTAIN.value
    if v in ("停用", "禁用", "不可用"):
        return MachineStatus.INACTIVE.value

    v_lower = v.lower()
    if v_lower in (
        MachineStatus.ACTIVE.value,
        MachineStatus.INACTIVE.value,
        MachineStatus.MAINTAIN.value,
    ):
        return v_lower
    return v


def normalize_operator_status(value: Any) -> str:
    """
    标准化人员状态（Operators.status）。

    - 中文别名 -> 标准英文枚举值（active/inactive）
    - 英文枚举值：大小写不敏感，返回标准小写
    - 其它未知值：原样透传（由调用方决定是否报错）
    """
    v = _text(value)
    if not v:
        return v
    if v in ("在岗", "启用", "可用", "正常"):
        return OperatorStatus.ACTIVE.value
    if v in ("停用", "休假", "停用/休假", "离岗"):
        return OperatorStatus.INACTIVE.value
    v_lower = v.lower()
    if v_lower in (OperatorStatus.ACTIVE.value, OperatorStatus.INACTIVE.value):
        return v_lower
    return v


def operator_status_label(value: Any) -> str:
    v = normalize_operator_status(value)
    if v == OperatorStatus.ACTIVE.value:
        return "在岗"
    if v == OperatorStatus.INACTIVE.value:
        return "停用"
    return v or "未知"


def normalize_supplier_status(value: Any) -> str:
    """
    标准化供应商状态（Suppliers.status）。

    约定（保持既有 Excel 导入口径）：
    - 空值默认 active
    - 中文别名/英文枚举：大小写不敏感，返回标准小写
    - 其它未知值：原样透传（由调用方决定是否报错）
    """
    v = _text(value)
    if not v:
        return SupplierStatus.ACTIVE.value

    if v in ("启用", "在用", "正常"):
        return SupplierStatus.ACTIVE.value
    if v in ("停用", "禁用"):
        return SupplierStatus.INACTIVE.value

    v_lower = v.lower()
    if v_lower in (SupplierStatus.ACTIVE.value, SupplierStatus.INACTIVE.value):
        return v_lower
    return v


def supplier_status_label(value: Any) -> str:
    v = normalize_supplier_status(value)
    if v == SupplierStatus.ACTIVE.value:
        return "启用"
    if v == SupplierStatus.INACTIVE.value:
        return "停用"
    return "未知"


def machine_status_label(value: Any) -> str:
    v = normalize_machine_status(value)
    if v == MachineStatus.ACTIVE.value:
        return "可用"
    if v == MachineStatus.INACTIVE.value:
        return "停用"
    if v == MachineStatus.MAINTAIN.value:
        return "维修"
    return v or "未知"


def normalize_op_type_category(value: Any) -> str:
    """
    标准化工种归属（OpTypes.category / SourceType）。

    约定（保持既有 Excel 导入口径）：
    - 空值默认 internal
    - 中文别名/英文枚举：大小写不敏感，返回标准小写
    - 其它未知值：原样透传（由调用方决定是否报错）
    """
    v = _text(value)
    if not v:
        return SourceType.INTERNAL.value

    if v in ("内部", "内"):
        return SourceType.INTERNAL.value
    if v in ("外部", "外"):
        return SourceType.EXTERNAL.value

    v_lower = v.lower()
    if v_lower in (SourceType.INTERNAL.value, SourceType.EXTERNAL.value):
        return v_lower
    return v


def source_type_label(value: Any) -> str:
    v = normalize_op_type_category(value)
    if v == SourceType.INTERNAL.value:
        return "内部"
    if v == SourceType.EXTERNAL.value:
        return "外部"
    return "未知"


_YES_NO_TRUE_WIDE = ("yes", "y", "true", "1", "on")
_YES_NO_FALSE_WIDE = ("no", "n", "false", "0", "off", "")


def normalize_yes_no_wide(value: Any, *, default: str = YesNo.NO.value, unknown_policy: str = "no") -> str:
    return normalize_yes_no_wide_value(value, default=default, unknown_policy=unknown_policy)


def normalize_yesno_narrow(value: Any, *, default: str = YesNo.YES.value, unknown_policy: str = "passthrough") -> str:
    return normalize_yes_no_narrow_value(value, default=default, unknown_policy=unknown_policy)


def yes_no_label(value: Any, *, default: str = YesNo.NO.value) -> str:
    v = normalize_yes_no_narrow_value(value, default=default, unknown_policy="passthrough")
    if v == YesNo.YES.value:
        return "是"
    if v == YesNo.NO.value:
        return "否"
    return v or "未知"


def normalize_skill_level(value: Any, *, default: str = "normal", allow_none: bool = False):
    return normalize_skill_level_value(value, default=default, allow_none=allow_none, unknown_policy="raise")


def skill_level_label(value: Any) -> str:
    try:
        v = normalize_skill_level_value(value, default="normal", allow_none=False, unknown_policy="raise")
    except Exception:
        return "未知"
    if v == "beginner":
        return "初级"
    if v == "expert":
        return "熟练"
    return "普通"


def skill_rank(value: Any) -> int:
    return skill_level_rank(value)


def batch_priority_label(value: Any) -> str:
    v = normalize_batch_priority_value(value, default=BatchPriority.NORMAL.value, unknown_policy="passthrough")
    if v == BatchPriority.CRITICAL.value:
        return "特急"
    if v == BatchPriority.URGENT.value:
        return "急件"
    if v == BatchPriority.NORMAL.value:
        return "普通"
    return v or "未知"


def ready_status_label(value: Any) -> str:
    v = normalize_ready_status_value(value, default=ReadyStatus.YES.value, unknown_policy="passthrough")
    if v == ReadyStatus.YES.value:
        return "齐套"
    if v == ReadyStatus.NO.value:
        return "未齐套"
    if v == ReadyStatus.PARTIAL.value:
        return "部分齐套"
    return v or "未知"


def calendar_day_type_label(value: Any) -> str:
    v = normalize_calendar_day_type_value(value, default=CalendarDayType.WORKDAY.value, unknown_policy="passthrough")
    if v == CalendarDayType.WORKDAY.value:
        return "工作日"
    if v in (CalendarDayType.HOLIDAY.value, CalendarDayType.WEEKEND.value):
        return "假期"
    return v or "未知"
