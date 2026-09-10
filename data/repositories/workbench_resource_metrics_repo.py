"""Read-only resource facts, bounded page states and shared aggregate scans."""

from .base_repo import BaseRepository


class WorkbenchResourceMetricsRepository(BaseRepository):
    def facts(self, names):
        sources = {
            "op_type": ("OpTypes", "op_type_id"),
            "machine": ("Machines", "machine_id"),
            "operator": ("Operators", "operator_id"),
            "supplier": ("Suppliers", "supplier_id"),
            "machine_group": ("WorkbenchMachineGroups", "group_id"),
            "shift_profile": ("WorkbenchShiftProfiles", "profile_id"),
            "operator_profiles": ("WorkbenchOperatorProfiles", "operator_id"),
            "supplier_profiles": ("WorkbenchSupplierProfiles", "supplier_id"),
            "groups": ("WorkbenchMachineGroupMembers", "machine_id"),
            "policies": ("WorkbenchOpTypePolicies", "op_type_id"),
            "skills": ("OperatorSkill", "operator_id,op_type_id"),
            "authorizations": ("OperatorMachine", "operator_id,machine_id"),
            "capabilities": ("WorkbenchSupplierOpTypes", "supplier_id,op_type_id"),
        }
        return {name: self.fetchall(f"SELECT * FROM {sources[name][0]} ORDER BY {sources[name][1]}")
                for name in names}

    def op_type_dependencies(self, codes):
        if not codes:
            return {}
        if len(codes) > 200:
            raise ValueError("Resource projection pages are limited to 200 work types")
        tables = {"machines": "Machines", "legacy_suppliers": "Suppliers",
                  "supplier_capabilities": "WorkbenchSupplierOpTypes", "skills": "OperatorSkill",
                  "part_operations": "PartOperations", "batch_operations": "BatchOperations"}
        result = {code: dict.fromkeys(tables, 0) for code in codes}
        marks = ",".join("?" for _ in codes)
        for name, table in tables.items():
            rows = self.fetchall(f"SELECT op_type_id,COUNT(*) AS amount FROM {table} "
                                 f"WHERE op_type_id IN ({marks}) GROUP BY op_type_id", codes)
            for row in rows:
                result[row["op_type_id"]][name] = row["amount"]
        return result
