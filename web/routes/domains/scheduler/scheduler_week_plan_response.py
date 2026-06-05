from __future__ import annotations

from typing import Any, Dict

from flask import send_file

from core.services.scheduler.schedule_plan_query_service import ROLE_ADOPTED


def _safe_filename_part(value: Any) -> str:
    text = str(value or "").strip()
    for old, new in (("/", "-"), ("\\", "-"), (":", "-"), ("*", ""), ("?", ""), ('"', ""), ("<", ""), (">", ""), ("|", "-")):
        text = text.replace(old, new)
    return text.strip()


def _scenario_display_name(plan_resolution: Dict[str, Any]) -> str:
    return str(
        plan_resolution.get("scenario_display_name") or plan_resolution.get("scenario_name") or "模拟预览（未命名）"
    ).strip()


def send_week_plan_export_file(output, *, version: int, week_start: Any, week_end: Any, plan_resolution: Dict[str, Any]):
    selected_role = str(plan_resolution.get("selected_role") or ROLE_ADOPTED)
    requested_role = str(plan_resolution.get("requested_role") or ROLE_ADOPTED)
    if bool(plan_resolution.get("is_scenario_preview")):
        plan_label = _safe_filename_part(_scenario_display_name(plan_resolution))
    else:
        # 文件名带"具体方案名"（selected_label，与资源派工/报表导出口径一致）；
        # 仅历史正式方案例外：历史身份只存在于 user_label，须原样标进文件名。
        user_label = str(plan_resolution.get("user_label") or "").strip()
        is_historical = user_label.startswith("历史正式方案")
        include_plan_label = selected_role != ROLE_ADOPTED or requested_role != selected_role or is_historical
        label_source = user_label if is_historical else plan_resolution.get("selected_label")
        plan_label = _safe_filename_part(label_source) if include_plan_label else ""
    plan_suffix = f"_{plan_label}" if plan_label else ""
    filename = f"周计划表_v{version}_{week_start}至{week_end}{plan_suffix}.xlsx"
    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
