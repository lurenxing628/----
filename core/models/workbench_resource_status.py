"""Resource status rules shared by public projections, counts and SQL scopes."""

SPECIAL_INACTIVE_REASONS = {"operator": "leave", "supplier": "pending_review"}
RAW_RESOURCE_STATUSES = {"machine": ("active", "maintain", "inactive")}


def reasoned_resource_state(kind, status, profile):
    reason = profile["inactive_reason"] if profile else None
    special = SPECIAL_INACTIVE_REASONS[kind]
    if status == "active":
        return {"status": "active", "inactive_reason": None}
    if status == "inactive":
        return {"status": special if reason == special else "inactive",
                "inactive_reason": reason if reason in (special, "disabled") else "unknown"}
    return {"status": "unknown", "inactive_reason": "unknown"}


def public_resource_status(kind, status, profile=None):
    if kind == "op_type":
        return None
    if kind in SPECIAL_INACTIVE_REASONS:
        state = reasoned_resource_state(kind, status, profile)
        return "unknown" if state["inactive_reason"] == "unknown" else state["status"]
    return status if status in RAW_RESOURCE_STATUSES.get(kind, ("active", "inactive")) else "unknown"
