"""Supplier changes share captured resource facts and the command transaction."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, Optional

from core.errors import AppError, ErrorCode
from core.models.supplier import Supplier
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.models.workbench_supplier import normalize_supplier_input
from data.repositories.supplier_repo import SupplierRepository
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_supplier_state_repo import WorkbenchSupplierStateRepository

from .state_projection import supplier_write_state
from .states import ResourceChange


class WorkbenchSupplierService:
    def __init__(self, conn, logger=None):
        self.conn = conn
        self._suppliers = SupplierRepository(conn, logger=logger)
        self._identities = WorkbenchIdentityRepository(conn, logger=logger)
        self._query = WorkbenchSupplierStateRepository(conn, logger=logger)

    @staticmethod
    def normalize_input(action: str, payload: Any) -> Dict[str, Any]:
        return normalize_supplier_input(action, payload)

    def snapshot(self, identity: WorkbenchEntityIdentity) -> Dict[str, Any]:
        if not isinstance(identity, WorkbenchEntityIdentity) or identity.kind != "supplier":
            raise WorkbenchCommandRejected("invalid_input", "请回到供应商列表重新选择。", 400)
        current = self._identities.get(identity.ref)
        if not identity.active or current is None or not current.active or current.kind != "supplier":
            raise WorkbenchCommandRejected("entity_not_found", "这条供应商记录已失效，请刷新后重新选择。", 404)
        if current != identity:
            raise WorkbenchCommandRejected("stale_write", "供应商资料已更新，请刷新后重新核对。")
        return self._snapshot_from_current(current)

    def _snapshot_from_current(self, identity):
        supplier = self._query.get_by_ref(identity.ref)
        if supplier is None:
            raise WorkbenchCommandRejected("entity_not_found", "供应商已不存在，请刷新。", 404)
        if (supplier["supplier_id"], supplier["ref"], supplier["revision"]) != (identity.entity_key, identity.ref, identity.revision):
            raise WorkbenchCommandRejected("stale_write", "供应商资料已更新，请刷新后重新核对。")
        return supplier_write_state(identity, supplier)

    def apply(self, action: str, payload: Dict[str, Any], identity: Optional[WorkbenchEntityIdentity] = None):
        from .queries import WorkbenchResourceQueryService

        payload = self.normalize_input(action, payload)
        preparation = WorkbenchResourceQueryService(self.conn, "supplier").preparation_for(
            action, payload, ref=getattr(identity, "ref", None))
        if action == "create" and identity is not None:
            raise WorkbenchCommandRejected("invalid_input", "新增资源时请使用新增入口。", 400)
        checked = None if action == "create" else preparation.state("supplier",
            preparation.current("supplier", identity).entity_key)
        return self.apply_prepared(self.prepare(action, payload, checked, preparation))

    def prepare(self, action, payload, checked, preparation):
        identity = None if action == "create" else preparation.identity("supplier", checked["identity"]["ref"])
        code = payload["business_code"] if identity is None else identity.entity_key
        if not code or code != code.strip():
            raise WorkbenchCommandRejected("constraint_conflict", "供应商编号含首尾空白，请先修正编号。")
        supplier = checked["supplier"] if checked is not None else {}
        if action == "delete":
            if any(supplier["references"].values()):
                raise WorkbenchCommandRejected("constraint_conflict", "这家供应商还被工序或外协组使用，请先解除这些关联。")
            return ResourceChange(action, code, identity, {}, {})
        if action == "create" and preparation.raw("supplier", code) is not None:
            raise WorkbenchCommandRejected("constraint_conflict", "供应商编号已经存在，请改用其他编号。")
        selected = ({preparation.selected("op_type", ref, category="external") for ref in payload["relationships"]["op_type_refs"]}
                    if "relationships" in payload else None)
        fields = dict(payload["fields"])
        if "label" in payload:
            fields["name"] = payload["label"]
        related = {}
        profile = supplier.get("profile")
        previous_reason = profile["inactive_reason"] if profile else None
        if action == "create" or "status" in fields:
            status, reason = self._stored_status(fields.pop("status", "active"))
            fields["status"] = status
            effective_reason = None if status != supplier.get("status") else previous_reason
            if reason != effective_reason:
                related["reason"] = reason, profile is not None
        existing = {row["op_type_id"] for row in supplier.get("op_types", []) if row["explicit"]}
        legacy = supplier.get("op_type_id")
        desired = existing if selected is None else selected - ({legacy} if legacy not in existing else set())
        if existing != desired:
            related["op_types"] = existing, desired
        if selected is not None and legacy is not None and legacy not in selected:
            fields["op_type_id"] = None
        changes = fields if action == "create" else {key: value for key, value in fields.items() if supplier[key] != value}
        return ResourceChange(action, code, identity, changes, related)

    @staticmethod
    def _stored_status(status):
        return ("active", None) if status == "active" else ("inactive", "pending_review" if status == "pending_review" else "disabled")

    def apply_prepared(self, change):
        if not self.conn.in_transaction:
            raise RuntimeError("供应商操作必须在外层工作台命令事务中执行。")
        code, identity = change.business_code, change.identity
        if change.action == "delete":
            self._delete(code)
        elif change.action == "create":
            self._suppliers.create(Supplier(supplier_id=code, **change.fields))
            identity = self._identities.find_active("supplier", code)
            if identity is None:
                raise RuntimeError("新增供应商缺少永久引用。")
        elif change.fields:
            self._suppliers.update(code, change.fields)
        if "op_types" in change.related:
            self._query.replace_op_types(code, *change.related["op_types"])
        if "reason" in change.related:
            reason, exists = change.related["reason"]
            self._query.write_reason(code, reason, exists=exists)
        changed = change.action != "update" or bool(change.fields or change.related)
        return WorkbenchCommandOutcome("committed" if changed else "unchanged", {"entity_ref": identity.ref, "business_code": code})

    def _delete(self, code):
        try:
            self._suppliers.delete(code)
        except AppError as exc:
            if (exc.code == ErrorCode.DB_INTEGRITY_ERROR and isinstance(exc.cause, sqlite3.IntegrityError)
                    and str(exc.cause) == "FOREIGN KEY constraint failed"):
                raise WorkbenchCommandRejected("constraint_conflict", "这家供应商还被其他资料使用，请先解除这些关联。") from exc
            raise
