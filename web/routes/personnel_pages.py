from __future__ import annotations

from typing import Any, Dict, List

from flask import current_app, flash, g, redirect, render_template, request, url_for

from core.infrastructure.errors import AppError, BusinessError, ErrorCode, ValidationError
from core.models.enums import OperatorStatus, YesNo
from core.services.common.normalization_matrix import skill_level_options
from core.services.equipment import MachineService
from core.services.personnel import OperatorMachineService, OperatorService
from core.services.personnel.operator_machine_query_service import OperatorMachineQueryService
from web.viewmodels.excel_entry_cards import personnel_excel_cards

from .navigation_utils import _safe_next_url
from .pagination import build_pager, parse_page_args
from .personnel_bp import _machine_status_zh, _operator_status_zh, bp
from .personnel_detail_context import build_personnel_detail_context
from .team_view_helpers import build_team_name_map, load_team_options


def _personnel_next_url() -> str:
    next_raw = (request.form.get("next") or "").strip()
    next_url = _safe_next_url(next_raw) if next_raw else None
    return next_url or url_for("personnel.list_page")


def _personnel_return_url_from_args() -> str:
    next_raw = (request.args.get("next") or "").strip()
    next_url = _safe_next_url(next_raw) if next_raw else None
    return next_url or url_for("personnel.list_page")


def _personnel_detail_redirect(operator_id: str):
    next_raw = (request.form.get("next") or request.args.get("next") or "").strip()
    next_url = _safe_next_url(next_raw) if next_raw else None
    if next_url:
        return redirect(url_for("personnel.detail_page", operator_id=operator_id, next=next_url))
    return redirect(url_for("personnel.detail_page", operator_id=operator_id))


def _operator_links_by_operator(operator_ids: List[str], machines: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    link_rows = OperatorMachineQueryService(g.db, op_logger=getattr(g, "op_logger", None)).list_simple_rows_for_operators(
        operator_ids
    )
    link_rows.sort(key=lambda r: (str(r.get("operator_id") or ""), str(r.get("machine_id") or "")))
    links_by_operator: Dict[str, List[Dict[str, Any]]] = {}
    for row in link_rows:
        op_id = row["operator_id"]
        machine_id = row["machine_id"]
        machine = machines.get(machine_id)
        links_by_operator.setdefault(op_id, []).append(
            {
                "machine_id": machine_id,
                "machine_name": machine.name if machine else None,
                "machine_status": machine.status if machine else None,
            }
        )
    return links_by_operator


def _operator_machine_text(links: List[Dict[str, Any]]) -> str:
    return ", ".join(
        [f"{item['machine_id']}{(' ' + item['machine_name']) if item.get('machine_name') else ''}".strip() for item in links]
    )


def _personnel_view_rows(operators: List[Any], team_name_map: Dict[str, str], machines: Dict[str, Any]) -> List[Dict[str, Any]]:
    links_by_operator = _operator_links_by_operator([op.operator_id for op in operators], machines)
    rows: List[Dict[str, Any]] = []
    for op in operators:
        links = links_by_operator.get(op.operator_id, [])
        rows.append(
            {
                "operator_id": op.operator_id,
                "name": op.name,
                "team_id": op.team_id,
                "team_name": team_name_map.get(op.team_id or ""),
                "status": op.status,
                "status_zh": _operator_status_zh(op.status),
                "remark": op.remark,
                "machine_text": _operator_machine_text(links),
                "machine_count": len(links),
            }
        )
    return rows


@bp.get("/")
def list_page():
    op_svc = OperatorService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    mc_svc = MachineService(g.db, op_logger=getattr(g, "op_logger", None))
    page, per_page = parse_page_args(request, default_per_page=100, max_per_page=300)
    selected_team_id = (request.args.get("team_id") or "").strip() or None

    team_options = load_team_options()
    team_name_map = build_team_name_map(team_options)
    try:
        operators, total = op_svc.list_page(status=None, team_id=selected_team_id, page=page, per_page=per_page)
    except BusinessError as e:
        if e.code == ErrorCode.TEAM_NOT_FOUND:
            flash(e.message, "warning")
            return redirect(url_for("personnel.list_page"))
        raise
    machines = {m.machine_id: m for m in mc_svc.list()}
    view_rows = _personnel_view_rows(operators, team_name_map, machines)

    pager = build_pager(total, page, per_page)

    return render_template(
        "personnel/list.html",
        title="人员管理",
        operators=view_rows,
        team_options=team_options,
        selected_team_id=selected_team_id,
        status_options=[(OperatorStatus.ACTIVE.value, "在岗"), (OperatorStatus.INACTIVE.value, "停用/休假")],
        pager=pager,
        excel_cards=personnel_excel_cards(),
    )


@bp.post("/create")
def create_operator():
    op_id = request.form.get("operator_id")
    name = request.form.get("name")
    status = request.form.get("status") or OperatorStatus.ACTIVE.value
    remark = request.form.get("remark")
    team_id = request.form.get("team_id") or None

    svc = OperatorService(g.db, op_logger=getattr(g, "op_logger", None))
    try:
        op = svc.create(operator_id=op_id, name=name, status=status, remark=remark, team_id=team_id)
        flash(f"已创建人员：{op.operator_id} {op.name}", "success")
        return _personnel_detail_redirect(op.operator_id)
    except AppError as e:
        flash(e.message, "error")
        return redirect(_personnel_next_url())


@bp.get("/<operator_id>")
def detail_page(operator_id: str):
    context = build_personnel_detail_context(g.db, operator_id, op_logger=getattr(g, "op_logger", None))
    personnel_return_url = _personnel_return_url_from_args()
    return render_template(
        "personnel/detail.html",
        **context,
        personnel_return_url=personnel_return_url,
        personnel_return_next=personnel_return_url,
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
    return _personnel_detail_redirect(op.operator_id)


@bp.post("/<operator_id>/status")
def set_status(operator_id: str):
    status = request.form.get("status")
    if not status:
        raise ValidationError("缺少状态参数", field="status")
    svc = OperatorService(g.db, op_logger=getattr(g, "op_logger", None))
    op = svc.set_status(operator_id=operator_id, status=status)
    flash(f"已更新状态：{op.operator_id}  {_operator_status_zh(op.status)}", "success")
    return _personnel_detail_redirect(op.operator_id)


@bp.post("/<operator_id>/delete")
def delete_operator(operator_id: str):
    next_url = _personnel_next_url()
    svc = OperatorService(g.db, op_logger=getattr(g, "op_logger", None))
    try:
        svc.delete(operator_id)
        flash(f"已删除人员：{operator_id}", "success")
    except AppError as e:
        flash(e.message, "error")
    return redirect(next_url)


@bp.post("/bulk/status")
def bulk_set_status():
    """
    批量设置人员状态（active/inactive）。
    """
    next_url = _personnel_next_url()
    status = (request.form.get("status") or "").strip()
    operator_ids = request.form.getlist("operator_ids")
    if not operator_ids:
        flash("请至少选择 1 个人员。", "error")
        return redirect(next_url)
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
    return redirect(next_url)


@bp.post("/bulk/delete")
def bulk_delete():
    """
    批量删除人员（受引用保护；建议优先批量停用）。
    """
    next_url = _personnel_next_url()
    operator_ids = request.form.getlist("operator_ids")
    if not operator_ids:
        flash("请至少选择 1 个人员。", "error")
        return redirect(next_url)

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
    return redirect(next_url)


@bp.post("/<operator_id>/link/add")
def add_link(operator_id: str):
    machine_id = request.form.get("machine_id")
    svc = OperatorMachineService(g.db, op_logger=getattr(g, "op_logger", None))
    svc.add_link(operator_id=operator_id, machine_id=machine_id)
    flash("已添加设备关联。", "success")
    return _personnel_detail_redirect(operator_id)


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
    return _personnel_detail_redirect(operator_id)


@bp.post("/<operator_id>/link/remove")
def remove_link(operator_id: str):
    machine_id = request.form.get("machine_id")
    svc = OperatorMachineService(g.db, op_logger=getattr(g, "op_logger", None))
    svc.remove_link(operator_id=operator_id, machine_id=machine_id)
    flash("已解除设备关联。", "success")
    return _personnel_detail_redirect(operator_id)
