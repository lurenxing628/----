"""Prototype batch fields; omission differs from an explicit empty value."""

import math
import re
from datetime import date

from core.errors import ValidationError
from core.models.workbench_command import WorkbenchCommandRejected

PRIORITIES = ("normal", "urgent", "critical")
READY = ("yes", "partial", "no")
STATUSES = ("pending", "scheduled", "processing", "completed", "cancelled")
FIELDS = ("quantity", "due_date", "priority", "ready_status", "ready_date", "remark")
SORTS = ("business_code", "part_no", "quantity", "due_date", "priority", "ready_status", "status")
MAX_INTEGER = 9007199254740991


def object_fields(value, allowed, required=()):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        raise WorkbenchCommandRejected("invalid_input", "请求缺少必要字段或包含不支持的字段。", 400)
    return value


def public_ref(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{48}", value) is None:
        raise WorkbenchCommandRejected("invalid_input", "对象引用无效，请重新选择。", 400)
    return value


def number(value, field, *, integer=False, positive=False, nullable=False):
    if nullable and value is None:
        return None
    valid = type(value) is int if integer else type(value) in (int, float)
    if valid:
        valid = 0 <= value <= MAX_INTEGER and (not positive or value > 0)
    if valid:
        valid = math.isfinite(value)
    if not valid:
        raise ValidationError("请输入有效的" + ("正整数。" if integer and positive else "非负有限数字。"), field=field)
    return value


def date_value(value, field):
    if value is None:
        return None
    if not isinstance(value, str) or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
        raise ValidationError("日期必须为真实日期 YYYY-MM-DD，清空请传 null。", field=field)
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError("日期不存在，请核对年月日。", field=field) from exc
    return value


def text(value, field, *, nullable=False, limit=2000):
    if value is None and nullable:
        return None
    if not isinstance(value, str) or "\x00" in value or len(value) > limit or (not nullable and not value.strip()):
        raise ValidationError("请输入有效文字。", field=field)
    return value.strip() or None


def normalize_batch_input(action, payload):
    if action == "delete":
        return dict(object_fields(payload, ()))
    if action not in ("create", "update"):
        raise WorkbenchCommandRejected("invalid_input", "不支持的批次操作。", 400)
    required = ("business_code", "part_ref", "fields") if action == "create" else ("fields",)
    object_fields(payload, required, required)
    fields = object_fields(payload["fields"], FIELDS, FIELDS if action == "create" else ())
    if not fields:
        raise ValidationError("至少填写一个要修改的字段。", field="fields")
    normalized_fields = {}
    for key, value in fields.items():
        path = "fields." + key
        if key == "quantity":
            value = number(value, path, integer=True, positive=True)
        elif key in ("due_date", "ready_date"):
            value = date_value(value, path)
        elif key == "remark":
            value = text(value, path, nullable=True)
        elif value not in (PRIORITIES if key == "priority" else READY) or not isinstance(value, str):
            raise ValidationError("请选择有效选项。", field=path)
        normalized_fields[key] = value
    if action == "create":
        return {"fields": normalized_fields,
                "business_code": text(payload["business_code"], "business_code", limit=200),
                "part_ref": public_ref(payload["part_ref"])}
    return {"fields": normalized_fields}


def normalize_operation_input(payload):
    object_fields(payload, ("operation_ref", "fields"), ("operation_ref", "fields"))
    fields = object_fields(payload["fields"], ("machine_ref", "operator_ref", "supplier_ref", "setup_hours", "unit_hours", "external_days"))
    if not fields:
        raise ValidationError("至少修改一项工序资料。", field="fields")
    normalized = {}
    for key, value in fields.items():
        normalized[key] = (None if value is None else public_ref(value)) if key.endswith("_ref") else number(
            value, "fields." + key, positive=key == "external_days", nullable=True)
    return {"operation_ref": public_ref(payload["operation_ref"]), "fields": normalized}
