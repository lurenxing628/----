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
        reject("这条记录已失效，请刷新后重新选择。", status=400)
    return value


def factory_time(value: object) -> datetime:
    if not isinstance(value, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", value) is None:
        reject("实际时间格式不对，请按 2026-09-13 08:30:00 这样填写。")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        reject("实际时间不是有效日期。")


def _validate_quantity(value):
    if type(value) is not int or not 0 <= value <= (1 << 53) - 1:
        reject("完成数量请填 0 或正整数；不填就留空。")


def _validate_hours(value):
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        valid = False
    if not valid:
        reject("有效加工小时请填 0 或正数；不填就留空。")


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
        reject("报工里的文字填写不对或太长。")


def _validate_create(result):
    if result.get("legacy_fact_ref") and not result.get("reason", "").strip():
        reject("补齐历史完工记录必须填写原因。")
    if "reason" in result and not result.get("legacy_fact_ref"):
        reject("新增报工不用填更正原因；补齐历史记录必须选好来源记录。", status=400)
    result.setdefault("source", "manual")
    if result["source"] not in ("manual", "excel"):
        reject("报工来源只能是手工或 Excel。")
    if "report_no" in result and (not result["report_no"].strip() or result["report_no"] != result["report_no"].strip()):
        reject("报工单号不能为空或包含首尾空格。")
    if not any(key in result and result[key] is not None for key in REQUIRED_FIELDS):
        reject("报工至少要填一项实际数据。")


def _validate_revision(result):
    public_ref(result.get("original_revision_ref"))
    if not result.get("reason", "").strip():
        reject("补齐或更正必须填写原因，并选好要改的那条记录。")
    if not any(key in result for key in REPORT_FIELDS):
        reject("没有填写要补齐或更正的内容。")


def normalize_report_input(action, payload):
    if action not in ("create", "supplement", "correct") or type(payload) is not dict:
        reject("报工动作或输入结构无效。", status=400)
    extra = {"declared_operator"}
    extra |= {"source", "report_no", "legacy_fact_ref", "reason"} if action == "create" else {"original_revision_ref", "reason"}
    if set(payload) - set(REPORT_FIELDS) - extra:
        reject("报工内容含有不支持的项，这次没有保存。请刷新页面后重试。", status=400)
    result = dict(payload)
    for key, value in result.items():
        _validate_field(key, value)
    if action == "create":
        _validate_create(result)
    else:
        _validate_revision(result)
    result.setdefault("declared_operator", "")
    return result


def normalize_report_void_input(report_ref, payload):
    public_ref(report_ref)
    fields = {"original_revision_ref", "reason", "declared_operator"}
    if type(payload) is not dict or set(payload) - fields:
        reject("撤销报工的输入格式不正确。", status=400)
    public_ref(payload.get("original_revision_ref"))
    result = dict(payload, report_ref=report_ref)
    for key in ("reason", "declared_operator"):
        value = result.get(key, "")
        _validate_field(key, value)
        result[key] = value.strip()
    if not result["reason"]:
        reject("请填写撤销原因，原报工和更正记录会保留。")
    return result


def validate_actual_values(values, now):
    if not isinstance(now, datetime) or now.tzinfo is not None:
        raise ValueError("Ledger clock must return naive factory-local datetime.")
    times = {key: factory_time(values[key]) for key in ("actual_start", "actual_end") if values.get(key) is not None}
    if any(value > now for value in times.values()):
        reject("实际时间不能晚于当前时间。")
    if len(times) == 2:
        span = (times["actual_end"] - times["actual_start"]).total_seconds() / 3600
        if span < 0:
            reject("实际结束不能早于实际开始。")
        hours = values.get("effective_processing_hours")
        if hours is not None and hours > span:
            reject("有效加工小时不能超过实际起止时间的时长。")


def closed_write_context(reason="context_not_bound"):
    return {"write_token": None, "expires_at": None, "capabilities": [],
            "blocked_reasons": [{"code": reason, "message": "本页数据已过期，请刷新后核对正式计划再录入。"}]}
