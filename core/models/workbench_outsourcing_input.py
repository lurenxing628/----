"""Strict sparse patches and explicit shipment membership."""

import re
from datetime import datetime
from typing import Dict, Optional

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_outsourcing import FACT_FIELDS, MAX_MEMBERS, STATES, reference, reject


def text(value, field, limit=2000):
    if type(value) is not str or not value.strip() or "\x00" in value or len(value) > limit:
        reject("请填写有效的" + field + "，不能留空或使用非文字内容。")
    return value.strip()


def factory_time(value: object) -> datetime:
    if type(value) is not str or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}", value) is None:
        raise WorkbenchCommandRejected("invalid_input", "登记时间必须是有效工厂本地时间 YYYY-MM-DDTHH:mm:ss。", 422)
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise WorkbenchCommandRejected("invalid_input", "登记时间不是有效日期。", 422) from exc


def target_input(target):
    fields = {"kind", "batch_ref", "supplier_ref", "operation_refs"}
    if type(target) is not dict or set(target) != fields or target["kind"] not in ("single", "merged"):
        reject("须明确选择单工序或合并发出，并提供批次、供应商及全部成员引用。", status=400)
    members = target["operation_refs"]
    if type(members) is not list or not 1 <= len(members) <= MAX_MEMBERS:
        reject("登记成员必须是1至200个明确工序引用。", status=400)
    members = [reference(ref) for ref in members]
    if len(set(members)) != len(members) or (target["kind"] == "single") != (len(members) == 1):
        reject("单工序只能选一项；合并发出至少两项，成员不可重复。")
    return {"kind": target["kind"], "batch_ref": reference(target["batch_ref"]),
            "supplier_ref": reference(target["supplier_ref"]), "operation_refs": sorted(members)}


def normalize_input(payload) -> Dict[str, object]:
    if type(payload) is not dict:
        reject("外协登记输入必须是对象。", status=400)
    creating = "outsourcing_ref" not in payload
    allowed = set(FACT_FIELDS) | {"declared_operator", "reason", "target" if creating else "outsourcing_ref"}
    required = {"declared_operator", "reason", "target"} | set(FACT_FIELDS) if creating else {"declared_operator", "reason", "outsourcing_ref"}
    if set(payload) - allowed or not required <= set(payload):
        reject("外协登记字段缺失或含未知字段；未忽略输入。", status=400)
    result: Dict[str, object] = {"declared_operator": text(payload["declared_operator"], "声明人", 200),
                                 "reason": text(payload["reason"], "本次核实或更正原因")}
    if creating:
        result["target"] = target_input(payload["target"])
    else:
        result["outsourcing_ref"] = reference(payload["outsourcing_ref"])
    result.update(_fact_patch(payload))
    return result


def _fact_patch(payload):
    result = {}
    for key in FACT_FIELDS:
        if key not in payload:
            continue
        value = payload[key]
        if key == "confirmedState":
            if type(value) is not str or value not in STATES:
                reject("确认状态必须是在途、已回厂或待确认。")
        elif value is not None or key != "returned":
            factory_time(value)
        result[key] = value
    return result


def _validate_timeline(sent: datetime, planned: datetime, returned: Optional[datetime], now: datetime) -> None:
    if planned < sent or returned is not None and returned < sent:
        reject("计划回厂和实际回厂不能早于发出时间。")
    if sent > now or returned is not None and returned > now:
        reject("实际发出和实际回厂不能晚于服务端当前时点。")


def next_values(before, payload, now):
    if not isinstance(now, datetime) or now.tzinfo is not None:
        raise ValueError("Outsourcing clock must return factory-local naive datetime")
    values = dict(before or {})
    values.update({key: payload[key] for key in FACT_FIELDS if key in payload})
    if set(values) != set(FACT_FIELDS):
        reject("首次登记须明确填写发出、计划回厂、实际回厂及确认状态。")
    # Revalidate preserved facts too; a sparse correction must not bless invalid history.
    values = _fact_patch(values)
    sent, planned = factory_time(values["sent"]), factory_time(values["planned"])
    returned = factory_time(values["returned"]) if values["returned"] is not None else None
    _validate_timeline(sent, planned, returned, now)
    if (values["confirmedState"] == "returned") != (returned is not None):
        reject("已回厂状态与实际回厂时间必须同时填写；未回厂时实际回厂必须为空。")
    return values
