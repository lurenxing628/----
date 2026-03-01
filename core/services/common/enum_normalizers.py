from __future__ import annotations

from typing import Any

from core.models.enums import MachineStatus, OperatorStatus, SourceType


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

    - 英文枚举值：大小写不敏感，返回标准小写
    - 其它未知值：原样透传（由调用方决定是否报错）
    """
    v = _text(value)
    if not v:
        return v
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
        return "active"

    if v in ("启用", "在用", "正常"):
        return "active"
    if v in ("停用", "禁用"):
        return "inactive"

    v_lower = v.lower()
    if v_lower in ("active", "inactive"):
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

