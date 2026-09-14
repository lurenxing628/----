"""Explicit resource fields and relation references, never display-name guessing."""

from __future__ import annotations

import re
from datetime import date
from typing import Literal, Optional, overload

from core.errors import ValidationError

_FIELDS = {
    "op_type": {"category", "remark", "default_merge_mode"},
    "machine": {"status", "category", "remark"},
    "operator": {"status", "remark"},
    "machine_group": {"status", "remark"},
    "shift_profile": {"status", "remark", "anchor_date", "cycle_days", "pattern"},
}
_RELATIONS = {"op_type": set(), "machine": {"op_type_ref", "group_ref"},
              "operator": {"skill_refs", "shift_profile_ref"}, "machine_group": set(), "shift_profile": set()}
_STATUS = {"machine": ("active", "maintain", "inactive"), "operator": ("active", "leave", "inactive"),
           "machine_group": ("active", "inactive"), "shift_profile": ("active", "inactive")}


def resource_object(value, allowed, path):
    if type(value) is not dict or any(type(key) is not str or key not in allowed for key in value):
        raise ValidationError("提交内容格式不对或含有不支持的项，这次操作没有执行。请刷新页面后重试。", field=path)
    return value


def resource_text(value, path, *, nullable=False):
    if value is None and nullable:
        return None
    if type(value) is not str:
        raise ValidationError("这一项必须填文字。", field=path)
    text = value.strip()
    if not text and not nullable:
        raise ValidationError("这一项不能为空。", field=path)
    return text or None


@overload
def resource_ref(value, path, *, nullable: Literal[False] = False) -> str: ...


@overload
def resource_ref(value, path, *, nullable: Literal[True]) -> Optional[str]: ...


def resource_ref(value, path, *, nullable=False):
    if value is None and nullable:
        return None
    if type(value) is not str or re.fullmatch("[0-9a-f]{48}", value) is None:
        raise ValidationError("请重新选择真实资料记录，不能以显示名称或内部编号代替。", field=path)
    return value


def _pattern(value):
    if type(value) is not list or not 1 <= len(value) <= 366:
        raise ValidationError("班次周期必须包含1至366条日期规则。", field="fields.pattern")
    days = []
    for row in value:
        resource_object(row, {"day_offset", "is_rest", "shift_start", "shift_end"}, "fields.pattern")
        offset = row.get("day_offset")
        if type(offset) is not int or not 0 <= offset <= 365 or type(row.get("is_rest")) is not bool:
            raise ValidationError("班次日期序号和休息标记不正确。", field="fields.pattern")
        for key in ("shift_start", "shift_end"):
            if type(row.get(key)) is not str or re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", row[key]) is None:
                raise ValidationError("班次开始和结束必须为HH:MM。", field="fields.pattern." + key)
        days.append(dict(row))
    days.sort(key=lambda row: row["day_offset"])
    if [row["day_offset"] for row in days] != list(range(len(days))):
        raise ValidationError("班次周期必须从第0天连续填写，不能重复或遗漏日期。", field="fields.pattern")
    _validate_adjacent_shifts(days)
    return days


def _validate_adjacent_shifts(days):
    for index, day in enumerate(days):
        following = days[(index + 1) % len(days)]
        if day["is_rest"] or following["is_rest"]:
            continue
        start, end, next_start = [_clock_minutes(value) for value in (day["shift_start"], day["shift_end"], following["shift_start"])]
        finish = end + (1440 if end <= start else 0)
        if finish > 1440 + next_start:
            raise ValidationError("相邻轮换日期的班次时间重叠，请核对跨午夜结束时间。", field="fields.pattern")
def _clock_minutes(value):
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def _field(kind, name, value):
    path = "fields." + name
    if name in ("remark", "category") and not (name == "category" and kind == "op_type"):
        return resource_text(value, path, nullable=True)
    if name == "pattern":
        return _pattern(value)
    if name == "cycle_days":
        if type(value) is not int or not 1 <= value <= 366:
            raise ValidationError("轮换周期必须是1至366之间的整数。", field=path)
        return value
    if name == "anchor_date":
        try:
            if type(value) is not str or date.fromisoformat(value).isoformat() != value:
                raise ValueError
        except (TypeError, ValueError):
            raise ValidationError("班次起始日期必须是有效的YYYY-MM-DD。", field=path) from None
        return value
    allowed = _STATUS[kind] if name == "status" else (("internal", "external") if name == "category" else (None, "separate", "merged"))
    if value not in allowed:
        raise ValidationError("这一项的选项不正确。", field=path)
    return value


def normalize_resource_input(kind, action, payload):
    if type(kind) is not str or kind not in _FIELDS or type(action) is not str or action not in ("create", "update", "delete"):
        raise ValidationError("资源类型或操作不受支持。", field="action")
    allowed = set() if action == "delete" else {"label", "fields", "relationships"}
    if action == "create":
        allowed.add("business_code")
    resource_object(payload, allowed, "input")
    if action == "delete":
        return {}
    result = {}
    if action == "create":
        result["business_code"] = resource_text(payload.get("business_code"), "business_code")
    if action == "create" or "label" in payload:
        result["label"] = resource_text(payload.get("label"), "label")
    fields = resource_object(payload.get("fields", {}), _FIELDS[kind], "fields")
    result["fields"] = {key: _field(kind, key, value) for key, value in fields.items()}
    if kind == "shift_profile" and action == "create" and not {"anchor_date", "cycle_days", "pattern"} <= fields.keys():
        raise ValidationError("新增班次必须填起始日期、轮换周期和每天的时间，不能只填名称。", field="fields")
    result["relationships"] = _normalize_relations(kind, payload.get("relationships", {}))
    return result


def _normalize_relations(kind, value):
    relations = resource_object(value, _RELATIONS[kind], "relationships")
    normalized = {}
    for key, value in relations.items():
        if key == "skill_refs":
            if type(value) is not list or len(value) > 2000:
                raise ValidationError("技能工种必须是明确选择的记录列表。", field="relationships.skill_refs")
            refs = [resource_ref(item, "relationships.skill_refs") for item in value]
            if len(set(refs)) != len(refs):
                raise ValidationError("技能工种不能重复。", field="relationships.skill_refs")
            normalized[key] = sorted(refs)
        else:
            normalized[key] = resource_ref(value, "relationships." + key, nullable=True)
    return normalized
