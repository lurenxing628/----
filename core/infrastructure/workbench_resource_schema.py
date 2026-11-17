"""Explicit resource relationships, separate from legacy machine authorization/teams."""

from __future__ import annotations

from typing import Dict, List

from core.models.enums import (
    MACHINE_GROUP_STATUS_VALUES,
    MERGE_MODE_VALUES,
    OPERATOR_INACTIVE_REASON_VALUES,
    SHIFT_CYCLE_DAYS_MAX,
    SHIFT_DAY_OFFSET_MAX,
    SHIFT_PROFILE_STATUS_VALUES,
    SUPPLIER_INACTIVE_REASON_VALUES,
    enum_check,
    flag_check,
    integer_range_check,
    nullable_enum_check,
)

from .schema_structure import SchemaStructure
from .workbench_metadata_schema import canonical_sql, identity_triggers

RESOURCE_ENTITY_TABLES = {
    "machine_group": ("WorkbenchMachineGroups", "group_id"),
    "shift_profile": ("WorkbenchShiftProfiles", "profile_id"),
}


_TABLES = {
    "WorkbenchMachineGroups": f"""CREATE TABLE IF NOT EXISTS WorkbenchMachineGroups (
        group_id TEXT PRIMARY KEY NOT NULL, name TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL DEFAULT 'active' {enum_check('status', MACHINE_GROUP_STATUS_VALUES)},
        remark TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""",
    "WorkbenchMachineGroupMembers": """CREATE TABLE IF NOT EXISTS WorkbenchMachineGroupMembers (
        machine_id TEXT PRIMARY KEY NOT NULL REFERENCES Machines(machine_id) ON DELETE CASCADE,
        group_id TEXT NOT NULL REFERENCES WorkbenchMachineGroups(group_id)
    )""",
    "WorkbenchShiftProfiles": f"""CREATE TABLE IF NOT EXISTS WorkbenchShiftProfiles (
        profile_id TEXT PRIMARY KEY NOT NULL, name TEXT NOT NULL UNIQUE,
        anchor_date TEXT NOT NULL, cycle_days INTEGER NOT NULL {integer_range_check('cycle_days', 1, SHIFT_CYCLE_DAYS_MAX)},
        status TEXT NOT NULL DEFAULT 'active' {enum_check('status', SHIFT_PROFILE_STATUS_VALUES)},
        remark TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""",
    "WorkbenchShiftPatternDays": f"""CREATE TABLE IF NOT EXISTS WorkbenchShiftPatternDays (
        profile_id TEXT NOT NULL REFERENCES WorkbenchShiftProfiles(profile_id) ON DELETE CASCADE,
        day_offset INTEGER NOT NULL {integer_range_check('day_offset', 0, SHIFT_DAY_OFFSET_MAX)},
        is_rest INTEGER NOT NULL {flag_check('is_rest')},
        periods_json TEXT NOT NULL,
        PRIMARY KEY(profile_id, day_offset)
    )""",
    "WorkbenchOperatorProfiles": f"""CREATE TABLE IF NOT EXISTS WorkbenchOperatorProfiles (
        operator_id TEXT PRIMARY KEY NOT NULL REFERENCES Operators(operator_id) ON DELETE CASCADE,
        shift_profile_id TEXT REFERENCES WorkbenchShiftProfiles(profile_id),
        skills_declared INTEGER NOT NULL DEFAULT 0 {flag_check('skills_declared')},
        inactive_reason TEXT {nullable_enum_check('inactive_reason', OPERATOR_INACTIVE_REASON_VALUES)}
    )""",
    "WorkbenchSupplierOpTypes": """CREATE TABLE IF NOT EXISTS WorkbenchSupplierOpTypes (
        supplier_id TEXT NOT NULL REFERENCES Suppliers(supplier_id) ON DELETE CASCADE,
        op_type_id TEXT NOT NULL REFERENCES OpTypes(op_type_id),
        PRIMARY KEY(supplier_id, op_type_id)
    )""",
    "WorkbenchSupplierProfiles": f"""CREATE TABLE IF NOT EXISTS WorkbenchSupplierProfiles (
        supplier_id TEXT PRIMARY KEY NOT NULL REFERENCES Suppliers(supplier_id) ON DELETE CASCADE,
        inactive_reason TEXT {nullable_enum_check('inactive_reason', SUPPLIER_INACTIVE_REASON_VALUES)}
    )""",
    "WorkbenchOpTypePolicies": f"""CREATE TABLE IF NOT EXISTS WorkbenchOpTypePolicies (
        op_type_id TEXT PRIMARY KEY NOT NULL REFERENCES OpTypes(op_type_id) ON DELETE CASCADE,
        default_merge_mode TEXT NOT NULL {enum_check('default_merge_mode', MERGE_MODE_VALUES)}
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


def workbench_resource_contract_issues(structure: SchemaStructure) -> List[str]:
    actual = structure.sql
    return [("missing_workbench_resource: " if name not in actual else "bad_workbench_resource: ") + name
            for name, sql in resource_objects().items()
            if name not in actual or canonical_sql(actual[name]) != canonical_sql(sql)]
