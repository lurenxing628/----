from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from flask import flash, g, redirect, request, url_for

from core.infrastructure.errors import AppError, ValidationError
from core.models.enums import MachineStatus, YesNo
from core.services.equipment import MachineDowntimeService, MachineService
from core.services.equipment.machine_downtime_query_service import MachineDowntimeQueryService
from core.services.personnel import OperatorMachineService, OperatorService
from core.services.personnel.operator_machine_query_service import OperatorMachineQueryService
from core.services.process import OpTypeService
from web.ui_mode import render_ui_template as render_template

from .equipment_bp import _machine_status_zh, _operator_status_zh, bp
from .pagination import paginate_rows, parse_page_args


@bp.get("/")
def list_page():
    svc = MachineService(g.db, op_logger=getattr(g, "op_logger", None))
    op_type_svc = OpTypeService(g.db, op_logger=getattr(g, "op_logger", None))
    page, per_page = parse_page_args(request, default_per_page=100, max_per_page=300)

    machines = svc.list()
    op_types = {ot.op_type_id: ot for ot in op_type_svc.list()}

    # 自动绑定：若当前时间落在停机计划内，则页面显示“停机（计划）”
    downtime_now_set = set()
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        dt_q = MachineDowntimeQueryService(g.db, op_logger=getattr(g, "op_logger", None))
        downtime_now_set = dt_q.list_active_machine_ids_at(now_str)
    except Exception:
        downtime_now_set = set()

    # 聚合关联人员
    om_q = OperatorMachineQueryService(g.db, op_logger=getattr(g, "op_logger", None))
    link_rows = om_q.list_links_with_operator_info()

    links_by_machine: Dict[str, List[Dict[str, Any]]] = {}
    for r in link_rows:
        mc_id = r["machine_id"]
        links_by_machine.setdefault(mc_id, []).append(
            {
                "operator_id": r["operator_id"],
                "operator_name": r["operator_name"],
                "operator_status": r["operator_status"],
            }
        )

    view_rows: List[Dict[str, Any]] = []
    for m in machines:
        ot = op_types.get(m.op_type_id or "")
        links = links_by_machine.get(m.machine_id, [])
        operator_text = ", ".join(
            [f"{x['operator_id']}{(' ' + x['operator_name']) if x.get('operator_name') else ''}".strip() for x in links]
        )
        view_rows.append(
            {
                "machine_id": m.machine_id,
                "name": m.name,
                "op_type_id": m.op_type_id,
                "op_type_name": (ot.name if ot else None),
                "status": m.status,
                "status_zh": ("停机（计划）" if m.machine_id in downtime_now_set else _machine_status_zh(m.status)),
                "remark": m.remark,
                "operator_text": operator_text,
                "operator_count": len(links),
            }
        )

    view_rows, pager = paginate_rows(view_rows, page, per_page)

    # 工种下拉：按 name 排序
    op_type_options = [(ot.op_type_id, ot.name) for ot in sorted(op_types.values(), key=lambda x: x.name)]

    return render_template(
        "equipment/list.html",
        title="设备管理",
        machines=view_rows,
        op_type_options=op_type_options,
        status_options=[
            (MachineStatus.ACTIVE.value, "可用"),
            (MachineStatus.MAINTAIN.value, "维修"),
            (MachineStatus.INACTIVE.value, "停用"),
        ],
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

    svc = MachineService(g.db, op_logger=getattr(g, "op_logger", None))
    m = svc.create(machine_id=machine_id, name=name, op_type_id=op_type_id, category=category, status=status, remark=remark)
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

    op_types = {ot.op_type_id: ot for ot in op_type_svc.list()}
    operators = {o.operator_id: o for o in operator_svc.list()}

    linked_operator_ids = {link.operator_id for link in links}

    linked_operators: List[Dict[str, Any]] = []
    for link in links:
        op = operators.get(link.operator_id)
        linked_operators.append(
            {
                "operator_id": link.operator_id,
                "operator_name": (op.name if op else None),
                "status": (op.status if op else None),
                "status_zh": _operator_status_zh(op.status) if op else "-",
                "skill_level": getattr(link, "skill_level", None),
                "is_primary": getattr(link, "is_primary", None),
            }
        )

    available_operators: List[Dict[str, Any]] = []
    for op in operators.values():
        if op.operator_id in linked_operator_ids:
            continue
        available_operators.append(
            {
                "operator_id": op.operator_id,
                "operator_name": op.name,
                "status": op.status,
                "status_zh": _operator_status_zh(op.status),
            }
        )
    available_operators.sort(key=lambda x: x["operator_id"])

    op_type_options = [(ot.op_type_id, ot.name) for ot in sorted(op_types.values(), key=lambda x: x.name)]

    return render_template(
        "equipment/detail.html",
        title=f"设备详情 - {m.machine_id} {m.name}",
        machine=m.to_dict(),
        machine_status_zh=_machine_status_zh(m.status),
        op_type_name=(op_types.get(m.op_type_id or "")).name if m.op_type_id and op_types.get(m.op_type_id) else None,
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
        skill_level_options=[("beginner", "初级"), ("normal", "普通"), ("expert", "熟练")],
    )


@bp.post("/<machine_id>/update")
def update_machine(machine_id: str):
    name = request.form.get("name")
    op_type_id = request.form.get("op_type_id")
    category = request.form.get("category")
    status = request.form.get("status")
    remark = request.form.get("remark")

    svc = MachineService(g.db, op_logger=getattr(g, "op_logger", None))
    svc.update(machine_id=machine_id, name=name, op_type_id=op_type_id, category=category, status=status, remark=remark)
    flash("设备信息已保存。", "success")
    return redirect(url_for("equipment.detail_page", machine_id=machine_id))


@bp.post("/<machine_id>/status")
def set_status(machine_id: str):
    status = request.form.get("status")
    if not status:
        raise ValidationError("缺少状态参数", field="status")
    svc = MachineService(g.db, op_logger=getattr(g, "op_logger", None))
    m = svc.set_status(machine_id=machine_id, status=status)
    flash(f"已更新状态：{m.machine_id} → {_machine_status_zh(m.status)}", "success")
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
        raise ValidationError("状态不合法（允许：active / maintain / inactive）", field="status")

    svc = MachineService(g.db, op_logger=getattr(g, "op_logger", None))
    ok = 0
    failed: List[str] = []
    for mid in machine_ids:
        try:
            svc.set_status(mid, status=status)
            ok += 1
        except Exception:
            failed.append(str(mid))
            continue

    flash(f"批量状态更新完成：成功 {ok}，失败 {len(failed)}。", "success" if ok else "warning")
    if failed:
        sample = "，".join(failed[:10])
        flash(f"失败设备（最多展示 10 个）：{sample}", "warning")
    return redirect(url_for("equipment.list_page"))


@bp.post("/bulk/delete")
def bulk_delete():
    """
    批量删除设备（受引用保护；建议优先批量“停用”）。
    """
    machine_ids = request.form.getlist("machine_ids")
    if not machine_ids:
        flash("请至少选择 1 台设备。", "error")
        return redirect(url_for("equipment.list_page"))

    svc = MachineService(g.db, op_logger=getattr(g, "op_logger", None))
    ok = 0
    failed: List[str] = []
    for mid in machine_ids:
        try:
            svc.delete(mid)
            ok += 1
        except Exception:
            failed.append(str(mid))
            continue

    flash(f"批量删除完成：成功 {ok}，失败 {len(failed)}。", "success" if ok else "warning")
    if failed:
        sample = "，".join(failed[:10])
        flash(f"删除失败（最多展示 10 个）：{sample}。常见原因：被批次工序/排程引用，请改为“停用”。", "warning")
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
    svc.update_link_fields(operator_id=operator_id, machine_id=machine_id, skill_level=skill_level, is_primary=is_primary)
    flash("已更新关联字段（技能等级/主操设备）。", "success")
    return redirect(url_for("equipment.detail_page", machine_id=machine_id))


@bp.post("/<machine_id>/link/remove")
def remove_link(machine_id: str):
    operator_id = request.form.get("operator_id")
    svc = OperatorMachineService(g.db, op_logger=getattr(g, "op_logger", None))
    svc.remove_link(operator_id=operator_id, machine_id=machine_id)
    flash("已解除人员关联。", "success")
    return redirect(url_for("equipment.detail_page", machine_id=machine_id))

