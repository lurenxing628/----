from __future__ import annotations

from typing import Any, Optional, Tuple

from flask import request

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.models.schedule_plan_role import ROLE_ADOPTED, plan_role_label
from core.services.report import ReportEngine
from core.services.report.report_context_filters import normalize_report_resource_filter
from core.services.scheduler.version_resolution import (
    VersionResolution,
    require_selected_version,
    resolve_version_or_latest,
)
from web.routes.report_plan_preview import request_scenario_id as _request_scenario_id_from_args


def resolve_report_version(engine: ReportEngine, raw_version: Any) -> VersionResolution:
    latest = int(engine.latest_version() or 0)
    return resolve_version_or_latest(
        raw_version,
        latest_version=latest,
        version_exists=lambda version: engine.history_repo.get_by_version(int(version)) is not None,
    )


def export_version_or_latest(engine: ReportEngine) -> int:
    resolution = resolve_report_version(engine, request.args.get("version"))
    if resolution.status == "missing_history":
        return require_selected_version(resolution)
    return require_selected_version(resolution, message="暂无排产历史，无法导出报表。")


def page_version_or_latest(engine: ReportEngine) -> VersionResolution:
    resolution = resolve_report_version(engine, request.args.get("version"))
    if resolution.status == "missing_history":
        raise BusinessError(
            ErrorCode.NOT_FOUND,
            "排产版本不存在，请先选择已有版本。",
            details={"field": "version", "requested_version": resolution.requested_version, "status": resolution.status},
        )
    return resolution


def request_plan_role() -> Any:
    return request.args.get("plan_role")


def request_scenario_id() -> Optional[str]:
    return _request_scenario_id_from_args(request.args)


def request_resource_filter() -> Tuple[str, str]:
    return normalize_report_resource_filter(
        request.args.get("resource_type"),
        request.args.get("resource_id"),
        scope_type=request.args.get("scope_type"),
        scope_id=request.args.get("scope_id"),
        machine_id=request.args.get("machine_id"),
        operator_id=request.args.get("operator_id"),
    )


def execution_review_plan_identity_error(plan_role: Any = None, scenario_id: Any = None) -> str:
    raw_role = str(plan_role if plan_role is not None else request.args.get("plan_role") or "").strip()
    raw_scenario = str(scenario_id if scenario_id is not None else request.args.get("scenario_id") or "").strip()
    if raw_scenario:
        return "计划和现场实际只复盘正式采用方案，当前请求带了模拟预览身份，不能当作正式现场复盘显示。"
    if raw_role and raw_role != ROLE_ADOPTED:
        return f"计划和现场实际只复盘正式采用方案，当前请求带的是“{plan_role_label(raw_role)}”，不能当作正式现场复盘显示。"
    return ""


def require_execution_review_adopted_plan() -> Tuple[str, None]:
    error = execution_review_plan_identity_error(request_plan_role(), request_scenario_id())
    if error:
        raise ValidationError(error, field="plan_role", details={"reason": "unsupported_execution_review_plan_identity"})
    return ROLE_ADOPTED, None


__all__ = [
    "execution_review_plan_identity_error",
    "export_version_or_latest",
    "page_version_or_latest",
    "require_execution_review_adopted_plan",
    "request_plan_role",
    "request_resource_filter",
    "request_scenario_id",
    "resolve_report_version",
]
