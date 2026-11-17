"""Explicit single-machine downtime input; no business-code based mutation.

停机起止的唯一事实是整数微秒 ``start_us/end_us``；``start_time/end_time`` 只作展示，写入时由微秒生成，读侧不解析。
库里的起止由 MachineDowntimes 的 CHECK 定型，运行、试调归档里的 JSON 副本由 ``production_capture.validate_production_archive``
准入，读侧都直接用 ``us_to_datetime`` 换算。
"""

import re
from datetime import datetime

from core.models.enums import MACHINE_DOWNTIME_REASON_VALUES
from core.models.workbench_command import WorkbenchCommandRejected
from core.shared.key_sets import keys_conform
from core.shared.local_datetime import datetime_to_us
from core.shared.refs import is_ref
from core.shared.stored_dates import stored_local_iso_datetime


def _time(value) -> datetime:
    if type(value) is not str or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}(:[0-9]{2})?", value) is None:
        raise WorkbenchCommandRejected("invalid_input", "停机起止须填写年月日和时分。", 422)
    parsed = stored_local_iso_datetime(value, allow_space=True, allow_minutes_only=True)
    if parsed is None:
        raise WorkbenchCommandRejected("invalid_input", "停机日期或时刻不存在，请核对。", 422)
    return parsed


def normalize_downtime(action, value):
    allowed = {"start_time", "end_time", "reason_code", "reason_detail"} if action != "cancel" else set()
    if action != "create":
        allowed.add("downtime_ref")
    if action not in ("create", "update", "cancel") or not keys_conform(value, (), allowed):
        raise WorkbenchCommandRejected("invalid_input", "停机资料格式不正确，请刷新后重新填写。", 422)
    result = {}
    if action != "create":
        ref = value.get("downtime_ref")
        if not is_ref(ref):
            raise WorkbenchCommandRejected("invalid_input", "请选择有效的停机记录。", 422)
        result["downtime_ref"] = ref
    if action == "cancel":
        return result
    return {**result, **_window_fields(value)}


def _window_fields(value):
    start, end = _time(value.get("start_time")), _time(value.get("end_time"))
    if end <= start:
        raise WorkbenchCommandRejected("invalid_input", "停机结束必须晚于开始。", 422)
    reason, detail = value.get("reason_code"), value.get("reason_detail")
    if type(reason) is not str or reason not in MACHINE_DOWNTIME_REASON_VALUES or detail is not None and type(detail) is not str:
        raise WorkbenchCommandRejected("invalid_input", "请选择停机原因，并使用文字填写说明。", 422)
    return {
        "start_us": datetime_to_us(start),
        "end_us": datetime_to_us(end),
        "reason_code": reason,
        "reason_detail": (detail.strip() or None) if detail is not None else None,
    }
