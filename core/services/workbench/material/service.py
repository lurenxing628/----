"""Private domain adapter; public queries and command orchestration live elsewhere."""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from core.errors import AppError, BusinessError, ErrorCode
from core.models import Material
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


class WorkbenchMaterialService:
    def __init__(self, conn, logger=None):
        self.conn = conn
        self._materials = MaterialRepository(conn, logger=logger)
        self._identities = WorkbenchIdentityRepository(conn, logger=logger)
        self._query = WorkbenchMaterialQueryRepository(conn, logger=logger)

    @staticmethod
    def normalize_input(action: str, payload: Any) -> Dict[str, Any]:
        return normalize_material_input(action, payload)

    @staticmethod
    def _snapshot_from_current(identity, material):
        """Project an identity and full material row already read in this transaction."""
        if (material["material_id"], material["ref"], material["revision"]) != (
                identity.entity_key, identity.ref, identity.revision):
            raise WorkbenchCommandRejected("stale_write", "物料和选中的记录对不上，请刷新后重新核对。")
        return {"identity": asdict(identity), "material": material}

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
        current = WorkbenchEntityIdentity(**checked["identity"])
        if current.entity_key != current.entity_key.strip():
            raise WorkbenchCommandRejected("constraint_conflict", "这个物料编号首尾有空格，现在改不了。请先核对原记录。")
        if action == "delete":
            return PreparedMaterialChange(action, current, current.entity_key, {})
        changes = dict(payload.get("fields", {}))
        if "label" in payload:
            changes["name"] = payload["label"]
        changes = {key: value for key, value in changes.items() if checked["material"][key] != value}
        return PreparedMaterialChange(action, current, current.entity_key, changes)

    def apply_prepared(self, prepared):
        if not self.conn.in_transaction:
            raise RuntimeError("物料操作必须在外层工作台命令事务中执行。")
        current = prepared.identity
        if prepared.action == "create":
            created = self._materials.create(Material(**prepared.values))
            current = self._identities.find_active("material", created.material_id)
            if current is None:
                raise RuntimeError("新增物料缺少永久引用，不能确认保存。")
        else:
            if prepared.action == "delete":
                self._delete(prepared.business_code)
            elif prepared.values:
                self._materials.update(prepared.business_code, prepared.values)
            else:
                return self._outcome("unchanged", current)
        return self._outcome("committed", current)

    def _delete(self, material_id: str) -> None:
        try:
            self._materials.delete(material_id)
        except AppError as exc:
            # Translate only the domain repository's actual foreign-key rejection.
            if (exc.code == ErrorCode.DB_INTEGRITY_ERROR
                    and isinstance(exc.cause, sqlite3.IntegrityError)
                    and str(exc.cause) == "FOREIGN KEY constraint failed"):
                raise WorkbenchCommandRejected("constraint_conflict", "这个物料还被别的数据用着，不能删除。") from exc
            raise

    @staticmethod
    def _outcome(result: str, identity: WorkbenchEntityIdentity) -> WorkbenchCommandOutcome:
        return WorkbenchCommandOutcome(result, {"entity_ref": identity.ref, "business_code": identity.entity_key})
