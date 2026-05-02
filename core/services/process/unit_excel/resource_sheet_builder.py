from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, List, Optional, Set, Tuple

from core.models.enums import MachineStatus, OperatorStatus, YesNo
from core.services.common.degradation import DegradationCollector

from .template_validation import record_diagnostic


def build_operator_rows(operator_names: Set[str]) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
    operator_id_map: Dict[str, str] = {}
    used_operator_ids: Set[str] = set()
    operators_rows: List[Dict[str, Any]] = []
    next_operator_no = 900001
    for name in sorted(operator_names):
        while f"{next_operator_no:06d}" in used_operator_ids:
            next_operator_no += 1
        op_id = f"{next_operator_no:06d}"
        used_operator_ids.add(op_id)
        next_operator_no += 1
        operator_id_map[name] = op_id
        operators_rows.append({"工号": op_id, "姓名": name, "状态": OperatorStatus.ACTIVE.value, "班组": None, "备注": None})
    return operator_id_map, operators_rows


def build_machines_rows(
    *,
    used_machine_ids: Set[str],
    machine_label_map: Dict[str, str],
    machine_internal_counter: Dict[str, Counter],
) -> List[Dict[str, Any]]:
    machines_rows: List[Dict[str, Any]] = []
    for machine_id in sorted(used_machine_ids):
        display = machine_label_map.get(machine_id) or machine_id
        machine_name = build_machine_name(machine_id=machine_id, machine_label=display)
        op_name = most_common_key(machine_internal_counter.get(machine_id))
        machines_rows.append(
            {
                "设备编号": machine_id,
                "设备名称": machine_name,
                "工种": op_name,
                "班组": None,
                "状态": MachineStatus.ACTIVE.value,
            }
        )
    return machines_rows


def build_operator_machine_rows(
    links: Set[Tuple[str, str]],
    operator_id_map: Dict[str, str],
    *,
    collector: DegradationCollector,
    samples: Dict[str, List[Any]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for operator_name, machine_id in sorted(links, key=lambda x: (operator_id_map.get(x[0], x[0]), x[1])):
        op_id = operator_id_map.get(operator_name)
        if not op_id:
            continue
        record_diagnostic(
            collector,
            samples,
            code="default_filled",
            scope="unit_excel.operator_machine",
            field="技能等级",
            message="人员设备关联缺少技能等级，已默认补齐为“普通”。",
            sample={"工号": op_id, "设备编号": machine_id, "value": "普通"},
        )
        record_diagnostic(
            collector,
            samples,
            code="default_filled",
            scope="unit_excel.operator_machine",
            field="主操设备",
            message="人员设备关联缺少主操标记，已默认补齐为“否”。",
            sample={"工号": op_id, "设备编号": machine_id, "value": "否"},
        )
        rows.append({"工号": op_id, "设备编号": machine_id, "技能等级": "normal", "主操设备": YesNo.NO.value})
    return rows


def build_machine_name(machine_id: str, machine_label: str) -> str:
    label = (machine_label or "").strip()
    label = re.sub(r"[（(].*?[）)]", "", label).strip()
    mid = (machine_id or "").strip()
    if label and label != mid:
        return label
    return mid or label


def most_common_key(counter: Optional[Counter]) -> Optional[str]:
    if not counter:
        return None
    try:
        return counter.most_common(1)[0][0]
    except Exception:
        return None
