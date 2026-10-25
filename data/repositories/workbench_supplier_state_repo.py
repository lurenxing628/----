"""Raw supplier state and explicit relationships; queries never repair metadata."""

from __future__ import annotations

from .base_repo import BaseRepository


class WorkbenchSupplierStateRepository(BaseRepository):
    def write_reason(self, code, reason, *, exists):
        if not exists:
            self.execute("INSERT INTO WorkbenchSupplierProfiles(supplier_id, inactive_reason) VALUES (?, ?)", (code, reason))
        else:
            self.execute("UPDATE WorkbenchSupplierProfiles SET inactive_reason = ? WHERE supplier_id = ?", (reason, code))

    def replace_op_types(self, code, existing, desired):
        removed = [(code, op_type_id) for op_type_id in sorted(set(existing) - set(desired))]
        if removed:
            self.executemany("DELETE FROM WorkbenchSupplierOpTypes WHERE supplier_id = ? AND op_type_id = ?", removed)
        added = [(code, op_type_id) for op_type_id in sorted(set(desired) - set(existing))]
        if added:
            self.executemany("INSERT INTO WorkbenchSupplierOpTypes(supplier_id, op_type_id) VALUES (?, ?)", added)
