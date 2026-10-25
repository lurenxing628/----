"""Raw resource state and explicit relations; no schema or default writes on reads."""

from __future__ import annotations

from core.models.calendar_periods import encode_periods

from .base_repo import BaseRepository

RESOURCE_KEYS = {"op_type": ("OpTypes", "op_type_id"), "machine": ("Machines", "machine_id"),
                 "operator": ("Operators", "operator_id"), "machine_group": ("WorkbenchMachineGroups", "group_id"),
                 "shift_profile": ("WorkbenchShiftProfiles", "profile_id")}


class WorkbenchResourceStateRepository(BaseRepository):
    def replace_machine_capabilities(self, code, existing, desired):
        removed = [(code, op_type) for op_type in sorted(set(existing) - set(desired))]
        if removed:
            self.executemany("DELETE FROM MachineOpTypes WHERE machine_id=? AND op_type_id=?", removed)
        added = [(code, op_type) for op_type in sorted(set(desired) - set(existing))]
        if added:
            self.executemany("INSERT INTO MachineOpTypes(machine_id,op_type_id) VALUES (?,?)", added)

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

    def replace_skills(self, operator_id, existing, desired):
        removed = [(operator_id, code) for code in sorted(set(existing) - set(desired))]
        if removed:
            self.executemany("DELETE FROM OperatorSkill WHERE operator_id=? AND op_type_id=?", removed)
        added = [(operator_id, code) for code in sorted(set(desired) - set(existing))]
        if added:
            self.executemany("INSERT INTO OperatorSkill(operator_id,op_type_id) VALUES (?,?)", added)

    def set_op_type_policy(self, code, mode):
        if mode is None:
            self.execute("DELETE FROM WorkbenchOpTypePolicies WHERE op_type_id=?", (code,))
        else:
            self.execute("""INSERT INTO WorkbenchOpTypePolicies(op_type_id,default_merge_mode) VALUES (?,?)
                ON CONFLICT(op_type_id) DO UPDATE SET default_merge_mode=excluded.default_merge_mode""", (code, mode))

    def insert_catalog(self, kind, code, fields):
        table, key = RESOURCE_KEYS[kind]
        columns = [key] + list(fields)
        marks = ",".join("?" for _ in columns)
        self.execute(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({marks})", [code] + list(fields.values()))

    def update_catalog(self, kind, code, fields):
        table, key = RESOURCE_KEYS[kind]
        self.execute(f"UPDATE {table} SET {','.join(name+'=?' for name in fields)} WHERE {key}=?", list(fields.values()) + [code])

    def delete_catalog(self, kind, code):
        table, key = RESOURCE_KEYS[kind]
        self.execute(f"DELETE FROM {table} WHERE {key}=?", (code,))

    def set_pattern(self, profile_id, days):
        self.execute("DELETE FROM WorkbenchShiftPatternDays WHERE profile_id=?", (profile_id,))
        self.executemany(
            "INSERT INTO WorkbenchShiftPatternDays(profile_id,day_offset,is_rest,shift_start,shift_end) VALUES (?,?,?,?,?)",
            [(profile_id, day["day_offset"], int(day["is_rest"]), day["shift_start"], day["shift_end"]) for day in days],
        )
        period_rows = [
            (profile_id, day["day_offset"], encode_periods(day["periods"], normalized=True))
            for day in days if day["periods"] is not None
        ]
        if period_rows:
            self.executemany(
                "INSERT INTO WorkbenchShiftDayPeriods(profile_id,day_offset,periods_json) VALUES (?,?,?)",
                period_rows,
            )
