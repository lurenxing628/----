from __future__ import annotations

from typing import Any, Dict, List, Optional

from flask import g, request, url_for

from web.ui_mode import render_ui_template as render_template
from web.viewmodels.scheduler_analysis_vm import build_analysis_context, build_candidate_comparison_display
from web.viewmodels.scheduler_summary_display import build_summary_display_state

from .scheduler_analysis_read import build_analysis_read_context
from .scheduler_bp import bp


def _plan_role_links(version: int, role: str) -> List[Dict[str, str]]:
    return [
        {
            "label": "设备甘特图",
            "url": url_for("scheduler.gantt_page", view="machine", version=version, plan_role=role),
        },
        {
            "label": "人员甘特图",
            "url": url_for("scheduler.gantt_page", view="operator", version=version, plan_role=role),
        },
        {
            "label": "周计划",
            "url": url_for("scheduler.week_plan_page", version=version, plan_role=role),
        },
        {
            "label": "资源排班",
            "url": url_for("scheduler.resource_dispatch_page", version=version, plan_role=role),
        },
    ]


def _attach_candidate_plan_links(ctx: Dict[str, Any], selected_ver: Optional[int]) -> None:
    display = ctx.get("candidate_comparison_display")
    if selected_ver is None or not isinstance(display, dict):
        return
    for row in list(display.get("rows") or []):
        if not isinstance(row, dict) or not row.get("plan_role_available"):
            continue
        role = str(row.get("role") or "").strip()
        if not role:
            continue
        row["links"] = _plan_role_links(int(selected_ver), role)


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
        _attach_candidate_plan_links(ctx, read_ctx.selected_version)

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
