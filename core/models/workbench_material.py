"""Pure JSON input contract for private workbench material commands."""

from __future__ import annotations

import math
from typing import Any, Dict

from core.errors import ValidationError

_CLEARABLE = ("spec", "unit", "remark")
_FIELDS = frozenset(_CLEARABLE + ("stock_qty", "status"))
_TOP_LEVEL = {
    "create": frozenset(("business_code", "label", "fields")),
    "update": frozenset(("label", "fields")),
    "delete": frozenset(),
}


def _object(value: Any, allowed, path: str) -> Dict[str, Any]:
    if type(value) is not dict:
        raise ValidationError("提交内容格式不对，这次操作没有执行。请刷新页面后重试。", field=path)
    if any(type(key) is not str or key not in allowed for key in value):
        raise ValidationError("提交内容含有不支持的项，这次操作没有执行。请刷新页面后重试。", field=path)
    return value


def _text(value: Any, path: str, *, clearable: bool = False):
    if value is None and clearable:
        return None
    if type(value) is not str:
        raise ValidationError("这一项必须填文字。", field=path)
    text = value.strip()
    if not text and not clearable:
        raise ValidationError("这一项不能为空。", field=path)
    return text or None


def _stock_qty(value: Any) -> float:
    message = "库存数量请填 0 或正数。"
    if type(value) not in (int, float):
        raise ValidationError(message, field="fields.stock_qty")
    try:
        quantity = float(value)
    except OverflowError as exc:
        raise ValidationError(message, field="fields.stock_qty") from exc
    if not math.isfinite(quantity) or quantity < 0:
        raise ValidationError(message, field="fields.stock_qty")
    return quantity if quantity else 0.0


def normalize_material_input(action: str, payload: Any) -> Dict[str, Any]:
    """Keep omissions distinct from clearing; never inspect current database state."""
    if type(action) is not str or action not in _TOP_LEVEL:
        raise ValidationError("不支持的物料操作。", field="action")
    payload = _object(payload, _TOP_LEVEL[action], "input")
    if action == "delete":
        return {}
    result: Dict[str, Any] = {}
    if action == "create":
        result["business_code"] = _text(payload.get("business_code"), "business_code")
    if action == "create" or "label" in payload:
        result["label"] = _text(payload.get("label"), "label")
    fields = _object(payload.get("fields", {}), _FIELDS, "fields")
    normalized: Dict[str, Any] = {}
    for key, value in fields.items():
        if key in _CLEARABLE:
            normalized[key] = _text(value, "fields." + key, clearable=True)
        elif key == "stock_qty":
            normalized[key] = _stock_qty(value)
        else:
            status = _text(value, "fields.status")
            if status not in ("active", "inactive"):
                raise ValidationError("状态仅允许 active 或 inactive。", field="fields.status")
            normalized[key] = status
    result["fields"] = normalized
    return result
