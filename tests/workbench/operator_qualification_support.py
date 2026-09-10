"""Current-schema fixtures for prospective qualifications and historical facts."""

from datetime import datetime

import pytest

from core.algorithms.greedy.auto_assign import auto_assign_internal_resources_attempt
from core.infrastructure.migration_state import CURRENT_SCHEMA_VERSION, ensure_schema_version, get_schema_version
from core.services.scheduler.calendar_service import CalendarService
from core.services.scheduler.config.config_service import ConfigService
from core.services.scheduler.operation_execution_feedback_service import (
    ExecutionFeedbackContext,
    OperationExecutionFeedbackService,
)
from core.services.scheduler.resource_pool_builder import (
    build_resource_pool,
    extend_downtime_map_for_resource_pool,
    load_machine_downtimes,
)
from core.services.scheduler.run.freeze_window import build_freeze_window_seed
from core.services.scheduler.run.schedule_input_builder import build_algo_operations
from core.services.scheduler.run.schedule_input_collector import collect_schedule_run_input
from core.services.scheduler.schedule_service import ScheduleService
from tests.workbench.identity_metadata_support import business_snapshot, insert_row, schema_snapshot, table_rows

BASE_TIME = datetime(2026, 9, 9, 8)
CASES = [
    pytest.param(False, 1, ["TURN"], False, "operator_machine_not_authorized", id="skill-without-authorization"),
    pytest.param(True, None, [], True, None, id="legacy-authorization-only"),
    pytest.param(True, 1, [], False, "operator_skill_not_qualified", id="explicit-empty"),
    pytest.param(True, 1, ["TURN"], True, None, id="matching"),
    pytest.param(True, 1, ["MILL"], False, "operator_skill_not_qualified", id="mismatch"),
    pytest.param(True, None, ["TURN"], True, None, id="existing-skill-without-profile"),
    pytest.param(True, None, ["MILL"], False, "operator_skill_not_qualified", id="existing-mismatching-skill"),
    pytest.param(True, 0, [], True, None, id="profile-without-declaration"),
    pytest.param(True, 0, ["MILL"], False, "operator_skill_not_qualified", id="records-override-zero-marker"),
]


@pytest.fixture(name="qualification_conn")
def qualification_database(schema_conn):
    conn = schema_conn
    ensure_schema_version(conn)
    assert get_schema_version(conn) == CURRENT_SCHEMA_VERSION
    for code, category in (("TURN", "internal"), ("MILL", "internal"), ("EXT", "external")):
        insert_row(conn, "OpTypes", {"op_type_id": code, "name": code, "category": category})
    insert_row(conn, "Machines", {"machine_id": "M1", "name": "machine", "op_type_id": "TURN"})
    insert_row(conn, "Operators", {"operator_id": "O1", "name": "operator"})
    insert_row(conn, "Parts", {"part_no": "P1", "part_name": "part"})
    insert_row(conn, "Batches", {"batch_id": "B1", "part_no": "P1", "quantity": 1, "ready_status": "yes", "due_date": "2026-09-30"})
    insert_row(conn, "BatchOperations", {"id": 10, "op_code": "B1:10", "batch_id": "B1", "seq": 10,
                                        "op_type_id": "TURN", "op_type_name": "TURN", "source": "internal",
                                        "setup_hours": 0, "unit_hours": 1, "status": "pending"})
    conn.commit()
    config = ConfigService(conn)
    config.ensure_defaults()
    config.set_auto_assign_enabled("yes")
    config.set_freeze_window("no", 0)
    return conn


def register_case(conn, authorized, declared, skills):
    if authorized:
        insert_row(conn, "OperatorMachine", {"operator_id": "O1", "machine_id": "M1", "skill_level": "expert", "is_primary": "yes"})
    if declared is not None:
        insert_row(conn, "WorkbenchOperatorProfiles", {"operator_id": "O1", "skills_declared": declared})
    for code in skills:
        insert_row(conn, "OperatorSkill", {"operator_id": "O1", "op_type_id": code,
                                          "skill_level": "beginner", "is_primary": "no", "created_at": "2020-01-02 03:04:05"})
    conn.commit()


def database_state(conn):
    return (schema_snapshot(conn), business_snapshot(conn), table_rows(conn, "WorkbenchEntityRefs"),
            table_rows(conn, "WorkbenchCommandReceipts"))


def build_pool(conn, svc=None):
    svc = svc or ScheduleService(conn)
    pool, warnings = build_resource_pool(svc, cfg=ConfigService(conn).get_snapshot(), algo_ops=svc.op_repo.list_by_batch("B1"))
    assert pool is not None and not warnings
    return pool


def auto_attempt(conn, pool, *, op=None):
    svc = ScheduleService(conn)
    return auto_assign_internal_resources_attempt(
        calendar=CalendarService(conn), op=op or svc.op_repo.get(10), batch=svc.batch_repo.get("B1"),
        batch_progress={}, machine_timeline={}, operator_timeline={}, base_time=BASE_TIME,
        end_dt_exclusive=datetime(2026, 9, 30), machine_downtimes={}, resource_pool=pool,
        last_op_type_by_machine={}, machine_busy_hours={}, operator_busy_hours={},
    )


def collect_input(conn):
    return collect_schedule_run_input(
        ScheduleService(conn), batch_ids=["B1"], start_dt=BASE_TIME, enforce_ready=False,
        calendar_service_cls=CalendarService, config_service_cls=ConfigService,
        get_snapshot_with_strict_mode=lambda service, strict_mode: service.get_snapshot(strict_mode=strict_mode),
        build_algo_operations_fn=build_algo_operations, build_freeze_window_seed_fn=build_freeze_window_seed,
        load_machine_downtimes_fn=load_machine_downtimes, build_resource_pool_fn=build_resource_pool,
        extend_downtime_map_for_resource_pool_fn=extend_downtime_map_for_resource_pool,
    )


def seed_protected_plan(conn, protection):
    register_case(conn, True, 1, ["TURN"])
    insert_row(conn, "Machines", {"machine_id": "M2", "name": "second", "op_type_id": "MILL"})
    insert_row(conn, "Operators", {"operator_id": "O2", "name": "second"})
    insert_row(conn, "OperatorMachine", {"operator_id": "O2", "machine_id": "M2"})
    insert_row(conn, "BatchOperations", {"id": 20, "op_code": "B1:20", "batch_id": "B1", "seq": 20,
                                        "op_type_id": "MILL", "op_type_name": "MILL", "source": "internal",
                                        "setup_hours": 0, "unit_hours": 1, "status": "pending",
                                        "machine_id": "M2", "operator_id": "O2"})
    conn.execute("UPDATE BatchOperations SET machine_id='M1',operator_id='O1',status='scheduled' WHERE id=10")
    insert_row(conn, "ScheduleVersionSeq", {"version": 1})
    insert_row(conn, "ScheduleHistory", {"version": 1, "strategy": "priority_first", "batch_count": 1,
                                        "op_count": 2, "result_status": "success", "result_summary": "{}"})
    for schedule_id, op_id, suffix, start, end in (
        (100, 10, "1", "2026-09-09 08:00:00", "2026-09-09 09:00:00"),
        (101, 20, "2", "2026-09-11 09:00:00", "2026-09-11 10:00:00"),
    ):
        insert_row(conn, "Schedule", {"id": schedule_id, "op_id": op_id, "machine_id": "M" + suffix,
                                     "operator_id": "O" + suffix, "start_time": start, "end_time": end,
                                     "version": 1, "lock_status": "unlocked"})
    conn.commit()
    if protection == "frozen":
        ConfigService(conn).set_freeze_window("yes", 1)
        return
    feedback = OperationExecutionFeedbackService(conn)
    context = ExecutionFeedbackContext(
        schedule_version=1, schedule_id=100, op_id=10, batch_id="B1", expected_state_revision="10:0:0",
        created_by="qualification-test", idempotency_key="qualification-start", requested_plan_role="adopted",
        source_table="schedule", effective_plan_role="adopted", scenario_id=None,
    )
    started = feedback.start_operation(context, event_time="2026-09-09 08:10:00", operator_id="O1", machine_id="M1")
    if protection == "completed":
        from dataclasses import replace

        feedback.finish_operation(replace(context, expected_state_revision=started.state_revision, idempotency_key="qualification-finish"),
                                  event_time="2026-09-09 09:30:00", quantity_done=1)
    conn.execute("UPDATE BatchOperations SET status=? WHERE id=10", ("completed" if protection == "completed" else "processing",))
    conn.commit()
