from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

PUBLIC_ERROR_SCHEMA_VERSION = "1.0"
GENERIC_PUBLIC_ERROR_MESSAGE = "排产执行遇到问题，请联系管理员查看日志。"

_PUBLIC_FIELD_MAX_CHARS = 80

# internal_operation._auto_assign_failure_message 的工时无效文案：前缀后面只跟工序编号。
_INVALID_HOURS_ERROR_PREFIX = "工时不合法：工序 "
# 这些前缀表是 legacy 中文错误串到公开错误码的反解桥;改中文模板时必须同步这里,
# 否则 infer_legacy_public_code 会静默退回 scheduler_error,用户可见错误会丢失具体归类。
_LEGACY_CODE_PREFIXES: Tuple[Tuple[str, str], ...] = (
    ("自制工序未补全设备或人员", "missing_internal_resource"),
    ("自动派工资料不完整", "auto_assign_resource_pool_incomplete"),
    ("自动派工没有找到可用的设备和人员组合", "auto_assign_no_resource_combination"),
    ("排产截止日期内无法完成：工序 ", "auto_assign_window_blocked"),
    ("排产窗口截止到 ", "schedule_window_exceeded"),
    ("工时不合法：工序 ", "invalid_internal_work_hours"),
)
# 这些后缀表专门反解 scheduler_generate_schedule 的资源校验中文尾巴;
# 改 internal_operation/resource_validation 模板时不要只改产出方。
_SGS_AUTO_ASSIGN_SUFFIX_CODES: Tuple[Tuple[str, str], ...] = (
    ("自动派工资料不完整，请检查设备工种和人员可操作设备后再排产。", "auto_assign_resource_pool_incomplete"),
    ("工时不合法，请修正工时后再排产。", "invalid_internal_work_hours"),
    (
        "没有找到可用的自动分配设备和人员组合，请检查设备工种、人员可操作设备和资源可用时间后再排产。",
        "auto_assign_no_resource_combination",
    ),
    # 窗口截止归因（A07）：不进 auto_assign 资源错误集合（它不是资质/资料问题），
    # 只用于把 SGS 上下文文案反解回 auto_assign_window_blocked。
    (
        "在排产截止日期内无法完成，请检查排产截止日期设置或减少排产量后再排产。",
        "auto_assign_window_blocked",
    ),
)
# 缺资源尾巴的两种顺序都要保留;这里不是重复文案,而是在承接历史中文串。
_SGS_MISSING_RESOURCE_SUFFIX_CODES: Tuple[Tuple[str, str], ...] = (
    ("缺少设备，请到批次详情补齐后再排产。", "missing_internal_resource"),
    ("缺少人员，请到批次详情补齐后再排产。", "missing_internal_resource"),
    ("缺少设备、人员，请到批次详情补齐后再排产。", "missing_internal_resource"),
    ("缺少人员、设备，请到批次详情补齐后再排产。", "missing_internal_resource"),
)
_SGS_RESOURCE_SUFFIX_CODES = _SGS_MISSING_RESOURCE_SUFFIX_CODES + _SGS_AUTO_ASSIGN_SUFFIX_CODES
_STRUCTURED_FAILURE_CODES = {
    "dispatch_operation_failed",
    "graph_blocked_after_failure",
    "graph_fixed_successor_order_conflict",
    "missing_batch",
    "skipped_after_batch_failure",
}


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

    # 结构化失败明细的 op_id/seq 由 ScheduleRunState._op_identity 取自已校验的工序（正整数）；
    # 旧中文错误串路径不带工序身份，传 None。
    if op_id is not None:
        item["op_id"] = op_id
    if seq is not None:
        item["seq"] = seq
    return item


def legacy_public_error_message(raw: str) -> str:
    text = raw.strip()
    if not text or len(text) > 500 or "\n" in text or "\r" in text:
        return ""
    if text.startswith(_INVALID_HOURS_ERROR_PREFIX) and not text[len(_INVALID_HOURS_ERROR_PREFIX) :].strip():
        return ""
    return text if infer_legacy_public_code(text) != "scheduler_error" else ""


def _structured_failure_message(detail: Dict[str, Any]) -> str:
    code = detail["code"]
    op_code = public_safe_identifier(detail.get("op_code")) or "-"
    failed_op_code = public_safe_identifier(detail.get("failed_op_code")) or "-"
    if code == "dispatch_operation_failed":
        return f"工序 {op_code} 没有形成有效排程，本次没有继续安排该批次后续工序。"
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
    return ""


def _public_error_from_structured_failure(detail: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    code = detail["code"]
    if code not in _STRUCTURED_FAILURE_CODES:
        return None
    message = _structured_failure_message(detail)
    return make_public_error(
        code=code,
        message=message,
        batch_id=detail.get("batch_id"),
        op_id=detail.get("op_id"),
        op_code=detail.get("op_code"),
        seq=detail.get("seq"),
        failed_op_code=detail.get("failed_op_code"),
    )


def infer_legacy_public_code(text: str) -> str:
    # 故意用中文前缀/后缀反解旧错误码:旧链路没有结构化 code,只能从已渲染文案倒推。
    # 模板和上面的三张反解表必须同生共死,否则会静默归类成 scheduler_error。
    if text.startswith("批次 "):
        code = _code_from_suffixes(text, _SGS_RESOURCE_SUFFIX_CODES)
        if code:
            return code
    for prefix, code in _LEGACY_CODE_PREFIXES:
        if text.startswith(prefix):
            return code
    return "scheduler_error"


def _code_from_suffixes(text: str, suffixes: Tuple[Tuple[str, str], ...]) -> str:
    for suffix, code in suffixes:
        if text.endswith(suffix):
            return code
    return ""


def _normalize_error_list(raw_errors: Any) -> List[str]:
    if raw_errors is None:
        values: Iterable[Any] = []
    elif isinstance(raw_errors, str):
        values = [raw_errors]
    elif isinstance(raw_errors, (list, tuple, set)):
        values = list(raw_errors)
    else:
        values = [raw_errors]

    out: List[str] = []
    for value in values:
        text = str(value or "").strip()
        if text:
            out.append(text)
    return out


def build_public_error_records(raw_errors: Any, structured_details: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    seen = set()
    for raw in _normalize_error_list(raw_errors):
        public_message = legacy_public_error_message(raw)
        if public_message:
            code = infer_legacy_public_code(public_message)
        else:
            public_message = GENERIC_PUBLIC_ERROR_MESSAGE
            code = "generic_scheduler_error"

        dedupe_key = (code, public_message)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        records.append(make_public_error(code=code, message=public_message))
    for detail in structured_details:
        record = _public_error_from_structured_failure(detail)
        if record is None:
            continue
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
    "infer_legacy_public_code",
    "legacy_public_error_message",
    "make_public_error",
    "public_safe_identifier",
    "public_safe_label",
]
