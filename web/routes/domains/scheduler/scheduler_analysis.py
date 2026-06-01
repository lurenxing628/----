from __future__ import annotations

from flask import g, request

from web.ui_mode import render_ui_template as render_template
from web.viewmodels.scheduler_analysis_vm import build_analysis_context, build_candidate_comparison_display
from web.viewmodels.scheduler_summary_display import build_summary_display_state

from .scheduler_analysis_links import attach_candidate_plan_links
from .scheduler_analysis_read import build_analysis_read_context
from .scheduler_bp import bp


def _request_arg_text(*names: str) -> str:
    for name in names:
        value = str(request.args.get(name) or "").strip()
        if value:
            return value
    return ""


def _request_resource_context() -> dict:
    resource_type = _request_arg_text("resource_type", "scope_type")
    resource_id = _request_arg_text("resource_id", "scope_id")
    if not resource_type:
        for key, value in (
            ("operator", request.args.get("operator_id")),
            ("machine", request.args.get("machine_id")),
            ("team", request.args.get("team_id")),
        ):
            if str(value or "").strip():
                resource_type = key
                resource_id = str(value or "").strip()
                break
    if resource_type and not resource_id:
        resource_id = str(request.args.get(f"{resource_type}_id") or "").strip()
    return {
        "resource_type": resource_type or None,
        "resource_id": resource_id or None,
        "query_date": _request_arg_text("query_date") or None,
        "period_preset": _request_arg_text("period_preset") or None,
    }


@bp.get("/analysis")
def analysis_page():
    read_ctx = build_analysis_read_context(
        g.services,
        raw_version=request.args.get("version"),
    )
    ctx = build_analysis_context(
        selected_ver=read_ctx.selected_version,
        raw_hist=read_ctx.raw_hist,
        selected_item=read_ctx.selected_item,
    )
    initial_candidate_display = ctx.get("candidate_comparison_display")
    if isinstance(initial_candidate_display, dict) and (
        initial_candidate_display.get("has_comparison")
        or initial_candidate_display.get("planned_candidate_count") is not None
    ):
        ctx["candidate_comparison_display"] = build_candidate_comparison_display(
            ctx.get("selected_summary"),
            selected_ver=read_ctx.selected_version,
            plan_role_options=read_ctx.plan_role_options,
            integrity_notice=read_ctx.plan_role_integrity_notice,
        )
        attach_candidate_plan_links(
            ctx,
            read_ctx.selected_version,
            date_from=_request_arg_text("date_from", "start_date"),
            date_to=_request_arg_text("date_to", "end_date"),
            batch_id=_request_arg_text("batch_id"),
            **_request_resource_context(),
        )

    selected_summary_display = build_summary_display_state(
        ctx.get("selected_summary"),
        result_status=(ctx.get("selected") or {}).get("result_status"),
        parse_state=(ctx.get("selected") or {}).get("result_summary_parse_state"),
    )

    return render_template(
        "scheduler/analysis.html",
        title="排产优化分析",
        versions=read_ctx.versions,
        selected_history_resolution=read_ctx.selected_history_resolution,
        selected_summary_display=selected_summary_display,
        trend_summary_state=read_ctx.trend_summary_state,
        version_resolution=read_ctx.version_resolution.to_dict(),
        **ctx,
    )
