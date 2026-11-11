"""Private domain adapter; public queries and command orchestration live elsewhere."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from core.errors import BusinessError, ErrorCode
from core.models.material import Material
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.models.workbench_material import normalize_material_input
from data.repositories.material_repo import MaterialRepository
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_material_query_repo import WorkbenchMaterialQueryRepository


@dataclass
class PreparedMaterialChange:
    action: str
    identity: Optional[WorkbenchEntityIdentity]
    business_code: str
    values: Dict[str, Any]


def material_action_policy(requirement_count: int) -> Tuple[List[str], Dict[str, bool], List[Dict[str, str]]]:
    referenced = requirement_count > 0
    actions = ["material.update"] + ([] if referenced else ["material.delete"])
    capabilities = {"material.update": True, "material.delete": not referenced}
    blocked_reasons = (
        [
            {
                "action": "material.delete",
                "code": "constraint_conflict",
                "message": "这条物料已经被批次的物料需求用到，不能删除。请先处理相关批次的物料需求，再删除物料。",
            }
        ]
        if referenced
        else []
    )
    return actions, capabilities, blocked_reasons


class WorkbenchMaterialService:
    def __init__(self, conn, logger=None):
        self.conn = conn
        self._materials = MaterialRepository(conn, logger=logger)
        self._identities = WorkbenchIdentityRepository(conn, logger=logger)
        self._query = WorkbenchMaterialQueryRepository(conn, logger=logger)

    @staticmethod
    def normalize_input(action: str, payload: Any) -> Dict[str, Any]:
        return normalize_material_input(action, payload)

    def prepare_checked(self, action, payload, checked):
        """Turn normalized input and this transaction's facts into the actual write."""
        if action == "create":
            code = payload["business_code"]
            material = self._query.get_raw(code) if checked is None else checked["material"]
            if material is not None:
                raise BusinessError(ErrorCode.DUPLICATE_ENTRY, f"物料“{code}”已存在")
            values = {"material_id": code, "name": payload["label"], "spec": None, "unit": None,
                      "stock_qty": 0.0, "status": "active", "remark": None, **payload["fields"]}
            return PreparedMaterialChange(action, None, code, values)
        current = checked["identity"]
        if action == "delete":
            _, capabilities, blocked = material_action_policy(checked["material"]["requirement_count"])
            if not capabilities["material.delete"]:
                raise WorkbenchCommandRejected(blocked[0]["code"], blocked[0]["message"])
            return PreparedMaterialChange(action, current, current.entity_key, {})
        changes = dict(payload["fields"])
        if "label" in payload:
            changes["name"] = payload["label"]
        changes = {key: value for key, value in changes.items() if checked["material"][key] != value}
        return PreparedMaterialChange(action, current, current.entity_key, changes)

    def apply_prepared_many(self, changes):
        if not self.conn.in_transaction:
            raise RuntimeError("物料操作必须在外层工作台命令事务中执行。")
        created_codes = []
        for prepared in changes:
            if prepared.action == "create":
                self._materials.create(Material(**prepared.values))
                created_codes.append(prepared.business_code)
            elif prepared.action == "delete":
                self._materials.delete(prepared.business_code)
            elif prepared.values:
                self._materials.update(prepared.business_code, prepared.values)
        created_identities = self._identities.active_map("material", created_codes) if created_codes else {}
        outcomes = []
        for prepared in changes:
            if prepared.action == "create":
                current = created_identities.get(prepared.business_code)
                if current is None:
                    raise RuntimeError("新增物料缺少永久引用，不能确认保存。")
                outcomes.append(self._outcome("committed", current))
            else:
                result = "committed" if prepared.action == "delete" or prepared.values else "unchanged"
                outcomes.append(self._outcome(result, prepared.identity))
        return outcomes

    def apply_prepared(self, prepared):
        return self.apply_prepared_many([prepared])[0]

    @staticmethod
    def _outcome(result: str, identity) -> WorkbenchCommandOutcome:
        return WorkbenchCommandOutcome(result, {"entity_ref": identity.ref, "business_code": identity.entity_key})
