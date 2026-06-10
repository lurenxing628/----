from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Pattern, Tuple

PUBLIC_ERROR_SCHEMA_VERSION = "1.0"
GENERIC_PUBLIC_ERROR_MESSAGE = "排产执行遇到问题，请联系管理员查看日志。"

_ALLOWED_IDENTIFIER_RE = re.compile(r"^[\w\u4e00-\u9fff./:-]{1,120}$")
_PUBLIC_ID_PATTERN = r"[\w\u4e00-\u9fff][\w\u4e00-\u9fff./_:-]{0,119}"
_PUBLIC_OPERATION_CODE_RE = re.compile(r"^[\w\u4e00-\u9fff./_:-]+(?: [\w\u4e00-\u9fff./_:-]+)*$")
_DATE_PATTERN = r"[0-9]{4}-[0-9]{2}-[0-9]{2}"
_TIME_PATTERN = r"[0-9]{2}:[0-9]{2}"
_SGS_INTERNAL_RESOURCE_CONTEXT_PATTERN = (
    rf"^批次 {_PUBLIC_ID_PATTERN} 的"
    rf"(?:工序 {_PUBLIC_ID_PATTERN}|工序顺序 [0-9]{{1,9}}|工序)"
    r"（[^）\r\n]{1,300}）"
)
_SGS_MISSING_RESOURCE_SUFFIX_PATTERN = r"缺少(?:设备|人员|设备、人员|人员、设备)，请到批次详情补齐后再排产。"
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

# 这些正则是老中文错误串到公开错误码的反解桥；改 internal_operation/resource_validation 的中文模板时必须同步这里。
LEGACY_PUBLIC_PATTERNS: Tuple[Pattern[str], ...] = (
    re.compile(rf"^自制工序未补全设备或人员，无法排产：工序 (?P<op>{_PUBLIC_ID_PATTERN})$"),
    re.compile(rf"^自制工序未补全设备或人员，而且系统自动分配失败：工序 (?P<op>{_PUBLIC_ID_PATTERN})$"),
    re.compile(rf"^自制工序缺少自动派工所需工种信息，无法自动分配：工序 (?P<op>{_PUBLIC_ID_PATTERN})$"),
    re.compile(rf"^自动派工资料不完整，本次无法自动补齐设备和人员：工序 (?P<op>{_PUBLIC_ID_PATTERN})$"),
    re.compile(
        rf"^自动派工没有找到可用的设备和人员组合：工序 (?P<op>{_PUBLIC_ID_PATTERN})。"
        r"请检查设备工种、人员可操作设备和资源可用时间后再排产。$"
    ),
    re.compile(_SGS_INTERNAL_RESOURCE_CONTEXT_PATTERN + _SGS_MISSING_RESOURCE_SUFFIX_PATTERN + "$"),
    re.compile(_SGS_INTERNAL_RESOURCE_CONTEXT_PATTERN + r"缺少自动派工所需工种信息，请补齐工种或固定设备后再排产。$"),
    re.compile(_SGS_INTERNAL_RESOURCE_CONTEXT_PATTERN + r"自动派工资料不完整，请检查设备工种和人员可操作设备后再排产。$"),
    re.compile(_SGS_INTERNAL_RESOURCE_CONTEXT_PATTERN + r"工时不合法，请修正工时后再排产。$"),
    re.compile(
        _SGS_INTERNAL_RESOURCE_CONTEXT_PATTERN
        + r"没有找到可用的自动分配设备和人员组合，请检查设备工种、人员可操作设备和资源可用时间后再排产。$"
    ),
    re.compile(
        rf"^排产窗口截止到 {_DATE_PATTERN}：(?:自制工序|外协工序|外协组) "
        rf"(?P<op>{_PUBLIC_ID_PATTERN})（批次 (?P<batch>{_PUBLIC_ID_PATTERN})）"
        rf"预计完工 {_DATE_PATTERN} {_TIME_PATTERN} 超出窗口$"
    ),
    re.compile(
        rf"^外部组合并周期未设置或不合法：批次 (?P<batch>{_PUBLIC_ID_PATTERN}) 组 (?P<group>{_PUBLIC_ID_PATTERN})"
        r"(?: total_days=[^\r\n]{1,120})?$"
    ),
)

_LEGACY_OPERATION_ERROR_PREFIXES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("工时不合法：工序 ", (" 工时字段不合法：", " 工时总量不合法：")),
    ("外协周期不合法：工序 ", (" ext_days=",)),
)
# 这些前缀表也是 legacy 中文错误串到公开错误码的反解桥;改中文模板时必须同步这里,
# 否则 infer_legacy_public_code 会静默退回 scheduler_error,用户可见错误会丢失具体归类。
_LEGACY_CODE_PREFIXES: Tuple[Tuple[str, str], ...] = (
    ("自制工序未补全设备或人员", "missing_internal_resource"),
    ("自制工序缺少自动派工所需工种信息", "auto_assign_inputs_missing"),
    ("自动派工资料不完整", "auto_assign_resource_pool_incomplete"),
    ("自动派工没有找到可用的设备和人员组合", "auto_assign_no_resource_combination"),
    ("排产窗口截止到 ", "schedule_window_exceeded"),
    ("工时不合法：工序 ", "invalid_internal_work_hours"),
    ("外协周期不合法：工序 ", "invalid_external_days"),
    ("外部组合并周期未设置或不合法：", "invalid_external_group_days"),
)
# 这些后缀表专门反解 scheduler_generate_schedule 的资源校验中文尾巴;
# 改 internal_operation/resource_validation 模板时不要只改产出方。
_SGS_AUTO_ASSIGN_SUFFIX_CODES: Tuple[Tuple[str, str], ...] = (
    ("缺少自动派工所需工种信息，请补齐工种或固定设备后再排产。", "auto_assign_inputs_missing"),
    ("自动派工资料不完整，请检查设备工种和人员可操作设备后再排产。", "auto_assign_resource_pool_incomplete"),
    ("工时不合法，请修正工时后再排产。", "invalid_internal_work_hours"),
    (
        "没有找到可用的自动分配设备和人员组合，请检查设备工种、人员可操作设备和资源可用时间后再排产。",
        "auto_assign_no_resource_combination",
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
    legacy_operation_message = _legacy_operation_error_message(text)
    if legacy_operation_message:
        return legacy_operation_message
    for pattern in LEGACY_PUBLIC_PATTERNS:
        match = pattern.fullmatch(text)
        if not match:
            continue
        if text.startswith("外部组合并周期未设置或不合法："):
            return f"外部组合并周期未设置或不合法：批次 {match.group('batch')} 组 {match.group('group')}"
        return text[:500]
    return ""


def _legacy_operation_error_message(text: str) -> str:
    for prefix, detail_markers in _LEGACY_OPERATION_ERROR_PREFIXES:
        if not text.startswith(prefix):
            continue
        op_code = _legacy_operation_error_op_code(text[len(prefix) :], detail_markers=detail_markers)
        return f"{prefix}{op_code}" if op_code else ""
    return ""


def _legacy_operation_error_op_code(tail: str, *, detail_markers: Tuple[str, ...]) -> str:
    op_code = str(tail or "").strip()
    for marker in detail_markers:
        if marker in op_code:
            op_code = op_code.split(marker, 1)[0].strip()
            break
    if not op_code or len(op_code) > 120:
        return ""
    if _PUBLIC_OPERATION_CODE_RE.fullmatch(op_code):
        return op_code
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
    # 故意用中文前缀/后缀反解旧错误码:旧链路没有结构化 code,只能从已渲染文案倒推。
    # 模板和上面的三张反解表必须同生共死,否则会静默归类成 scheduler_error。
    text = str(message or "").strip()
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
