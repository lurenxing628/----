from __future__ import annotations

from typing import Any, Dict, List

from core.models.enums import OperatorStatus
from core.services.common.normalization_matrix import skill_level_options
from core.services.equipment import MachineService
from core.services.personnel import OperatorService
from core.services.personnel.operator_machine_query_service import OperatorMachineQueryService
from web.routes.personnel_bp import _machine_status_zh, _operator_status_zh
from web.routes.team_view_helpers import build_team_name_map, load_team_options


def build_personnel_detail_context(db, operator_id: str, *, op_logger=None) -> Dict[str, Any]:
    op_svc = OperatorService(db, op_logger=op_logger)
    link_q = OperatorMachineQueryService(db, op_logger=op_logger)
    mc_svc = MachineService(db, op_logger=op_logger)

    operator = op_svc.get(operator_id)
    links = _operator_links(link_q, operator_id)
    team_options = load_team_options()
    team_name_map = build_team_name_map(team_options)
    machines = {machine.machine_id: machine for machine in mc_svc.list()}
    linked_machines = _build_linked_machines(links, machines)
    available_machines = _build_available_machines(links, machines)
    dirty_summary = _build_link_dirty_summary(linked_machines)

    return {
        "title": f"人员详情 - {operator.operator_id} {operator.name}",
        "operator": operator.to_dict(),
        "operator_team_name": team_name_map.get(operator.team_id or ""),
        "team_options": team_options,
        "operator_status_zh": _operator_status_zh(operator.status),
        "status_options": [(OperatorStatus.ACTIVE.value, "在岗"), (OperatorStatus.INACTIVE.value, "停用/休假")],
        "linked_machines": linked_machines,
        "link_dirty_summary": dirty_summary,
        "available_machines": available_machines,
        "skill_level_options": list(skill_level_options()),
    }


def _operator_links(link_q: OperatorMachineQueryService, operator_id: str) -> List[Dict[str, Any]]:
    normalized_operator_id = str(operator_id or "").strip()
    return [
        row
        for row in link_q.list_simple_rows()
        if str(row.get("operator_id") or "").strip() == normalized_operator_id
    ]


def _build_linked_machines(links: List[Dict[str, Any]], machines: Dict[str, Any]) -> List[Dict[str, Any]]:
    linked_machines: List[Dict[str, Any]] = []
    for link in links:
        machine_id = str(link.get("machine_id") or "").strip()
        machine = machines.get(machine_id)
        linked_machines.append(
            {
                "machine_id": machine_id,
                "machine_name": machine.name if machine else None,
                "status": machine.status if machine else None,
                "status_zh": _machine_status_zh(machine.status) if machine else "-",
                "skill_level": link.get("skill_level"),
                "is_primary": link.get("is_primary"),
                "dirty_fields": list(link.get("dirty_fields") or []),
                "dirty_reasons": dict(link.get("dirty_reasons") or {}),
            }
        )
    return linked_machines


def _build_available_machines(links: List[Dict[str, Any]], machines: Dict[str, Any]) -> List[Dict[str, Any]]:
    linked_machine_ids = {str(link.get("machine_id") or "").strip() for link in links}
    available_machines: List[Dict[str, Any]] = []
    for machine in machines.values():
        if machine.machine_id in linked_machine_ids:
            continue
        available_machines.append(
            {
                "machine_id": machine.machine_id,
                "machine_name": machine.name,
                "status": machine.status,
                "status_zh": _machine_status_zh(machine.status),
            }
        )
    available_machines.sort(key=lambda item: item["machine_id"])
    return available_machines


def _build_link_dirty_summary(linked_machines: List[Dict[str, Any]]) -> Dict[str, Any]:
    dirty_link_rows = [machine for machine in linked_machines if bool(machine.get("dirty_fields"))]
    dirty_link_fields = sorted(
        {
            str(field).strip()
            for row in dirty_link_rows
            for field in list(row.get("dirty_fields") or [])
            if str(field).strip()
        }
    )
    dirty_link_reasons: Dict[str, str] = {}
    for row in dirty_link_rows:
        for field, reason in dict(row.get("dirty_reasons") or {}).items():
            if field not in dirty_link_reasons and str(reason or "").strip():
                dirty_link_reasons[str(field)] = str(reason)
    return {
        "row_count": int(len(dirty_link_rows)),
        "fields": dirty_link_fields,
        "reasons": dirty_link_reasons,
    }
