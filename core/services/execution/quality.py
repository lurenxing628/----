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
        gaps.append(gap("target_quantity_unknown", "工序目标量缺失或无效，剩余数量未知。"))
    if not operation.get("identity_active") or operation.get("id") is None:
        gaps.append(gap("operation_retired", "原工序已移除，历史引用不会改指同号新工序。"))
    if unresolved:
        gaps.append(gap("legacy_identity_unresolved", "存在无法无歧义关联的旧事件，未按编号推测归属。"))
    if operation.get("source") not in ("internal", "external"):
        gaps.append(gap("operation_source_invalid", "工序来源无效，无法确认必要报工字段。"))
    return target, basis, gaps


def classify_quality(gaps, *, legacy_uncovered, has_records):
    if any(item["code"] in INVALID_CODES for item in gaps):
        return "invalid"
    if legacy_uncovered:
        return "legacy_incomplete"
    return "incomplete" if gaps or not has_records else "complete"
