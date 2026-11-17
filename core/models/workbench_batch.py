"""Prototype batch fields; omission differs from an explicit empty value."""

import re
from datetime import date

from core.errors import ValidationError
from core.models.enums import BATCH_PRIORITY_VALUES, READY_STATUS_VALUES
from core.models.workbench_command import SHAPE_REJECTED, WorkbenchCommandRejected
from core.shared.key_sets import keys_conform
from core.shared.refs import is_ref
from core.shared.strict_parse import EXTERNAL_DAYS_RANGE_TEXT, is_external_days, is_stored_number

FIELDS = ("quantity", "due_date", "priority", "ready_status", "ready_date", "remark")
SORTS = ("business_code", "part_no", "quantity", "due_date", "priority", "ready_status", "status")

_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def object_fields(value, allowed, required=()):
    if not keys_conform(value, required, allowed):
        raise WorkbenchCommandRejected("invalid_input", SHAPE_REJECTED, 400)
    return value


def public_ref(value):
    if not is_ref(value):
        raise WorkbenchCommandRejected("invalid_input", "这条记录已失效，请刷新后重新选择。", 400)
    return value


def number(value, field, *, integer=False, positive=False):
    if not is_stored_number(value, positive=positive, integer=integer):
        raise ValidationError("请输入有效的" + ("正整数。" if integer and positive else "非负有限数字。"), field=field)
    return value


def date_value(value, field):
    if value is None:
        return None
    if not isinstance(value, str) or _DATE_RE.fullmatch(value) is None:
        raise ValidationError("日期请按 2026-09-13 这样填；不填就是清除。", field=field)
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


def normalize_batch_fields(fields):
    normalized = {}
    for key, value in fields.items():
        path = "fields." + key
        if key == "quantity":
            value = number(value, path, integer=True, positive=True)
        elif key in ("due_date", "ready_date"):
            value = date_value(value, path)
        elif key == "remark":
            value = text(value, path, nullable=True)
        elif value not in (BATCH_PRIORITY_VALUES if key == "priority" else READY_STATUS_VALUES) or not isinstance(value, str):
            raise ValidationError("请选择有效选项。", field=path)
        normalized[key] = value
    return normalized


def normalize_batch_input(action, payload):
    if action == "delete":
        object_fields(payload, ())
        return {}
    if action not in ("create", "update"):
        raise WorkbenchCommandRejected("invalid_input", "不支持的批次操作。", 400)
    required = ("business_code", "part_ref", "fields") if action == "create" else ("fields",)
    object_fields(payload, required, required)
    fields = object_fields(payload["fields"], FIELDS, FIELDS if action == "create" else ())
    if not fields:
        raise ValidationError("至少填写一项要修改的内容。", field="fields")
    normalized_fields = normalize_batch_fields(fields)
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
        if value is None:
            normalized[key] = None
        elif key.endswith("_ref"):
            normalized[key] = public_ref(value)
        elif key == "external_days":
            if not is_external_days(value):
                raise ValidationError("外协周期" + EXTERNAL_DAYS_RANGE_TEXT + "。", field="fields." + key)
            normalized[key] = value
        else:
            normalized[key] = number(value, "fields." + key)
    return {"operation_ref": public_ref(payload["operation_ref"]), "fields": normalized}
