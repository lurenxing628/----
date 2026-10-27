"""Append-only collision guards for the existing plan identity write triggers."""

from typing import Dict, List

from .schema_structure import schema_objects
from .workbench_metadata_schema import canonical_sql
from .workbench_plan_identity_schema import workbench_plan_identity_contract_issues


def plan_identity_write_guard_objects() -> Dict[str, str]:
    result = {}
    for kind, table in (("source", "WorkbenchPlanSourceRefs"), ("task", "WorkbenchTaskRefs")):
        name = "wb_plan_" + kind + "_ref_insert_guard"
        result[name] = f"""CREATE TRIGGER IF NOT EXISTS {name} BEFORE INSERT ON {table}
            WHEN EXISTS (SELECT 1 FROM {table} WHERE ref = NEW.ref)
            BEGIN SELECT RAISE(ABORT, 'UNIQUE constraint failed: {table}.ref'); END"""
    return result


def plan_identity_write_guard_contract_issues(conn, *, structure) -> List[str]:
    """SELECT-only contract for the coordinator's new schema-version gate."""
    issues = workbench_plan_identity_contract_issues(conn, structure=structure)
    actual = schema_objects(conn, structure=structure)
    for name, sql in plan_identity_write_guard_objects().items():
        if name not in actual:
            issues.append("missing_workbench_plan_write_guard: " + name)
        elif canonical_sql(actual[name]) != canonical_sql(sql):
            issues.append("bad_workbench_plan_write_guard: " + name)
    return issues
