"""Isolated execution-resource guardrail fixtures; never opens a business DB."""

from dataclasses import asdict
from unittest.mock import patch

import core.services.scheduler.schedule_service as service_module
from core.models.schedule_plan_role import ROLE_ADOPTED, SOURCE_SCHEDULE
from core.services.scheduler.operation_execution_feedback_service import (
    ExecutionFeedbackContext,
    OperationExecutionFeedbackService,
)
from core.services.scheduler.schedule_service import ScheduleService


def seed_plan(conn):
    conn.executescript("""
        INSERT INTO ResourceTeams(team_id, name, status) VALUES ('T1', 'Team', 'active');
        INSERT INTO Machines(machine_id, name, status, team_id)
        VALUES ('M1', 'Machine 1', 'active', 'T1'), ('M2', 'Machine 2', 'active', 'T1');
        INSERT INTO Operators(operator_id, name, status, team_id)
        VALUES ('O1', 'Operator 1', 'active', 'T1'), ('O2', 'Operator 2', 'active', 'T1');
        INSERT INTO OperatorMachine(operator_id, machine_id)
        VALUES ('O1', 'M1'), ('O1', 'M2'), ('O2', 'M1'), ('O2', 'M2');
        INSERT INTO Parts(part_no, part_name) VALUES ('P1', 'Part');
        INSERT INTO Batches(batch_id, part_no, quantity, due_date, priority, ready_status, status)
        VALUES ('B1', 'P1', 1, '2026-09-30', 'normal', 'yes', 'scheduled'),
               ('B2', 'P1', 1, '2026-09-30', 'normal', 'yes', 'scheduled');
        INSERT INTO BatchOperations(id, op_code, batch_id, seq, op_type_name, source,
                                    machine_id, operator_id, setup_hours, unit_hours, status)
        VALUES (10, 'OP10', 'B1', 10, 'Turning', 'internal', 'M1', 'O1', 0, 1, 'scheduled'),
               (20, 'OP20', 'B2', 10, 'Turning', 'internal', 'M1', 'O1', 0, 1, 'scheduled');
        INSERT INTO ScheduleVersionSeq(version) VALUES (1);
        INSERT INTO Schedule(id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
        VALUES (100, 10, 'M1', 'O1', '2026-09-08 08:00:00', '2026-09-08 09:00:00', 'unlocked', 1),
               (101, 20, 'M1', 'O1', '2026-09-08 09:00:00', '2026-09-08 10:00:00', 'unlocked', 1);
        INSERT INTO ScheduleHistory(version, strategy, batch_count, op_count, result_status, result_summary, created_by)
        VALUES (1, 'priority_first', 2, 2, 'success', '{}', 'pytest');
    """)
    conn.commit()


def context(revision="10:0:0", key="start"):
    return ExecutionFeedbackContext(
        schedule_version=1, schedule_id=100, op_id=10, batch_id="B1",
        expected_state_revision=revision, created_by="pytest", idempotency_key=key,
        requested_plan_role=ROLE_ADOPTED, source_table=SOURCE_SCHEDULE,
        effective_plan_role=ROLE_ADOPTED, scenario_id=None,
    )


def start(conn, machine_id="M1", operator_id="O1"):
    return OperationExecutionFeedbackService(conn).start_operation(
        context(), event_time="2026-09-08 08:00:00",
        machine_id=machine_id, operator_id=operator_id,
    )


def rows(conn, version):
    return {row["op_id"]: dict(row) for row in conn.execute(
        "SELECT * FROM Schedule WHERE version = ? ORDER BY op_id", (version,),
    )}


def persistent_state(conn):
    return {table: [tuple(row) for row in conn.execute("SELECT * FROM " + table + " ORDER BY 1")]
            for table in ("Schedule", "ScheduleHistory", "ScheduleVersionSeq")}


def execution_state(conn):
    return {table: [tuple(row) for row in conn.execute(sql)] for table, sql in (
        ("events", "SELECT * FROM OperationExecutionEvents ORDER BY id"),
        ("batch", "SELECT * FROM Batches WHERE batch_id = 'B1'"),
        ("operations", "SELECT * FROM BatchOperations WHERE batch_id = 'B1' ORDER BY id"),
    )}


def preview(conn, batch_ids=None):
    captured = []
    original = service_module.orchestrate_schedule_run

    def observe(*args, **kwargs):
        outcome = original(*args, **kwargs)
        captured.append(outcome)
        return outcome

    with patch.object(service_module, "orchestrate_schedule_run", observe):
        ScheduleService(conn).run_schedule(batch_ids or ["B2"], start_dt="2026-09-08 08:30:00", simulate=True)
    outcome = captured[0]
    schedule_rows = {row.op_id: asdict(row) for row in outcome.results}
    for row in schedule_rows.values():
        row["start_time"] = row["start_time"].strftime("%Y-%m-%d %H:%M:%S")
        row["end_time"] = row["end_time"].strftime("%Y-%m-%d %H:%M:%S")
    return schedule_rows, outcome.result_summary_obj
