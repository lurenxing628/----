from __future__ import annotations

from flask import flash, g, redirect, request, url_for

from core.models.enums import ResourceTeamStatus
from core.services.personnel import ResourceTeamService
from web.ui_mode import render_ui_template as render_template

from .pagination import paginate_rows, parse_page_args
from .personnel_bp import bp


def _team_status_zh(status: str) -> str:
    if status == ResourceTeamStatus.INACTIVE.value:
        return "停用"
    return "启用"


@bp.get("/teams")
def teams_page():
    page, per_page = parse_page_args(request, default_per_page=100, max_per_page=300)
    svc = ResourceTeamService(g.db, op_logger=getattr(g, "op_logger", None))
    rows = svc.list_with_counts()
    view_rows = []
    for row in rows:
        view_rows.append(
            {
                **row,
                "status_zh": _team_status_zh(str(row.get("status") or ResourceTeamStatus.ACTIVE.value)),
            }
        )
    view_rows, pager = paginate_rows(view_rows, page, per_page)
    return render_template(
        "personnel/teams.html",
        title="班组管理",
        teams=view_rows,
        status_options=[(ResourceTeamStatus.ACTIVE.value, "启用"), (ResourceTeamStatus.INACTIVE.value, "停用")],
        pager=pager,
    )


@bp.post("/teams/create")
def create_team():
    team_id = request.form.get("team_id")
    name = request.form.get("name")
    status = request.form.get("status") or ResourceTeamStatus.ACTIVE.value
    remark = request.form.get("remark")

    svc = ResourceTeamService(g.db, op_logger=getattr(g, "op_logger", None))
    team = svc.create(team_id=team_id, name=name, status=status, remark=remark)
    flash(f"已创建班组：{team.team_id} {team.name}", "success")
    return redirect(url_for("personnel.teams_page"))


@bp.post("/teams/<team_id>/update")
def update_team(team_id: str):
    name = request.form.get("name")
    status = request.form.get("status")
    remark = request.form.get("remark")

    svc = ResourceTeamService(g.db, op_logger=getattr(g, "op_logger", None))
    svc.update(team_id=team_id, name=name, status=status, remark=remark)
    flash("班组信息已保存。", "success")
    return redirect(url_for("personnel.teams_page"))


@bp.post("/teams/<team_id>/delete")
def delete_team(team_id: str):
    svc = ResourceTeamService(g.db, op_logger=getattr(g, "op_logger", None))
    svc.delete(team_id)
    flash("已删除班组。", "success")
    return redirect(url_for("personnel.teams_page"))
