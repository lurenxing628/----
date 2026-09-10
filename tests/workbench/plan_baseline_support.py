"""Real SQLite fixtures for baseline projection; no production app or database."""

import sqlite3
from pathlib import Path

import pytest

from core.infrastructure.workbench_plan_identity_schema import install_plan_identity
from core.models.workbench_plan_reference import WorkbenchPlanLocator
from core.models.workbench_plan_scope import PlanReadScope
from core.services.workbench.plan_baseline import build_plan_baseline
from core.services.workbench.plan_queries import WorkbenchPlanQueryService
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository
from tests.workbench.plan_catalog_support import candidate, history, scenario, seed_operation, selection

NIGHT_START = "2026-09-09T22:30:00"
NIGHT_END = "2026-09-10T06:30:00"
MOVED_START = "2026-09-12T23:00:00"
MOVED_END = "2026-09-13T02:00:00"


def connect(path):
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


class BaselineCase:
    def __init__(self, conn, path):
        self.conn, self.path = conn, path

    def ref(self, role="adopted", scenario_id="saved", version=3):
        return WorkbenchPlanIdentityRepository(self.conn).get_plan_ref(WorkbenchPlanLocator(version, role, scenario_id))

    def inputs(self, role="adopted", scenario_id="saved", version=3, start=None, end=None):
        scope = PlanReadScope(self.ref(role, scenario_id, version), start, end)
        query = WorkbenchPlanQueryService(self.conn)
        repo, entry, _ = query._selected(scope.plan_ref)
        return {"entry": entry, "scope": scope, "selected_rows": query._task_rows(repo, entry, scope)}

    def read(self, **kwargs):
        self.conn.execute("BEGIN")
        try:
            return build_plan_baseline(self.conn, **self.inputs(**kwargs))
        finally:
            self.conn.rollback()

    def add_operations(self, count, *, base=True, current=True, start=NIGHT_START, end=NIGHT_END):
        first = self.conn.execute("SELECT MAX(id)+1 FROM BatchOperations").fetchone()[0]
        ids = range(first, first + count)
        self.conn.executemany("INSERT INTO BatchOperations(id,op_code,batch_id,seq,op_type_name) "
                              "VALUES (?,?,'CAT-B',?,'Extra')", ((op, "EXTRA-" + str(op), op) for op in ids))
        if base:
            self.conn.executemany("INSERT INTO Schedule(version,op_id,start_time,end_time) VALUES (3,?,?,?)",
                                  ((op, start, end) for op in ids))
        if current:
            self.conn.executemany("INSERT INTO ScheduleAdjustmentScenarioRow(scenario_id,source_table,op_id,start_time,end_time) "
                                  "VALUES ('saved','schedule',?,?,?)", ((op, start, end) for op in ids))
        self.conn.commit()
        return list(ids)


@pytest.fixture(name="baseline_case")
def baseline_fixture(tmp_path):
    path = tmp_path / "baseline.db"
    conn = connect(path)
    conn.executescript((Path(__file__).resolve().parents[2] / "schema.sql").read_text(encoding="utf-8"))
    install_plan_identity(conn)
    op = seed_operation(conn)
    conn.execute("INSERT INTO Machines(machine_id,name) VALUES ('PRIVATE-M1','Machine one'),('PRIVATE-M2','Machine two')")
    conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('PRIVATE-O1','Operator one'),('PRIVATE-O2','Operator two')")
    history(conn, 1, op_id=op)
    history(conn, 3, op_id=op)
    adopted = candidate(conn, 3, "adopted", source="schedule")
    selection(conn, 3, "baseline_best", adopted)
    other = candidate(conn, 3, "critical_best", op_id=op)
    for key, role, source, cid, ckey in (
        ("saved", "adopted", "schedule", adopted, "adopted"),
        ("alias", "baseline_best", "schedule", adopted, "adopted"),
        ("candidate", "critical_best", "candidate_rows", other, "critical_best"),
    ):
        scenario(conn, key, 3, op_id=op, role=role, source=source, candidate_id=cid, candidate_key=ckey)
    conn.execute("UPDATE Schedule SET start_time=?,end_time=?,machine_id='PRIVATE-M1',operator_id='PRIVATE-O1' WHERE version=3",
                 (NIGHT_START, NIGHT_END))
    conn.execute("UPDATE ScheduleAdjustmentScenarioRow SET start_time=?,end_time=?,machine_id='PRIVATE-M2',operator_id='PRIVATE-O2'",
                 (MOVED_START, MOVED_END))
    conn.commit()
    try:
        yield BaselineCase(conn, path)
    finally:
        conn.close()


def assert_public(value):
    forbidden = {"scenario_id", "candidate_id", "candidate_key", "source_table", "source_row_id", "schedule_id",
                 "op_id", "machine_id", "operator_id", "supplier_id", "locator", "revision", "source_draft_id"}
    if isinstance(value, dict):
        assert not forbidden.intersection(value)
        for item in value.values():
            assert_public(item)
    elif isinstance(value, list):
        for item in value:
            assert_public(item)
    elif isinstance(value, str):
        assert "PRIVATE-" not in value


def projection_trace(case, **kwargs):
    conn = case.conn
    conn.execute("BEGIN")
    try:
        inputs = case.inputs(**kwargs)
        statements = []
        conn.set_trace_callback(statements.append)
        try:
            result = build_plan_baseline(conn, **inputs)
        finally:
            conn.set_trace_callback(None)
        return result, statements
    finally:
        conn.rollback()
