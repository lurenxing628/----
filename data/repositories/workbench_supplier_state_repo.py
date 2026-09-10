"""Raw supplier state and explicit relationships; queries never repair metadata."""

from __future__ import annotations

from .base_repo import BaseRepository


class WorkbenchSupplierStateRepository(BaseRepository):
    def get_by_ref(self, ref):
        supplier = self.fetchone("""SELECT s.*, r.ref, r.revision FROM Suppliers AS s
            JOIN WorkbenchEntityRefs AS r ON r.kind = 'supplier' AND r.active = 1
                AND r.entity_key = s.supplier_id WHERE r.ref = ?""", (ref,))
        if supplier is None:
            return None
        code = supplier["supplier_id"]
        supplier["profile"] = self.get_profile(code)
        supplier["op_types"] = self.fetchall("""WITH bindings AS (
                SELECT op_type_id, 1 AS legacy, 0 AS explicit FROM Suppliers
                    WHERE supplier_id = ? AND op_type_id IS NOT NULL AND op_type_id <> ''
                UNION ALL SELECT op_type_id, 0, 1 FROM WorkbenchSupplierOpTypes WHERE supplier_id = ?
            ) SELECT b.op_type_id, MAX(b.legacy) AS legacy, MAX(b.explicit) AS explicit,
                ot.name, ot.category, ot.default_hours, ot.remark, ot.created_at,
                r.ref, r.revision
            FROM bindings AS b LEFT JOIN OpTypes AS ot ON ot.op_type_id = b.op_type_id
            LEFT JOIN WorkbenchEntityRefs AS r ON r.kind = 'op_type' AND r.active = 1
                AND r.entity_key = ot.op_type_id
            GROUP BY b.op_type_id ORDER BY b.op_type_id""", (code, code))
        supplier["references"] = {
            "part_operations": self.fetchall("SELECT * FROM PartOperations WHERE supplier_id = ? ORDER BY id", (code,)),
            "batch_operations": self.fetchall("SELECT * FROM BatchOperations WHERE supplier_id = ? ORDER BY id", (code,)),
            "external_groups": self.fetchall("SELECT * FROM ExternalGroups WHERE supplier_id = ? ORDER BY group_id", (code,)),
        }
        return supplier

    def get_op_type_by_ref(self, ref):
        return self.fetchone("""SELECT ot.*, r.ref, r.revision FROM OpTypes AS ot
            JOIN WorkbenchEntityRefs AS r ON r.kind = 'op_type' AND r.active = 1
                AND r.entity_key = ot.op_type_id WHERE r.ref = ?""", (ref,))

    def get_profile(self, code):
        return self.fetchone("SELECT * FROM WorkbenchSupplierProfiles WHERE supplier_id = ?", (code,))

    def set_reason(self, code, reason):
        current = self.get_profile(code)
        if current is None:
            if reason is None:
                return False
            self.execute("INSERT INTO WorkbenchSupplierProfiles(supplier_id, inactive_reason) VALUES (?, ?)", (code, reason))
        elif current["inactive_reason"] != reason:
            self.execute("UPDATE WorkbenchSupplierProfiles SET inactive_reason = ? WHERE supplier_id = ?", (reason, code))
        else:
            return False
        return True

    def replace_op_types(self, code, existing, desired):
        removed, added = set(existing) - set(desired), set(desired) - set(existing)
        for op_type_id in sorted(removed):
            self.execute("DELETE FROM WorkbenchSupplierOpTypes WHERE supplier_id = ? AND op_type_id = ?", (code, op_type_id))
        for op_type_id in sorted(added):
            self.execute("INSERT INTO WorkbenchSupplierOpTypes(supplier_id, op_type_id) VALUES (?, ?)", (code, op_type_id))
        return bool(removed or added)
