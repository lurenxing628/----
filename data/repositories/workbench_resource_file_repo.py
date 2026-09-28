"""Read-only complete selection and dependency evidence for resource actions."""

from datetime import date

from core.models.workbench_command import canonical_json

from .base_repo import BaseRepository
from .workbench_resource_dependencies import DEPENDENCIES
from .workbench_resource_state_repo import RESOURCE_KEYS

TABLES = dict(RESOURCE_KEYS, supplier=("Suppliers", "supplier_id"))


class WorkbenchResourceFileRepository(BaseRepository):
    def raw(self, kind, code):
        table, key = TABLES[kind]
        return self.fetchone(f'SELECT * FROM "{table}" WHERE "{key}"=?', (code,))

    def identity_history(self, kind, code):
        return self.fetchall("SELECT ref,revision,active FROM WorkbenchEntityRefs WHERE kind=? AND entity_key=? ORDER BY ref", (kind, code))

    def references(self, kind, code):
        """Referencing rows per fixed (table, column) of the kind; identifiers come only from DEPENDENCIES."""
        result = {}
        for table, key in DEPENDENCIES[kind]:
            rows = self.fetchall(f"SELECT * FROM {table} WHERE {key}=?", (code,))
            # Production connections decode DATE. Keep every column; never truncate datetime.
            values = [{name: value.isoformat() if type(value) is date else value for name, value in row.items()} for row in rows]
            result[table + "." + key] = sorted(values, key=canonical_json)
        return result

    def authorizations(self, kind, code):
        key = "machine_id" if kind == "machine" else "operator_id"
        return self.fetchall(f"SELECT * FROM OperatorMachine WHERE {key}=? ORDER BY operator_id,machine_id", (code,))

    def name_owner(self, kind, name):
        table, key = TABLES[kind]
        return self.fetchone(f"SELECT {key} AS business_code FROM {table} WHERE name=?", (name,))
