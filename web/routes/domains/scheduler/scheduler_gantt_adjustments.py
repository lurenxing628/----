from __future__ import annotations

from typing import Any, Dict

from flask import current_app, g, jsonify, request, url_for

from core.infrastructure.errors import AppError, ErrorCode, ValidationError, error_response
from web.error_boundary import json_error_response

from .scheduler_bp import bp
from .scheduler_utils import _current_scheduler_operator


@bp.post("/gantt/adjustments/create-draft")
def create_gantt_adjustment_draft():
    try:
        payload = _json_payload()
        draft = g.services.gantt_adjustment_draft_service.create_draft(
            base_version=payload.get("base_version"),
            base_plan_role=payload.get("base_plan_role"),
            created_by=_current_scheduler_operator(),
            reason=payload.get("reason"),
            expires_at=payload.get("expires_at"),
        )
        return jsonify({"success": True, "data": _draft_public_data(draft, "已创建模拟调整草稿，正式计划还没有改变。")})
    except AppError as exc:
        return json_error_response(exc)
    except Exception:
        current_app.logger.exception("甘特图调整草稿创建失败")
        return jsonify(error_response(ErrorCode.UNKNOWN_ERROR, "甘特图调整草稿创建失败，请稍后重试。")), 500


@bp.post("/gantt/adjustments/record-time-change")
def record_gantt_adjustment_time_change():
    try:
        payload = _json_payload()
        change = g.services.gantt_adjustment_draft_service.record_time_change(
            draft_id=payload.get("draft_id"),
            schedule_id=payload.get("schedule_id"),
            op_id=payload.get("op_id"),
            change_type=payload.get("change_type") or "move_time",
            from_start=payload.get("from_start"),
            from_end=payload.get("from_end"),
            to_start=payload.get("to_start"),
            to_end=payload.get("to_end"),
        )
        return jsonify({"success": True, "data": _change_public_data(change, "已记录时间调整，正式计划还没有改变。")})
    except AppError as exc:
        return json_error_response(exc)
    except Exception:
        current_app.logger.exception("甘特图时间调整记录失败")
        return jsonify(error_response(ErrorCode.UNKNOWN_ERROR, "甘特图时间调整记录失败，请稍后重试。")), 500


@bp.post("/gantt/adjustments/record-resource-change")
def record_gantt_adjustment_resource_change():
    try:
        payload = _json_payload()
        change = g.services.gantt_adjustment_draft_service.record_resource_change(
            draft_id=payload.get("draft_id"),
            schedule_id=payload.get("schedule_id"),
            op_id=payload.get("op_id"),
            from_machine_id=payload.get("from_machine_id"),
            to_machine_id=payload.get("to_machine_id"),
            from_operator_id=payload.get("from_operator_id"),
            to_operator_id=payload.get("to_operator_id"),
        )
        return jsonify({"success": True, "data": _change_public_data(change, "已记录资源调整，正式计划还没有改变。")})
    except AppError as exc:
        return json_error_response(exc)
    except Exception:
        current_app.logger.exception("甘特图资源调整记录失败")
        return jsonify(error_response(ErrorCode.UNKNOWN_ERROR, "甘特图资源调整记录失败，请稍后重试。")), 500


@bp.post("/gantt/adjustments/discard-draft")
def discard_gantt_adjustment_draft():
    try:
        payload = _json_payload()
        draft = g.services.gantt_adjustment_draft_service.discard_draft(
            draft_id=payload.get("draft_id"),
            reason=payload.get("reason"),
        )
        return jsonify({"success": True, "data": _draft_public_data(draft, "已废弃模拟调整草稿，正式计划还没有改变。")})
    except AppError as exc:
        return json_error_response(exc)
    except Exception:
        current_app.logger.exception("甘特图调整草稿废弃失败")
        return jsonify(error_response(ErrorCode.UNKNOWN_ERROR, "甘特图调整草稿废弃失败，请稍后重试。")), 500


@bp.post("/gantt/adjustments/validate-simulate")
def validate_gantt_adjustment():
    try:
        payload = _json_payload()
        data = g.services.gantt_adjustment_validation_service.validate_draft(
            draft_id=payload.get("draft_id"),
            expected_base_version=payload.get("base_version"),
            expected_base_plan_role=payload.get("base_plan_role"),
        )
        return jsonify({"success": True, "data": _validation_public_data(data)})
    except AppError as exc:
        return json_error_response(exc)
    except Exception:
        current_app.logger.exception("甘特图调整校验失败")
        return jsonify(error_response(ErrorCode.UNKNOWN_ERROR, "甘特图调整校验失败，请稍后重试。")), 500


@bp.post("/gantt/adjustments/save-scenario")
def save_gantt_adjustment_scenario():
    try:
        payload = _json_payload()
        operator = _current_scheduler_operator()
        scenario = g.services.gantt_adjustment_scenario_service.save_scenario(
            draft_id=payload.get("draft_id"),
            scenario_name=payload.get("scenario_name"),
            created_by=operator,
            expected_base_version=payload.get("base_version"),
            expected_base_plan_role=payload.get("base_plan_role"),
        )
        data = {
            "scenario_name": scenario.scenario_name,
            "created_by": scenario.created_by,
            "message": "已保存为模拟方案，正式计划还没有改变。请从模拟方案入口打开预览。",
        }
        return jsonify({"success": True, "data": data})
    except AppError as exc:
        return json_error_response(exc)
    except Exception:
        current_app.logger.exception("甘特图模拟方案保存失败")
        return jsonify(error_response(ErrorCode.UNKNOWN_ERROR, "甘特图模拟方案保存失败，请稍后重试。")), 500


@bp.post("/gantt/adjustments/publish-scenario")
def publish_gantt_adjustment_scenario():
    try:
        payload = _json_payload()
        operator = _current_scheduler_operator()
        result = g.services.gantt_adjustment_publish_service.publish_scenario(
            scenario_id=payload.get("scenario_id"),
            confirm_text=payload.get("confirm_text"),
            reason=payload.get("reason"),
            published_by=operator,
            expected_base_version=payload.get("base_version"),
            expected_base_plan_role=payload.get("base_plan_role"),
        )
        result_data = {
            "new_version": result.new_version,
            "published_by": result.published_by,
            "reason": result.reason,
            "view_url": url_for(
                "scheduler.gantt_page",
                version=result.new_version,
                plan_role="adopted",
                gantt_zoom="day",
            ),
            "message": "已正式采用模拟方案，并生成新的正式排产版本。",
        }
        return jsonify({"success": True, "data": result_data})
    except AppError as exc:
        return json_error_response(exc)
    except Exception:
        current_app.logger.exception("甘特图模拟方案正式采用失败")
        return jsonify(error_response(ErrorCode.UNKNOWN_ERROR, "甘特图模拟方案正式采用失败，请稍后重试。")), 500


def _json_payload() -> Dict[str, Any]:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValidationError("请求内容必须是 JSON 对象。", field="body")
    return payload


def _validation_public_data(data: Any) -> Dict[str, Any]:
    payload = dict(data or {}) if isinstance(data, dict) else {}
    issues = []
    for issue in payload.get("issues") or []:
        if not isinstance(issue, dict):
            continue
        issues.append(
            {
                "severity": str(issue.get("severity") or "").strip(),
                "code": str(issue.get("code") or "").strip(),
                "message": str(issue.get("message") or "").strip(),
            }
        )
    return {
        "status": str(payload.get("status") or "").strip(),
        "can_apply": bool(payload.get("can_apply")),
        "message": str(payload.get("message") or "").strip(),
        "issue_count": int(payload.get("issue_count") or len(issues)),
        "issues": issues,
    }


def _draft_public_data(draft: Any, message: str) -> Dict[str, Any]:
    return {
        "draft_id": str(getattr(draft, "draft_id", "") or ""),
        "status": str(getattr(draft, "status", "") or ""),
        "change_count": int(getattr(draft, "change_count", 0) or 0),
        "message": message,
    }


def _change_public_data(change: Any, message: str) -> Dict[str, Any]:
    return {
        "draft_id": str(getattr(change, "draft_id", "") or ""),
        "change_type": str(getattr(change, "change_type", "") or ""),
        "validation_status": str(getattr(change, "validation_status", "") or ""),
        "message": message,
    }
