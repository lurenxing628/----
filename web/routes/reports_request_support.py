from __future__ import annotations

from typing import Any, Optional, Tuple

from flask import request

from core.infrastructure.errors import BusinessError, ErrorCode
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


__all__ = [
    "export_version_or_latest",
    "page_version_or_latest",
    "request_plan_role",
    "request_resource_filter",
    "request_scenario_id",
    "resolve_report_version",
]
