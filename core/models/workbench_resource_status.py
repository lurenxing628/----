"""Resource status rules shared by public projections, counts and SQL scopes."""

from core.models.workbench_command import WorkbenchCommandRejected

SPECIAL_INACTIVE_REASONS = {"operator": "leave", "supplier": "pending_review"}
RAW_RESOURCE_STATUSES = {"machine": ("active", "maintain", "inactive")}


def _damaged():
    # 写入口只产出“启用”或“带登记原因的停用”；其余组合只可能是存储被改坏，直接拒绝，不猜是启用还是停用。
    return WorkbenchCommandRejected("storage_failure", "有资源的状态或停用原因存得不对，系统没有猜是启用还是停用。"
                                    "请联系维护人员核对资料。", 500)


def reasoned_resource_state(kind, status, profile):
    reason = profile["inactive_reason"] if profile else None
    special = SPECIAL_INACTIVE_REASONS[kind]
    if status == "active":
        return {"status": "active", "inactive_reason": None}
    if status == "inactive" and reason in (special, "disabled"):
        return {"status": special if reason == special else "inactive", "inactive_reason": reason}
    raise _damaged()


def public_resource_status(kind, status, profile=None):
    if kind == "op_type":
        return None
    if kind in SPECIAL_INACTIVE_REASONS:
        return reasoned_resource_state(kind, status, profile)["status"]
    if status not in RAW_RESOURCE_STATUSES.get(kind, ("active", "inactive")):
        raise _damaged()
    return status
