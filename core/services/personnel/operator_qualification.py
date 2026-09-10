"""Personnel qualification shared by planning and editing, without scheduler imports."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set

from core.infrastructure.errors import AppError, ValidationError
from data.repositories.operator_machine_repo import OperatorMachineRepository
from data.repositories.operator_qualification_repo import OperatorQualificationRepository


class OperatorQualificationError(ValidationError):
    """Qualification failures must not fall back to an unfiltered resource pool."""


def _invalid_facts(message: str) -> OperatorQualificationError:
    return OperatorQualificationError(
        message, field="operator_qualification", details={"reason": "operator_qualification_data_invalid"},
    )


def _identifier(value: Any) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or "\x00" in value:
        raise _invalid_facts("人员资格资料中的编号无效，请核对原始资料；本次没有生成新排程。")
    return value


def require_machine_authorization(authorizations: OperatorMachineRepository, operator_id: str, machine_id: Optional[str]) -> None:
    if machine_id and not authorizations.exists(operator_id, machine_id):
        raise OperatorQualificationError(
            f"人员“{operator_id}”未被配置为可操作设备“{machine_id}”。"
            "请先在【人员管理】或【设备管理】中维护人机关联后再排产。",
            field="设备/人员",
            details={"reason": "operator_machine_not_authorized", "operator_id": operator_id, "machine_id": machine_id},
        )


def _require_explicit_auto_work_types(operations: Sequence[Any], rows: List[Dict[str, Any]],
                                     qualifications: Dict[str, Optional[Set[str]]]) -> None:
    declared_machines = {row["machine_id"] for row in rows
                         if row["operator_id"] in qualifications and qualifications[row["operator_id"]] is not None}
    for op in operations:
        if str(getattr(op, "source", "") or "").strip().lower() != "internal" or getattr(op, "operator_id", None):
            continue
        if getattr(op, "machine_id", None) in declared_machines:
            op_type_id = getattr(op, "op_type_id", None)
            if not op_type_id:
                raise _invalid_facts("固定设备的工序缺少真实工种编号，不能用设备工种猜测人员资格；请补齐工序工种后再自动选人。")
            _identifier(op_type_id)


class OperatorQualificationService:
    def __init__(self, conn, logger=None):
        self.repo = OperatorQualificationRepository(conn, logger=logger)
        self.authorizations = OperatorMachineRepository(conn, logger=logger)

    def load(self, operator_ids: Sequence[str]) -> Dict[str, Optional[Set[str]]]:
        ids = {_identifier(value) for value in operator_ids}
        try:
            profiles, skills = self.repo.read_skill_facts(sorted(ids))
        except AppError as exc:
            raise _invalid_facts("人员技能或登记资料无法读取，请检查数据库；本次不会退回旧授权名单排产。") from exc
        qualifications: Dict[str, Optional[Set[str]]] = {}
        for row in profiles:
            oid = _identifier(row["operator_id"])
            declared = row["skills_declared"]
            if row["profile_operator_id"] is not None and (type(declared) is not int or declared not in (0, 1)):
                raise _invalid_facts(f"人员“{oid}”的技能登记标记无效，请核对资料。")
            if oid in qualifications:
                raise _invalid_facts(f"人员“{oid}”的技能登记资料重复，请核对资料。")
            qualifications[oid] = set() if declared == 1 else None
        if set(qualifications) != ids:
            raise _invalid_facts("人员资格对应的人员记录不存在，不能按旧授权名单继续排产。")
        for row in skills:
            oid, op_type_id = _identifier(row["operator_id"]), _identifier(row["op_type_id"])
            if row["category"] != "internal":
                raise _invalid_facts(f"人员“{oid}”的技能工种“{op_type_id}”不存在或不是自制工种，请核对资料。")
            current = qualifications[oid]
            if current is None:
                current = qualifications[oid] = set()
            if op_type_id in current:
                raise _invalid_facts(f"人员“{oid}”的技能工种重复，请核对资料。")
            current.add(op_type_id)
        return qualifications

    def eligible_links(self, rows: List[Dict[str, Any]], machines: List[Any], active_operator_ids: Set[str],
                       operations: Sequence[Any]) -> List[Dict[str, Any]]:
        qualifications = self.load(sorted(active_operator_ids))
        _require_explicit_auto_work_types(operations, rows, qualifications)
        machine_types = {machine.machine_id: machine.op_type_id for machine in machines}
        result = []
        for row in rows:
            oid, mid = row["operator_id"], row["machine_id"]
            if oid not in qualifications or mid not in machine_types:
                continue
            skills = qualifications[oid]
            if skills is None or machine_types[mid] in skills:
                result.append(row)
        return result

    def require(self, *, operator_id: str, op_type_id: Optional[str], machine_id: Optional[str],
                qualifications: Optional[Dict[str, Optional[Set[str]]]] = None) -> None:
        oid = _identifier(operator_id)
        require_machine_authorization(self.authorizations, oid, machine_id)
        facts = self.load([oid]) if qualifications is None else qualifications
        skills = facts[oid]
        if skills is not None and op_type_id not in skills:
            raise OperatorQualificationError(
                f"人员“{oid}”未登记自制工种“{op_type_id or '未填写'}”的资格，不能分配；请核对技能登记。",
                field="operator_qualification",
                details={"reason": "operator_skill_not_qualified", "operator_id": oid, "op_type_id": op_type_id},
            )


def validate_fixed_operator_qualifications(conn, operations: List[Any], logger=None) -> None:
    selected = [op for op in operations if str(getattr(op, "source", "") or "").strip().lower() == "internal"
                and getattr(op, "operator_id", None)]
    if not selected:
        return
    service = OperatorQualificationService(conn, logger=logger)
    facts = service.load([op.operator_id for op in selected])
    for op in selected:
        service.require(operator_id=op.operator_id, op_type_id=getattr(op, "op_type_id", None),
                        machine_id=getattr(op, "machine_id", None), qualifications=facts)
