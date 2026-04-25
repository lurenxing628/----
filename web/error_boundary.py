from __future__ import annotations

import html
import json
import re
from typing import Any, Optional

from flask import current_app, jsonify, render_template, request

from core.infrastructure.errors import AppError, ErrorCode, app_error_http_status, error_response

_INTERNAL_ASCII_RE = re.compile(r"[A-Za-z]")
_INTERNAL_KEY_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]*\b")
_MACHINE_FIELD_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_PATH_LIKE_RE = re.compile(r"(^|[\s:：,，;；(（\[{])(/[A-Za-z0-9_.-]|[A-Za-z]:[\\/]|\\\\|\.{1,2}/)")
_PUBLIC_DIAGNOSTIC_REASONS = {
    "invalid_query_date",
    "invalid_schedule_rows",
    "no_actionable_schedule_rows",
    "out_of_scope_schedule_rows",
}
_PUBLIC_DETAIL_MODES = {"reject_need_async"}
_PUBLIC_LITERAL_MESSAGE_FIELDS = {"version"}
_GENERIC_ERROR_MESSAGES = {
    ErrorCode.NOT_FOUND: "请求的资源不存在或已不可用。",
    ErrorCode.PERMISSION_DENIED: "当前操作没有权限或不允许执行。",
    ErrorCode.DUPLICATE_ENTRY: "请求与现有数据冲突，请调整后重试。",
    ErrorCode.FILE_TOO_LARGE: "上传文件过大，请缩小文件后重试。",
    ErrorCode.DB_CONNECTION_ERROR: "数据访问失败，请稍后重试。",
    ErrorCode.DB_QUERY_ERROR: "数据访问失败，请稍后重试。",
    ErrorCode.DB_TRANSACTION_ERROR: "数据访问失败，请稍后重试。",
    ErrorCode.DB_INTEGRITY_ERROR: "请求与现有数据冲突，请调整后重试。",
}
_KNOWN_FIELD_LABELS = {
    "end_date": "结束日期",
    "machine_id": "设备",
    "offset": "偏移周数",
    "operator_id": "人员",
    "period_preset": "时间范围",
    "query_date": "查询日期",
    "scope_id": "范围对象",
    "scope_type": "范围类型",
    "start_date": "开始日期",
    "team_axis": "班组维度",
    "team_id": "班组",
    "version": "版本",
    "view": "视图",
    "week_start": "周起始日期",
}


def _normalized_reason(details: Any) -> str:
    if not isinstance(details, dict):
        return ""
    return str(details.get("reason") or "").strip().lower()


def _field_only_details(exc: AppError) -> Optional[dict]:
    details = exc.details if isinstance(exc.details, dict) else {}
    field = str(details.get("field") or "").strip()
    field_label = get_user_visible_field_label(field)
    return {"field": field_label} if field_label else None


def _looks_internal_message(message: str) -> bool:
    text = str(message or "").strip()
    return bool(text) and bool(_INTERNAL_ASCII_RE.search(text)) and not re.search(r"[\u4e00-\u9fff]", text)


def _generic_app_error_message(code: ErrorCode) -> str:
    if code in _GENERIC_ERROR_MESSAGES:
        return _GENERIC_ERROR_MESSAGES[code]
    if code.value.startswith("2"):
        return "数据访问失败，请稍后重试。"
    if code.value.endswith("02"):
        return "请求与现有数据冲突，请调整后重试。"
    if code.value.endswith("03") or code.value.endswith("04") or code.value.endswith("05"):
        return "当前操作无法完成，请调整后重试。"
    return "操作失败，请稍后重试。"


def _looks_internal_non_validation_message(message: str) -> bool:
    text = str(message or "").strip()
    if not text:
        return False
    if _looks_internal_message(text):
        return True
    if _message_mentions_machine_key(text):
        return True
    if _message_mentions_path_like(text):
        return True
    return False


def get_user_visible_field_label(field: Any) -> str:
    key = str(field or "").strip()
    if not key:
        return ""
    try:
        from core.services.scheduler.config.config_field_spec import field_label_for

        label = str(field_label_for(key) or "").strip()
    except Exception:
        label = ""
    if label and label != key:
        return label
    return str(_KNOWN_FIELD_LABELS.get(key) or "").strip()


def _message_mentions_internal_field(message: str, field: str) -> bool:
    text = str(message or "").strip()
    key = str(field or "").strip()
    if not text or not key:
        return False
    if key in _PUBLIC_LITERAL_MESSAGE_FIELDS:
        return False
    if not _MACHINE_FIELD_RE.match(key):
        return False
    return key in text


def _message_mentions_machine_key(message: str) -> bool:
    return bool(_INTERNAL_KEY_RE.search(str(message or "")))


def _message_mentions_path_like(message: str) -> bool:
    return bool(_PATH_LIKE_RE.search(str(message or "")))


def _public_invalid_query_details(details: dict) -> dict:
    invalid_query_keys = details.get("invalid_query_keys")
    if not isinstance(invalid_query_keys, list):
        return {}
    raw_keys: list[str] = []
    labels: list[str] = []
    for item in invalid_query_keys:
        key = str(item).strip()
        label = get_user_visible_field_label(key)
        if not key or not label:
            continue
        raw_keys.append(key)
        labels.append(label)
    if not raw_keys:
        return {}
    return {
        "invalid_query_keys": raw_keys,
        "invalid_query_labels": labels,
    }


def _public_report_details(details: dict) -> dict:
    mode = str(details.get("mode") or "").strip()
    if mode not in _PUBLIC_DETAIL_MODES:
        return {}

    sanitized: dict = {"mode": mode}
    estimated_rows = details.get("estimated_rows")
    if isinstance(estimated_rows, int) and not isinstance(estimated_rows, bool):
        sanitized["estimated_rows"] = estimated_rows
    report_name = str(details.get("report_name") or "").strip()
    if report_name and not _INTERNAL_ASCII_RE.search(report_name):
        sanitized["report_name"] = report_name
    return sanitized


def _replace_field_details(details: dict) -> Optional[dict]:
    field = str(details.get("field") or "").strip()
    field_label = get_user_visible_field_label(field)

    sanitized: dict = {}
    if field_label:
        sanitized["field"] = field_label
    sanitized.update(_public_invalid_query_details(details))
    sanitized.update(_public_report_details(details))
    return sanitized or None


def _validation_error_message(exc: AppError, details: dict) -> str:
    reason = _normalized_reason(details)
    field = str(details.get("field") or "").strip()
    field_label = get_user_visible_field_label(field)
    message_mentions_field = _message_mentions_internal_field(exc.message, field)
    message_mentions_key = _message_mentions_machine_key(exc.message)
    message_mentions_path = _message_mentions_path_like(exc.message)
    reason_messages = {
        "invalid_schedule_rows": "排产结果包含无效排程行，系统已拒绝写入，请检查排产结果后重试。",
        "no_actionable_schedule_rows": "本次排产没有生成可保存的有效排程结果，请检查排产条件后重试。",
        "out_of_scope_schedule_rows": "排产结果超出了本次允许的重排范围，系统已拒绝写入，请刷新数据后重试。",
    }
    if reason in reason_messages:
        return reason_messages[reason]
    if field == "freeze_window":
        return "冻结窗口配置或种子排程异常，请修复后重试。"
    if not (_looks_internal_message(exc.message) or message_mentions_field or message_mentions_key or message_mentions_path):
        return exc.message
    return f"{field_label}填写不正确，请检查后重试。" if field_label else "参数填写不正确，请检查后重试。"


def user_visible_app_error_message(exc: AppError) -> str:
    details = exc.details if isinstance(exc.details, dict) else {}
    if exc.code == ErrorCode.VALIDATION_ERROR:
        return _validation_error_message(exc, details)
    if _looks_internal_non_validation_message(exc.message):
        return _generic_app_error_message(exc.code)
    return exc.message


def user_visible_app_error_details(exc: AppError) -> Optional[dict]:
    details = exc.details if isinstance(exc.details, dict) else None
    if not details:
        return None
    reason = _normalized_reason(details)
    if exc.code == ErrorCode.VALIDATION_ERROR:
        if isinstance(details.get("invalid_query_keys"), list):
            return _replace_field_details(details)
        if reason in {"invalid_schedule_rows", "no_actionable_schedule_rows", "out_of_scope_schedule_rows"}:
            return _field_only_details(exc)
        if str(details.get("field") or "").strip() == "freeze_window":
            return _field_only_details(exc)
        if (
            _looks_internal_message(exc.message)
            or _message_mentions_internal_field(exc.message, str(details.get("field") or ""))
            or _message_mentions_machine_key(exc.message)
            or _message_mentions_path_like(exc.message)
        ):
            return _field_only_details(exc)
    return _replace_field_details(details)


def user_visible_app_error_diagnostics(exc: AppError) -> Optional[dict]:
    details = exc.details if isinstance(exc.details, dict) else None
    if not details:
        return None
    diagnostics: dict = {}
    reason = _normalized_reason(details)
    if reason in _PUBLIC_DIAGNOSTIC_REASONS:
        diagnostics["reason"] = reason
    for key in (
        "invalid_schedule_row_count",
        "valid_schedule_row_count",
        "no_actionable_schedule_row_count",
        "out_of_scope_schedule_row_count",
    ):
        value = details.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            diagnostics[key] = value
    return diagnostics or None


def build_user_visible_app_error_payload(exc: AppError) -> dict:
    payload = error_response(
        exc.code,
        user_visible_app_error_message(exc),
        details=user_visible_app_error_details(exc),
    )
    diagnostics = user_visible_app_error_diagnostics(exc)
    if diagnostics:
        payload.setdefault("error", {})["diagnostics"] = diagnostics
    return payload


def wants_json_error_response() -> bool:
    if request.path.startswith("/api/"):
        return True
    best = request.accept_mimetypes.best
    if best and "json" in best:
        return True
    if request.is_json:
        return True
    return False


def wants_json_error_response_or_default(
    *,
    default: bool = False,
    log_message: Optional[str] = None,
) -> bool:
    try:
        return wants_json_error_response()
    except Exception as exc:
        if log_message:
            logger = getattr(current_app, "logger", None)
            if logger is not None:
                logger.warning(log_message, exc)
        return bool(default)


def json_error_response(exc: AppError, *, payload: Optional[dict] = None):
    return jsonify(payload if payload is not None else build_user_visible_app_error_payload(exc)), app_error_http_status(exc.code)


def _details_text(details: Any) -> Optional[str]:
    if details is None:
        return None
    if isinstance(details, str):
        return details
    try:
        return json.dumps(details, ensure_ascii=False, indent=2)
    except Exception:
        return str(details)


def render_minimal_error_page(
    *,
    title: str,
    code: Any,
    message: str,
    details: Any = None,
    field_label: Optional[str] = None,
) -> str:
    title_text = html.escape(str(title or "发生错误"))
    code_text = html.escape(str(code or "未知"))
    message_text = html.escape(str(message or "发生未知错误，请查看日志。"))
    details_text = _details_text(details)
    extra_parts = []
    if field_label:
        extra_parts.append(f"<p><strong>相关字段：</strong>{html.escape(str(field_label))}</p>")
    if details_text:
        extra_parts.append(f"<pre>{html.escape(str(details_text))}</pre>")
    extra_html = "".join(extra_parts)
    return (
        "<!doctype html>"
        "<html lang=\"zh-CN\">"
        "<head>"
        "<meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{title_text}</title>"
        "<style>"
        "body{margin:0;font-family:'Segoe UI',sans-serif;background:#f5f1ea;color:#1f2933;}"
        ".shell{max-width:640px;margin:64px auto;padding:32px;background:#fff;border:1px solid #d9cbb8;"
        "border-radius:18px;box-shadow:0 20px 40px rgba(15,23,42,.08);}"
        "h1{margin:0 0 12px;font-size:28px;}.code,.message,.hint{margin:12px 0;line-height:1.6;}"
        "pre{margin:16px 0 0;padding:16px;border-radius:12px;background:#f8fafc;overflow:auto;white-space:pre-wrap;}"
        "</style>"
        "</head>"
        "<body>"
        "<main class=\"shell\">"
        f"<h1>{title_text}</h1>"
        f"<p class=\"code\"><strong>错误码：</strong>{code_text}</p>"
        f"<p class=\"message\"><strong>提示：</strong>{message_text}</p>"
        f"{extra_html}"
        "<p class=\"hint\">如果问题反复出现，请联系管理员查看运行日志。</p>"
        "</main>"
        "</body>"
        "</html>"
    )


def render_error_template(
    template_name: str = "error.html",
    *,
    title: str,
    code: Any,
    message: str,
    details: Any = None,
    field_label: Optional[str] = None,
) -> str:
    context = {
        "title": title,
        "code": code,
        "message": message,
        "details": details,
        "field_label": field_label,
    }
    try:
        return render_template(template_name, **context)
    except Exception as exc:
        logger = getattr(current_app, "logger", None)
        if logger is not None:
            logger.error("错误页渲染失败，已回退最小错误页：%s", exc)
        return render_minimal_error_page(
            title=title,
            code=code,
            message=message,
            details=details,
            field_label=field_label,
        )
