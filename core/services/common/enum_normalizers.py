from __future__ import annotations

from typing import Any

from core.models.enums import MachineStatus, OperatorStatus, SkillLevel, SourceType, SupplierStatus, YesNo


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
    """
    归一化“宽口径”的 yes/no 开关：
    - 兼容 HTML checkbox（on/None）
    - 兼容常见布尔文本（true/false/1/0）

    unknown_policy:
    - "no"：未知值一律视为 no（保守；适用于系统配置/调度配置等）
    - "default"：未知值回退 default（适用于 plugin enabled 等）
    """
    default_norm = YesNo.YES.value if str(default).strip().lower() in _YES_NO_TRUE_WIDE else YesNo.NO.value
    if value is None:
        return default_norm
    v = str(value).strip().lower()
    if v in _YES_NO_TRUE_WIDE:
        return YesNo.YES.value
    if v in _YES_NO_FALSE_WIDE:
        return YesNo.NO.value
    if unknown_policy == "default":
        return default_norm
    return YesNo.NO.value


def normalize_yesno_narrow(value: Any, *, default: str = YesNo.YES.value, unknown_policy: str = "passthrough") -> str:
    """
    归一化“窄口径”的 yes/no：
    - 兼容 yes/no/y/n、true/false、1/0 与中文 是/否
    - 不把 on/off 视为 yes/no（由上层按值域决定是否报错）

    unknown_policy:
    - "passthrough"：未知值原样透传（strip 后）；供上层显式 not in(...) 校验报错展示用户输入
    - "raise"：未知值直接抛 ValueError（由上层决定如何转成 ValidationError）
    """
    default_norm = YesNo.YES.value if str(default).strip().lower() in ("y", "yes", YesNo.YES.value) else YesNo.NO.value
    v = "" if value is None else str(value).strip()
    if v == "":
        return default_norm
    v_lower = v.lower()
    if v == "是" or v_lower in ("y", YesNo.YES.value, "true", "1"):
        return YesNo.YES.value
    if v == "否" or v_lower in ("n", YesNo.NO.value, "false", "0"):
        return YesNo.NO.value
    if unknown_policy == "raise":
        raise ValueError(f"invalid yes/no: {v!r}")
    return v


def normalize_skill_level(value: Any, *, default: str = "normal", allow_none: bool = False):
    """
    skill_level 归一化（canonical3）：
    - 输出只可能是 beginner/normal/expert
    - 兼容 legacy alias：low/normal/high、skilled
    - 兼容常见中文：初级/普通/熟练（以及 高级/专家/一般/中级/新手）
    """
    if value is None:
        return None if allow_none else normalize_skill_level(default, default="normal", allow_none=False)
    s0 = str(value).strip()
    if s0 == "":
        return None if allow_none else normalize_skill_level(default, default="normal", allow_none=False)
    low = s0.lower()
    if low in (SkillLevel.EXPERT.value, "high", SkillLevel.SKILLED.value):
        return SkillLevel.EXPERT.value
    if low == SkillLevel.NORMAL.value:
        return SkillLevel.NORMAL.value
    if low in (SkillLevel.BEGINNER.value, "low"):
        return SkillLevel.BEGINNER.value
    if s0 in ("熟练", "高级", "专家"):
        return SkillLevel.EXPERT.value
    if s0 in ("普通", "一般", "中级"):
        return SkillLevel.NORMAL.value
    if s0 in ("初级", "新手"):
        return SkillLevel.BEGINNER.value
    raise ValueError(f"invalid skill_level: {s0!r}")


def skill_rank(value: Any) -> int:
    """
    技能等级排序（数值越小越优）。
    - expert/high/skilled -> 0
    - normal -> 1
    - beginner/low -> 2
    - unknown/empty -> 9
    """
    try:
        s = normalize_skill_level(value, default="normal", allow_none=True)
    except Exception:
        return 9
    if s is None:
        return 9
    if s == SkillLevel.EXPERT.value:
        return 0
    if s == SkillLevel.NORMAL.value:
        return 1
    if s == SkillLevel.BEGINNER.value:
        return 2
    return 9

