"""Supplier input normalization and public state projection."""

from __future__ import annotations

import math
import re
from typing import Any, Dict

from core.errors import ValidationError
from core.models.workbench_resource_input import resource_object, resource_text
from core.models.workbench_resource_status import reasoned_resource_state

#: 供应商命令与导入归一化接受的状态代号，与 workbench_resource_file.ENUM_CODES["supplier"]["status"] 保持一致。
STATUS_VALUES = ("active", "pending_review", "inactive")

_TOP_LEVEL = {
    "create": frozenset(("business_code", "label", "fields", "relationships")),
    "update": frozenset(("label", "fields", "relationships")),
    "delete": frozenset(),
}
_FIELDS = frozenset(("default_days", "status", "remark"))


def _days(value):
    message = "默认周期请填正数。"
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
    relation = resource_object(value, {"op_type_refs"}, "relationships")
    refs = relation.get("op_type_refs")
    if type(refs) is not list or any(type(ref) is not str or re.fullmatch(r"[0-9a-f]{48}", ref) is None for ref in refs):
        raise ValidationError("请从列表里选工种，而且要一次提交完整的工种列表。", field="relationships.op_type_refs")
    if len(set(refs)) != len(refs):
        raise ValidationError("工种不能重复选。", field="relationships.op_type_refs")
    return {"op_type_refs": sorted(refs)}


def normalize_supplier_input(action: str, payload: Any) -> Dict[str, Any]:
    if type(action) is not str or action not in _TOP_LEVEL:
        raise ValidationError("不支持的供应商操作。", field="action")
    payload = resource_object(payload, _TOP_LEVEL[action], "input")
    if action == "delete":
        return {}
    result: Dict[str, Any] = {}
    if action == "create":
        result["business_code"] = resource_text(payload.get("business_code"), "business_code")
    if action == "create" or "label" in payload:
        result["label"] = resource_text(payload.get("label"), "label")
    fields = resource_object(payload.get("fields", {}), _FIELDS, "fields")
    normalized = {}
    for key, value in fields.items():
        if key == "default_days":
            normalized[key] = _days(value)
        elif key == "remark":
            normalized[key] = resource_text(value, "fields.remark", nullable=True)
        else:
            if type(value) is not str or value not in STATUS_VALUES:
                raise ValidationError("状态只能选启用、待复核或停用。", field="fields.status")
            normalized[key] = value
    if action == "create" and "default_days" not in normalized:
        raise ValidationError("新增供应商必须明确填写有效默认周期。", field="fields.default_days")
    result["fields"] = normalized
    if "relationships" in payload:
        result["relationships"] = _relationships(payload["relationships"])
    return result


def supplier_state(status, profile) -> Dict[str, Any]:
    """Project stored supplier status and optional profile reason into public status and inactive_reason."""
    return reasoned_resource_state("supplier", status, profile)
