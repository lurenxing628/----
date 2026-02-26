from __future__ import annotations

from typing import Any, Dict, List

from flask import flash, g, redirect, request, url_for

from web.ui_mode import render_ui_template as render_template

from core.infrastructure.errors import AppError, ValidationError
from core.services.personnel import OperatorMachineService, OperatorService
from data.repositories import MachineRepository

from .personnel_bp import bp, _machine_status_zh, _operator_status_zh
from .pagination import paginate_rows, parse_page_args


@bp.get("/")
def list_page():
    op_svc = OperatorService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    m_repo = MachineRepository(g.db)
    page, per_page = parse_page_args(request, default_per_page=100, max_per_page=300)

    operators = op_svc.list()
    # 预加载所有设备（用于展示名称）
    machines = {m.machine_id: m for m in m_repo.list()}

    # 预加载关联并聚合到人员
    link_rows = g.db.execute(
        "SELECT operator_id, machine_id FROM OperatorMachine ORDER BY operator_id, machine_id"
    ).fetchall()
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
        status_options=[("active", "在岗"), ("inactive", "停用/休假")],
        pager=pager,
    )


@bp.post("/create")
def create_operator():
    op_id = request.form.get("operator_id")
    name = request.form.get("name")
    status = request.form.get("status") or "active"
    remark = request.form.get("remark")

    svc = OperatorService(g.db, op_logger=getattr(g, "op_logger", None))
    op = svc.create(operator_id=op_id, name=name, status=status, remark=remark)
    flash(f"已创建人员：{op.operator_id} {op.name}", "success")
    return redirect(url_for("personnel.detail_page", operator_id=op.operator_id))


@bp.get("/<operator_id>")
def detail_page(operator_id: str):
    op_svc = OperatorService(g.db, op_logger=getattr(g, "op_logger", None))
    link_svc = OperatorMachineService(g.db, op_logger=getattr(g, "op_logger", None))
    m_repo = MachineRepository(g.db)

    op = op_svc.get(operator_id)
    links = link_svc.list_by_operator(operator_id)

    machines = {m.machine_id: m for m in m_repo.list()}
    linked_machine_ids = {l.machine_id for l in links}

    linked_machines: List[Dict[str, Any]] = []
    for l in links:
        m = machines.get(l.machine_id)
        linked_machines.append(
            {
                "machine_id": l.machine_id,
                "machine_name": (m.name if m else None),
                "status": (m.status if m else None),
                "status_zh": _machine_status_zh(m.status) if m else "-",
                "skill_level": getattr(l, "skill_level", None),
                "is_primary": getattr(l, "is_primary", None),
            }
        )

    available_machines: List[Dict[str, Any]] = []
    for m in machines.values():
        if m.machine_id in linked_machine_ids:
            continue
        available_machines.append(
            {
                "machine_id": m.machine_id,
                "machine_name": m.name,
                "status": m.status,
                "status_zh": _machine_status_zh(m.status),
            }
        )
    available_machines.sort(key=lambda x: x["machine_id"])

    return render_template(
        "personnel/detail.html",
        title=f"人员详情 - {op.operator_id} {op.name}",
        operator=op.to_dict(),
        operator_status_zh=_operator_status_zh(op.status),
        status_options=[("active", "在岗"), ("inactive", "停用/休假")],
        linked_machines=linked_machines,
        available_machines=available_machines,
        skill_level_options=[("beginner", "初级"), ("normal", "普通"), ("expert", "熟练")],
    )


@bp.post("/<operator_id>/update")
def update_operator(operator_id: str):
    name = request.form.get("name")
    status = request.form.get("status")
    remark = request.form.get("remark")

    svc = OperatorService(g.db, op_logger=getattr(g, "op_logger", None))
    op = svc.update(operator_id=operator_id, name=name, status=status, remark=remark)
    flash("人员信息已保存。", "success")
    return redirect(url_for("personnel.detail_page", operator_id=op.operator_id))


@bp.post("/<operator_id>/status")
def set_status(operator_id: str):
    status = request.form.get("status")
    if not status:
        raise ValidationError("缺少状态参数", field="status")
    svc = OperatorService(g.db, op_logger=getattr(g, "op_logger", None))
    op = svc.set_status(operator_id=operator_id, status=status)
    flash(f"已更新状态：{op.operator_id} → {_operator_status_zh(op.status)}", "success")
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
    if status not in ("active", "inactive"):
        raise ValidationError("状态不合法（允许：active / inactive）", field="status")

    svc = OperatorService(g.db, op_logger=getattr(g, "op_logger", None))
    ok = 0
    failed: List[str] = []
    for oid in operator_ids:
        try:
            svc.set_status(oid, status=status)
            ok += 1
        except Exception:
            failed.append(str(oid))
            continue

    flash(f"批量状态更新完成：成功 {ok}，失败 {len(failed)}。", "success" if ok else "warning")
    if failed:
        sample = "，".join(failed[:10])
        flash(f"失败人员（最多展示 10 个）：{sample}", "warning")
    return redirect(url_for("personnel.list_page"))


@bp.post("/bulk/delete")
def bulk_delete():
    """
    批量删除人员（受引用保护；建议优先批量“停用”）。
    """
    operator_ids = request.form.getlist("operator_ids")
    if not operator_ids:
        flash("请至少选择 1 个人员。", "error")
        return redirect(url_for("personnel.list_page"))

    svc = OperatorService(g.db, op_logger=getattr(g, "op_logger", None))
    ok = 0
    failed: List[str] = []
    for oid in operator_ids:
        try:
            svc.delete(oid)
            ok += 1
        except Exception:
            failed.append(str(oid))
            continue

    flash(f"批量删除完成：成功 {ok}，失败 {len(failed)}。", "success" if ok else "warning")
    if failed:
        sample = "，".join(failed[:10])
        flash(f"删除失败（最多展示 10 个）：{sample}。常见原因：被批次工序/排程引用，请改为“停用”。", "warning")
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
    is_primary = "yes" if request.form.get("is_primary") else "no"
    svc = OperatorMachineService(g.db, op_logger=getattr(g, "op_logger", None))
    svc.update_link_fields(operator_id=operator_id, machine_id=machine_id, skill_level=skill_level, is_primary=is_primary)
    flash("已更新关联字段（技能等级/主操设备）。", "success")
    return redirect(url_for("personnel.detail_page", operator_id=operator_id))


@bp.post("/<operator_id>/link/remove")
def remove_link(operator_id: str):
    machine_id = request.form.get("machine_id")
    svc = OperatorMachineService(g.db, op_logger=getattr(g, "op_logger", None))
    svc.remove_link(operator_id=operator_id, machine_id=machine_id)
    flash("已解除设备关联。", "success")
    return redirect(url_for("personnel.detail_page", operator_id=operator_id))

