"""Explicit resource fields and relation references, never display-name guessing."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Literal, Optional, overload

from core.errors import ValidationError
from core.models.calendar_periods import normalize_periods, period_windows, reject_rest_day_periods
from core.models.enums import MERGE_MODE_VALUES, OP_TYPE_CATEGORY_VALUES, SHIFT_CYCLE_DAYS_MAX, SHIFT_DAY_OFFSET_MAX
from core.models.workbench_resource_status import PUBLIC_STATUS_VALUES
from core.shared.key_sets import keys_conform
from core.shared.refs import is_ref
from core.shared.stored_dates import stored_day

_FIELDS = {
    "op_type": {"category", "remark", "default_merge_mode"},
    "machine": {"status", "category", "remark"},
    "operator": {"status", "remark"},
    "machine_group": {"status", "remark"},
    "shift_profile": {"status", "remark", "anchor_date", "cycle_days", "pattern"},
}
_RELATIONS = {"op_type": set(), "machine": {"op_type_refs", "group_ref"},
              "operator": {"skill_refs", "shift_profile_ref"}, "machine_group": set(), "shift_profile": set()}
_SHIFT_BASE_DATE = date(2000, 1, 1)
_SHIFT_NEXT_DATE = date(2000, 1, 2)


def resource_object(value: Any, allowed, field: str) -> Dict[str, Any]:
    if type(value) is not dict:
        raise ValidationError("提交内容格式不对，这次操作没有执行。请刷新页面后重试。", field=field)
    if not keys_conform(value, (), allowed):
        raise ValidationError("提交内容含有不支持的项，这次操作没有执行。请刷新页面后重试。", field=field)
    return value


def resource_text(value, path, *, nullable=False):
    if value is None and nullable:
        return None
    if type(value) is not str:
        raise ValidationError("这一项必须填文字。", field=path)
    if "\x00" in value:
        raise ValidationError("这一项含有不支持的空字符，请修改后重试。", field=path)
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
    if not is_ref(value):
        raise ValidationError("请重新选择真实资料记录，不能以显示名称或内部编号代替。", field=path)
    return value


def _pattern(value):
    """Each day's rejection points at its submitted position ``fields.pattern.<i>``; the rows are stored in day order."""
    if type(value) is not list or not 1 <= len(value) <= 366:
        raise ValidationError("班次周期必须包含1至366条日期规则。", field="fields.pattern")
    days = [_pattern_day(row, "fields.pattern." + str(index)) for index, row in enumerate(value)]
    order = sorted(range(len(days)), key=lambda index: days[index]["day_offset"])
    if [days[index]["day_offset"] for index in order] != list(range(len(days))):
        raise ValidationError("班次周期必须从第0天连续填写，不能重复或遗漏日期。", field="fields.pattern")
    _validate_adjacent_shifts(days, order)
    return [days[index] for index in order]


def _pattern_day(raw, path):
    resource_object(raw, {"day_offset", "is_rest", "periods"}, path)
    offset = raw.get("day_offset")
    is_rest = raw.get("is_rest")
    if type(offset) is not int or not 0 <= offset <= SHIFT_DAY_OFFSET_MAX or type(is_rest) is not bool:
        raise ValidationError("班次日期序号和休息标记不正确。", field=path)
    try:
        periods = normalize_periods(raw.get("periods"))
        if is_rest:
            reject_rest_day_periods(periods)
    except ValidationError as exc:
        # 时段与休息日规则报中立字段名，班次档落到这一天的 fields.pattern.<i>.periods。
        raise ValidationError(exc.message, field=path + ".periods") from exc
    if not is_rest and not periods:
        raise ValidationError("工作日请至少填写一个工作时段，或明确改为休息日。", field=path + ".periods")
    return {"day_offset": offset, "is_rest": is_rest, "periods": periods}


def _validate_adjacent_shifts(days, order):
    """``order`` lists submitted positions in day order; an overlap points at the earlier day's periods."""
    effective = [None if days[index]["is_rest"] else days[index]["periods"] for index in order]
    for position, current in enumerate(effective):
        following = effective[(position + 1) % len(effective)]
        if current is None or following is None:
            continue
        left, right = period_windows(_SHIFT_BASE_DATE, current), period_windows(_SHIFT_NEXT_DATE, following)
        if left and right and left[-1][1] > right[0][0]:
            raise ValidationError("相邻轮换日期的班次时间重叠，请核对跨午夜结束时间。",
                                  field="fields.pattern." + str(order[position]) + ".periods")



def _field(kind, name, value):
    path = "fields." + name
    if name in ("remark", "category") and not (name == "category" and kind == "op_type"):
        return resource_text(value, path, nullable=True)
    if name == "pattern":
        return _pattern(value)
    if name == "cycle_days":
        if type(value) is not int or not 1 <= value <= SHIFT_CYCLE_DAYS_MAX:
            raise ValidationError(f"轮换周期必须是1至{SHIFT_CYCLE_DAYS_MAX}之间的整数。", field=path)
        return value
    if name == "anchor_date":
        if stored_day(value) is None:
            raise ValidationError("班次起始日期必须是有效的YYYY-MM-DD。", field=path)
        return value
    allowed = (PUBLIC_STATUS_VALUES[kind] if name == "status"
               else OP_TYPE_CATEGORY_VALUES if name == "category" else (None,) + MERGE_MODE_VALUES)
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
        if key in ("skill_refs", "op_type_refs"):
            if type(value) is not list or len(value) > 2000:
                raise ValidationError("工种必须是明确选择的记录列表。", field="relationships." + key)
            refs = [resource_ref(item, "relationships." + key) for item in value]
            if len(set(refs)) != len(refs):
                raise ValidationError("工种不能重复。", field="relationships." + key)
            normalized[key] = sorted(refs)
        else:
            normalized[key] = resource_ref(value, "relationships." + key, nullable=True)
    return normalized
