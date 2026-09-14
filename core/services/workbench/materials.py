"""Private domain adapter; public queries and command orchestration live elsewhere."""

from __future__ import annotations

import sqlite3
from dataclasses import asdict
from typing import Any, Dict, Optional, Tuple

from core.errors import AppError, ErrorCode
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.models.workbench_material import normalize_material_input
from core.services.material.material_service import MaterialService
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_material_query_repo import WorkbenchMaterialQueryRepository


class WorkbenchMaterialService:
    def __init__(self, conn, logger=None):
        self.conn = conn
        self._materials = MaterialService(conn, logger=logger)
        self._identities = WorkbenchIdentityRepository(conn, logger=logger)
        self._query = WorkbenchMaterialQueryRepository(conn, logger=logger)

    @staticmethod
    def normalize_input(action: str, payload: Any) -> Dict[str, Any]:
        return normalize_material_input(action, payload)

    def _current_material(self, identity: Optional[WorkbenchEntityIdentity]) -> Tuple[WorkbenchEntityIdentity, Dict[str, Any]]:
        if not isinstance(identity, WorkbenchEntityIdentity) or identity.kind != "material":
            raise WorkbenchCommandRejected("invalid_input", "要先选中一条已核对过的物料。", 400)
        if not identity.active:
            raise WorkbenchCommandRejected("entity_not_found", "这条物料记录已失效，请刷新后重新选择。", 404)
        current = self._identities.get(identity.ref)
        if current is None or not current.active or current.kind != "material":
            raise WorkbenchCommandRejected("entity_not_found", "这条物料记录已失效，请刷新后重新选择。", 404)
        if current != identity:
            raise WorkbenchCommandRejected("stale_write", "物料已变化，请刷新后重新核对。")
        material = self._query.get_by_ref(current.ref)
        if material is None:
            raise WorkbenchCommandRejected("entity_not_found", "该物料已不存在，请刷新。", 404)
        if (material["material_id"], material["ref"], material["revision"]) != (
                current.entity_key, current.ref, current.revision):
            raise WorkbenchCommandRejected("stale_write", "物料和选中的记录对不上，请刷新后重新核对。")
        return current, material

    def snapshot(self, identity: WorkbenchEntityIdentity) -> Dict[str, Any]:
        """Internal full model state for a guard, not a public DTO or a ref repair."""
        current, material = self._current_material(identity)
        return {"identity": asdict(current), "material": material}

    def apply(self, action: str, normalized_input: Dict[str, Any],
              identity: Optional[WorkbenchEntityIdentity] = None) -> WorkbenchCommandOutcome:
        """Use the outer WorkbenchCommandService transaction and its checked identity.

        The outcome is provisional until that owner saves the receipt and commits.
        No token, revision or mutable snapshot belongs in the immutable receipt.
        """
        if not self.conn.in_transaction:
            raise RuntimeError("物料操作必须在外层工作台命令事务中执行。")
        payload = self.normalize_input(action, normalized_input)
        if action == "create":
            if identity is not None:
                raise WorkbenchCommandRejected("invalid_input", "新增物料时不能指定一条已有记录。", 400)
            created = self._materials.create(payload["business_code"], payload["label"], **payload["fields"])
            current = self._identities.find_active("material", created.material_id)
            if current is None:
                raise RuntimeError("新增物料缺少永久引用，不能确认保存。")
        else:
            current, material = self._current_material(identity)
            # Legacy keys must not be redirected by MaterialService's text trimming.
            if current.entity_key != current.entity_key.strip():
                raise WorkbenchCommandRejected("constraint_conflict", "这个物料编号首尾有空格，现在改不了。请先核对原记录。")
            if action == "delete":
                self._delete(current.entity_key)
            elif not self._update(material, payload):
                return self._outcome("unchanged", current)
        return self._outcome("committed", current)

    def _update(self, material: Dict[str, Any], payload: Dict[str, Any]) -> bool:
        changes = dict(payload["fields"])
        if "label" in payload:
            changes["name"] = payload["label"]
        changes = {key: value for key, value in changes.items() if material[key] != value}
        if not changes:
            return False
        # MaterialService treats None as omission; only clearable fields can reach None here.
        self._materials.update(material["material_id"], **{
            key: "" if value is None else value for key, value in changes.items()
        })
        return True

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
