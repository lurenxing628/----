"""资源对外状态：存储状态加停用原因按同一条规则推出，Python 判定与 SQL 片段都出自这里。

值域、叫法和业务顺序取 ``core.models.enums``；这里只写“停用原因怎样变成对外状态”这一条规则。
"""

from core.models.enums import (
    MACHINE_GROUP_STATUS_VALUES,
    MACHINE_STATUS_VALUES,
    OPERATOR_STATUS_VALUES,
    RESOURCE_ACTIVE_LABELS,
    RESOURCE_STATUS_LABELS,
    RESOURCE_STATUS_RANKS,
    SHIFT_PROFILE_STATUS_VALUES,
    SUPPLIER_STATUS_VALUES,
    OperatorInactiveReason,
    SupplierInactiveReason,
)

#: 停用时只有这一种原因单独成为对外状态：人员请假、供应商待复核；其余原因和没登记原因都算停用。
SPECIAL_INACTIVE_REASONS = {"operator": OperatorInactiveReason.LEAVE.value, "supplier": SupplierInactiveReason.PENDING_REVIEW.value}

_STORED_STATUS_VALUES = {
    "machine": MACHINE_STATUS_VALUES, "operator": OPERATOR_STATUS_VALUES, "supplier": SUPPLIER_STATUS_VALUES,
    "machine_group": MACHINE_GROUP_STATUS_VALUES, "shift_profile": SHIFT_PROFILE_STATUS_VALUES,
}

#: 每类资料能有的对外状态（存储状态加上按停用原因推出的那一种），按业务顺序排；表单、导入文件、列表筛选和计数共用。
PUBLIC_STATUS_VALUES = {
    kind: tuple(sorted(values + ((SPECIAL_INACTIVE_REASONS[kind],) if kind in SPECIAL_INACTIVE_REASONS else ()),
                       key=RESOURCE_STATUS_RANKS.__getitem__))
    for kind, values in _STORED_STATUS_VALUES.items()
}


def table_status_label(kind, status):
    """对外状态在页面上的叫法；“可用”在人员、供应商、物料等页面另有叫法。"""
    return RESOURCE_ACTIVE_LABELS[kind] if status == "active" else RESOURCE_STATUS_LABELS[status]


def reasoned_resource_state(kind, status, profile):
    """唯一的特殊状态判定：只有停用才看停用原因，是本类那一种原因就成为对外状态；没登记原因按 disabled。"""
    if status != "inactive":
        return {"status": status, "inactive_reason": None}
    reason = profile["inactive_reason"] if profile else None
    special = SPECIAL_INACTIVE_REASONS[kind]
    return {"status": special if reason == special else status, "inactive_reason": reason or "disabled"}


def public_resource_status(kind, status, profile):
    if kind == "op_type":
        return None
    if kind in SPECIAL_INACTIVE_REASONS:
        return reasoned_resource_state(kind, status, profile)["status"]
    return status


def public_status_sql(kind, status, reason):
    """``public_resource_status`` 的 SQL 写法，供分页前的筛选、排序和计数；列名由仓储常量给出。"""
    if kind == "op_type":
        return "NULL"
    if kind not in SPECIAL_INACTIVE_REASONS:
        return status
    special = SPECIAL_INACTIVE_REASONS[kind]
    return f"CASE WHEN {status}='inactive' AND {reason}='{special}' THEN '{special}' ELSE {status} END"
