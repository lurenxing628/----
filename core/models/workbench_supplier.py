"""Pure input and state projection for private supplier commands."""

from __future__ import annotations

import math
import re
from typing import Any, Dict

from core.errors import ValidationError

_TOP_LEVEL = {
    "create": frozenset(("business_code", "label", "fields", "relationships")),
    "update": frozenset(("label", "fields", "relationships")),
    "delete": frozenset(),
}
_FIELDS = frozenset(("default_days", "status", "remark"))


def _object(value, allowed, path):
    if type(value) is not dict:
        raise ValidationError("操作内容必须是 JSON 对象。", field=path)
    if any(type(key) is not str or key not in allowed for key in value):
        raise ValidationError("操作内容包含不允许的字段。", field=path)
    return value


def _text(value, path, clearable=False):
    if value is None and clearable:
        return None
    if type(value) is not str or (not value.strip() and not clearable):
        raise ValidationError("该字段必须是非空文字。", field=path)
    return value.strip() or None


def _days(value):
    message = "默认周期必须是有限正数，不能是布尔值或数字字符串。"
    if type(value) not in (int, float):
        raise ValidationError(message, field="fields.default_days")
    try:
        days = float(value)
    except OverflowError as exc:
        raise ValidationError(message, field="fields.default_days") from exc
    if not math.isfinite(days) or days <= 0:
        raise ValidationError(message, field="fields.default_days")
    return days


def _relationships(value):
    relation = _object(value, {"op_type_refs"}, "relationships")
    refs = relation.get("op_type_refs")
    if type(refs) is not list or any(type(ref) is not str or re.fullmatch(r"[0-9a-f]{48}", ref) is None for ref in refs):
        raise ValidationError("必须提交完整的工种永久引用列表，不能使用内部编号。", field="relationships.op_type_refs")
    if len(set(refs)) != len(refs):
        raise ValidationError("工种引用不能重复。", field="relationships.op_type_refs")
    return {"op_type_refs": sorted(refs)}


def normalize_supplier_input(action: str, payload: Any) -> Dict[str, Any]:
    if type(action) is not str or action not in _TOP_LEVEL:
        raise ValidationError("不支持的供应商操作。", field="action")
    payload = _object(payload, _TOP_LEVEL[action], "input")
    if action == "delete":
        return {}
    result: Dict[str, Any] = {}
    if action == "create":
        result["business_code"] = _text(payload.get("business_code"), "business_code")
    if action == "create" or "label" in payload:
        result["label"] = _text(payload.get("label"), "label")
    fields = _object(payload.get("fields", {}), _FIELDS, "fields")
    normalized = {}
    for key, value in fields.items():
        if key == "default_days":
            normalized[key] = _days(value)
        elif key == "remark":
            normalized[key] = _text(value, "fields.remark", clearable=True)
        else:
            if type(value) is not str or value not in ("active", "pending_review", "inactive"):
                raise ValidationError("状态仅允许 active、pending_review 或 inactive。", field="fields.status")
            normalized[key] = value
    if action == "create" and "default_days" not in normalized:
        raise ValidationError("新增供应商必须明确填写有效默认周期。", field="fields.default_days")
    result["fields"] = normalized
    if "relationships" in payload:
        result["relationships"] = _relationships(payload["relationships"])
    return result


def supplier_state(status, profile) -> Dict[str, Any]:
    """Keep legacy inactive-without-reason distinct from explicit pending review."""
    reason = profile["inactive_reason"] if profile else None
    if status == "active":
        return {"status": "active", "inactive_reason": None}
    if status == "inactive":
        return {"status": "pending_review" if reason == "pending_review" else "inactive",
                "inactive_reason": reason if reason in ("pending_review", "disabled") else "unknown"}
    return {"status": "unknown", "inactive_reason": "unknown"}
