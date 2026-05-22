from __future__ import annotations

from typing import Any, Dict

from flask import current_app, g, jsonify, request

from core.infrastructure.errors import AppError, ErrorCode, ValidationError, error_response
from web.error_boundary import json_error_response

from .scheduler_bp import bp


@bp.post("/gantt/adjustments/validate-simulate")
def validate_gantt_adjustment():
    try:
        payload = _json_payload()
        data = g.services.gantt_adjustment_validation_service.validate_draft(
            draft_id=payload.get("draft_id"),
            expected_base_version=payload.get("base_version"),
            expected_base_plan_role=payload.get("base_plan_role"),
        )
        return jsonify({"success": True, "data": data})
    except AppError as exc:
        return json_error_response(exc)
    except Exception:
        current_app.logger.exception("甘特图调整校验失败")
        return jsonify(error_response(ErrorCode.UNKNOWN_ERROR, "甘特图调整校验失败，请稍后重试。")), 500


def _json_payload() -> Dict[str, Any]:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValidationError("请求内容必须是 JSON 对象。", field="body")
    return payload
