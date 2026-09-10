"""Explicit skills constrain future assignments without rewriting historical facts."""

from dataclasses import replace

import pytest

from core.algorithm_runtime.auto_assign_contract import AUTO_ASSIGN_REASON_NO_OPERATOR_CANDIDATE
from core.algorithms import GreedyScheduler
from core.services.personnel.operator_qualification import (
    OperatorQualificationError,
    OperatorQualificationService,
    validate_fixed_operator_qualifications,
)
from core.services.scheduler.calendar_service import CalendarService
from core.services.scheduler.config.config_service import ConfigService
from core.services.scheduler.resource_pool_builder import build_resource_pool
from core.services.scheduler.schedule_service import ScheduleService
from data.repositories.operator_machine_repo import OperatorMachineRepository
from tests.workbench.identity_metadata_support import insert_row, table_rows
from tests.workbench.operator_qualification_support import (
    BASE_TIME,
    CASES,
    auto_attempt,
    build_pool,
    collect_input,
    database_state,
    qualification_database,
    register_case,
    seed_protected_plan,
)


@pytest.mark.parametrize("authorized,declared,skills,eligible,reason", CASES)
def test_pool_and_real_auto_selection_use_authorization_intersect_skills(qualification_conn, authorized, declared, skills, eligible, reason):
    conn = qualification_conn
    register_case(conn, authorized, declared, skills)
    before, changes = database_state(conn), conn.total_changes
    pool = build_pool(conn)
    assert pool["machines_by_op_type"] == {"TURN": ["M1"]}
    assert pool["operators_by_machine"] == ({"M1": ["O1"]} if eligible else {})
    assert pool["machines_by_operator"] == ({"O1": ["M1"]} if eligible else {})
    attempt = auto_attempt(conn, pool)
    assert (attempt.machine_id, attempt.operator_id) == (("M1", "O1") if eligible else ("", ""))
    if not eligible:
        assert attempt.reason == AUTO_ASSIGN_REASON_NO_OPERATOR_CANDIDATE
    auth_repo = OperatorMachineRepository(conn)
    assert auth_repo.exists("O1", "M1") is authorized
    assert len(auth_repo.list_by_operator("O1")) == int(authorized)
    assert database_state(conn) == before and conn.total_changes == changes


@pytest.mark.parametrize("authorized,declared,skills,eligible,reason", CASES)
def test_manual_assignment_has_same_qualification_contract(qualification_conn, authorized, declared, skills, eligible, reason):
    conn = qualification_conn
    register_case(conn, authorized, declared, skills)
    svc = ScheduleService(conn)
    before = database_state(conn)
    if eligible:
        updated = svc.update_internal_operation(10, machine_id="M1", operator_id="O1", setup_hours=0, unit_hours=1)
        assert updated.machine_id == "M1" and updated.operator_id == "O1"
    else:
        with pytest.raises(OperatorQualificationError) as error:
            svc.update_internal_operation(10, machine_id="M1", operator_id="O1", setup_hours=0, unit_hours=1)
        assert error.value.details is not None
        assert error.value.details["reason"] == reason
        assert database_state(conn) == before
    assert not conn.in_transaction


@pytest.mark.parametrize("authorized,declared,skills,eligible,reason", CASES)
@pytest.mark.parametrize("auto", ("yes", "no"))
def test_saved_fixed_pair_is_checked_before_algorithm_never_silently_reassigned(qualification_conn, authorized, declared, skills, eligible, reason, auto):
    conn = qualification_conn
    register_case(conn, authorized, declared, skills)
    ConfigService(conn).set_auto_assign_enabled(auto)
    conn.execute("UPDATE BatchOperations SET machine_id='M1',operator_id='O1' WHERE id=10")
    conn.commit()
    before = database_state(conn)
    if eligible:
        collected = collect_input(conn)
        assert collected.missing_internal_resource_op_ids == set()
        assert [(op.machine_id, op.operator_id) for op in collected.algo_ops_to_schedule] == [("M1", "O1")]
    else:
        with pytest.raises(OperatorQualificationError) as error:
            ScheduleService(conn).run_schedule(["B1"], start_dt=BASE_TIME)
        assert error.value.details is not None
        assert error.value.details["reason"] == reason
        assert error.value.field == ("\u8bbe\u5907/\u4eba\u5458" if reason == "operator_machine_not_authorized" else "operator_qualification")
    assert database_state(conn) == before and not conn.in_transaction


@pytest.mark.parametrize("dispatch_mode", ("batch_order", "sgs"))
def test_both_dispatch_modes_receive_only_eligible_links(qualification_conn, dispatch_mode):
    conn = qualification_conn
    register_case(conn, True, 1, [])
    insert_row(conn, "Operators", {"operator_id": "O2", "name": "qualified"})
    insert_row(conn, "OperatorMachine", {"operator_id": "O2", "machine_id": "M1", "skill_level": "beginner", "is_primary": "no"})
    insert_row(conn, "OperatorSkill", {"operator_id": "O2", "op_type_id": "TURN"})
    conn.commit()
    svc = ScheduleService(conn)
    operations = svc.op_repo.list_by_batch("B1")
    before = database_state(conn)
    scheduler = GreedyScheduler(calendar_service=CalendarService(conn), config_service=ConfigService(conn))
    rows, summary, _strategy, _params = scheduler.schedule(
        operations=operations, batches={"B1": svc.batch_repo.get("B1")}, start_dt=BASE_TIME,
        resource_pool=build_pool(conn), dispatch_mode=dispatch_mode, dispatch_rule="slack",
    )
    assert summary.success and [(row.machine_id, row.operator_id) for row in rows] == [("M1", "O2")]
    assert database_state(conn) == before


def test_skill_rank_metadata_never_overwrites_authorization_rank(qualification_conn):
    conn = qualification_conn
    register_case(conn, True, 1, ["TURN"])
    insert_row(conn, "Operators", {"operator_id": "O2", "name": "second"})
    insert_row(conn, "OperatorMachine", {"operator_id": "O2", "machine_id": "M1", "skill_level": "beginner", "is_primary": "no"})
    insert_row(conn, "OperatorSkill", {"operator_id": "O2", "op_type_id": "TURN", "skill_level": "expert", "is_primary": "yes"})
    conn.commit()
    before = database_state(conn)
    pool = build_pool(conn)
    assert pool["pair_rank"] == {("O1", "M1"): 0, ("O2", "M1"): 12}
    assert pool["operators_by_machine"] == {"M1": ["O1", "O2"]}
    assert auto_attempt(conn, pool).operator_id == "O1"
    assert database_state(conn) == before


def test_changed_skills_apply_on_next_query_without_touching_original_facts(qualification_conn):
    conn = qualification_conn
    seed_protected_plan(conn, "processing")
    svc, qualification = ScheduleService(conn), OperatorQualificationService(conn)
    old_facts = {table: table_rows(conn, table) for table in (
        "OperatorMachine", "BatchOperations", "Schedule", "ScheduleHistory", "OperationExecutionEvents", "Operators",
    )}
    for op_type in ("TURN", "MILL", "TURN"):
        conn.execute("UPDATE OperatorSkill SET op_type_id=? WHERE operator_id='O1'", (op_type,))
        conn.commit()
        before = database_state(conn)
        assert qualification.load(["O1"])["O1"] == {op_type}
        pool = build_pool(conn, svc)
        assert ("O1" in pool["operators_by_machine"].get("M1", [])) is (op_type == "TURN")
        assert {table: table_rows(conn, table) for table in old_facts} == old_facts
        assert database_state(conn) == before
    skill = dict(conn.execute("SELECT * FROM OperatorSkill WHERE operator_id='O1'").fetchone())
    assert (skill["skill_level"], skill["is_primary"], skill["created_at"]) == ("beginner", "no", "2020-01-02 03:04:05")


@pytest.mark.parametrize("protection", ("frozen", "processing", "completed"))
def test_later_skill_removal_does_not_rewrite_protected_plan_or_actual_events(qualification_conn, protection):
    conn = qualification_conn
    seed_protected_plan(conn, protection)
    conn.execute("DELETE FROM OperatorSkill WHERE operator_id='O1'")
    conn.commit()
    before = database_state(conn)
    collected = collect_input(conn)
    assert [op.id for op in collected.algo_ops_to_schedule] == [20]
    assert 10 in {row["op_id"] for row in collected.seed_results}
    assert 10 in collected.frozen_op_ids if protection == "frozen" else 10 in (collected.execution_fixed_op_ids | collected.execution_completed_op_ids)
    assert database_state(conn) == before
    old_op = tuple(conn.execute("SELECT * FROM BatchOperations WHERE id=10").fetchone())
    old_plan = table_rows(conn, "Schedule")
    old_events, old_auth = table_rows(conn, "OperationExecutionEvents"), table_rows(conn, "OperatorMachine")
    result = ScheduleService(conn).run_schedule(["B1"], start_dt=BASE_TIME)
    assert result["version"] > 1
    assert tuple(conn.execute("SELECT * FROM BatchOperations WHERE id=10").fetchone()) == old_op
    assert [tuple(row) for row in conn.execute("SELECT * FROM Schedule WHERE version=1 ORDER BY rowid")] == old_plan
    assert table_rows(conn, "OperationExecutionEvents") == old_events
    assert table_rows(conn, "OperatorMachine") == old_auth
    row = conn.execute("SELECT machine_id,operator_id,lock_status FROM Schedule WHERE version=? AND op_id=10", (result["version"],)).fetchone()
    assert tuple(row) == ("M1", "O1", "locked")


@pytest.mark.parametrize("table", ("WorkbenchOperatorProfiles", "OperatorSkill"))
@pytest.mark.parametrize("entry", ("pool", "manual", "fixed"))
def test_missing_qualification_tables_fail_closed_without_repair(qualification_conn, table, entry):
    conn = qualification_conn
    register_case(conn, True, None, [])
    conn.execute(f'DROP TABLE "{table}"')
    conn.commit()
    before = database_state(conn)
    with pytest.raises(OperatorQualificationError) as error:
        if entry == "pool":
            build_pool(conn)
        elif entry == "manual":
            ScheduleService(conn).update_internal_operation(10, machine_id="M1", operator_id="O1")
        else:
            op = replace(ScheduleService(conn).get_operation(10), machine_id="M1", operator_id="O1")
            validate_fixed_operator_qualifications(conn, [op])
    assert error.value.details is not None
    assert error.value.details["reason"] == "operator_qualification_data_invalid"
    assert error.value.__cause__ is not None
    assert database_state(conn) == before


@pytest.mark.parametrize("bad", ("marker", "unknown_skill", "external_skill", "blank_skill"))
def test_corrupt_qualification_facts_never_restore_legacy_eligibility(qualification_conn, bad):
    conn = qualification_conn
    register_case(conn, True, 1, [])
    if bad == "marker":
        conn.execute("PRAGMA ignore_check_constraints=ON")
        conn.execute("UPDATE WorkbenchOperatorProfiles SET skills_declared=2")
        conn.execute("PRAGMA ignore_check_constraints=OFF")
    else:
        code = {"unknown_skill": "UNKNOWN", "external_skill": "EXT", "blank_skill": " "}[bad]
        conn.execute("PRAGMA foreign_keys=OFF")
        insert_row(conn, "OperatorSkill", {"operator_id": "O1", "op_type_id": code})
        conn.commit()
        conn.execute("PRAGMA foreign_keys=ON")
    conn.commit()
    before = database_state(conn)
    meta = {}
    with pytest.raises(OperatorQualificationError) as error:
        build_resource_pool(ScheduleService(conn), cfg=ConfigService(conn).get_snapshot(),
                            algo_ops=ScheduleService(conn).op_repo.list_by_batch("B1"), meta=meta)
    assert error.value.details is not None
    assert error.value.details["reason"] == "operator_qualification_data_invalid"
    assert meta["resource_pool_build_ok"] is False
    assert database_state(conn) == before


def test_fixed_operator_without_machine_cannot_bypass_empty_skills(qualification_conn):
    conn = qualification_conn
    register_case(conn, True, 1, [])
    conn.execute("UPDATE BatchOperations SET operator_id='O1' WHERE id=10")
    conn.commit()
    before = database_state(conn)
    with pytest.raises(OperatorQualificationError) as error:
        collect_input(conn)
    assert error.value.details is not None
    assert error.value.details["reason"] == "operator_skill_not_qualified"
    assert database_state(conn) == before


def test_large_qualification_query_chunks_and_does_not_invent_skill_records(qualification_conn):
    conn = qualification_conn
    ids = ["many-" + str(index) for index in range(1001)]
    conn.executemany("INSERT INTO Operators(operator_id,name) VALUES (?,?)", [(oid, oid) for oid in ids])
    conn.execute("INSERT INTO WorkbenchOperatorProfiles(operator_id,skills_declared) VALUES (?,1)", (ids[-1],))
    conn.commit()
    before, changes = database_state(conn), conn.total_changes
    facts = OperatorQualificationService(conn).load(ids)
    assert set(facts) == set(ids) and facts[ids[-1]] == set()
    assert all(facts[oid] is None for oid in ids[:-1])
    assert database_state(conn) == before and conn.total_changes == changes


def test_fixed_machine_cannot_assign_someone_qualified_for_the_machine_but_not_the_operation(qualification_conn):
    conn = qualification_conn
    register_case(conn, True, 1, ["TURN"])
    conn.execute("UPDATE BatchOperations SET machine_id='M1',op_type_id='MILL' WHERE id=10")
    conn.commit()
    before = database_state(conn)
    attempt = auto_attempt(conn, build_pool(conn))
    assert (attempt.machine_id, attempt.operator_id) == ("", "")
    assert database_state(conn) == before


@pytest.mark.parametrize("declared", (None, 1))
def test_missing_operation_type_cannot_be_inferred_from_machine_for_declared_skills(qualification_conn, declared):
    conn = qualification_conn
    register_case(conn, True, declared, [] if declared is None else ["TURN"])
    conn.execute("UPDATE BatchOperations SET machine_id='M1',op_type_id=NULL WHERE id=10")
    conn.commit()
    before = database_state(conn)
    if declared is None:
        attempt = auto_attempt(conn, build_pool(conn))
        assert (attempt.machine_id, attempt.operator_id) == ("M1", "O1")
    else:
        with pytest.raises(OperatorQualificationError) as error:
            build_pool(conn)
        assert error.value.details is not None
        assert error.value.details["reason"] == "operator_qualification_data_invalid"
    assert database_state(conn) == before


def test_actual_started_operation_with_old_missing_fields_is_not_requalified(qualification_conn):
    conn = qualification_conn
    seed_protected_plan(conn, "processing")
    conn.execute("UPDATE BatchOperations SET op_type_id=NULL,operator_id=NULL WHERE id=10")
    conn.execute("DELETE FROM OperatorSkill WHERE operator_id='O1'")
    conn.commit()
    before = database_state(conn)
    collected = collect_input(conn)
    assert [op.id for op in collected.algo_ops_to_schedule] == [20]
    seed = next(row for row in collected.seed_results if row["op_id"] == 10)
    assert (seed["machine_id"], seed["operator_id"], seed["start_time"]) == ("M1", "O1", BASE_TIME.replace(minute=10))
    assert database_state(conn) == before
