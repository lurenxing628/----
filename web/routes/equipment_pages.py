from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from flask import current_app, flash, g, redirect, request, url_for

from core.infrastructure.errors import AppError, BusinessError, ErrorCode, ValidationError
from core.models.enums import MachineStatus, YesNo
from core.services.common.normalization_matrix import skill_level_options
from core.services.equipment import MachineDowntimeService, MachineService
from core.services.equipment.machine_downtime_query_service import MachineDowntimeQueryService
from core.services.personnel import OperatorMachineService, OperatorService
from core.services.personnel.operator_machine_query_service import OperatorMachineQueryService
from core.services.process import OpTypeService
from web.ui_mode import render_ui_template as render_template

from .equipment_bp import _machine_status_zh, _operator_status_zh, bp
from .pagination import paginate_rows, parse_page_args
from .team_view_helpers import build_team_name_map, load_team_options


def _build_linked_operator_rows(links, operators: Dict[str, Any]) -> List[Dict[str, Any]]:
    linked_operators: List[Dict[str, Any]] = []
    for link in links:
        operator = operators.get(link.operator_id)
        linked_operators.append(
            {
                "operator_id": link.operator_id,
                "operator_name": (operator.name if operator else None),
                "status": (operator.status if operator else None),
                "status_zh": _operator_status_zh(operator.status) if operator else "-",
                "skill_level": getattr(link, "skill_level", None),
                "is_primary": getattr(link, "is_primary", None),
            }
        )
    return linked_operators


def _build_available_operator_rows(operators: Dict[str, Any], linked_operator_ids: set) -> List[Dict[str, Any]]:
    available_operators: List[Dict[str, Any]] = []
    for operator in operators.values():
        if operator.operator_id in linked_operator_ids:
            continue
        available_operators.append(
            {
                "operator_id": operator.operator_id,
                "operator_name": operator.name,
                "status": operator.status,
                "status_zh": _operator_status_zh(operator.status),
            }
        )
    available_operators.sort(key=lambda item: item["operator_id"])
    return available_operators


def _selected_op_type_name(op_types: Dict[str, Any], machine) -> Any:
    op_type = op_types.get(machine.op_type_id or "") if machine.op_type_id else None
    return op_type.name if op_type else None


def _load_active_downtime_machine_ids() -> Dict[str, Any]:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        dt_q = MachineDowntimeQueryService(g.db, op_logger=getattr(g, "op_logger", None))
        return {"machine_ids": dt_q.list_active_machine_ids_at(now_str), "degraded": False, "reason": None}
    except Exception:
        current_app.logger.exception("设备列表页读取计划停机状态失败（now=%s）", now_str)
        return {"machine_ids": set(), "degraded": True, "reason": "query_failed"}


def _group_machine_operator_links(link_rows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    links_by_machine: Dict[str, List[Dict[str, Any]]] = {}
    for row in link_rows:
        machine_id = row["machine_id"]
        links_by_machine.setdefault(machine_id, []).append(
            {
                "operator_id": row["operator_id"],
                "operator_name": row["operator_name"],
                "operator_status": row["operator_status"],
            }
        )
    return links_by_machine


def _build_machine_list_rows(
    machines,
    *,
    op_types: Dict[str, Any],
    team_name_map: Dict[str, str],
    links_by_machine: Dict[str, List[Dict[str, Any]]],
    downtime_now_set: set,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for machine in machines:
        op_type = op_types.get(machine.op_type_id or "")
        links = links_by_machine.get(machine.machine_id, [])
        operator_text = ", ".join(
            [f"{item['operator_id']}{(' ' + item['operator_name']) if item.get('operator_name') else ''}".strip() for item in links]
        )
        rows.append(
            {
                "machine_id": machine.machine_id,
                "name": machine.name,
                "op_type_id": machine.op_type_id,
                "op_type_name": (op_type.name if op_type else None),
                "team_id": machine.team_id,
                "team_name": team_name_map.get(machine.team_id or ""),
                "status": machine.status,
                "status_zh": ("停机（计划）" if machine.machine_id in downtime_now_set else _machine_status_zh(machine.status)),
                "remark": machine.remark,
                "operator_text": operator_text,
                "operator_count": len(links),
            }
        )
    return rows


@bp.get("/")
def list_page():
    svc = MachineService(g.db, op_logger=getattr(g, "op_logger", None))
    op_type_svc = OpTypeService(g.db, op_logger=getattr(g, "op_logger", None))
    page, per_page = parse_page_args(request, default_per_page=100, max_per_page=300)
    selected_team_id = (request.args.get("team_id") or "").strip() or None

    team_options = load_team_options()
    team_name_map = build_team_name_map(team_options)
    try:
        machines = svc.list(team_id=selected_team_id)
    except BusinessError as e:
        if e.code == ErrorCode.TEAM_NOT_FOUND:
            flash(e.message, "warning")
            return redirect(url_for("equipment.list_page"))
        raise
    op_types = {ot.op_type_id: ot for ot in op_type_svc.list()}
    downtime_state = _load_active_downtime_machine_ids()
    downtime_now_set = downtime_state["machine_ids"]
    downtime_overlay_degraded = bool(downtime_state.get("degraded"))

    om_q = OperatorMachineQueryService(g.db, op_logger=getattr(g, "op_logger", None))
    links_by_machine = _group_machine_operator_links(om_q.list_links_with_operator_info())
    view_rows = _build_machine_list_rows(
        machines,
        op_types=op_types,
        team_name_map=team_name_map,
        links_by_machine=links_by_machine,
        downtime_now_set=downtime_now_set,
    )

    view_rows, pager = paginate_rows(view_rows, page, per_page)
    op_type_options = [(ot.op_type_id, ot.name) for ot in sorted(op_types.values(), key=lambda x: x.name)]

    return render_template(
        "equipment/list.html",
        title="设备管理",
        machines=view_rows,
        team_options=team_options,
        selected_team_id=selected_team_id,
        op_type_options=op_type_options,
        status_options=[
            (MachineStatus.ACTIVE.value, "可用"),
            (MachineStatus.MAINTAIN.value, "维修"),
            (MachineStatus.INACTIVE.value, "停用"),
        ],
        downtime_overlay_degraded=downtime_overlay_degraded,
        pager=pager,
    )


@bp.post("/create")
def create_machine():
    machine_id = request.form.get("machine_id")
    name = request.form.get("name")
    op_type_id = request.form.get("op_type_id") or None
    category = request.form.get("category") or None
    status = request.form.get("status") or MachineStatus.ACTIVE.value
    remark = request.form.get("remark")
    team_id = request.form.get("team_id") or None

    svc = MachineService(g.db, op_logger=getattr(g, "op_logger", None))
    m = svc.create(
        machine_id=machine_id,
        name=name,
        op_type_id=op_type_id,
        category=category,
        status=status,
        remark=remark,
        team_id=team_id,
    )
    flash(f"已创建设备：{m.machine_id} {m.name}", "success")
    return redirect(url_for("equipment.detail_page", machine_id=m.machine_id))


@bp.get("/<machine_id>")
def detail_page(machine_id: str):
    m_svc = MachineService(g.db, op_logger=getattr(g, "op_logger", None))
    link_svc = OperatorMachineService(g.db, op_logger=getattr(g, "op_logger", None))
    dt_svc = MachineDowntimeService(g.db, op_logger=getattr(g, "op_logger", None))

    op_type_svc = OpTypeService(g.db, op_logger=getattr(g, "op_logger", None))
    operator_svc = OperatorService(g.db, op_logger=getattr(g, "op_logger", None))

    m = m_svc.get(machine_id)
    links = link_svc.list_by_machine(machine_id)
    downtimes = dt_svc.list_by_machine(machine_id, include_cancelled=False)
    team_options = load_team_options()
    team_name_map = build_team_name_map(team_options)

    op_types = {ot.op_type_id: ot for ot in op_type_svc.list()}
    operators = {o.operator_id: o for o in operator_svc.list()}

    linked_operator_ids = {link.operator_id for link in links}
    linked_operators = _build_linked_operator_rows(links, operators)
    available_operators = _build_available_operator_rows(operators, linked_operator_ids)

    op_type_options = [(ot.op_type_id, ot.name) for ot in sorted(op_types.values(), key=lambda x: x.name)]

    return render_template(
        "equipment/detail.html",
        title=f"设备详情 - {m.machine_id} {m.name}",
        machine=m.to_dict(),
        machine_team_name=team_name_map.get(m.team_id or ""),
        team_options=team_options,
        machine_status_zh=_machine_status_zh(m.status),
        op_type_name=_selected_op_type_name(op_types, m),
        op_type_options=op_type_options,
        status_options=[
            (MachineStatus.ACTIVE.value, "可用"),
            (MachineStatus.MAINTAIN.value, "维修"),
            (MachineStatus.INACTIVE.value, "停用"),
        ],
        linked_operators=linked_operators,
        available_operators=available_operators,
        downtime_rows=[d.to_dict() for d in downtimes],
        downtime_reason_options=list(MachineDowntimeService.REASON_OPTIONS),
        skill_level_options=list(skill_level_options()),
    )


@bp.post("/<machine_id>/update")
def update_machine(machine_id: str):
    name = request.form.get("name")
    op_type_id = request.form.get("op_type_id")
    category = request.form.get("category")
    status = request.form.get("status")
    remark = request.form.get("remark")
    team_id = request.form.get("team_id")

    svc = MachineService(g.db, op_logger=getattr(g, "op_logger", None))
    svc.update(
        machine_id=machine_id,
        name=name,
        op_type_id=op_type_id,
        category=category,
        status=status,
        remark=remark,
        team_id=team_id,
    )
    flash("设备信息已保存。", "success")
    return redirect(url_for("equipment.detail_page", machine_id=machine_id))


@bp.post("/<machine_id>/status")
def set_status(machine_id: str):
    status = request.form.get("status")
    if not status:
        raise ValidationError("缺少状态参数", field="status")
    svc = MachineService(g.db, op_logger=getattr(g, "op_logger", None))
    m = svc.set_status(machine_id=machine_id, status=status)
    flash(f"已更新状态：{m.machine_id}  {_machine_status_zh(m.status)}", "success")
    return redirect(url_for("equipment.detail_page", machine_id=machine_id))


@bp.post("/<machine_id>/delete")
def delete_machine(machine_id: str):
    svc = MachineService(g.db, op_logger=getattr(g, "op_logger", None))
    try:
        svc.delete(machine_id)
        flash(f"已删除设备：{machine_id}", "success")
    except AppError as e:
        flash(e.message, "error")
    return redirect(url_for("equipment.list_page"))


@bp.post("/bulk/status")
def bulk_set_status():
    """
    批量设置设备状态（active/maintain/inactive）。
    """
    status = (request.form.get("status") or "").strip()
    machine_ids = request.form.getlist("machine_ids")
    if not machine_ids:
        flash("请至少选择 1 台设备。", "error")
        return redirect(url_for("equipment.list_page"))
    if status not in (MachineStatus.ACTIVE.value, MachineStatus.MAINTAIN.value, MachineStatus.INACTIVE.value):
        raise ValidationError("状态不正确，请选择：可用 / 维修 / 停用。", field="状态")

    svc = MachineService(g.db, op_logger=getattr(g, "op_logger", None))
    ok = 0
    failed: List[str] = []
    failed_details: List[str] = []
    for mid in machine_ids:
        try:
            svc.set_status(mid, status=status)
            ok += 1
        except AppError as e:
            failed.append(str(mid))
            failed_details.append(f"{mid}: {e.message}")
            continue
        except Exception:
            current_app.logger.exception("批量设置设备状态失败（machine_id=%s, status=%s）", mid, status)
            failed.append(str(mid))
            failed_details.append(f"{mid}: 内部错误，请查看日志")
            continue

    flash(f"批量状态更新完成：成功 {ok}，失败 {len(failed)}。", "success" if ok else "warning")
    if failed:
        sample = "；".join(failed_details[:10])
        flash(f"失败设备（最多展示 10 个）：{sample}", "warning")
    return redirect(url_for("equipment.list_page"))


@bp.post("/bulk/delete")
def bulk_delete():
    """
    批量删除设备（受引用保护；建议优先批量停用）。
    """
    machine_ids = request.form.getlist("machine_ids")
    if not machine_ids:
        flash("请至少选择 1 台设备。", "error")
        return redirect(url_for("equipment.list_page"))

    svc = MachineService(g.db, op_logger=getattr(g, "op_logger", None))
    ok = 0
    failed: List[str] = []
    failed_details: List[str] = []
    for mid in machine_ids:
        try:
            svc.delete(mid)
            ok += 1
        except AppError as e:
            failed.append(str(mid))
            failed_details.append(f"{mid}: {e.message}")
            continue
        except Exception:
            current_app.logger.exception("批量删除设备失败（machine_id=%s）", mid)
            failed.append(str(mid))
            failed_details.append(f"{mid}: 内部错误，请查看日志")
            continue

    flash(f"批量删除完成：成功 {ok}，失败 {len(failed)}。", "success" if ok else "warning")
    if failed:
        sample = "；".join(failed_details[:10])
        flash(f"删除失败（最多展示 10 个）：{sample}", "warning")
    return redirect(url_for("equipment.list_page"))


@bp.post("/<machine_id>/link/add")
def add_link(machine_id: str):
    operator_id = request.form.get("operator_id")
    svc = OperatorMachineService(g.db, op_logger=getattr(g, "op_logger", None))
    svc.add_link(operator_id=operator_id, machine_id=machine_id)
    flash("已添加人员关联。", "success")
    return redirect(url_for("equipment.detail_page", machine_id=machine_id))


@bp.post("/<machine_id>/link/update")
def update_link(machine_id: str):
    operator_id = request.form.get("operator_id")
    skill_level = request.form.get("skill_level")
    is_primary = YesNo.YES.value if request.form.get("is_primary") else YesNo.NO.value
    svc = OperatorMachineService(g.db, op_logger=getattr(g, "op_logger", None))
    svc.update_link_fields(
        operator_id=operator_id,
        machine_id=machine_id,
        skill_level=skill_level,
        is_primary=is_primary,
    )
    flash("已更新关联字段（技能等级/主操设备）。", "success")
    return redirect(url_for("equipment.detail_page", machine_id=machine_id))


@bp.post("/<machine_id>/link/remove")
def remove_link(machine_id: str):
    operator_id = request.form.get("operator_id")
    svc = OperatorMachineService(g.db, op_logger=getattr(g, "op_logger", None))
    svc.remove_link(operator_id=operator_id, machine_id=machine_id)
    flash("已解除人员关联。", "success")
    return redirect(url_for("equipment.detail_page", machine_id=machine_id))
