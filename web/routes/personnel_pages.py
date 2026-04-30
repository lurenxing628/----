from __future__ import annotations

from typing import Any, Dict, List

from flask import current_app, flash, g, redirect, request, url_for

from core.infrastructure.errors import AppError, BusinessError, ErrorCode, ValidationError
from core.models.enums import OperatorStatus, YesNo
from core.services.common.normalization_matrix import skill_level_options
from core.services.equipment import MachineService
from core.services.personnel import OperatorMachineService, OperatorService
from core.services.personnel.operator_machine_query_service import OperatorMachineQueryService
from web.ui_mode import render_ui_template as render_template

from .pagination import paginate_rows, parse_page_args
from .personnel_bp import _machine_status_zh, _operator_status_zh, bp
from .personnel_detail_context import build_personnel_detail_context
from .team_view_helpers import build_team_name_map, load_team_options


@bp.get("/")
def list_page():
    op_svc = OperatorService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    mc_svc = MachineService(g.db, op_logger=getattr(g, "op_logger", None))
    page, per_page = parse_page_args(request, default_per_page=100, max_per_page=300)
    selected_team_id = (request.args.get("team_id") or "").strip() or None

    team_options = load_team_options()
    team_name_map = build_team_name_map(team_options)
    try:
        operators = op_svc.list(team_id=selected_team_id)
    except BusinessError as e:
        if e.code == ErrorCode.TEAM_NOT_FOUND:
            flash(e.message, "warning")
            return redirect(url_for("personnel.list_page"))
        raise
    machines = {m.machine_id: m for m in mc_svc.list()}

    link_rows = OperatorMachineQueryService(g.db, op_logger=getattr(g, "op_logger", None)).list_simple_rows()
    link_rows.sort(key=lambda r: (str(r.get("operator_id") or ""), str(r.get("machine_id") or "")))
    links_by_operator: Dict[str, List[Dict[str, Any]]] = {}
    for r in link_rows:
        op_id = r["operator_id"]
        mc_id = r["machine_id"]
        m = machines.get(mc_id)
        links_by_operator.setdefault(op_id, []).append(
            {
                "machine_id": mc_id,
                "machine_name": (m.name if m else None),
                "machine_status": (m.status if m else None),
            }
        )

    view_rows: List[Dict[str, Any]] = []
    for op in operators:
        links = links_by_operator.get(op.operator_id, [])
        machine_text = ", ".join(
            [f"{x['machine_id']}{(' ' + x['machine_name']) if x.get('machine_name') else ''}".strip() for x in links]
        )
        view_rows.append(
            {
                "operator_id": op.operator_id,
                "name": op.name,
                "team_id": op.team_id,
                "team_name": team_name_map.get(op.team_id or ""),
                "status": op.status,
                "status_zh": _operator_status_zh(op.status),
                "remark": op.remark,
                "machine_text": machine_text,
                "machine_count": len(links),
            }
        )

    view_rows, pager = paginate_rows(view_rows, page, per_page)

    return render_template(
        "personnel/list.html",
        title="人员管理",
        operators=view_rows,
        team_options=team_options,
        selected_team_id=selected_team_id,
        status_options=[(OperatorStatus.ACTIVE.value, "在岗"), (OperatorStatus.INACTIVE.value, "停用/休假")],
        pager=pager,
    )


@bp.post("/create")
def create_operator():
    op_id = request.form.get("operator_id")
    name = request.form.get("name")
    status = request.form.get("status") or OperatorStatus.ACTIVE.value
    remark = request.form.get("remark")
    team_id = request.form.get("team_id") or None

    svc = OperatorService(g.db, op_logger=getattr(g, "op_logger", None))
    op = svc.create(operator_id=op_id, name=name, status=status, remark=remark, team_id=team_id)
    flash(f"已创建人员：{op.operator_id} {op.name}", "success")
    return redirect(url_for("personnel.detail_page", operator_id=op.operator_id))


@bp.get("/<operator_id>")
def detail_page(operator_id: str):
    context = build_personnel_detail_context(g.db, operator_id, op_logger=getattr(g, "op_logger", None))
    return render_template(
        "personnel/detail.html",
        **context,
    )


@bp.post("/<operator_id>/update")
def update_operator(operator_id: str):
    name = request.form.get("name")
    status = request.form.get("status")
    remark = request.form.get("remark")
    team_id = request.form.get("team_id")

    svc = OperatorService(g.db, op_logger=getattr(g, "op_logger", None))
    op = svc.update(operator_id=operator_id, name=name, status=status, remark=remark, team_id=team_id)
    flash("人员信息已保存。", "success")
    return redirect(url_for("personnel.detail_page", operator_id=op.operator_id))


@bp.post("/<operator_id>/status")
def set_status(operator_id: str):
    status = request.form.get("status")
    if not status:
        raise ValidationError("缺少状态参数", field="status")
    svc = OperatorService(g.db, op_logger=getattr(g, "op_logger", None))
    op = svc.set_status(operator_id=operator_id, status=status)
    flash(f"已更新状态：{op.operator_id}  {_operator_status_zh(op.status)}", "success")
    return redirect(url_for("personnel.detail_page", operator_id=op.operator_id))


@bp.post("/<operator_id>/delete")
def delete_operator(operator_id: str):
    svc = OperatorService(g.db, op_logger=getattr(g, "op_logger", None))
    try:
        svc.delete(operator_id)
        flash(f"已删除人员：{operator_id}", "success")
    except AppError as e:
        flash(e.message, "error")
    return redirect(url_for("personnel.list_page"))


@bp.post("/bulk/status")
def bulk_set_status():
    """
    批量设置人员状态（active/inactive）。
    """
    status = (request.form.get("status") or "").strip()
    operator_ids = request.form.getlist("operator_ids")
    if not operator_ids:
        flash("请至少选择 1 个人员。", "error")
        return redirect(url_for("personnel.list_page"))
    if status not in (OperatorStatus.ACTIVE.value, OperatorStatus.INACTIVE.value):
        raise ValidationError("状态不正确，请选择：在岗 / 停用或休假。", field="状态")

    svc = OperatorService(g.db, op_logger=getattr(g, "op_logger", None))
    ok = 0
    failed: List[str] = []
    failed_details: List[str] = []
    for oid in operator_ids:
        try:
            svc.set_status(oid, status=status)
            ok += 1
        except AppError as e:
            failed.append(str(oid))
            failed_details.append(f"{oid}: {e.message}")
            continue
        except Exception:
            current_app.logger.exception("批量设置人员状态失败（operator_id=%s, status=%s）", oid, status)
            failed.append(str(oid))
            failed_details.append(f"{oid}: 内部错误，请查看日志")
            continue

    flash(f"批量状态更新完成：成功 {ok}，失败 {len(failed)}。", "success" if ok else "warning")
    if failed:
        sample = "；".join(failed_details[:10])
        flash(f"失败人员（最多展示 10 个）：{sample}", "warning")
    return redirect(url_for("personnel.list_page"))


@bp.post("/bulk/delete")
def bulk_delete():
    """
    批量删除人员（受引用保护；建议优先批量停用）。
    """
    operator_ids = request.form.getlist("operator_ids")
    if not operator_ids:
        flash("请至少选择 1 个人员。", "error")
        return redirect(url_for("personnel.list_page"))

    svc = OperatorService(g.db, op_logger=getattr(g, "op_logger", None))
    ok = 0
    failed: List[str] = []
    failed_details: List[str] = []
    for oid in operator_ids:
        try:
            svc.delete(oid)
            ok += 1
        except AppError as e:
            failed.append(str(oid))
            failed_details.append(f"{oid}: {e.message}")
            continue
        except Exception:
            current_app.logger.exception("批量删除人员失败（operator_id=%s）", oid)
            failed.append(str(oid))
            failed_details.append(f"{oid}: 内部错误，请查看日志")
            continue

    flash(f"批量删除完成：成功 {ok}，失败 {len(failed)}。", "success" if ok else "warning")
    if failed:
        sample = "；".join(failed_details[:10])
        flash(f"删除失败（最多展示 10 个）：{sample}", "warning")
    return redirect(url_for("personnel.list_page"))


@bp.post("/<operator_id>/link/add")
def add_link(operator_id: str):
    machine_id = request.form.get("machine_id")
    svc = OperatorMachineService(g.db, op_logger=getattr(g, "op_logger", None))
    svc.add_link(operator_id=operator_id, machine_id=machine_id)
    flash("已添加设备关联。", "success")
    return redirect(url_for("personnel.detail_page", operator_id=operator_id))


@bp.post("/<operator_id>/link/update")
def update_link(operator_id: str):
    machine_id = request.form.get("machine_id")
    skill_level = request.form.get("skill_level")
    # checkbox：未勾选时 form 中不存在该 key
    is_primary = YesNo.YES.value if request.form.get("is_primary") else YesNo.NO.value
    svc = OperatorMachineService(g.db, op_logger=getattr(g, "op_logger", None))
    svc.update_link_fields(
        operator_id=operator_id,
        machine_id=machine_id,
        skill_level=skill_level,
        is_primary=is_primary,
    )
    flash("已更新关联字段（技能等级/主操设备）。", "success")
    return redirect(url_for("personnel.detail_page", operator_id=operator_id))


@bp.post("/<operator_id>/link/remove")
def remove_link(operator_id: str):
    machine_id = request.form.get("machine_id")
    svc = OperatorMachineService(g.db, op_logger=getattr(g, "op_logger", None))
    svc.remove_link(operator_id=operator_id, machine_id=machine_id)
    flash("已解除设备关联。", "success")
    return redirect(url_for("personnel.detail_page", operator_id=operator_id))
