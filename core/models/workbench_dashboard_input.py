"""Strict patches: absent means preserve; explicit null is never a default fill."""

import re
from datetime import date, datetime
from typing import Any, Dict

from core.errors import ValidationError
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_dashboard import HANDLING_FIELDS, STATUSES


def invalid(field, message):
    raise ValidationError(message, field=field)


def _text(key, value, required):
    if value is None and key not in required:
        return None
    if type(value) is not str or "\x00" in value or len(value) > (200 if key == "owner" else 4000):
        invalid(key, "请填写有效文字，不能以数字、布尔值或对象替代。")
    return value.strip() or None


def normalize_input(action, payload):
    if type(payload) is not dict:
        raise WorkbenchCommandRejected("invalid_input", "处置输入必须是对象。", 400)
    allowed = {"reason"} if action == "reopen" else set(HANDLING_FIELDS) | {"target_status"}
    required = {"reason"} if action == "reopen" else {"remark", "target_status"}
    if set(payload) - allowed or not required <= set(payload):
        raise WorkbenchCommandRejected("invalid_input", "处置字段缺失或含未知字段，未忽略输入。", 400)
    result = {key: _text(key, value, required) for key, value in payload.items()}
    for key in required:
        if not result[key]:
            invalid(key, "请填写重开原因。" if key == "reason" else "请填写处置状态和本次核实备注。")
    if action == "transition" and result["target_status"] not in STATUSES:
        invalid("target_status", "请选择有效的处置状态。")
    if result.get("evidence_ref") is not None:
        invalid("evidence_ref", "本批尚未接入已核验附件关联，请使用凭据文字；文字不会冒充已核验引用。")
    return result


def _dates(value, now):
    deadline = value["deadline"]
    if deadline is not None:
        try:
            if date.fromisoformat(deadline).isoformat() != deadline:
                raise ValueError()
        except (ValueError, TypeError):
            invalid("deadline", "责任期限必须是有效的 YYYY-MM-DD 日期。")
    completed = value["completed_at"]
    if completed is not None:
        try:
            if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}", completed) is None:
                raise ValueError()
            parsed = datetime.fromisoformat(completed)
            if parsed > now:
                raise ValueError()
        except (TypeError, ValueError):
            invalid("completed_at", "完成时间必须是有效工厂本地时点，精确到秒且不晚于当前时点。")


def validate_handling(value, now):
    if not value["remark"]:
        invalid("remark", "请填写本次核实备注。")
    if value["status"] != "new":
        for key in ("owner", "deadline", "action"):
            if not value[key]:
                invalid(key, "跟进、待验证或关闭必须填写责任人、期限和处置动作。")
    _dates(value, now)
    if value["status"] == "closed":
        for key in ("completed_at", "completion_evidence", "evidence_reference_text"):
            if not value[key]:
                invalid(key, "关闭必须填写完成时间、具体完成结果和可核对凭据。")
        if re.fullmatch(r"(已处理|已完成|完成|已核实|已关闭|关闭|ok|done)[。.!！\s]*",
                        value["completion_evidence"], re.IGNORECASE):
            invalid("completion_evidence", "请填写具体完成结果，不能只写已处理或已完成。")


def next_handling(action, before, payload, now):
    if action == "reopen":
        if before["status"] != "closed":
            raise WorkbenchCommandRejected("constraint_conflict", "只有已关闭条目可以重开。")
        after: Dict[str, Any] = dict(before, status="following", remark=payload["reason"])
        for key in ("completed_at", "completion_evidence", "evidence_reference_text", "evidence_ref"):
            after[key] = None
    else:
        if before["status"] == "closed":
            raise WorkbenchCommandRejected("constraint_conflict", "已关闭条目只读，请通过独立重开动作填写原因。")
        after = dict(before, status=payload["target_status"])
        after.update({key: value for key, value in payload.items() if key in HANDLING_FIELDS})
    validate_handling(after, now)
    return after
