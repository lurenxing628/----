"""Real-schema delivery fixtures; all writes target throwaway SQLite databases."""

from contextlib import contextmanager
from dataclasses import replace
from typing import Optional

from core.infrastructure.workbench_plan_identity_schema import install_plan_identity
from core.models.workbench_plan_reference import WorkbenchPlanLocator
from core.models.workbench_plan_scope import PlanReadScope
from core.services.workbench.plan_delivery import read_plan_delivery
from core.services.workbench.plan_queries import WorkbenchPlanQueryService
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository
from tests.workbench.plan_catalog_support import candidate, history, scenario, seed_operation, selection


def seed_delivery(conn):
    install_plan_identity(conn)
    op = seed_operation(conn)
    conn.execute("UPDATE Batches SET part_name='Delivery part',due_date='2026-09-09' WHERE batch_id='CAT-B'")
    history(conn, 1, op_id=op)
    history(conn, 2, op_id=op)
    adopted = candidate(conn, 2, "adopted", source="schedule")
    baseline = candidate(conn, 2, "baseline_best", op_id=op)
    critical = candidate(conn, 2, "critical_best", op_id=op)
    scenario(conn, "DELIVERY-SCENARIO", 2, op_id=op, role="baseline_best", source="candidate_rows",
             candidate_id=baseline, candidate_key="baseline_best")
    conn.commit()
    return {"op": op, "adopted": adopted, "baseline": baseline, "critical": critical}


def context(conn, version=2, role="adopted", scenario_id=None, start=None, end=None):
    ref = WorkbenchPlanIdentityRepository(conn).get_plan_ref(WorkbenchPlanLocator(version, role, scenario_id))
    service = WorkbenchPlanQueryService(conn)
    with service.read_snapshot():
        _, entry, _ = service._selected(ref)
    assert entry.plan_identity is not None
    return PlanReadScope(ref, start, end), entry.plan_identity


@contextmanager
def readonly(conn):
    assert not conn.in_transaction
    conn.execute("PRAGMA query_only = ON")
    conn.execute("BEGIN")
    try:
        yield
    finally:
        conn.rollback()
        conn.execute("PRAGMA query_only = OFF")


def read(conn, ctx):
    with readonly(conn):
        return read_plan_delivery(conn, scope=ctx[0], identity=ctx[1])


def add_operation(conn, *, batch="CAT-B", seq=2, version: Optional[int] = 2, start="2026-09-10 01:00:00", end="2026-09-10 03:00:00"):
    op = conn.execute("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_name) VALUES (?,?,?,'Delivery op')",
                      (batch + "-OP-" + str(seq), batch, seq)).lastrowid
    if version is not None:
        conn.execute("INSERT INTO Schedule(version,op_id,start_time,end_time) VALUES (?,?,?,?)", (version, op, start, end))
    return op


def add_batch(conn, key, *, due="2026-09-09", version=2):
    conn.execute("INSERT INTO Batches(batch_id,part_no,part_name,quantity,due_date) VALUES (?,'CAT-P','Other part',1,?)", (key, due))
    return add_operation(conn, batch=key, seq=1, version=version)


def finish_event(conn, op, *, version=1):
    schedule_id = conn.execute("SELECT id FROM Schedule WHERE op_id=? AND version=?", (op, version)).fetchone()[0]
    conn.execute("INSERT INTO OperationExecutionEvents(schedule_version,schedule_id,op_id,batch_id,source_table,"
                 "effective_plan_role,event_type,reported_status,event_time,created_by,idempotency_key,"
                 "request_fingerprint,previous_state_revision) VALUES (?,?,?,'CAT-B','schedule','adopted',"
                 "'finish','completed','2026-09-08 12:00:00','fixture','delivery-event','private-fingerprint','private-revision')",
                 (version, schedule_id, op))


def assert_public(value):
    private = {"op_id", "schedule_id", "source_table", "candidate_id", "candidate_key", "scenario_id", "version",
               "revision", "source_row_id", "identity", "completion_record", "entity_key", "fingerprint"}
    if isinstance(value, dict):
        assert not set(value).intersection(private)
        for item in value.values():
            assert_public(item)
    elif isinstance(value, list):
        for item in value:
            assert_public(item)


def alias_official(conn, seed):
    conn.execute("DELETE FROM ScheduleCandidateSelection WHERE version=2 AND role='baseline_best'")
    selection(conn, 2, "baseline_best", seed["adopted"])
    conn.commit()


def allow_legacy_segments(conn):
    """Only this temporary fixture admits duplicate/segmented legacy task rows."""
    conn.execute("DROP INDEX idx_schedule_version_op_unique")


def grow_tasks(conn, count, *, batches=False):
    first = conn.execute("SELECT MAX(id)+1 FROM BatchOperations").fetchone()[0]
    ids = range(first, first + count)
    if batches:
        conn.executemany("INSERT INTO Batches(batch_id,part_no,part_name,quantity,due_date) "
                         "VALUES (?,'CAT-P','Scale part',1,'2026-09-09')", (("S-" + str(op),) for op in ids))
    conn.executemany("INSERT INTO BatchOperations(id,op_code,batch_id,seq,op_type_name) VALUES (?,?,?,?,'Scale op')",
                     ((op, "S-OP-" + str(op), "S-" + str(op) if batches else "CAT-B", op) for op in ids))
    conn.executemany("INSERT INTO Schedule(version,op_id,start_time,end_time) VALUES (2,?,'2026-09-10 01:00:00','2026-09-10 03:00:00')",
                     ((op,) for op in ids))
    conn.commit()


def spaced_scenario_context(conn, seed):
    _, identity = context(conn, role="baseline_best", scenario_id="DELIVERY-SCENARIO")
    key = " DELIVERY-SCENARIO "
    scenario(conn, key, 2, op_id=seed["op"], role="baseline_best", source="candidate_rows",
             candidate_id=seed["baseline"], candidate_key="baseline_best")
    conn.execute("UPDATE ScheduleAdjustmentScenarioRow SET end_time='2026-09-10 06:30:00' WHERE scenario_id=?", (key,))
    conn.commit()
    ref = WorkbenchPlanIdentityRepository(conn).get_plan_ref(WorkbenchPlanLocator(2, "baseline_best", key))
    return PlanReadScope(ref), replace(identity, scenario_id=key)
