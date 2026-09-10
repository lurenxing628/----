"""Raw resource state and explicit relations; no schema or default writes on reads."""

from __future__ import annotations

from .base_repo import BaseRepository

RESOURCE_KEYS = {"op_type": ("OpTypes", "op_type_id"), "machine": ("Machines", "machine_id"),
                 "operator": ("Operators", "operator_id"), "machine_group": ("WorkbenchMachineGroups", "group_id"),
                 "shift_profile": ("WorkbenchShiftProfiles", "profile_id")}


class WorkbenchResourceStateRepository(BaseRepository):
    def get_raw(self, kind, code):
        table, key = RESOURCE_KEYS[kind]
        return self.fetchone(f'SELECT * FROM "{table}" WHERE "{key}" = ?', (code,))

    def get_profile(self, kind, code):
        table, key = {"machine": ("WorkbenchMachineGroupMembers", "machine_id"),
                      "operator": ("WorkbenchOperatorProfiles", "operator_id"),
                      "op_type": ("WorkbenchOpTypePolicies", "op_type_id")}[kind]
        return self.fetchone(f'SELECT * FROM "{table}" WHERE "{key}" = ?', (code,))

    def pattern(self, profile_id):
        return self.fetchall("SELECT * FROM WorkbenchShiftPatternDays WHERE profile_id=? ORDER BY day_offset", (profile_id,))

    def skills(self, operator_id):
        return self.fetchall("SELECT * FROM OperatorSkill WHERE operator_id=? ORDER BY op_type_id", (operator_id,))

    def authorizations(self, operator_id):
        return self.fetchall("SELECT * FROM OperatorMachine WHERE operator_id=? ORDER BY machine_id", (operator_id,))

    def op_type_dependencies(self, code):
        tables = {"machines": "Machines", "legacy_suppliers": "Suppliers", "supplier_capabilities": "WorkbenchSupplierOpTypes",
                  "skills": "OperatorSkill", "part_operations": "PartOperations", "batch_operations": "BatchOperations"}
        return {name: int(self.fetchvalue(f"SELECT COUNT(*) FROM {table} WHERE op_type_id=?", (code,), default=0))
                for name, table in tables.items()}

    def assigned_dependencies(self, kind, code):
        column = {"machine": "machine_id", "operator": "operator_id"}[kind]
        return {name: int(self.fetchvalue(f"SELECT COUNT(*) FROM {table} WHERE {column}=?", (code,), default=0))
                for name, table in (("batch_operations", "BatchOperations"), ("schedule", "Schedule"))}

    def catalog_by_name(self, kind, name):
        if kind not in ("machine_group", "shift_profile"):
            raise ValueError("Unsupported resource catalog")
        table, key = RESOURCE_KEYS[kind]
        return self.fetchone(f"SELECT {key} AS business_code FROM {table} WHERE name=?", (name,))

    def set_machine_group(self, machine_id, group_id):
        if group_id is None:
            self.execute("DELETE FROM WorkbenchMachineGroupMembers WHERE machine_id=?", (machine_id,))
        else:
            self.execute("""INSERT INTO WorkbenchMachineGroupMembers(machine_id,group_id) VALUES (?,?)
                ON CONFLICT(machine_id) DO UPDATE SET group_id=excluded.group_id""", (machine_id, group_id))

    def set_operator_profile(self, operator_id, *, shift_profile_id, skills_declared, inactive_reason):
        self.execute("""INSERT INTO WorkbenchOperatorProfiles(operator_id,shift_profile_id,skills_declared,inactive_reason)
            VALUES (?,?,?,?) ON CONFLICT(operator_id) DO UPDATE SET shift_profile_id=excluded.shift_profile_id,
            skills_declared=excluded.skills_declared,inactive_reason=excluded.inactive_reason""",
                     (operator_id, shift_profile_id, skills_declared, inactive_reason))

    def set_skills(self, operator_id, codes):
        existing = {row["op_type_id"] for row in self.skills(operator_id)}
        for code in sorted(existing - set(codes)):
            self.execute("DELETE FROM OperatorSkill WHERE operator_id=? AND op_type_id=?", (operator_id, code))
        for code in sorted(set(codes) - existing):
            self.execute("INSERT INTO OperatorSkill(operator_id,op_type_id) VALUES (?,?)", (operator_id, code))

    def set_op_type_policy(self, code, mode):
        if mode is None:
            self.execute("DELETE FROM WorkbenchOpTypePolicies WHERE op_type_id=?", (code,))
        else:
            self.execute("""INSERT INTO WorkbenchOpTypePolicies(op_type_id,default_merge_mode) VALUES (?,?)
                ON CONFLICT(op_type_id) DO UPDATE SET default_merge_mode=excluded.default_merge_mode""", (code, mode))

    def group_members(self, group_id):
        return self.fetchall("SELECT machine_id FROM WorkbenchMachineGroupMembers WHERE group_id=? ORDER BY machine_id", (group_id,))

    def shift_members(self, profile_id):
        return self.fetchall("SELECT operator_id FROM WorkbenchOperatorProfiles WHERE shift_profile_id=? ORDER BY operator_id", (profile_id,))

    def insert_catalog(self, kind, code, fields):
        table, key = RESOURCE_KEYS[kind]
        allowed = {"name", "status", "remark"} | ({"anchor_date", "cycle_days"} if kind == "shift_profile" else set())
        if kind not in ("machine_group", "shift_profile") or set(fields) - allowed:
            raise ValueError("Unsupported resource catalog fields")
        columns = [key] + list(fields)
        marks = ",".join("?" for _ in columns)
        self.execute(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({marks})", [code] + list(fields.values()))

    def update_catalog(self, kind, code, fields):
        table, key = RESOURCE_KEYS[kind]
        allowed = {"name", "status", "remark"} | ({"anchor_date", "cycle_days"} if kind == "shift_profile" else set())
        if kind not in ("machine_group", "shift_profile") or set(fields) - allowed:
            raise ValueError("Unsupported resource catalog fields")
        if fields:
            self.execute(f"UPDATE {table} SET {','.join(name+'=?' for name in fields)} WHERE {key}=?", list(fields.values()) + [code])

    def delete_catalog(self, kind, code):
        if kind not in ("machine_group", "shift_profile"):
            raise ValueError("Unsupported resource catalog")
        table, key = RESOURCE_KEYS[kind]
        self.execute(f"DELETE FROM {table} WHERE {key}=?", (code,))

    def set_pattern(self, profile_id, days):
        self.execute("DELETE FROM WorkbenchShiftPatternDays WHERE profile_id=?", (profile_id,))
        for day in days:
            self.execute("""INSERT INTO WorkbenchShiftPatternDays(profile_id,day_offset,is_rest,shift_start,shift_end)
                VALUES (?,?,?,?,?)""", (profile_id, day["day_offset"], int(day["is_rest"]), day["shift_start"], day["shift_end"]))
