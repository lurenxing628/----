"""Personnel qualification shared by planning and editing, without scheduler imports.

Callers bring the facts their own read holds: the authorized operator/machine pairs and the
qualifications ``project_facts`` interprets. Nothing here reads a connection.
"""

from __future__ import annotations

from typing import AbstractSet, Any, Dict, List, Optional, Sequence, Set, Tuple

from core.errors import ValidationError
from core.models.resource_capabilities import supports_source


class OperatorQualificationError(ValidationError):
    """Qualification failures must not fall back to an unfiltered resource pool."""

    details: Dict[str, Any]  # every raise site records the failure ``reason``


def _invalid_facts(message: str) -> OperatorQualificationError:
    return OperatorQualificationError(
        message, field="operator_qualification", details={"reason": "operator_qualification_data_invalid"},
    )


def _identifier(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise _invalid_facts("人员资格资料中的编号无效，请核对原始资料；本次没有生成新排程。")
    return value


def require_machine_authorization(authorized_pairs: AbstractSet[Tuple[str, str]], operator_id: str,
                                  machine_id: Optional[str]) -> None:
    if machine_id and (operator_id, machine_id) not in authorized_pairs:
        raise OperatorQualificationError(
            f"人员“{operator_id}”未被配置为可操作设备“{machine_id}”。"
            "请先在【人员管理】或【设备管理】中维护人机关联后再排产。",
            field="设备/人员",
            details={"reason": "operator_machine_not_authorized", "operator_id": operator_id, "machine_id": machine_id},
        )


def require_explicit_auto_work_types(operations: Sequence[Any], rows: List[Dict[str, Any]],
                                    qualifications: Dict[str, Optional[Set[str]]]) -> None:
    declared_machines = {row["machine_id"] for row in rows
                         if row["operator_id"] in qualifications and qualifications[row["operator_id"]] is not None}
    for op in operations:
        if op.source != "internal" or op.operator_id:
            continue
        if op.machine_id in declared_machines:
            op_type_id = op.op_type_id
            if not op_type_id:
                raise _invalid_facts("固定设备的工序缺少真实工种编号，不能用设备工种猜测人员资格；请补齐工序工种后再自动选人。")
            _identifier(op_type_id)


def require_work_type_qualification(qualifications: Dict[str, Optional[Set[str]]], operator_id: str,
                                    op_type_id: Optional[str]) -> None:
    """``qualifications`` come from ``OperatorQualificationService.project_facts``, which already admitted the id."""
    skills = qualifications[operator_id]
    if skills is not None and op_type_id not in skills:
        raise OperatorQualificationError(
            f"人员“{operator_id}”未登记自制工种“{op_type_id or '未填写'}”的资格，不能分配；请核对技能登记。",
            field="operator_qualification",
            details={"reason": "operator_skill_not_qualified", "operator_id": operator_id, "op_type_id": op_type_id},
        )


class OperatorQualificationService:
    @staticmethod
    def project_facts(operator_ids: Sequence[str], profiles: List[Dict[str, Any]],
                      skills: List[Dict[str, Any]]) -> Dict[str, Optional[Set[str]]]:
        """Interpret supplied qualification facts using the same rules as planning reads."""
        ids = {_identifier(value) for value in operator_ids}
        return OperatorQualificationService._project_validated_facts(ids, profiles, skills)

    @staticmethod
    def _project_validated_facts(ids, profiles, skills):
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
            if not supports_source(row["category"], "internal"):
                raise _invalid_facts(f"人员“{oid}”的技能工种“{op_type_id}”不存在或不是自制工种，请核对资料。")
            current = qualifications[oid]
            if current is None:
                current = qualifications[oid] = set()
            if op_type_id in current:
                raise _invalid_facts(f"人员“{oid}”的技能工种重复，请核对资料。")
            current.add(op_type_id)
        return qualifications

    @staticmethod
    def eligible_links(rows: List[Dict[str, Any]], machine_capabilities: Dict[str, Set[str]], *,
                       qualifications: Dict[str, Optional[Set[str]]]) -> List[Dict[str, Any]]:
        """Links whose machine is in ``machine_capabilities`` and whose operator is qualified for one of its work types."""
        result = []
        for row in rows:
            oid, mid = row["operator_id"], row["machine_id"]
            if oid not in qualifications or mid not in machine_capabilities:
                continue
            skills = qualifications[oid]
            if skills is None or machine_capabilities[mid] & skills:
                result.append(row)
        return result
