"""Resource status rules shared by public projections, counts and SQL scopes."""

SPECIAL_INACTIVE_REASONS = {"operator": "leave", "supplier": "pending_review"}


def reasoned_resource_state(kind, status, profile):
    if status == "active":
        return {"status": "active", "inactive_reason": None}
    reason = profile["inactive_reason"] if profile else None
    special = SPECIAL_INACTIVE_REASONS[kind]
    return {"status": special if reason == special else "inactive", "inactive_reason": reason or "disabled"}


def public_resource_status(kind, status, profile=None):
    if kind == "op_type":
        return None
    if kind in SPECIAL_INACTIVE_REASONS:
        return reasoned_resource_state(kind, status, profile)["status"]
    return status
