"""Temporary real-schema plan instances and complete preservation snapshots."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List

from core.infrastructure.migration_state import set_schema_version
from core.infrastructure.migrations import v24
from core.infrastructure.workbench_plan_identity_schema import (
    plan_identity_objects,
)
from core.infrastructure.workbench_process_schema import process_objects
from core.models.workbench_plan_reference import WorkbenchPlanLocator
from data.repositories.schedule_plan_query_repo import SchedulePlanQueryRepository
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository
from tests.workbench.plan_catalog_support import END, START, candidate, history, scenario, seed_operation, selection

IDENTITY_TABLES = ("WorkbenchPlanSourceRefs", "WorkbenchTaskRefs", "WorkbenchPlanIdentityClock")
LEDGER_TABLES = ("WorkbenchExecutionLedgerClock", "WorkbenchExecutionLegacyFacts",
                 "WorkbenchProductionReports", "WorkbenchProductionReportRevisions")


def load_v24_schema(conn):
    """Load the immutable predecessor DDL into an empty test connection only."""
    assert not conn.execute("SELECT name FROM sqlite_master").fetchall()
    source = Path(__file__).resolve().parent / "fixtures" / "schema-v24.sql"
    conn.executescript(source.read_text(encoding="utf-8"))
    assert not set(LEDGER_TABLES) & set(table_snapshot(conn))
    return conn


def load_v23_schema(conn):
    """Model v23 from fixed v24 DDL, without any current-schema ledger objects."""
    load_v24_schema(conn)
    legacy_schema(conn)
    use_legacy_process_triggers(conn)
    set_schema_version(conn, 23)
    conn.commit()
    return conn


def legacy_schema(conn):
    """Remove plan identity objects only, also used for deliberate damage tests."""
    for name in reversed(plan_identity_objects()):
        row = conn.execute("SELECT type FROM sqlite_master WHERE name = ?", (name,)).fetchone()
        if row:
            conn.execute('DROP ' + row[0].upper() + ' "' + name + '"')
    conn.commit()
    return conn


def table_snapshot(conn, exclude=()):
    names = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
    return {table: sorted((tuple(row) for row in conn.execute('SELECT * FROM "' + table + '"')), key=repr)
            for table in names if table not in exclude}


def seed_plans(conn):
    op_id = seed_operation(conn)
    other_id = conn.execute("INSERT INTO BatchOperations(op_code, batch_id, seq, piece_id, op_type_name) "
                            "VALUES ('OTHER', 'CAT-B', 2, 'piece', 'Other')").lastrowid
    history(conn, 1, op_id=op_id)
    history(conn, 2, op_id=op_id)
    adopted = candidate(conn, 1, "adopted", source="schedule")
    selection(conn, 1, "baseline_best", adopted)
    candidate(conn, 1, "critical_best", op_id=op_id)
    scenario(conn, "saved", 1, op_id=op_id, candidate_id=adopted, candidate_key="adopted")
    conn.commit()
    return op_id, other_id


def installed_case(conn, *, legacy=False):
    if legacy:
        load_v23_schema(conn)
    else:
        v24.run(conn)
    ids = seed_plans(conn)
    if legacy:
        v24.run(conn)
    return conn, WorkbenchPlanIdentityRepository(conn), ids


def plan_rows(conn, locator) -> List[Dict[str, Any]]:
    if locator.scenario_id is not None:
        source, candidate_id = "adjustment_scenario_rows", None
    elif locator.plan_role == "adopted":
        source, candidate_id = "schedule", None
    else:
        source, candidate_id = conn.execute("SELECT source_table, candidate_id FROM ScheduleCandidateSelection "
                                            "WHERE version = ? AND role = ?",
                                            (locator.version, locator.plan_role)).fetchone()
    rows = SchedulePlanQueryRepository(conn).list_detail_rows_all(
        version=locator.version, source_table=source, candidate_id=candidate_id, scenario_id=locator.scenario_id)
    return [dict(row) for row in rows]


def all_refs(conn):
    repo = WorkbenchPlanIdentityRepository(conn)
    result = {}
    locators = [WorkbenchPlanLocator(1, role) for role in ("adopted", "baseline_best", "critical_best")]
    locators += [WorkbenchPlanLocator(2, "adopted"), WorkbenchPlanLocator(1, "adopted", "saved")]
    for locator in locators:
        ref = repo.get_plan_ref(locator)
        result[locator] = ref, repo.get_task_refs(ref, plan_rows(conn, locator))
    result["operations"] = repo.get_operation_refs([row[0] for row in conn.execute("SELECT id FROM BatchOperations")])
    return result


def replace_row(conn, table, row, **changes):
    payload = dict(row)
    payload.update(changes)
    columns = ",".join('"' + key + '"' for key in payload)
    conn.execute('INSERT OR REPLACE INTO "' + table + '" (' + columns + ') VALUES (' +
                 ",".join("?" for _ in payload) + ")", tuple(payload.values()))


def foreign_keys_off(conn):
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 0


def dynamic_scale(conn, count=10000):
    """Exercise source writes with many distinct operations and all role sources."""
    v24.run(conn)
    seed_operation(conn)
    steps = []
    conn.set_progress_handler(lambda: steps.append(1) or 0, 1000)
    started = time.perf_counter()
    conn.executemany("INSERT INTO BatchOperations(op_code, batch_id, seq, op_type_name) "
                     "VALUES (?, 'CAT-B', ?, 'scale')", (("scale-" + str(i), i + 1) for i in range(1, count + 1)))
    conn.executemany("INSERT INTO ScheduleHistory(version, strategy) VALUES (?, 'scale')", ((i,) for i in range(1, count + 1)))
    conn.executemany("INSERT INTO Schedule(version, op_id, start_time, end_time) VALUES (?, ?, ?, ?)",
                     ((i, i + 1, START, END) for i in range(1, count + 1)))
    conn.executemany("INSERT INTO ScheduleCandidate(version, candidate_key, candidate_label, candidate_kind, status) "
                     "VALUES (?, 'scale', 'scale', 'baseline', 'completed')", ((i,) for i in range(1, count + 1)))
    for role, source in (("adopted", "schedule"), ("baseline_best", "schedule"), ("critical_best", "candidate_rows")):
        conn.executemany("INSERT INTO ScheduleCandidateSelection(version, role, candidate_id, source_table) VALUES (?, ?, ?, ?)",
                         ((i, role, i, source) for i in range(1, count + 1)))
    conn.executemany("INSERT INTO ScheduleCandidateRows(version, candidate_id, op_id, start_time, end_time) VALUES (?, ?, ?, ?, ?)",
                     ((i, i, i + 1, START, END) for i in range(1, count + 1)))
    elapsed = time.perf_counter() - started
    conn.set_progress_handler(None, 0)
    return elapsed, (len(steps) + 1) * 1000


def exec_plan_objects(conn):
    conn.executescript(";\n".join(plan_identity_objects().values()) + ";\n")


def use_legacy_process_triggers(conn):
    for name, sql in process_objects(legacy=True).items():
        conn.execute('DROP TRIGGER IF EXISTS "' + name + '"')
        conn.execute(sql)
    conn.commit()

