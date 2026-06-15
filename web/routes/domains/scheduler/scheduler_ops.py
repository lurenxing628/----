from __future__ import annotations

from flask import flash, g, redirect, request, url_for

from core.infrastructure.errors import AppError, ValidationError
from core.models.enums import SourceType
from web.public_token_registry import issue_public_token, resolve_public_token

from ...navigation_utils import _safe_next_url
from .scheduler_bp import bp
from .scheduler_user_messages import scheduler_user_visible_app_error_message

_OP_UPDATE_TOKEN_SCOPE = "scheduler-op-update-v1"
_OP_UPDATE_TOKEN_MESSAGE = "工序保存入口已失效，请刷新页面后重试。"


def operation_update_token(op_id: int) -> str:
    return issue_public_token(_OP_UPDATE_TOKEN_SCOPE, int(op_id))


def _operation_id_from_token(token: str) -> int:
    try:
        op_id = int(resolve_public_token(_OP_UPDATE_TOKEN_SCOPE, token, message=_OP_UPDATE_TOKEN_MESSAGE, field="operation"))
    except ValueError as exc:
        raise ValidationError(_OP_UPDATE_TOKEN_MESSAGE, field="operation") from exc
    if op_id <= 0:
        raise ValidationError(_OP_UPDATE_TOKEN_MESSAGE, field="operation")
    return op_id


def _operation_return_next_url() -> str:
    next_raw = (request.values.get("next") or "").strip()
    next_url = _safe_next_url(next_raw) if next_raw else None
    return next_url or url_for("scheduler.batches_manage_page")


@bp.post("/ops/<int:op_id>/update")
def update_op(op_id: int):
    _ = op_id
    flash(_OP_UPDATE_TOKEN_MESSAGE, "error")
    return redirect(_operation_return_next_url())


@bp.post("/ops/update-token/<token>")
def update_op_by_token(token: str):
    try:
        op_id = _operation_id_from_token(token)
    except AppError as exc:
        flash(scheduler_user_visible_app_error_message(exc), "error")
        return redirect(_operation_return_next_url())
    return _update_op_by_id(op_id)


def _update_op_by_id(op_id: int):
    sch_svc = g.services.schedule_service
    op = None
    next_url = _operation_return_next_url()

    try:
        op = sch_svc.get_operation(op_id)
        src = (getattr(op, "source", "") or "").strip().lower()
        if src == SourceType.INTERNAL.value:
            machine_id = request.form.get("machine_id") or None
            operator_id = request.form.get("operator_id") or None
            setup_hours = request.form.get("setup_hours")
            unit_hours = request.form.get("unit_hours")
            sch_svc.update_internal_operation(
                op_id=op_id,
                machine_id=machine_id,
                operator_id=operator_id,
                setup_hours=setup_hours,
                unit_hours=unit_hours,
            )
            flash("自制工序已保存。", "success")
        else:
            supplier_id = request.form.get("supplier_id") or None
            ext_days = request.form.get("ext_days")
            # merged 外协组时 ext_days 可能为空；服务层会区分 merged 限制与普通外协周期必填校验
            sch_svc.update_external_operation(op_id=op_id, supplier_id=supplier_id, ext_days=ext_days)
            flash("外协工序已保存。", "success")
    except AppError as exc:
        flash(scheduler_user_visible_app_error_message(exc), "error")

    batch_id = getattr(op, "batch_id", None)
    if batch_id:
        return redirect(url_for("scheduler.batch_detail", batch_id=batch_id, next=next_url))
    return redirect(next_url)
