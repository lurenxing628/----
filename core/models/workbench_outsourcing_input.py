"""Strict sparse patches and explicit shipment membership."""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

from core.models.enums import OUTSOURCING_TARGET_KIND_VALUES
from core.models.workbench_outsourcing import FACT_FIELDS, MAX_MEMBERS, STATES, reference, reject
from core.shared.filled_text import is_filled_text
from core.shared.key_sets import keys_conform
from core.shared.stored_dates import stored_local_iso_datetime


def text(value, path, label, limit=2000):
    if not is_filled_text(value, limit):
        reject("请填写有效的" + label + "，不能留空或使用非文字内容。", fields=(path,))
    return value.strip()


def factory_time(value: object, path: str, *, parsed_times: Optional[Dict[str, datetime]] = None) -> datetime:
    if parsed_times is not None and type(value) is str and value in parsed_times:
        return parsed_times[value]
    if type(value) is not str or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}", value) is None:
        reject("登记时间格式不对，请按 2026-09-13 08:30:00 这样填写。", fields=(path,))
    parsed = stored_local_iso_datetime(value)
    if parsed is None:
        reject("登记时间不是有效日期。", fields=(path,))
    if parsed_times is not None:
        parsed_times[value] = parsed
    return parsed


def target_input(target):
    fields = {"kind", "batch_ref", "supplier_ref", "operation_refs"}
    if type(target) is not dict or set(target) != fields or target["kind"] not in OUTSOURCING_TARGET_KIND_VALUES:
        reject("请选择单工序发出或合并发出，并选好批次、供应商和全部工序。", status=400)
    members = target["operation_refs"]
    if type(members) is not list or not 1 <= len(members) <= MAX_MEMBERS:
        reject("一次最少选 1 道工序、最多选 200 道工序。", status=400)
    members = [reference(ref) for ref in members]
    if len(set(members)) != len(members) or (target["kind"] == "single") != (len(members) == 1):
        reject("单工序只能选一项；合并发出至少两项，成员不可重复。")
    return {"kind": target["kind"], "batch_ref": reference(target["batch_ref"]),
            "supplier_ref": reference(target["supplier_ref"]), "operation_refs": sorted(members)}


def normalize_input(payload, *, parsed_times: Optional[Dict[str, datetime]] = None) -> Dict[str, object]:
    if type(payload) is not dict:
        reject("提交内容格式不对，这次登记没有保存。请刷新页面后重试。", status=400)
    creating = "outsourcing_ref" not in payload
    allowed = set(FACT_FIELDS) | {"declared_operator", "reason", "target" if creating else "outsourcing_ref"}
    required = {"declared_operator", "reason", "target"} | set(FACT_FIELDS) if creating else {"declared_operator", "reason", "outsourcing_ref"}
    if not keys_conform(payload, required, allowed):
        reject("外协登记缺少必填项或含有多余项，这次登记没有保存。请刷新页面后重试。", status=400)
    result: Dict[str, object] = {"declared_operator": text(payload["declared_operator"], "declared_operator", "经办人", 200),
                                 "reason": text(payload["reason"], "reason", "本次核实或更正原因")}
    if creating:
        result["target"] = target_input(payload["target"])
    else:
        result["outsourcing_ref"] = reference(payload["outsourcing_ref"])
    result.update(_fact_patch(payload, parsed_times=parsed_times))
    return result


def _fact_patch(payload, *, parsed_times: Optional[Dict[str, datetime]] = None):
    result = {}
    for key in FACT_FIELDS:
        if key not in payload:
            continue
        value = payload[key]
        if key == "confirmedState":
            if type(value) is not str or value not in STATES:
                reject("确认状态必须是在途、已回厂或待确认。", fields=(key,))
        elif value is not None or key != "returned":
            factory_time(value, key, parsed_times=parsed_times)
        result[key] = value
    return result


def _validate_timeline(sent: datetime, planned: datetime, returned: Optional[datetime]) -> None:
    early = (("planned",) if planned < sent else ()) + (("returned",) if returned is not None and returned < sent else ())
    if early:
        reject("计划回厂和实际回厂不能早于发出时间。", fields=early)


@dataclass
class PreparedReceiptValues:
    values: dict
    sent: datetime
    returned: Optional[datetime]

    def check_recording_time(self, now):
        late = (("sent",) if self.sent > now else ()) + (("returned",) if self.returned is not None and self.returned > now else ())
        if late:
            reject("实际发出和实际回厂不能晚于当前时间。", fields=late)


def prepare_values(before, payload, now, *, parsed_times: Optional[Dict[str, datetime]] = None):
    values = dict(before or {})
    values.update({key: payload[key] for key in FACT_FIELDS if key in payload})
    if set(values) != set(FACT_FIELDS):
        reject("新增登记要填写发出时间、计划回厂、实际回厂和确认状态。")
    # Preserved facts are parsed here together with the patch; later recording
    # only compares the already parsed actual times with its new clock value.
    if type(values["confirmedState"]) is not str or values["confirmedState"] not in STATES:
        reject("确认状态必须是在途、已回厂或待确认。", fields=("confirmedState",))
    sent = factory_time(values["sent"], "sent", parsed_times=parsed_times)
    planned = factory_time(values["planned"], "planned", parsed_times=parsed_times)
    returned = (
        factory_time(values["returned"], "returned", parsed_times=parsed_times)
        if values["returned"] is not None
        else None
    )
    _validate_timeline(sent, planned, returned)
    result = PreparedReceiptValues(values, sent, returned)
    result.check_recording_time(now)
    if (values["confirmedState"] == "returned") != (returned is not None):
        reject("已回厂状态与实际回厂时间必须同时填写；未回厂时实际回厂必须为空。", fields=("confirmedState", "returned"))
    return result
