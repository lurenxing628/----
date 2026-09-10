"""Read-only complete selection and dependency evidence for resource actions."""

from datetime import date

from core.models.workbench_command import canonical_json

from .base_repo import BaseRepository
from .workbench_resource_state_repo import RESOURCE_KEYS

TABLES = dict(RESOURCE_KEYS, supplier=("Suppliers", "supplier_id"))
DEPENDENCIES = {
    "op_type": (("Machines", "op_type_id"), ("Suppliers", "op_type_id"), ("OperatorSkill", "op_type_id"),
                ("WorkbenchSupplierOpTypes", "op_type_id"), ("PartOperations", "op_type_id"), ("BatchOperations", "op_type_id")),
    "machine": (("BatchOperations", "machine_id"), ("Schedule", "machine_id"), ("OperatorMachine", "machine_id"),
                ("MachineDowntimes", "machine_id"), ("OperationExecutionEvents", "actual_machine_id"),
                ("OperationExecutionEvents", "affected_machine_id")),
    "operator": (("BatchOperations", "operator_id"), ("Schedule", "operator_id"), ("OperatorMachine", "operator_id"),
                 ("OperatorCalendar", "operator_id"), ("OperationExecutionEvents", "actual_operator_id"),
                 ("OperationExecutionEvents", "affected_operator_id")),
    "supplier": (("PartOperations", "supplier_id"), ("BatchOperations", "supplier_id"), ("ExternalGroups", "supplier_id")),
}


class WorkbenchResourceFileRepository(BaseRepository):
    def raw(self, kind, code):
        table, key = TABLES[kind]
        return self.fetchone(f'SELECT * FROM "{table}" WHERE "{key}"=?', (code,))

    def identity_history(self, kind, code):
        return self.fetchall("SELECT ref,revision,active FROM WorkbenchEntityRefs WHERE kind=? AND entity_key=? ORDER BY ref", (kind, code))

    def references(self, kind, code):
        return {table + "." + key: self._references(table, key, code)
                for table, key in DEPENDENCIES[kind]}

    def _references(self, table, key, code):
        rows = self.fetchall(f"SELECT * FROM {table} WHERE {key}=?", (code,))
        # Production connections decode DATE. Keep every column; never truncate datetime.
        values = [{name: value.isoformat() if type(value) is date else value for name, value in row.items()} for row in rows]
        return sorted(values, key=canonical_json)

    def authorizations(self, kind, code):
        key = "machine_id" if kind == "machine" else "operator_id"
        return self.fetchall(f"SELECT * FROM OperatorMachine WHERE {key}=? ORDER BY operator_id,machine_id", (code,))

    def name_owner(self, kind, name):
        table, key = TABLES[kind]
        return self.fetchone(f"SELECT {key} AS business_code FROM {table} WHERE name=?", (name,))
