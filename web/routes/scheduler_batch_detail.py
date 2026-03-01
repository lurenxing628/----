from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

from flask import g, request

from core.models.enums import MachineStatus, OperatorStatus, SourceType, SupplierStatus, YesNo
from core.services.equipment import MachineService
from core.services.personnel import OperatorService
from core.services.personnel.operator_machine_query_service import OperatorMachineQueryService
from core.services.process import SupplierService
from core.services.scheduler import BatchService, ConfigService, ScheduleService
from web.ui_mode import render_ui_template as render_template

from .scheduler_bp import _batch_status_zh, _priority_zh, _ready_zh, bp


def _count_internal_ops(ops: List[Any]) -> int:
    try:
        cnt = 0
        for op in ops or []:
            src = (getattr(op, "source", "") or "").strip().lower()
            if src == SourceType.INTERNAL.value:
                cnt += 1
        return cnt
    except Exception:
        return 0


def _collect_selected_resource_ids(ops: List[Any]) -> Tuple[Set[str], Set[str], Set[str]]:
    selected_machine_ids: Set[str] = set()
    selected_operator_ids: Set[str] = set()
    selected_supplier_ids: Set[str] = set()
    for op in ops or []:
        src = (getattr(op, "source", "") or "").strip().lower()
        if src == SourceType.INTERNAL.value:
            if getattr(op, "machine_id", None):
                selected_machine_ids.add(str(op.machine_id))
            if getattr(op, "operator_id", None):
                selected_operator_ids.add(str(op.operator_id))
        elif src == SourceType.EXTERNAL.value:
            if getattr(op, "supplier_id", None):
                selected_supplier_ids.add(str(op.supplier_id))
    return selected_machine_ids, selected_operator_ids, selected_supplier_ids


def _build_machine_options(machine_svc: MachineService, selected_machine_ids: Set[str]) -> List[Dict[str, Any]]:
    machines_active = machine_svc.list(status=MachineStatus.ACTIVE.value)
    machines_by_id = {m.machine_id: m for m in machines_active}
    missing_machine_ids: Set[str] = set()
    for mid in sorted(selected_machine_ids):
        if mid in machines_by_id:
            continue
        extra = machine_svc.get_optional(mid)
        if extra:
            machines_by_id[extra.machine_id] = extra
        else:
            missing_machine_ids.add(mid)

    machine_options: List[Dict[str, Any]] = []
    for m in sorted(
        machines_by_id.values(),
        key=lambda x: ((x.status or "").strip() != MachineStatus.ACTIVE.value, x.machine_id),
    ):
        status_text = (m.status or "").strip()
        disabled = status_text != MachineStatus.ACTIVE.value
        status_note = f"（不可用：{status_text}）" if disabled else ""
        machine_options.append(
            {"value": m.machine_id, "label": f"{m.machine_id} {m.name}{status_note}", "disabled": disabled}
        )
    for mid in sorted(missing_machine_ids):
        machine_options.append({"value": mid, "label": f"{mid}（已删除）", "disabled": True, "orphan": True})
    return machine_options


def _build_operator_options(operator_svc: OperatorService, selected_operator_ids: Set[str]) -> List[Dict[str, Any]]:
    operators_active = operator_svc.list(status=OperatorStatus.ACTIVE.value)
    operators_by_id = {o.operator_id: o for o in operators_active}
    missing_operator_ids: Set[str] = set()
    for oid in sorted(selected_operator_ids):
        if oid in operators_by_id:
            continue
        extra = operator_svc.get_optional(oid)
        if extra:
            operators_by_id[extra.operator_id] = extra
        else:
            missing_operator_ids.add(oid)

    operator_options: List[Dict[str, Any]] = []
    for o in sorted(
        operators_by_id.values(),
        key=lambda x: ((x.status or "").strip() != OperatorStatus.ACTIVE.value, x.operator_id),
    ):
        status_text = (o.status or "").strip()
        disabled = status_text != OperatorStatus.ACTIVE.value
        status_note = f"（不可用：{status_text}）" if disabled else ""
        operator_options.append(
            {"value": o.operator_id, "label": f"{o.operator_id} {o.name}{status_note}", "disabled": disabled}
        )
    for oid in sorted(missing_operator_ids):
        operator_options.append({"value": oid, "label": f"{oid}（已删除）", "disabled": True, "orphan": True})
    return operator_options


def _build_supplier_options(supplier_svc: SupplierService, selected_supplier_ids: Set[str]) -> List[Dict[str, Any]]:
    suppliers_active = supplier_svc.list(status=SupplierStatus.ACTIVE.value)
    suppliers_by_id = {s.supplier_id: s for s in suppliers_active}
    missing_supplier_ids: Set[str] = set()
    for sid in sorted(selected_supplier_ids):
        if sid in suppliers_by_id:
            continue
        extra = supplier_svc.get_optional(sid)
        if extra:
            suppliers_by_id[extra.supplier_id] = extra
        else:
            missing_supplier_ids.add(sid)

    supplier_options: List[Dict[str, Any]] = []
    for s in sorted(
        suppliers_by_id.values(),
        key=lambda x: ((x.status or "").strip() != SupplierStatus.ACTIVE.value, x.supplier_id),
    ):
        status_text = (s.status or "").strip()
        disabled = status_text != SupplierStatus.ACTIVE.value
        status_note = f"（不可用：{status_text}）" if disabled else ""
        name = (s.name or "").strip()
        label = f"{s.supplier_id} {name}".strip() + status_note
        supplier_options.append({"value": s.supplier_id, "label": label, "disabled": disabled})
    for sid in sorted(missing_supplier_ids):
        supplier_options.append({"value": sid, "label": f"{sid}（已删除）", "disabled": True})
    return supplier_options


def _resolve_lazy_select_enabled(
    internal_op_count: int,
    machine_options: List[Dict[str, Any]],
    operator_options: List[Dict[str, Any]],
) -> bool:
    lazy_q = (request.args.get("lazy_select") or "").strip().lower()
    if lazy_q in ("1", "true", "yes", "y", "on"):
        return True
    if lazy_q in ("0", "false", "no", "n", "off"):
        return False
    return bool(internal_op_count > 30 or len(machine_options) > 80 or len(operator_options) > 80)


def _build_machine_operator_maps(
    *,
    machine_options: List[Dict[str, Any]],
    operator_options: List[Dict[str, Any]],
    selected_machine_ids: Set[str],
    selected_operator_ids: Set[str],
    prefer_primary_skill: str,
    om_q: OperatorMachineQueryService,
) -> Tuple[Dict[str, List[str]], Dict[str, Dict[str, Dict[str, Any]]]]:
    active_machine_ids = [x["value"] for x in machine_options if not x.get("disabled")]
    active_operator_ids = [x["value"] for x in operator_options if not x.get("disabled")]
    machine_ids_needed = set(active_machine_ids) | set(selected_machine_ids)
    operator_ids_needed = set(active_operator_ids) | set(selected_operator_ids)

    machine_operators: Dict[str, List[str]] = {}
    machine_operator_meta: Dict[str, Dict[str, Dict[str, Any]]] = {}
    if not machine_ids_needed or not operator_ids_needed:
        return machine_operators, machine_operator_meta

    m_list = sorted(machine_ids_needed)
    o_list = sorted(operator_ids_needed)
    link_rows = om_q.list_simple_rows_for_machine_operator_sets(m_list, o_list)
    for r in link_rows:
        mc_id = r.get("machine_id")
        op_id = r.get("operator_id")
        if not mc_id or not op_id:
            continue
        machine_operators.setdefault(mc_id, []).append(op_id)
        if prefer_primary_skill == YesNo.YES.value:
            machine_operator_meta.setdefault(mc_id, {})[op_id] = {
                "skill_level": r.get("skill_level"),
                "is_primary": r.get("is_primary"),
            }
    return machine_operators, machine_operator_meta


def _build_view_ops(ops: List[Any], sch_svc: ScheduleService) -> List[Dict[str, Any]]:
    view_ops: List[Dict[str, Any]] = []
    for op in ops or []:
        d = op.to_dict()
        d["source"] = (d.get("source") or "").strip().lower()
        d["merge_hint"] = sch_svc.get_external_merge_hint(op.id)
        view_ops.append(d)
    return view_ops


@bp.get("/batches/<batch_id>")
def batch_detail(batch_id: str):
    batch_svc = BatchService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    sch_svc = ScheduleService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))

    b = batch_svc.get(batch_id)
    ops = sch_svc.list_batch_operations(batch_id=b.batch_id)

    internal_op_count = _count_internal_ops(ops)
    selected_machine_ids, selected_operator_ids, selected_supplier_ids = _collect_selected_resource_ids(ops)

    m_svc = MachineService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    o_svc = OperatorService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    s_svc = SupplierService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))

    machine_options = _build_machine_options(m_svc, selected_machine_ids)
    operator_options = _build_operator_options(o_svc, selected_operator_ids)
    supplier_options = _build_supplier_options(s_svc, selected_supplier_ids)

    lazy_select_enabled = _resolve_lazy_select_enabled(internal_op_count, machine_options, operator_options)

    prefer_primary_skill = ConfigService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None)).get_snapshot().prefer_primary_skill
    om_q = OperatorMachineQueryService(g.db, op_logger=getattr(g, "op_logger", None))
    machine_operators, machine_operator_meta = _build_machine_operator_maps(
        machine_options=machine_options,
        operator_options=operator_options,
        selected_machine_ids=selected_machine_ids,
        selected_operator_ids=selected_operator_ids,
        prefer_primary_skill=prefer_primary_skill,
        om_q=om_q,
    )

    view_ops = _build_view_ops(ops, sch_svc)

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

