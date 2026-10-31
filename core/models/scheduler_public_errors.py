from __future__ import annotations

from typing import Any, Dict, List, Optional

PUBLIC_ERROR_SCHEMA_VERSION = "1.0"
GENERIC_PUBLIC_ERROR_MESSAGE = "排产执行遇到问题，请联系管理员查看日志。"

_PUBLIC_FIELD_MAX_CHARS = 80


def _clean_text(value: Any) -> str:
    text = str(value or "").strip()
    text = text.replace("\r", " ").replace("\n", " ")
    while "  " in text:
        text = text.replace("  ", " ")
    return text


def public_safe_identifier(value: Any) -> str:
    return _clean_text(value)[:_PUBLIC_FIELD_MAX_CHARS]


def public_safe_label(value: Any) -> str:
    return _clean_text(value)[:_PUBLIC_FIELD_MAX_CHARS]


def make_public_error(
    *,
    code: str,
    message: str,
    batch_id: Any = None,
    op_id: Optional[int] = None,
    op_code: Any = None,
    seq: Optional[int] = None,
    failed_op_code: Any = None,
) -> Dict[str, Any]:
    clean_message = _clean_text(message)[:500] or GENERIC_PUBLIC_ERROR_MESSAGE
    item: Dict[str, Any] = {
        "schema_version": PUBLIC_ERROR_SCHEMA_VERSION,
        "code": code,
        "severity": "error",
        "message": clean_message,
    }

    safe_batch_id = public_safe_identifier(batch_id)
    if safe_batch_id:
        item["batch_id"] = safe_batch_id
    safe_op_code = public_safe_identifier(op_code)
    if safe_op_code:
        item["op_code"] = safe_op_code
    safe_failed_op_code = public_safe_identifier(failed_op_code)
    if safe_failed_op_code:
        item["failed_op_code"] = safe_failed_op_code

    if op_id is not None:
        item["op_id"] = op_id
    if seq is not None:
        item["seq"] = seq
    return item


def _structured_failure_message(detail: Dict[str, Any]) -> str:
    code = detail["code"]
    op_code = public_safe_identifier(detail.get("op_code")) or "-"
    failed_op_code = public_safe_identifier(detail.get("failed_op_code")) or "-"
    if code == "missing_internal_resource":
        return f"自制工序未补全设备或人员，无法排产：工序 {op_code}"
    if code == "auto_assign_resource_pool_incomplete":
        return f"自动派工资料不完整，本次无法自动补齐设备和人员：工序 {op_code}"
    if code == "auto_assign_window_blocked":
        return (
            f"排产截止日期内无法完成：工序 {op_code}。"
            "请检查排产截止日期设置或减少排产量后再排产。"
        )
    if code == "auto_assign_no_resource_combination":
        return (
            f"自动派工没有找到可用的设备和人员组合：工序 {op_code}。"
            "请检查设备工种、人员可操作设备和资源可用时间后再排产。"
        )
    if code == "schedule_window_exceeded":
        deadline = public_safe_identifier(detail.get("deadline")) or "-"
        batch_id = public_safe_identifier(detail.get("batch_id")) or "-"
        end_time = public_safe_identifier(detail.get("estimated_end_time")) or "-"
        if detail.get("source") == "external":
            if detail.get("ext_merge_mode") == "merged":
                group_id = public_safe_identifier(detail.get("ext_group_id")) or "-"
                target = f"外协组 {group_id}"
            else:
                target = f"外协工序 {op_code}"
        else:
            target = f"自制工序 {op_code}"
        return f"排产窗口截止到 {deadline}：{target}（批次 {batch_id}）预计完工 {end_time} 超出窗口"
    if code == "skipped_after_batch_failure":
        if failed_op_code != "-":
            return f"工序 {op_code}：同批前序工序 {failed_op_code} 排产失败，本次跳过。"
        return f"工序 {op_code}：同批前序工序排产失败，本次跳过。"
    if code == "graph_blocked_after_failure":
        return f"工序 {op_code}：依赖的前序工序 {failed_op_code} 排产失败，本次跳过。"
    if code == "graph_fixed_successor_order_conflict":
        return (
            f"工序 {op_code}：它的后道工序已报工，但该前道工序排产失败，"
            "报工顺序和工艺顺序不一致，本次没有继续安排该批次，请核对报工数据。"
        )
    if code == "missing_batch":
        return f"工序 {op_code} 找不到所属批次，本次无法排产。"
    raise ValueError(f"Unknown structured failure code: {code!r}")


def public_error_from_structured_failure(detail: Dict[str, Any]) -> Dict[str, Any]:
    code = detail["code"]
    message = _structured_failure_message(detail)
    return make_public_error(
        code=code,
        message=message,
        batch_id=detail["batch_id"],
        op_id=detail["op_id"],
        op_code=detail["op_code"],
        seq=detail["seq"],
        failed_op_code=detail.get("failed_op_code"),
    )


def build_public_error_records(structured_details: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    seen = set()
    for detail in structured_details:
        record = public_error_from_structured_failure(detail)
        dedupe_key = (record["code"], record["message"], record.get("op_id"), record.get("batch_id"))
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        records.append(record)
    return records


__all__ = [
    "GENERIC_PUBLIC_ERROR_MESSAGE",
    "PUBLIC_ERROR_SCHEMA_VERSION",
    "build_public_error_records",
    "make_public_error",
    "public_error_from_structured_failure",
    "public_safe_identifier",
    "public_safe_label",
]
