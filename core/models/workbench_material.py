"""Material input normalization contract."""

from __future__ import annotations

from typing import Any, Dict

from core.errors import ValidationError
from core.models.enums import MATERIAL_STATUS_VALUES
from core.models.workbench_resource_input import resource_object, resource_text
from core.shared.strict_parse import JS_SAFE_INT_MAX, is_stored_number

_CLEARABLE = ("spec", "unit", "remark")
_FIELDS = frozenset(_CLEARABLE + ("stock_qty", "status"))
_TOP_LEVEL = {
    "create": frozenset(("business_code", "label", "fields")),
    "update": frozenset(("label", "fields")),
    "delete": frozenset(),
}


def _stock_qty(value: Any) -> float:
    """写入与读取共用 is_stored_number：能存进去的库存，下次读出来一定合法。"""
    if not is_stored_number(value):
        over = type(value) in (int, float) and value > JS_SAFE_INT_MAX
        raise ValidationError("库存数量超出有效数字范围。" if over else "库存数量请填 0 或正数。", field="fields.stock_qty")
    quantity = float(value)
    return quantity if quantity else 0.0


def normalize_material_input(action: str, payload: Any) -> Dict[str, Any]:
    """Keep omissions distinct from clearing; never inspect current database state."""
    if type(action) is not str or action not in _TOP_LEVEL:
        raise ValidationError("不支持的物料操作。", field="action")
    payload = resource_object(payload, _TOP_LEVEL[action], "input")
    if action == "delete":
        return {}
    result: Dict[str, Any] = {}
    if action == "create":
        result["business_code"] = resource_text(payload.get("business_code"), "business_code")
    if action == "create" or "label" in payload:
        result["label"] = resource_text(payload.get("label"), "label")
    fields = resource_object(payload.get("fields", {}), _FIELDS, "fields")
    normalized: Dict[str, Any] = {}
    for key, value in fields.items():
        if key in _CLEARABLE:
            normalized[key] = resource_text(value, "fields." + key, nullable=True)
        elif key == "stock_qty":
            normalized[key] = _stock_qty(value)
        else:
            status = resource_text(value, "fields.status")
            if status not in MATERIAL_STATUS_VALUES:
                raise ValidationError("状态请选择启用或停用。", field="fields.status")
            normalized[key] = status
    result["fields"] = normalized
    return result
