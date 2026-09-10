"""Deterministic identity boundaries, not a claimed reproduction of the BP fault."""

import sqlite3
from contextlib import closing

import pytest

from core.infrastructure.database import get_connection
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_plan_identity_schema import install_plan_identity
from core.infrastructure.workbench_plan_identity_write_guard import contract_issues, install, objects
from core.models.workbench_plan_reference import WorkbenchPlanLocator, WorkbenchPlanReferenceError
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository
from tests.workbench.plan_catalog_support import END, START
from tests.workbench.plan_identity_insert_collision_support import (
    REF_TABLES,
    RefProbe,
    insert_many_operations,
    operation,
    seed_parents,
    source_refs,
)
from tests.workbench.plan_identity_support import (
    all_refs,
    legacy_schema,
    load_v24_schema,
    plan_rows,
    replace_row,
    seed_plans,
    table_snapshot,
)
from tests.workbench.plan_identity_write_guard_support import (
    assert_frozen_hashes,
    capture_collision,
    exact_snapshot,
    frozen_v29_connection,
    schema_snapshot,
)


@pytest.fixture
def guarded_conn(tmp_path):
    """Real frozen v29, then explicitly apply only the additive guard step."""
    with closing(frozen_v29_connection(tmp_path / "frozen-v29.sqlite")) as conn:
        install(conn)
        yield conn


@pytest.mark.parametrize("recursive", (0, 1))
@pytest.mark.parametrize("mode", ("single", "multi", "backfill"))
def test_each_source_row_gets_one_distinct_evaluation(guarded_conn, mem_conn, recursive, mode):
    conn = load_v24_schema(mem_conn) if mode == "backfill" else guarded_conn
    seed_parents(conn)
    conn.execute(f"PRAGMA recursive_triggers={recursive}")
    if mode == "backfill":
        legacy_schema(conn)
        insert_many_operations(conn, 257)
        before = table_snapshot(conn)
        probe = RefProbe(conn, observe=False)
        install_plan_identity(conn)
        assert probe.draws == [ref for _, ref, _ in source_refs(conn)]
        assert len(probe.draws) == len(set(probe.draws)) == 257
        # Install once more on the unchanged DB must not issue or rotate any ref.
        refs = source_refs(conn)
        install_plan_identity(conn)
        assert len(probe.draws) == 257 and source_refs(conn) == refs
        after = table_snapshot(conn)
        assert all(after[name] == rows for name, rows in before.items())
    else:
        probe = RefProbe(conn)
        if mode == "multi":
            insert_many_operations(conn, 257)
        else:
            for seq in range(1, 258):
                operation(conn, seq)
        probe.assert_one_draw_per_attempt()
        assert len(probe.draws) == 257
    refs = source_refs(conn)
    assert len(refs) == len({ref for _, ref, _ in refs}) == 257
    assert {active for _, _, active in refs} == {1}
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


@pytest.mark.parametrize("recursive", (0, 1))
@pytest.mark.parametrize("arrival", ("plan_first", "rows_first"))
def test_nested_task_insert_select_evaluates_random_per_pair(guarded_conn, recursive, arrival):
    conn = guarded_conn
    seed_parents(conn)
    insert_many_operations(conn, 17)
    conn.execute(f"PRAGMA recursive_triggers={recursive}")
    probe = RefProbe(conn)
    if arrival == "plan_first":
        conn.execute("INSERT INTO ScheduleHistory(version,strategy) VALUES (1,'probe')")
    conn.execute("INSERT INTO Schedule(version,op_id,start_time,end_time) "
                 "SELECT 1,id,?,? FROM BatchOperations", (START, END))
    if arrival == "rows_first":
        conn.execute("INSERT INTO ScheduleHistory(version,strategy) VALUES (1,'probe')")
    probe.assert_one_draw_per_attempt()
    assert len([row for row in probe.attempts if row[0] in REF_TABLES]) == 35
    assert len(probe.draws) == 35 + 2 * 17
    tasks = list(conn.execute("SELECT ref,plan_ref,row_ref FROM WorkbenchTaskRefs"))
    assert len(tasks) == len({row[0] for row in tasks}) == 17
    assert len({row[1] for row in tasks}) == 1
    assert len({row[2] for row in tasks}) == 17
    maps = [tuple(row) for row in conn.execute(
        "SELECT item_ref,category,task_ref FROM WorkbenchDashboardItems WHERE task_ref IS NOT NULL")]
    assert len(maps) == 2 * 17
    assert {(row[1], row[2]) for row in maps} == {
        (category, task[0]) for task in tasks for category in ("actual", "downtime")}
    assert {row[0] for row in maps} == {ref for table, ref in probe.attempts if table == "WorkbenchDashboardItems"}
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


@pytest.mark.parametrize("retired", (False, True))
@pytest.mark.parametrize("verb", ("INSERT", "INSERT OR REPLACE"))
@pytest.mark.parametrize("recursive", (0, 1))
def test_forced_source_collision_aborts_without_retry_or_data_loss(guarded_conn, retired, verb, recursive):
    # The original two REPLACE probes stay strict; this does not establish the BP cause.
    conn = guarded_conn
    conn.execute(f"PRAGMA recursive_triggers={recursive}")
    seed_parents(conn)
    operation(conn, 13)
    duplicate = source_refs(conn)[0][1]
    if retired:
        conn.execute("DELETE FROM BatchOperations WHERE seq=13")
    if verb == "INSERT OR REPLACE":
        operation(conn, 15)
    conn.commit()
    operation(conn, 14)
    before = exact_snapshot(conn)
    probe = RefProbe(conn, outputs=[bytes.fromhex(duplicate)])
    with pytest.raises(sqlite3.IntegrityError, match=r"UNIQUE constraint failed: WorkbenchPlanSourceRefs.ref"):
        operation(conn, 15, verb=verb)
    assert probe.draws == [duplicate]
    assert probe.attempts == [("WorkbenchPlanSourceRefs", duplicate)]
    assert conn.in_transaction
    assert exact_snapshot(conn) == before
    # The previous successful statement still exists, as it would before teardown.
    assert conn.execute("SELECT count(*) FROM BatchOperations WHERE seq=14").fetchone()[0] == 1


def test_forced_collision_rolls_back_all_rows_of_one_insert_select(guarded_conn):
    conn = guarded_conn
    seed_parents(conn)
    operation(conn, 99)
    duplicate = source_refs(conn)[0][1]
    before = table_snapshot(conn)
    distinct = bytes.fromhex("12" * 24)
    probe = RefProbe(conn, outputs=[distinct, bytes.fromhex(duplicate)])
    with pytest.raises(sqlite3.IntegrityError, match=r"WorkbenchPlanSourceRefs.ref"):
        insert_many_operations(conn, 2)
    assert probe.draws == [distinct.hex(), duplicate]
    assert table_snapshot(conn) == before


@pytest.mark.parametrize("verb", ("UPDATE", "UPDATE OR REPLACE"))
@pytest.mark.parametrize("recursive", (0, 1))
def test_identity_rotating_update_collision_retains_previous_binding(guarded_conn, verb, recursive):
    conn = guarded_conn
    conn.execute(f"PRAGMA recursive_triggers={recursive}")
    seed_parents(conn)
    operation(conn, 14)
    duplicate = source_refs(conn)[0][1]
    conn.execute("INSERT INTO ScheduleCandidate(version,candidate_key,candidate_label,candidate_kind,status) "
                 "VALUES (1,'before','Before','baseline','completed')")
    before = table_snapshot(conn)
    probe = RefProbe(conn, outputs=[bytes.fromhex(duplicate)])
    with pytest.raises(sqlite3.IntegrityError, match=r"WorkbenchPlanSourceRefs.ref"):
        conn.execute(verb + " ScheduleCandidate SET candidate_key='after'")
    assert probe.draws == [duplicate]
    assert table_snapshot(conn) == before


def test_ordinary_operation_updates_do_not_evaluate_random_or_rotate_refs(guarded_conn):
    conn = guarded_conn
    seed_parents(conn)
    operation(conn, 15)
    before = source_refs(conn)
    probe = RefProbe(conn, outputs=[])
    conn.execute("UPDATE BatchOperations SET unit_hours=2,op_type_name='Renamed'")
    assert probe.draws == [] and probe.attempts == []
    assert source_refs(conn) == before


def test_equal_sql_timestamps_do_not_share_native_random_refs(guarded_conn):
    conn = guarded_conn
    seed_parents(conn)
    conn.create_function("current_timestamp", 0, lambda: "2026-09-09 20:21:26", deterministic=True)
    insert_many_operations(conn, 17)
    assert conn.execute("SELECT count(DISTINCT created_at) FROM BatchOperations").fetchone()[0] == 1
    refs = source_refs(conn)
    assert len(refs) == len({ref for _, ref, _ in refs}) == 17


def test_observer_can_capture_attempts_without_replacing_native_random(guarded_conn):
    conn = guarded_conn
    seed_parents(conn)
    probe = RefProbe(conn, native_random=True)
    operation(conn, 15)
    ref = source_refs(conn)[0][1]
    assert probe.draws == []
    assert probe.attempts == [("WorkbenchPlanSourceRefs", ref)]


def test_teardown_rollback_cannot_retain_the_failing_attempt(guarded_conn, tmp_path):
    seed_parents(guarded_conn)
    operation(guarded_conn, 13)
    guarded_conn.commit()
    before = table_snapshot(guarded_conn)
    path = tmp_path / "collision.sqlite"
    conn = sqlite3.connect(str(path))
    try:
        guarded_conn.backup(conn)
        operation(conn, 14)
        duplicate = source_refs(conn)[0][1]
        probe = RefProbe(conn, outputs=[bytes.fromhex(duplicate)])
        with pytest.raises(sqlite3.IntegrityError, match=r"WorkbenchPlanSourceRefs.ref"):
            operation(conn, 15)
        assert len(source_refs(conn)) == 2 and probe.attempts
    finally:
        conn.close()
    reopened = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    try:
        assert table_snapshot(reopened) == before
    finally:
        reopened.close()


@pytest.mark.parametrize("recursive", (0, 1))
@pytest.mark.parametrize("retired", (False, True))
def test_replace_collision_rolls_back_the_whole_business_transaction(guarded_conn, recursive, retired):
    conn = guarded_conn
    conn.execute(f"PRAGMA recursive_triggers={recursive}")
    seed_parents(conn)
    operation(conn, 13)
    duplicate = source_refs(conn)[0][1]
    if retired:
        conn.execute("DELETE FROM BatchOperations WHERE seq=13")
    operation(conn, 15)
    conn.commit()
    committed = exact_snapshot(conn)
    with pytest.raises(sqlite3.IntegrityError, match=r"WorkbenchPlanSourceRefs.ref"):
        with TransactionManager(conn).transaction():
            operation(conn, 14)
            probe = RefProbe(conn, outputs=[bytes.fromhex(duplicate)])
            operation(conn, 15, verb="INSERT OR REPLACE")
    assert not conn.in_transaction
    assert probe.draws == [duplicate]
    assert exact_snapshot(conn) == committed
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert not conn.execute("PRAGMA foreign_key_check").fetchall()


@pytest.mark.parametrize("recursive", (0, 1))
@pytest.mark.parametrize("retired", (False, True))
def test_nested_task_ref_collision_never_overwrites_prior_task(guarded_conn, recursive, retired):
    conn = guarded_conn
    conn.execute(f"PRAGMA recursive_triggers={recursive}")
    seed_plans(conn)
    row = conn.execute("SELECT * FROM Schedule WHERE version=2").fetchone()
    repo = WorkbenchPlanIdentityRepository(conn)
    locator = WorkbenchPlanLocator(2, "adopted")
    plan = repo.get_plan_ref(locator)
    duplicate = repo.get_task_refs(plan, plan_rows(conn, locator))[row["id"]]
    if retired:
        conn.execute("DELETE FROM Schedule WHERE id=?", (row["id"],))
    conn.commit()
    before = exact_snapshot(conn)
    probe = RefProbe(conn, outputs=[bytes.fromhex("12" * 24), bytes.fromhex(duplicate)])
    with pytest.raises(sqlite3.IntegrityError, match=r"WorkbenchTaskRefs.ref"):
        with TransactionManager(conn).transaction():
            conn.execute("UPDATE BatchOperations SET unit_hours=2")
            replace_row(conn, "Schedule", row)
    assert probe.draws == ["12" * 24, duplicate]
    assert probe.attempts == [("WorkbenchPlanSourceRefs", "12" * 24), ("WorkbenchTaskRefs", duplicate)]
    assert exact_snapshot(conn) == before


@pytest.mark.parametrize("recursive", (0, 1))
@pytest.mark.parametrize("kind,table,primary", [
    ("operation", "BatchOperations", "id"),
    ("candidate", "ScheduleCandidate", "id"),
    ("selection", "ScheduleCandidateSelection", "id"),
    ("scenario", "ScheduleAdjustmentScenario", "scenario_id"),
    ("schedule_row", "Schedule", "id"),
    ("candidate_row", "ScheduleCandidateRows", "id"),
    ("scenario_row", "ScheduleAdjustmentScenarioRow", "id"),
])
def test_same_number_replace_allocates_new_instance_and_keeps_history(guarded_conn, recursive, kind, table, primary):
    conn = guarded_conn
    conn.execute(f"PRAGMA recursive_triggers={recursive}")
    seed_plans(conn)
    raw = conn.execute('SELECT * FROM "' + table + '" ORDER BY "' + primary + '" DESC LIMIT 1').fetchone()
    before = {row["ref"]: dict(row) for row in conn.execute("SELECT * FROM WorkbenchPlanSourceRefs")}
    tasks = [tuple(row) for row in conn.execute("SELECT * FROM WorkbenchTaskRefs ORDER BY ref")]
    old = next(row for row in before.values() if row["kind"] == kind and row["source_key"] == str(raw[primary]) and row["active"])
    replace_row(conn, table, raw)
    current = conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind=? AND source_key=? AND active=1",
                           (kind, str(raw[primary]))).fetchone()[0]
    assert current not in before and current != old["ref"]
    for ref, previous in before.items():
        kept = dict(conn.execute("SELECT * FROM WorkbenchPlanSourceRefs WHERE ref=?", (ref,)).fetchone())
        if ref == old["ref"]:
            assert kept["active"] == 0
        assert dict(kept, active=previous["active"]) == previous
    for task in tasks:
        assert tuple(conn.execute("SELECT * FROM WorkbenchTaskRefs WHERE ref=?", (task[0],)).fetchone()) == task
    if kind.endswith("_row"):
        prior_tasks = {task[0] for task in tasks if task[2] == old["ref"]}
        new_tasks = {row[0] for row in conn.execute("SELECT ref FROM WorkbenchTaskRefs WHERE row_ref=?", (current,))}
        assert prior_tasks and new_tasks and prior_tasks.isdisjoint(new_tasks)
    repo = WorkbenchPlanIdentityRepository(conn)
    if kind == "operation":
        assert repo.get_operation_refs([raw[primary]])[raw[primary]] == current
    if kind in ("selection", "scenario"):
        with pytest.raises(WorkbenchPlanReferenceError):
            repo.resolve_plan(old["ref"])
    assert not conn.execute("PRAGMA foreign_key_check").fetchall()


def test_guard_upgrade_is_additive_idempotent_and_survives_reopen(tmp_path):
    hashes = assert_frozen_hashes()
    path = tmp_path / "upgrade.sqlite"
    with closing(frozen_v29_connection(path)) as conn:
        seed_plans(conn)
        facts, ddl, refs = exact_snapshot(conn), schema_snapshot(conn), all_refs(conn)
        probe = RefProbe(conn, outputs=[])
        assert len(contract_issues(conn)) == 2
        install(conn)
        install(conn)
        assert exact_snapshot(conn) == facts and all_refs(conn) == refs
        assert probe.draws == [] and probe.attempts == []
        assert [row for row in schema_snapshot(conn) if row[1] not in objects()] == ddl
    with closing(get_connection(str(path))) as conn:
        conn.execute("PRAGMA query_only=ON")
        assert not contract_issues(conn)
        assert exact_snapshot(conn) == facts and all_refs(conn) == refs
    assert assert_frozen_hashes() == hashes


@pytest.mark.parametrize("damage", ("partial", "bad_guard", "lost_active_ref", "lost_clock"))
def test_guard_upgrade_rejects_damage_without_repair(guarded_conn, damage):
    conn = guarded_conn
    seed_plans(conn)
    name = next(iter(objects()))
    if damage in ("partial", "bad_guard"):
        conn.execute('DROP TRIGGER "' + name + '"')
        if damage == "bad_guard":
            conn.execute('CREATE TRIGGER "' + name + '" BEFORE INSERT ON WorkbenchPlanSourceRefs BEGIN SELECT 1; END')
    elif damage == "lost_active_ref":
        conn.execute("UPDATE WorkbenchPlanSourceRefs SET active=0 WHERE kind='operation'")
    else:
        conn.execute("DELETE FROM WorkbenchPlanIdentityClock")
    conn.commit()
    before = exact_snapshot(conn), schema_snapshot(conn)
    with pytest.raises(RuntimeError):
        install(conn)
    assert (exact_snapshot(conn), schema_snapshot(conn)) == before


def test_guard_upgrade_ddl_failure_rolls_back_first_trigger(tmp_path):
    with closing(frozen_v29_connection(tmp_path / "ddl-failure.sqlite")) as conn:
        seed_plans(conn)
        before = exact_snapshot(conn), schema_snapshot(conn)
        second = list(objects())[1]

        def authorizer(action, name, *unused):
            return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_CREATE_TRIGGER and name == second else sqlite3.SQLITE_OK

        conn.set_authorizer(authorizer)
        try:
            with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
                install(conn)
        finally:
            # Python 3.8 requires a callable; None support arrived later.
            conn.set_authorizer(lambda *args: sqlite3.SQLITE_OK)
        assert not conn.in_transaction
        assert (exact_snapshot(conn), schema_snapshot(conn)) == before


def test_guard_upgrade_does_not_commit_the_callers_business_transaction(tmp_path):
    with closing(frozen_v29_connection(tmp_path / "caller-rollback.sqlite")) as conn:
        seed_parents(conn)
        before = exact_snapshot(conn), schema_snapshot(conn)
        with pytest.raises(RuntimeError, match="caller rejected"):
            with TransactionManager(conn).transaction():
                operation(conn, 13)
                install(conn)
                assert not contract_issues(conn) and conn.in_transaction
                raise RuntimeError("caller rejected")
        assert not conn.in_transaction
        assert (exact_snapshot(conn), schema_snapshot(conn)) == before


@pytest.mark.parametrize("retired", (False, True))
def test_frozen_v29_unfixed_replace_baseline_is_not_current(tmp_path, retired):
    result = capture_collision(tmp_path, guarded=False, retired=retired, recursive=0)
    assert result["schema_version"] == 29
    assert result["error"] is None and not result["statement_unchanged"]
    assert result["rollback_unchanged"] and result["transaction_open"]
    assert len(result["draws"]) == 1
    assert result["integrity_check"] == "ok" and result["foreign_key_check"] == []
