"""Execution target authority and explicit data-quality classification."""

INVALID_CODES = frozenset(("quantity_exceeded", "legacy_quantity_conflict", "legacy_target_conflict",
    "invalid_legacy_sequence", "legacy_identity_unresolved", "operation_retired", "operation_source_invalid"))


def gap(code, message, **fields):
    return {"code": code, "message": message, **fields}


def operation_target(operation, unresolved):
    gaps = []
    piece = operation.get("piece_id")
    basis = "piece" if piece is not None and piece != "" else "batch"
    raw = 1 if basis == "piece" else operation.get("batch_quantity")
    target = raw if type(raw) is int and 0 <= raw <= (1 << 53) - 1 else None
    if target is None:
        gaps.append(gap("target_quantity_unknown", "这道工序的目标数量缺失或无效，系统算不出剩余数量，请核对批次数量。"))
    if not operation.get("identity_active") or operation.get("id") is None:
        gaps.append(gap("operation_retired", "这道工序已被删除，原来的报工记录仍留在旧工序上，不会自动转到同序号的新工序，请核对工艺。"))
    if unresolved:
        gaps.append(gap("legacy_identity_unresolved", "有旧现场记录分不清属于哪道工序，系统没有按编号猜。当前工作台不能直接修改这类归属，请联系维护人员核对原始记录并修正数据。"))
    if operation.get("source") not in ("internal", "external"):
        gaps.append(gap("operation_source_invalid", "这道工序的来源既不是自制也不是外协，系统分不清报工要填哪些项，请先在工艺里改正来源。"))
    return target, basis, gaps


def classify_quality(gaps, *, legacy_uncovered, has_records):
    if any(item["code"] in INVALID_CODES for item in gaps):
        return "invalid"
    if legacy_uncovered:
        return "legacy_incomplete"
    return "incomplete" if gaps or not has_records else "complete"
