"""Strict sparse report input; an omitted field never means zero or clearing."""

import math
import re
from datetime import datetime
from typing import NoReturn

from core.models.workbench_command import WorkbenchCommandRejected

REPORT_FIELDS = ("actual_start", "actual_end", "completed_quantity", "effective_processing_hours",
                 "actual_machine_ref", "actual_operator_ref", "remark")
REQUIRED_FIELDS = REPORT_FIELDS[:-1]
MAX_OPERATIONS = 10000
MAX_FACT_ROWS = 50000
MAX_REPORT_BYTES = 16 * 1024 * 1024


def reject(message: str, code: str = "invalid_input", status: int = 422) -> NoReturn:
    raise WorkbenchCommandRejected(code, message, status)


def public_ref(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{48}", value) is None:
        reject("永久引用无效，不能使用内部编号或显示名称代替。", status=400)
    return value


def factory_time(value: object) -> datetime:
    if not isinstance(value, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", value) is None:
        reject("实际时间必须是工厂本地时间 YYYY-MM-DDTHH:mm:ss。")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        reject("实际时间不是有效日期。")


def _validate_quantity(value):
    if type(value) is not int or not 0 <= value <= (1 << 53) - 1:
        reject("完成数量必须是有限非负整数，未填写请保留空值。")


def _validate_hours(value):
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        valid = False
    if not valid:
        reject("有效加工小时必须是有限非负数，未填写请保留空值。")


def _validate_field(key, value):
    if key in ("actual_start", "actual_end"):
        if value is not None:
            factory_time(value)
    elif key == "completed_quantity":
        if value is not None:
            _validate_quantity(value)
    elif key == "effective_processing_hours":
        if value is not None:
            _validate_hours(value)
    elif key.endswith("_ref"):
        if value is not None:
            public_ref(value)
    elif not isinstance(value, str) or "\x00" in value or len(value) > (64 if key == "report_no" else 2000):
        reject("报工文字字段无效或过长。")


def _validate_create(result):
    if result.get("legacy_fact_ref") and not result.get("reason", "").strip():
        reject("补录旧完工事实必须填写明确原因。")
    if "reason" in result and not result.get("legacy_fact_ref"):
        reject("普通新增不接受更正原因字段；旧事实补录必须提供明确来源引用。", status=400)
    result.setdefault("source", "manual")
    if result["source"] not in ("manual", "excel"):
        reject("报工来源只能是手工或 Excel。")
    if "report_no" in result and (not result["report_no"].strip() or result["report_no"] != result["report_no"].strip()):
        reject("报工单号不能为空或包含首尾空格。")
    if not any(key in result and result[key] is not None for key in REQUIRED_FIELDS):
        reject("报工至少需要填写一项实际事实。")


def _validate_revision(result):
    public_ref(result.get("original_revision_ref"))
    if not result.get("reason", "").strip():
        reject("补齐或更正必须填写原因并引用原记录版本。")
    if not any(key in result for key in REPORT_FIELDS):
        reject("未提供要补齐或更正的字段。")


def normalize_report_input(action, payload):
    if action not in ("create", "supplement", "correct") or type(payload) is not dict:
        reject("报工动作或输入结构无效。", status=400)
    extra = {"declared_operator"}
    extra |= {"source", "report_no", "legacy_fact_ref", "reason"} if action == "create" else {"original_revision_ref", "reason"}
    if set(payload) - set(REPORT_FIELDS) - extra:
        reject("报工包含未登记字段，不会忽略或覆盖隐藏数据。", status=400)
    result = dict(payload)
    for key, value in result.items():
        _validate_field(key, value)
    if action == "create":
        _validate_create(result)
    else:
        _validate_revision(result)
    result.setdefault("declared_operator", "")
    return result


def validate_actual_values(values, now):
    if not isinstance(now, datetime) or now.tzinfo is not None:
        raise ValueError("Ledger clock must return naive factory-local datetime.")
    times = {key: factory_time(values[key]) for key in ("actual_start", "actual_end") if values.get(key) is not None}
    if any(value > now for value in times.values()):
        reject("实际记录不得晚于服务端确认的当前时点。")
    if len(times) == 2:
        span = (times["actual_end"] - times["actual_start"]).total_seconds() / 3600
        if span < 0:
            reject("实际结束不能早于实际开始。")
        hours = values.get("effective_processing_hours")
        if hours is not None and hours > span:
            reject("有效加工小时不能超过本次实际起止跨度。")


def closed_write_context(reason="context_not_bound"):
    return {"write_token": None, "expires_at": None, "capabilities": [],
            "blocked_reasons": [{"code": reason, "message": "当前上下文不可录入，请刷新并核对正式计划。"}]}
