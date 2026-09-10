"""Explicit resource relationships, separate from legacy machine authorization/teams."""

from __future__ import annotations

from typing import Dict, List

from .workbench_metadata_schema import _canonical_sql, identity_triggers

RESOURCE_ENTITY_TABLES = {
    "machine_group": ("WorkbenchMachineGroups", "group_id"),
    "shift_profile": ("WorkbenchShiftProfiles", "profile_id"),
}
RESOURCE_TABLE_NAMES = (
    "WorkbenchMachineGroups", "WorkbenchMachineGroupMembers", "WorkbenchShiftProfiles",
    "WorkbenchShiftPatternDays", "WorkbenchOperatorProfiles", "WorkbenchSupplierOpTypes",
    "WorkbenchSupplierProfiles", "WorkbenchOpTypePolicies",
)

_TABLES = {
    "WorkbenchMachineGroups": """CREATE TABLE IF NOT EXISTS WorkbenchMachineGroups (
        group_id TEXT PRIMARY KEY NOT NULL, name TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'inactive')),
        remark TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""",
    "WorkbenchMachineGroupMembers": """CREATE TABLE IF NOT EXISTS WorkbenchMachineGroupMembers (
        machine_id TEXT PRIMARY KEY NOT NULL REFERENCES Machines(machine_id) ON DELETE CASCADE,
        group_id TEXT NOT NULL REFERENCES WorkbenchMachineGroups(group_id)
    )""",
    "WorkbenchShiftProfiles": """CREATE TABLE IF NOT EXISTS WorkbenchShiftProfiles (
        profile_id TEXT PRIMARY KEY NOT NULL, name TEXT NOT NULL UNIQUE,
        anchor_date TEXT NOT NULL, cycle_days INTEGER NOT NULL CHECK(typeof(cycle_days) = 'integer' AND cycle_days BETWEEN 1 AND 366),
        status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'inactive')),
        remark TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""",
    "WorkbenchShiftPatternDays": """CREATE TABLE IF NOT EXISTS WorkbenchShiftPatternDays (
        profile_id TEXT NOT NULL REFERENCES WorkbenchShiftProfiles(profile_id) ON DELETE CASCADE,
        day_offset INTEGER NOT NULL CHECK(typeof(day_offset) = 'integer' AND day_offset BETWEEN 0 AND 365),
        is_rest INTEGER NOT NULL CHECK(is_rest IN (0, 1)),
        shift_start TEXT NOT NULL, shift_end TEXT NOT NULL,
        PRIMARY KEY(profile_id, day_offset)
    )""",
    "WorkbenchOperatorProfiles": """CREATE TABLE IF NOT EXISTS WorkbenchOperatorProfiles (
        operator_id TEXT PRIMARY KEY NOT NULL REFERENCES Operators(operator_id) ON DELETE CASCADE,
        shift_profile_id TEXT REFERENCES WorkbenchShiftProfiles(profile_id),
        skills_declared INTEGER NOT NULL DEFAULT 0 CHECK(skills_declared IN (0, 1)),
        inactive_reason TEXT CHECK(inactive_reason IS NULL OR inactive_reason IN ('leave', 'disabled'))
    )""",
    "WorkbenchSupplierOpTypes": """CREATE TABLE IF NOT EXISTS WorkbenchSupplierOpTypes (
        supplier_id TEXT NOT NULL REFERENCES Suppliers(supplier_id) ON DELETE CASCADE,
        op_type_id TEXT NOT NULL REFERENCES OpTypes(op_type_id),
        PRIMARY KEY(supplier_id, op_type_id)
    )""",
    "WorkbenchSupplierProfiles": """CREATE TABLE IF NOT EXISTS WorkbenchSupplierProfiles (
        supplier_id TEXT PRIMARY KEY NOT NULL REFERENCES Suppliers(supplier_id) ON DELETE CASCADE,
        inactive_reason TEXT CHECK(inactive_reason IS NULL OR inactive_reason IN ('pending_review', 'disabled'))
    )""",
    "WorkbenchOpTypePolicies": """CREATE TABLE IF NOT EXISTS WorkbenchOpTypePolicies (
        op_type_id TEXT PRIMARY KEY NOT NULL REFERENCES OpTypes(op_type_id) ON DELETE CASCADE,
        default_merge_mode TEXT NOT NULL CHECK(default_merge_mode IN ('separate', 'merged'))
    )""",
}
_INDEXES = {
    "idx_wb_machine_members_group": "CREATE INDEX IF NOT EXISTS idx_wb_machine_members_group ON WorkbenchMachineGroupMembers(group_id)",
    "idx_wb_operator_profiles_shift": "CREATE INDEX IF NOT EXISTS idx_wb_operator_profiles_shift ON WorkbenchOperatorProfiles(shift_profile_id)",
    "idx_wb_supplier_op_types_op": "CREATE INDEX IF NOT EXISTS idx_wb_supplier_op_types_op ON WorkbenchSupplierOpTypes(op_type_id)",
    "idx_wb_operator_skill_op": "CREATE INDEX IF NOT EXISTS idx_wb_operator_skill_op ON OperatorSkill(op_type_id)",
}


def _relationship_triggers(table: str, owners) -> Dict[str, str]:
    result = {}
    for event in ("INSERT", "UPDATE", "DELETE"):
        aliases = ("OLD", "NEW") if event == "UPDATE" else (("OLD",) if event == "DELETE" else ("NEW",))
        predicates = []
        for kind, column in owners:
            keys = ", ".join(f'{alias}."{column}"' for alias in aliases)
            predicates.append(f"(kind = '{kind}' AND entity_key IN ({keys}))")
        name = "wb_resource_touch_" + table.lower() + "_" + event.lower()
        result[name] = f"""CREATE TRIGGER IF NOT EXISTS {name} AFTER {event} ON "{table}" BEGIN
            UPDATE WorkbenchEntityRefs SET revision = revision + 1
                WHERE active = 1 AND ({' OR '.join(predicates)});
        END"""
    return result


def _shift_member_triggers() -> Dict[str, str]:
    result = {}
    for event in ("INSERT", "UPDATE", "DELETE"):
        aliases = ("OLD", "NEW") if event == "UPDATE" else (("OLD",) if event == "DELETE" else ("NEW",))
        keys = ", ".join(alias + ".shift_profile_id" for alias in aliases)
        changed = " WHEN OLD.shift_profile_id IS NOT NEW.shift_profile_id OR OLD.operator_id IS NOT NEW.operator_id" if event == "UPDATE" else ""
        name = "wb_resource_shift_members_" + event.lower()
        result[name] = f"""CREATE TRIGGER IF NOT EXISTS {name} AFTER {event} ON WorkbenchOperatorProfiles{changed} BEGIN
            UPDATE WorkbenchEntityRefs SET revision = revision + 1
                WHERE active = 1 AND kind = 'shift_profile' AND entity_key IN ({keys});
        END"""
    return result


def resource_objects() -> Dict[str, str]:
    objects = {**_TABLES, **_INDEXES}
    for kind, (table, key) in RESOURCE_ENTITY_TABLES.items():
        objects.update(identity_triggers(kind, table, (key,), alternate_column="name"))
    for table, owners in {
        "WorkbenchMachineGroupMembers": (("machine", "machine_id"), ("machine_group", "group_id")),
        "WorkbenchShiftPatternDays": (("shift_profile", "profile_id"),),
        "WorkbenchOperatorProfiles": (("operator", "operator_id"),),
        "WorkbenchSupplierOpTypes": (("supplier", "supplier_id"), ("op_type", "op_type_id")),
        "WorkbenchSupplierProfiles": (("supplier", "supplier_id"),),
        "WorkbenchOpTypePolicies": (("op_type", "op_type_id"),),
        "OperatorSkill": (("operator", "operator_id"), ("op_type", "op_type_id")),
        "OperatorMachine": (("operator", "operator_id"), ("machine", "machine_id")),
    }.items():
        objects.update(_relationship_triggers(table, owners))
    objects.update(_shift_member_triggers())
    for kind, table, key, profile in (
        ("operator", "Operators", "operator_id", "WorkbenchOperatorProfiles"),
        ("supplier", "Suppliers", "supplier_id", "WorkbenchSupplierProfiles"),
    ):
        name = "wb_resource_" + kind + "_status_reason"
        objects[name] = f"""CREATE TRIGGER IF NOT EXISTS {name} AFTER UPDATE OF status ON {table} BEGIN
            UPDATE {profile} SET inactive_reason = NULL WHERE {key} = NEW.{key} AND inactive_reason IS NOT NULL;
        END"""
    return objects


def install_resources(conn) -> None:
    for sql in resource_objects().values():
        conn.execute(sql)
    for kind, (table, key) in RESOURCE_ENTITY_TABLES.items():
        conn.execute(f"""INSERT INTO WorkbenchEntityRefs(ref, kind, entity_key, alternate_key)
            SELECT lower(hex(randomblob(24))), ?, source.{key}, source.name FROM {table} AS source
            WHERE NOT EXISTS (SELECT 1 FROM WorkbenchEntityRefs AS r
                WHERE r.kind = ? AND r.entity_key = source.{key} AND r.active = 1)""", (kind, kind))


def workbench_resource_contract_issues(conn) -> List[str]:
    rows = conn.execute("SELECT name, sql FROM sqlite_master WHERE type IN ('table', 'index', 'trigger')").fetchall()
    actual = {row[0]: row[1] for row in rows}
    return [("missing_workbench_resource: " if name not in actual else "bad_workbench_resource: ") + name
            for name, sql in resource_objects().items()
            if name not in actual or _canonical_sql(actual[name] or "") != _canonical_sql(sql)]
