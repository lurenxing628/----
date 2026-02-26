from __future__ import annotations

from typing import Any, Dict, List

from flask import g, request

from web.ui_mode import render_ui_template as render_template

from core.models.enums import SourceType
from core.services.scheduler import BatchService, ConfigService, ScheduleService
from data.repositories import MachineRepository, OperatorMachineRepository, OperatorRepository, SupplierRepository

from .scheduler_bp import bp, _batch_status_zh, _priority_zh, _ready_zh


@bp.get("/batches/<batch_id>")
def batch_detail(batch_id: str):
    batch_svc = BatchService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    sch_svc = ScheduleService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))

    b = batch_svc.get(batch_id)
    ops = sch_svc.list_batch_operations(batch_id=b.batch_id)
    internal_op_count = 0
    try:
        for op in ops or []:
            src = (getattr(op, "source", "") or "").strip().lower()
            if src == SourceType.INTERNAL.value:
                internal_op_count += 1
    except Exception:
        internal_op_count = 0

    # 预收集：当前批次已选的资源（用于回显，即使其已停用/维修/已删除）
    selected_machine_ids = set()
    selected_operator_ids = set()
    selected_supplier_ids = set()
    for op in ops:
        src = (op.source or "").strip().lower()
        if src == SourceType.INTERNAL.value:
            if op.machine_id:
                selected_machine_ids.add(op.machine_id)
            if op.operator_id:
                selected_operator_ids.add(op.operator_id)
        elif src == SourceType.EXTERNAL.value:
            if op.supplier_id:
                selected_supplier_ids.add(op.supplier_id)

    # 下拉选项：默认只给“启用/在岗”的资源，减少误选
    m_repo = MachineRepository(g.db)
    o_repo = OperatorRepository(g.db)
    s_repo = SupplierRepository(g.db)
    machines_active = m_repo.list(status="active")
    operators_active = o_repo.list(status="active")
    suppliers_active = s_repo.list(status="active")

    # 为了让用户能定位问题：
    # - 若历史上已选过停用/维修资源，也回显在下拉中（但禁用）
    # - 若资源已被删除（get() 返回 None），也注入一个占位选项（禁用 + “已删除”标注）
    machines_by_id = {m.machine_id: m for m in machines_active}
    missing_machine_ids = set()
    for mid in sorted(selected_machine_ids):
        if mid in machines_by_id:
            continue
        extra = m_repo.get(mid)
        if extra:
            machines_by_id[extra.machine_id] = extra
        else:
            missing_machine_ids.add(mid)

    operators_by_id = {o.operator_id: o for o in operators_active}
    missing_operator_ids = set()
    for oid in sorted(selected_operator_ids):
        if oid in operators_by_id:
            continue
        extra = o_repo.get(oid)
        if extra:
            operators_by_id[extra.operator_id] = extra
        else:
            missing_operator_ids.add(oid)

    # 供模板渲染：value/label/disabled（disabled=非 active，用于只回显不可选）
    machine_options: List[Dict[str, Any]] = []
    for m in sorted(machines_by_id.values(), key=lambda x: ((x.status or "").strip() != "active", x.machine_id)):
        status_text = (m.status or "").strip()
        disabled = status_text != "active"
        status_note = f"（不可用：{status_text}）" if disabled else ""
        machine_options.append(
            {"value": m.machine_id, "label": f"{m.machine_id} {m.name}{status_note}", "disabled": disabled}
        )
    for mid in sorted(missing_machine_ids):
        machine_options.append({"value": mid, "label": f"{mid}（已删除）", "disabled": True, "orphan": True})

    operator_options: List[Dict[str, Any]] = []
    for o in sorted(operators_by_id.values(), key=lambda x: ((x.status or "").strip() != "active", x.operator_id)):
        status_text = (o.status or "").strip()
        disabled = status_text != "active"
        status_note = f"（不可用：{status_text}）" if disabled else ""
        operator_options.append(
            {"value": o.operator_id, "label": f"{o.operator_id} {o.name}{status_note}", "disabled": disabled}
        )
    for oid in sorted(missing_operator_ids):
        operator_options.append({"value": oid, "label": f"{oid}（已删除）", "disabled": True, "orphan": True})

    suppliers_by_id = {s.supplier_id: s for s in suppliers_active}
    missing_supplier_ids = set()
    for sid in sorted(selected_supplier_ids):
        if sid in suppliers_by_id:
            continue
        extra = s_repo.get(sid)
        if extra:
            suppliers_by_id[extra.supplier_id] = extra
        else:
            missing_supplier_ids.add(sid)

    supplier_options: List[Dict[str, Any]] = []
    for s in sorted(suppliers_by_id.values(), key=lambda x: ((x.status or "").strip() != "active", x.supplier_id)):
        status_text = (s.status or "").strip()
        disabled = status_text != "active"
        status_note = f"（不可用：{status_text}）" if disabled else ""
        name = (s.name or "").strip()
        label = f"{s.supplier_id} {name}".strip() + status_note
        supplier_options.append({"value": s.supplier_id, "label": label, "disabled": disabled})
    for sid in sorted(missing_supplier_ids):
        supplier_options.append({"value": sid, "label": f"{sid}（已删除）", "disabled": True})

    # Win7 性能：批次详情页下拉选项懒加载（避免每行重复渲染大量 <option>）
    # - auto：内部工序行较多或可选资源较多时启用
    # - query 参数强制：?lazy_select=1 / ?lazy_select=0（便于现场回退/对比）
    lazy_q = (request.args.get("lazy_select") or "").strip().lower()
    if lazy_q in ("1", "true", "yes", "y", "on"):
        lazy_select_enabled = True
    elif lazy_q in ("0", "false", "no", "n", "off"):
        lazy_select_enabled = False
    else:
        lazy_select_enabled = bool(
            internal_op_count > 30
            or len(machine_options) > 80
            or len(operator_options) > 80
        )

    # 构建人机映射（用于批次详情页的“设备/人员”双向联动）。为避免过重，仅保留本页涉及的资源。
    active_machine_ids = [x["value"] for x in machine_options if not x.get("disabled")]
    active_operator_ids = [x["value"] for x in operator_options if not x.get("disabled")]
    machine_ids_needed = set(active_machine_ids) | set(selected_machine_ids)
    operator_ids_needed = set(active_operator_ids) | set(selected_operator_ids)

    machine_operators: Dict[str, List[str]] = {}
    operator_machines: Dict[str, List[str]] = {}
    machine_operator_meta: Dict[str, Dict[str, Dict[str, Any]]] = {}
    prefer_primary_skill = ConfigService(g.db).get_snapshot().prefer_primary_skill
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
            # 仅在“主操优先”启用时注入 meta，减少页面内联 JSON 体积
            if prefer_primary_skill == "yes":
                machine_operator_meta.setdefault(mc_id, {})[op_id] = {
                    "skill_level": r.get("skill_level"),
                    "is_primary": r.get("is_primary"),
                }

    view_ops: List[Dict[str, Any]] = []
    for op in ops:
        d = op.to_dict()
        # 防御：历史数据/导入可能出现大小写不一致（Internal/EXTERNAL），此处统一归一化供模板判断分支使用
        d["source"] = (d.get("source") or "").strip().lower()
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
        # operatorMachines 可在前端由 machineOperators 反推，避免双份映射带来的 HTML 膨胀
        operator_machines=None,
        machine_operator_meta=machine_operator_meta,
        prefer_primary_skill=prefer_primary_skill,
        lazy_select_enabled=lazy_select_enabled,
    )

