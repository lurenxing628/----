from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Pattern, Tuple

PUBLIC_ERROR_SCHEMA_VERSION = "1.0"
GENERIC_PUBLIC_ERROR_MESSAGE = "排产执行遇到问题，请联系管理员查看日志。"

_ALLOWED_IDENTIFIER_RE = re.compile(r"^[\w\u4e00-\u9fff./:-]{1,120}$")
_PUBLIC_ID_PATTERN = r"[\w\u4e00-\u9fff][\w\u4e00-\u9fff./_:-]{0,119}"
_DATE_PATTERN = r"[0-9]{4}-[0-9]{2}-[0-9]{2}"
_TIME_PATTERN = r"[0-9]{2}:[0-9]{2}"
_SENSITIVE_ERROR_MARKERS: Tuple[str, ...] = (
    "traceback",
    "password",
    "passwd",
    "secret",
    "token",
    "apikey",
    "api_key",
    "authorization",
    "bearer",
    "cookie",
    "session",
    "credential",
    "dsn=",
    "access_key",
    "private key",
    "sqlite",
    "operationalerror",
    "database",
    "connection string",
    "file \"",
    ".py",
    ".db",
    ".sqlite",
    ".env",
    "/users/",
    "\\users\\",
    "/home/",
    "/tmp/",
    "/var/",
    "/etc/",
    "/mnt/",
    "/root/",
    "/opt/",
    "/app/",
    "\\",
)
_PATH_LIKE_RE = re.compile(
    r"(^|\s)(/[A-Za-z0-9_.-]+/|[A-Za-z]:\\|\\\\|[^\s]*\.(?:py|db|sqlite|env)\b)",
    re.IGNORECASE,
)

LEGACY_PUBLIC_PATTERNS: Tuple[Pattern[str], ...] = (
    re.compile(rf"^自制工序未补全设备或人员，无法排产：工序 (?P<op>{_PUBLIC_ID_PATTERN})$"),
    re.compile(rf"^自制工序未补全设备或人员，而且系统自动分配失败：工序 (?P<op>{_PUBLIC_ID_PATTERN})$"),
    re.compile(
        rf"^排产窗口截止到 {_DATE_PATTERN}：(?:自制工序|外协工序|外协组) "
        rf"(?P<op>{_PUBLIC_ID_PATTERN})（批次 (?P<batch>{_PUBLIC_ID_PATTERN})）"
        rf"预计完工 {_DATE_PATTERN} {_TIME_PATTERN} 超出窗口$"
    ),
    re.compile(rf"^工时不合法：工序 (?P<op>{_PUBLIC_ID_PATTERN})(?: [^\r\n]{{1,300}})?$"),
    re.compile(rf"^外协周期不合法：工序 (?P<op>{_PUBLIC_ID_PATTERN})(?: [^\r\n]{{1,200}})?$"),
    re.compile(
        rf"^外部组合并周期未设置或不合法：批次 (?P<batch>{_PUBLIC_ID_PATTERN}) 组 (?P<group>{_PUBLIC_ID_PATTERN})"
        r"(?: total_days=[^\r\n]{1,120})?$"
    ),
)


def _clean_text(value: Any) -> str:
    text = str(value or "").strip()
    text = text.replace("\r", " ").replace("\n", " ")
    while "  " in text:
        text = text.replace("  ", " ")
    return text


def _clean_short_text(value: Any, *, max_chars: int = 120) -> str:
    text = _clean_text(value)
    return text[:max_chars]


def _contains_sensitive_marker(text: str) -> bool:
    lower_text = str(text or "").lower()
    if any(marker in lower_text for marker in _SENSITIVE_ERROR_MARKERS):
        return True
    return bool(_PATH_LIKE_RE.search(str(text or "")))


def public_safe_identifier(value: Any, *, max_chars: int = 80) -> str:
    full_text = _clean_text(value)
    if not full_text or _contains_sensitive_marker(full_text):
        return ""
    text = full_text[:max_chars]
    if text.startswith(("/", "\\")):
        return ""
    if not _ALLOWED_IDENTIFIER_RE.fullmatch(text):
        return ""
    return text[:max_chars]


def public_safe_label(value: Any, *, max_chars: int = 80) -> str:
    full_text = _clean_text(value)
    if not full_text or _contains_sensitive_marker(full_text):
        return ""
    text = full_text[:max_chars]
    return text[:max_chars]


# Backward-compatible private alias for callers inside this module.
def _safe_identifier(value: Any, *, max_chars: int = 80) -> str:
    return public_safe_identifier(value, max_chars=max_chars)


def _positive_int(value: Any) -> int:
    try:
        number = int(value or 0)
    except Exception:
        return 0
    return number if number > 0 else 0


def make_public_error(
    *,
    code: str,
    message: str,
    severity: str = "error",
    batch_id: Any = None,
    op_id: Any = None,
    op_code: Any = None,
    seq: Any = None,
    missing_fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    full_message = _clean_text(message)
    clean_message = full_message[:500]
    if not clean_message or _contains_sensitive_marker(full_message):
        clean_message = GENERIC_PUBLIC_ERROR_MESSAGE
    item: Dict[str, Any] = {
        "schema_version": PUBLIC_ERROR_SCHEMA_VERSION,
        "code": _clean_short_text(code, max_chars=80) or "scheduler_error",
        "severity": _clean_short_text(severity, max_chars=20) or "error",
        "message": clean_message,
    }

    safe_batch_id = public_safe_identifier(batch_id)
    if safe_batch_id:
        item["batch_id"] = safe_batch_id
    safe_op_code = public_safe_identifier(op_code)
    if safe_op_code:
        item["op_code"] = safe_op_code

    op_id_number = _positive_int(op_id)
    if op_id_number > 0:
        item["op_id"] = op_id_number
    seq_number = _positive_int(seq)
    if seq_number > 0:
        item["seq"] = seq_number

    if missing_fields:
        fields = [str(v).strip() for v in missing_fields if str(v).strip() in {"设备", "人员"}]
        if fields:
            item["missing_fields"] = fields[:2]
    return item


def legacy_public_error_message(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text or len(text) > 500:
        return ""
    if "\n" in text or "\r" in text:
        return ""
    if _contains_sensitive_marker(text):
        return ""
    for pattern in LEGACY_PUBLIC_PATTERNS:
        match = pattern.fullmatch(text)
        if not match:
            continue
        if text.startswith("工时不合法：工序 "):
            return f"工时不合法：工序 {match.group('op')}"
        if text.startswith("外协周期不合法：工序 "):
            return f"外协周期不合法：工序 {match.group('op')}"
        if text.startswith("外部组合并周期未设置或不合法："):
            return f"外部组合并周期未设置或不合法：批次 {match.group('batch')} 组 {match.group('group')}"
        return text[:500]
    return ""


def public_error_message_from_detail(raw: Any) -> str:
    if not isinstance(raw, dict):
        return ""

    schema_version = str(raw.get("schema_version") or "").strip()
    if schema_version and schema_version != PUBLIC_ERROR_SCHEMA_VERSION:
        return GENERIC_PUBLIC_ERROR_MESSAGE

    full_message = _clean_text(raw.get("message"))
    if not full_message:
        return ""
    if _contains_sensitive_marker(full_message):
        return GENERIC_PUBLIC_ERROR_MESSAGE
    message = full_message[:500]

    legacy_message = legacy_public_error_message(message)
    if legacy_message:
        return legacy_message
    if message == GENERIC_PUBLIC_ERROR_MESSAGE:
        return GENERIC_PUBLIC_ERROR_MESSAGE
    return GENERIC_PUBLIC_ERROR_MESSAGE


def infer_legacy_public_code(message: Any) -> str:
    text = str(message or "").strip()
    if text.startswith("自制工序未补全设备或人员"):
        return "missing_internal_resource"
    if text.startswith("排产窗口截止到 "):
        return "schedule_window_exceeded"
    if text.startswith("工时不合法：工序 "):
        return "invalid_internal_work_hours"
    if text.startswith("外协周期不合法：工序 "):
        return "invalid_external_days"
    if text.startswith("外部组合并周期未设置或不合法："):
        return "invalid_external_group_days"
    return "scheduler_error"


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


def build_public_error_records(raw_errors: Any) -> List[Dict[str, Any]]:
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
    return records


__all__ = [
    "GENERIC_PUBLIC_ERROR_MESSAGE",
    "LEGACY_PUBLIC_PATTERNS",
    "PUBLIC_ERROR_SCHEMA_VERSION",
    "build_public_error_records",
    "infer_legacy_public_code",
    "legacy_public_error_message",
    "make_public_error",
    "public_error_message_from_detail",
    "public_safe_identifier",
    "public_safe_label",
]
