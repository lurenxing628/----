"""Permanent operation instance refs and plan identity clock, maintained on source writes.

Operation refs retain tombstones so an orphan cannot attach itself to a later
same-number replacement. Official plan and task refs are persisted directly on
ScheduleHistory(plan_ref) and Schedule(task_ref); INSERT triggers on both tables
advance WorkbenchPlanIdentityClock.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from core.models.enums import PLAN_SOURCE_KIND_VALUES, PlanSourceKind, enum_check, flag_check

from .schema_structure import SchemaStructure
from .workbench_metadata_schema import canonical_sql, entity_key_sql

_REF = "TEXT PRIMARY KEY NOT NULL CHECK(length(ref) = 48 AND ref NOT GLOB '*[^0-9a-f]*')"
_RANDOM = "lower(hex(randomblob(24)))"
_COLUMNS = ("kind", "source_key", "alternate_key", "extra_key")
_SOURCES: Dict[str, Tuple[str, str, Tuple[Tuple[str, ...], ...]]] = {
    PlanSourceKind.OPERATION.value: ("BatchOperations", "id", (("op_code",), ("batch_id", "seq", "piece_id"))),
}
_INITIALIZATION_TABLES = ("WorkbenchPlanSourceRefs", "ScheduleHistory", "Schedule", "BatchOperations")
_TABLES = {
    "WorkbenchPlanSourceRefs": f"""CREATE TABLE IF NOT EXISTS WorkbenchPlanSourceRefs (
        ref {_REF}, kind TEXT NOT NULL {enum_check('kind', PLAN_SOURCE_KIND_VALUES)}, source_key TEXT NOT NULL,
        alternate_key TEXT, extra_key TEXT,
        active INTEGER NOT NULL DEFAULT 1 {flag_check('active')}
    )""",
    "WorkbenchPlanIdentityClock": """CREATE TABLE IF NOT EXISTS WorkbenchPlanIdentityClock (
        singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
        revision INTEGER NOT NULL CHECK(typeof(revision) = 'integer' AND revision > 0)
    )""",
}
_INDEXES = {
    "idx_wb_plan_source_key": "CREATE UNIQUE INDEX IF NOT EXISTS idx_wb_plan_source_key ON WorkbenchPlanSourceRefs(kind, source_key) WHERE active = 1",
    "idx_wb_plan_source_alternate": "CREATE INDEX IF NOT EXISTS idx_wb_plan_source_alternate ON WorkbenchPlanSourceRefs(kind, alternate_key) WHERE active = 1",
    "idx_wb_plan_source_extra": "CREATE INDEX IF NOT EXISTS idx_wb_plan_source_extra ON WorkbenchPlanSourceRefs(kind, extra_key) WHERE active = 1",
}


def _values(kind: str, prefix: str) -> Dict[str, str]:
    _, primary, alternates = _SOURCES[kind]
    values: Dict[str, str] = dict.fromkeys(_COLUMNS, "NULL")
    values.update(kind="'" + kind + "'", source_key=entity_key_sql((primary,), prefix))
    for field, columns in zip(("alternate_key", "extra_key"), alternates):
        values[field] = entity_key_sql(columns, prefix)
    return values


def _insert(values: Dict[str, str]) -> str:
    return ("INSERT INTO WorkbenchPlanSourceRefs(ref, " + ", ".join(_COLUMNS) + ") VALUES (" +
            _RANDOM + ", " + ", ".join(values[column] for column in _COLUMNS) + ");")


def _plan_clock_triggers() -> Dict[str, str]:
    bump = "UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1;"
    return {
        "wb_plan_history_insert": (
            f"CREATE TRIGGER IF NOT EXISTS wb_plan_history_insert AFTER INSERT ON ScheduleHistory BEGIN {bump} END"
        ),
        "wb_plan_schedule_insert": (
            f'CREATE TRIGGER IF NOT EXISTS wb_plan_schedule_insert AFTER INSERT ON "Schedule" BEGIN {bump} END'
        ),
    }


def _source_triggers(kind: str) -> Dict[str, str]:
    table, primary, _ = _SOURCES[kind]
    values = _values(kind, "NEW")
    old_key = entity_key_sql((primary,), "OLD")
    conflicts = [column + " = " + values[column] for column in
                 ("source_key", "alternate_key", "extra_key") if values[column] != "NULL"]
    where = f"kind = '{kind}' AND active = 1"
    retire = "".join(f"UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE {where} AND {conflict};"
                     for conflict in conflicts)
    update_retire = "".join(f"UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE {where} "
                            f"AND {conflict} AND source_key != {old_key};" for conflict in conflicts)
    assignments = ", ".join(column + " = " + values[column] for column in _COLUMNS)
    bodies = {
        "insert": retire + _insert(values),
        "update": update_retire + f"UPDATE WorkbenchPlanSourceRefs SET {assignments} WHERE {where} AND source_key = {old_key};",
        "delete": f"UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE {where} AND source_key = {old_key};",
    }
    result = {}
    for event, body in bodies.items():
        name = "wb_plan_" + kind + "_" + event
        result[name] = (f'CREATE TRIGGER IF NOT EXISTS {name} AFTER {event.upper()} ON "{table}" BEGIN ' +
                        body + "UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1; END")
    return result


def plan_identity_objects() -> Dict[str, str]:
    objects = dict(_TABLES)
    objects.update(_INDEXES)
    objects.update(_plan_clock_triggers())
    for kind in _SOURCES:
        objects.update(_source_triggers(kind))
    return objects


def _structure_issues(*, structure: SchemaStructure) -> List[str]:
    actual = structure.sql
    issues = []
    if structure.has_table("WorkbenchTaskRefs"):
        issues.append("unexpected_workbench_plan_identity: WorkbenchTaskRefs")
    for name, sql in plan_identity_objects().items():
        if name not in actual:
            issues.append("missing_workbench_plan_identity: " + name)
        elif canonical_sql(actual[name]) != canonical_sql(sql):
            issues.append("bad_workbench_plan_identity: " + name)
    return issues


def _clock_issues(conn) -> List[str]:
    rows = conn.execute("SELECT singleton, revision FROM WorkbenchPlanIdentityClock LIMIT 2").fetchall()
    if not rows:
        return ["missing_workbench_plan_clock_state"]
    if len(rows) != 1 or rows[0][0] != 1 or type(rows[0][1]) is not int or rows[0][1] <= 0:
        return ["bad_workbench_plan_clock_state"]
    return []


def workbench_plan_identity_contract_issues(conn, *, structure: SchemaStructure) -> List[str]:
    """SELECT-only structure and required clock check, not business completeness."""
    issues = _structure_issues(structure=structure)
    return issues if issues else _clock_issues(conn)


def plan_identity_initialization_sql() -> str:
    """Seed for the end of a NEW database's DDL script, never a repair script.

    The revision CHECK deliberately aborts a missing-clock initialization when any
    source/identity data exists. Do not replace it with INSERT OR IGNORE. Python
    installers validate the complete DDL before checking or initializing its clock.
    """
    empty = " AND ".join(f'NOT EXISTS (SELECT 1 FROM "{table}" LIMIT 1)' for table in _INITIALIZATION_TABLES)
    return ("INSERT INTO WorkbenchPlanIdentityClock(singleton, revision) "
            f"SELECT 1, CASE WHEN {empty} THEN 1 ELSE 0 END "
            "WHERE NOT EXISTS (SELECT 1 FROM WorkbenchPlanIdentityClock);")
