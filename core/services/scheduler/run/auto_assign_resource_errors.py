from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from core.models.scheduler_public_errors import infer_legacy_public_code, legacy_public_error_message

AUTO_ASSIGN_RESOURCE_ERROR_PREFIXES = (
    "自动派工没有找到可用的设备和人员组合：工序 ",
    "自动派工资料不完整，本次无法自动补齐设备和人员：工序 ",
)
AUTO_ASSIGN_INVALID_HOURS_PREFIX = "工时不合法：工序 "
AUTO_ASSIGN_RESOURCE_ERROR_CODES = {
    "auto_assign_resource_pool_incomplete",
    "auto_assign_no_resource_combination",
}
SGS_AUTO_ASSIGN_RESOURCE_ERROR_CODES = {*AUTO_ASSIGN_RESOURCE_ERROR_CODES, "invalid_internal_work_hours"}


def is_auto_assign_resource_error(message: Any) -> bool:
    text = str(message or "").strip()
    if any(text.startswith(prefix) for prefix in AUTO_ASSIGN_RESOURCE_ERROR_PREFIXES):
        return True
    if text.startswith(AUTO_ASSIGN_INVALID_HOURS_PREFIX):
        return bool(legacy_public_error_message(text) == text)
    return text.startswith("批次 ") and infer_legacy_public_code(text) in SGS_AUTO_ASSIGN_RESOURCE_ERROR_CODES


def public_auto_assign_resource_error_message(message: Any) -> str:
    text = str(message or "").strip()
    if not is_auto_assign_resource_error(text):
        return ""
    return legacy_public_error_message(text)


def first_public_auto_assign_resource_error(messages: Optional[List[str]]) -> str:
    for item in messages or ():
        public_message = public_auto_assign_resource_error_message(item)
        if public_message:
            return public_message
    return ""


def auto_assign_failed_op_ids_from_failure_details(failure_details: List[Dict[str, Any]]) -> Set[int]:
    return {
        int(detail["op_id"])
        for detail in failure_details
        if is_auto_assign_resource_error(detail.get("error_message"))
    }
