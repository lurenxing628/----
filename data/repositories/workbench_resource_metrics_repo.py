"""Read-only resource facts, bounded page states and shared aggregate scans."""

from .base_repo import BaseRepository


class WorkbenchResourceMetricsRepository(BaseRepository):
    def facts(self, names):
        sources = {
            "op_type": ("OpTypes", "op_type_id"),
            "machine": ("Machines", "machine_id"),
            "machine_capabilities": ("MachineOpTypes", "machine_id,op_type_id"),
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
            "shift_pattern": ("WorkbenchShiftPatternDays", "profile_id,day_offset"),
        }
        result = {}
        for name in names:
            result[name] = self.fetchall(f"SELECT * FROM {sources[name][0]} ORDER BY {sources[name][1]}")
        return result
