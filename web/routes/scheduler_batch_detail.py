from __future__ import annotations

from typing import Any, Dict, List

from flask import g

from web.ui_mode import render_ui_template as render_template

from core.services.scheduler import BatchService, ConfigService, ScheduleService
from data.repositories import MachineRepository, OperatorMachineRepository, OperatorRepository, SupplierRepository

from .scheduler_bp import bp, _batch_status_zh, _priority_zh, _ready_zh


@bp.get("/batches/<batch_id>")
def batch_detail(batch_id: str):
    batch_svc = BatchService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    sch_svc = ScheduleService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))

    b = batch_svc.get(batch_id)
    ops = sch_svc.list_batch_operations(batch_id=b.batch_id)

    # 预收集：当前批次内部工序已选的设备/人员（用于回显，即使其已停用/维修）
    selected_machine_ids = set()
    selected_operator_ids = set()
    for op in ops:
        if (op.source or "").strip() != "internal":
            continue
        if op.machine_id:
            selected_machine_ids.add(op.machine_id)
        if op.operator_id:
            selected_operator_ids.add(op.operator_id)

    # 下拉选项：默认只给“启用/在岗”的资源，减少误选
    m_repo = MachineRepository(g.db)
    o_repo = OperatorRepository(g.db)
    machines_active = m_repo.list(status="active")
    operators_active = o_repo.list(status="active")
    suppliers = SupplierRepository(g.db).list(status="active")

    # 为了让用户能定位问题：若历史上已选过停用/维修资源，也回显在下拉中（但禁用）
    machines_by_id = {m.machine_id: m for m in machines_active}
    for mid in sorted(selected_machine_ids):
        if mid in machines_by_id:
            continue
        extra = m_repo.get(mid)
        if extra:
            machines_by_id[extra.machine_id] = extra

    operators_by_id = {o.operator_id: o for o in operators_active}
    for oid in sorted(selected_operator_ids):
        if oid in operators_by_id:
            continue
        extra = o_repo.get(oid)
        if extra:
            operators_by_id[extra.operator_id] = extra

    # 供模板渲染：value/label/disabled（disabled=非 active，用于只回显不可选）
    machine_options: List[Dict[str, Any]] = []
    for m in sorted(machines_by_id.values(), key=lambda x: (x.status != "active", x.machine_id)):
        disabled = (m.status or "").strip() != "active"
        status_note = f"（不可用：{m.status}）" if disabled else ""
        machine_options.append({"value": m.machine_id, "label": f"{m.machine_id} {m.name}{status_note}", "disabled": disabled})

    operator_options: List[Dict[str, Any]] = []
    for o in sorted(operators_by_id.values(), key=lambda x: (x.status != "active", x.operator_id)):
        disabled = (o.status or "").strip() != "active"
        status_note = f"（不可用：{o.status}）" if disabled else ""
        operator_options.append({"value": o.operator_id, "label": f"{o.operator_id} {o.name}{status_note}", "disabled": disabled})

    supplier_options = [(s.supplier_id, f"{s.supplier_id} {s.name}") for s in suppliers]

    # 构建人机映射（用于批次详情页的“设备/人员”双向联动）。为避免过重，仅保留本页涉及的资源。
    active_machine_ids = [x["value"] for x in machine_options if not x.get("disabled")]
    active_operator_ids = [x["value"] for x in operator_options if not x.get("disabled")]
    machine_ids_needed = set(active_machine_ids) | set(selected_machine_ids)
    operator_ids_needed = set(active_operator_ids) | set(selected_operator_ids)

    machine_operators: Dict[str, List[str]] = {}
    operator_machines: Dict[str, List[str]] = {}
    machine_operator_meta: Dict[str, Dict[str, Dict[str, Any]]] = {}
    if machine_ids_needed and operator_ids_needed:
        m_list = sorted(machine_ids_needed)
        o_list = sorted(operator_ids_needed)
        link_rows = OperatorMachineRepository(g.db).list_simple_rows_for_machine_operator_sets(m_list, o_list)
        for r in link_rows:
            mc_id = r.get("machine_id")
            op_id = r.get("operator_id")
            if not mc_id or not op_id:
                continue
            machine_operators.setdefault(mc_id, []).append(op_id)
            operator_machines.setdefault(op_id, []).append(mc_id)
            machine_operator_meta.setdefault(mc_id, {})[op_id] = {
                "skill_level": r.get("skill_level"),
                "is_primary": r.get("is_primary"),
            }

    view_ops: List[Dict[str, Any]] = []
    for op in ops:
        d = op.to_dict()
        hint = sch_svc.get_external_merge_hint(op.id)
        d["merge_hint"] = hint
        view_ops.append(d)

    return render_template(
        "scheduler/batch_detail.html",
        title=f"批次详情 - {b.batch_id}",
        batch=b.to_dict(),
        batch_status_zh=_batch_status_zh(b.status),
        priority_zh=_priority_zh(b.priority),
        ready_status_zh=_ready_zh(b.ready_status),
        operations=view_ops,
        machine_options=machine_options,
        operator_options=operator_options,
        supplier_options=supplier_options,
        machine_operators=machine_operators,
        operator_machines=operator_machines,
        machine_operator_meta=machine_operator_meta,
        prefer_primary_skill=ConfigService(g.db).get_snapshot().prefer_primary_skill,
    )

