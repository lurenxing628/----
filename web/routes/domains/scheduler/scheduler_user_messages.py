from __future__ import annotations

from core.infrastructure.errors import AppError, ErrorCode
from web.error_boundary import user_visible_app_error_message

_DIRECT_SCHEDULER_VALIDATION_FIELDS = {
    "batch_ids",
    "end_date",
    "start_dt",
    "批次",
    "排产",
    "排产版本",
    "齐套",
    # 停机加载失败是受控安全文案（“全部/部分设备…（N 台，如：MC_x）…”），机器编号本就面向用户。
    # 不加入白名单的话，消息里的机器编号会命中 error_boundary 的内部键正则被泛化成“参数填写不正确”，
    # 让“全挂/个别挂”分流对用户不可见。
    "downtime",
}


def scheduler_user_visible_app_error_message(exc: AppError) -> str:
    details = exc.details if isinstance(exc.details, dict) else {}
    if exc.code == ErrorCode.VALIDATION_ERROR:
        user_message = str(details.get("user_message") or "").strip()
        if user_message:
            return user_message
        reason = str(details.get("reason") or "").strip()
        if reason == "no_actionable_schedule_rows":
            return user_visible_app_error_message(exc)
        field = str(details.get("field") or getattr(exc, "field", "") or "").strip()
        if field in _DIRECT_SCHEDULER_VALIDATION_FIELDS and str(exc.message or "").strip():
            return str(exc.message).strip()
    return user_visible_app_error_message(exc)
