"""Append-only collision guards for the existing plan identity write triggers.

The outer statement's OR REPLACE policy reaches writes inside triggers. Explicit
RAISE(ABORT) keeps both live refs and tombstones from being replaced, including
when recursive_triggers is OFF. The caller's business transaction handles the
propagated IntegrityError; earlier statements are not committed by this helper.

Register install() in a NEW migration and require contract_issues() at that new
version. Keep the v24..29 objects and fixtures unchanged. This module does not
register itself, alter SchemaVersion, repair old mappings, or generate refs.
"""

from typing import Dict, List

from .transaction import TransactionManager
from .workbench_metadata_schema import _canonical_sql
from .workbench_plan_identity_schema import (
    install_plan_identity,
    workbench_plan_identity_contract_issues,
)


def plan_identity_write_guard_objects() -> Dict[str, str]:
    result = {}
    for kind, table in (("source", "WorkbenchPlanSourceRefs"), ("task", "WorkbenchTaskRefs")):
        name = "wb_plan_" + kind + "_ref_insert_guard"
        result[name] = f"""CREATE TRIGGER IF NOT EXISTS {name} BEFORE INSERT ON {table}
            WHEN EXISTS (SELECT 1 FROM {table} WHERE ref = NEW.ref)
            BEGIN SELECT RAISE(ABORT, 'UNIQUE constraint failed: {table}.ref'); END"""
    return result


def plan_identity_write_guard_contract_issues(conn) -> List[str]:
    """SELECT-only contract for the coordinator's new schema-version gate."""
    issues = workbench_plan_identity_contract_issues(conn)
    actual = dict(conn.execute("SELECT name, sql FROM sqlite_master"))
    for name, sql in plan_identity_write_guard_objects().items():
        if name not in actual:
            issues.append("missing_workbench_plan_write_guard: " + name)
        elif _canonical_sql(actual[name] or "") != _canonical_sql(sql):
            issues.append("bad_workbench_plan_write_guard: " + name)
    return issues


def install_plan_identity_write_guards(conn) -> None:
    """Add guards atomically; reject partial/damaged schemas without repair."""
    with TransactionManager(conn).transaction():
        issues = workbench_plan_identity_contract_issues(conn)
        expected = plan_identity_write_guard_objects()
        present = set(expected) & {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
        if present:
            issues = plan_identity_write_guard_contract_issues(conn)
        if issues:
            raise RuntimeError("Cannot install plan identity write guards: " + "; ".join(issues))
        # On the validated existing schema this only checks coverage. Lost refs
        # must fail explicitly; no backfill or clock initialization is possible.
        install_plan_identity(conn)
        if not present:
            for sql in expected.values():
                conn.execute(sql)


objects = plan_identity_write_guard_objects
install = install_plan_identity_write_guards
contract_issues = plan_identity_write_guard_contract_issues
