"""Private D06 supplier adapter using the outer workbench command transaction."""

from __future__ import annotations

import sqlite3
from dataclasses import asdict
from typing import Any, Dict, Optional

from core.errors import AppError, ErrorCode, ValidationError
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.models.workbench_supplier import normalize_supplier_input, supplier_state
from core.services.process.supplier_service import SupplierService
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_supplier_state_repo import WorkbenchSupplierStateRepository


class WorkbenchSupplierService:
    def __init__(self, conn, logger=None):
        self.conn = conn
        self._suppliers = SupplierService(conn, logger=logger)
        self._identities = WorkbenchIdentityRepository(conn, logger=logger)
        self._query = WorkbenchSupplierStateRepository(conn, logger=logger)

    @staticmethod
    def normalize_input(action: str, payload: Any) -> Dict[str, Any]:
        return normalize_supplier_input(action, payload)

    def _current_supplier(self, identity):
        if not isinstance(identity, WorkbenchEntityIdentity) or identity.kind != "supplier":
            raise WorkbenchCommandRejected("invalid_input", "需要已核对的供应商引用。", 400)
        current = self._identities.get(identity.ref)
        if not identity.active or current is None or not current.active or current.kind != "supplier":
            raise WorkbenchCommandRejected("entity_not_found", "该供应商引用已失效，请刷新。", 404)
        if current != identity:
            raise WorkbenchCommandRejected("stale_write", "供应商已变化，请刷新后重新核对。")
        supplier = self._query.get_by_ref(current.ref)
        if supplier is None:
            raise WorkbenchCommandRejected("entity_not_found", "供应商已不存在，请刷新。", 404)
        if (supplier["supplier_id"], supplier["ref"], supplier["revision"]) != (current.entity_key, current.ref, current.revision):
            raise WorkbenchCommandRejected("stale_write", "供应商与引用不一致，请重新核对。")
        return current, supplier

    def snapshot(self, identity: WorkbenchEntityIdentity) -> Dict[str, Any]:
        current, supplier = self._current_supplier(identity)
        return {"identity": asdict(current), "supplier": supplier,
                "state": supplier_state(supplier["status"], supplier["profile"])}

    def _resolve_op_types(self, payload):
        if "relationships" not in payload:
            return None
        keys = set()
        for ref in payload["relationships"]["op_type_refs"]:
            op_type = self._query.get_op_type_by_ref(ref)
            if op_type is None:
                raise WorkbenchCommandRejected("entity_not_found", "工种引用不存在或已失效，请刷新。", 404)
            if op_type["category"] != "external":
                raise ValidationError("供应商只能绑定外协工种。", field="relationships.op_type_refs")
            keys.add(op_type["op_type_id"])
        return keys

    def apply(self, action: str, normalized_input: Dict[str, Any],
              identity: Optional[WorkbenchEntityIdentity] = None) -> WorkbenchCommandOutcome:
        if not self.conn.in_transaction:
            raise RuntimeError("供应商操作必须在外层工作台命令事务中执行。")
        payload = self.normalize_input(action, normalized_input)
        if action == "create":
            if identity is not None:
                raise WorkbenchCommandRejected("invalid_input", "新增供应商不能指定已有对象。", 400)
            selected = self._resolve_op_types(payload)
            fields = dict(payload["fields"])
            status, reason = self._stored_status(fields.pop("status", "active"))
            created = self._suppliers.create(payload["business_code"], payload["label"], status=status, **fields)
            current = self._identities.find_active("supplier", created.supplier_id)
            if current is None:
                raise RuntimeError("新增供应商缺少永久引用，不能确认保存。")
            self._query.replace_op_types(current.entity_key, (), selected or ())
            self._query.set_reason(current.entity_key, reason)
        else:
            current, supplier = self._current_supplier(identity)
            if not current.entity_key or current.entity_key != current.entity_key.strip():
                raise WorkbenchCommandRejected("constraint_conflict", "供应商编号含首尾空白，无法按当前领域规则修改。")
            if action == "delete":
                self._delete(current.entity_key)
            elif not self._update(supplier, payload, self._resolve_op_types(payload)):
                return self._outcome("unchanged", current)
        return self._outcome("committed", current)

    @staticmethod
    def _stored_status(status):
        if status == "active":
            return "active", None
        return "inactive", "pending_review" if status == "pending_review" else "disabled"

    def _update(self, supplier, payload, selected):
        changes = dict(payload["fields"])
        if "label" in payload:
            changes["name"] = payload["label"]
        if "status" in changes:
            changes["status"], reason = self._stored_status(changes["status"])
        changes = {key: value for key, value in changes.items() if supplier[key] != value}
        existing, desired, relation_fields = self._relation_changes(supplier, selected)
        changes.update(relation_fields)
        if changes:
            self._suppliers.update(supplier["supplier_id"], **{
                key: "" if value is None else value for key, value in changes.items()
            })
        relations_changed = self._query.replace_op_types(supplier["supplier_id"], existing, desired)
        reason_changed = False
        if "status" in payload["fields"]:
            # The domain status update trigger clears old reasons before this write.
            reason_changed = self._query.set_reason(supplier["supplier_id"], reason)
        return bool(changes or relations_changed or reason_changed)

    @staticmethod
    def _relation_changes(supplier, selected):
        existing = {row["op_type_id"] for row in supplier["op_types"] if row["explicit"]}
        if selected is None:
            return existing, existing, {}
        legacy = supplier["op_type_id"]
        # Preserve legacy provenance on an unchanged effective selection.
        desired = selected - ({legacy} if legacy not in existing else set())
        fields = {"op_type_value": ""} if legacy is not None and legacy not in selected else {}
        return existing, desired, fields

    def _delete(self, code):
        try:
            self._suppliers.delete(code)
        except AppError as exc:
            if (exc.code == ErrorCode.DB_INTEGRITY_ERROR
                    and isinstance(exc.cause, sqlite3.IntegrityError)
                    and str(exc.cause) == "FOREIGN KEY constraint failed"):
                raise WorkbenchCommandRejected("constraint_conflict", "供应商仍被其他数据引用，不能删除。") from exc
            raise

    @staticmethod
    def _outcome(result, identity):
        return WorkbenchCommandOutcome(result, {"entity_ref": identity.ref, "business_code": identity.entity_key})
