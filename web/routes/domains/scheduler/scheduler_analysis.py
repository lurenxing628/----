from __future__ import annotations

from flask import g, request

from web.request_resource_context import request_report_resource_context
from web.ui_mode import render_ui_template as render_template
from web.viewmodels.scheduler_analysis_action_hub import build_analysis_action_hub
from web.viewmodels.scheduler_analysis_vm import build_analysis_context, build_candidate_comparison_display
from web.viewmodels.scheduler_summary_display import build_summary_display_state

from .scheduler_analysis_links import attach_candidate_plan_links
from .scheduler_analysis_read import build_analysis_read_context
from .scheduler_bp import bp
from .scheduler_navigation_publish import publish_analysis_navigation_context, resolve_navigation_plan_context


def _request_arg_text(*names: str) -> str:
    for name in names:
        value = str(request.args.get(name) or "").strip()
        if value:
            return value
    return ""


def _request_resource_context() -> dict:
    resource = request_report_resource_context()
    return {
        "resource_type": resource["resource_type"] or None,
        "resource_id": resource["resource_id"] or None,
        "resource_label": resource["resource_label"] or None,
        "query_date": _request_arg_text("query_date") or None,
        "period_preset": _request_arg_text("period_preset") or None,
    }


def _request_candidate_link_context() -> dict:
    resource = _request_resource_context()
    return {
        "resource_type": resource.get("resource_type"),
        "resource_id": resource.get("resource_id"),
        "query_date": resource.get("query_date"),
        "period_preset": resource.get("period_preset"),
    }


def _publish_analysis_navigation_context(selected_version) -> None:
    if selected_version is None:
        return
    plan_role = _request_arg_text("plan_role") or "adopted"
    scenario_id = _request_arg_text("scenario_id") or None
    plan_resolution = resolve_navigation_plan_context(g.services, selected_version, plan_role, scenario_id)
    publish_analysis_navigation_context(
        version=selected_version,
        plan_resolution=plan_resolution,
        date_from=_request_arg_text("date_from", "start_date"),
        date_to=_request_arg_text("date_to", "end_date"),
        resource_context=_request_resource_context(),
        batch_id=_request_arg_text("batch_id") or None,
        back_to=_request_arg_text("back_to") or None,
    )


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
            **_request_candidate_link_context(),
        )

    selected_summary_display = build_summary_display_state(
        ctx.get("selected_summary"),
        result_status=(ctx.get("selected") or {}).get("result_status"),
        parse_state=(ctx.get("selected") or {}).get("result_summary_parse_state"),
    )
    if ctx.get("selected"):
        ctx["analysis_action_hub"] = build_analysis_action_hub(
            ctx.get("candidate_comparison_display"),
            ctx.get("diagnostic_sections"),
        )
    _publish_analysis_navigation_context(read_ctx.selected_version)

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
