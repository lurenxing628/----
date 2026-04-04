from __future__ import annotations

from typing import Any

from core.models.enums import MachineStatus, OperatorStatus, SourceType, SupplierStatus, YesNo
from core.services.common.normalization_matrix import (
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


_YES_NO_TRUE_WIDE = ("yes", "y", "true", "1", "on")
_YES_NO_FALSE_WIDE = ("no", "n", "false", "0", "off", "")


def normalize_yes_no_wide(value: Any, *, default: str = YesNo.NO.value, unknown_policy: str = "no") -> str:
    return normalize_yes_no_wide_value(value, default=default, unknown_policy=unknown_policy)


def normalize_yesno_narrow(value: Any, *, default: str = YesNo.YES.value, unknown_policy: str = "passthrough") -> str:
    return normalize_yes_no_narrow_value(value, default=default, unknown_policy=unknown_policy)


def normalize_skill_level(value: Any, *, default: str = "normal", allow_none: bool = False):
    return normalize_skill_level_value(value, default=default, allow_none=allow_none, unknown_policy="raise")


def skill_rank(value: Any) -> int:
    return skill_level_rank(value)

