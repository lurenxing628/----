"""Persistent identity lifecycle under real SQL, including damaged bindings."""

from __future__ import annotations

import re
import sqlite3
import time
from typing import Any, Dict

import pytest

from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.migrations import v24
from core.infrastructure.workbench_plan_identity_schema import (
    contract_issues,
    initialize_plan_identity,
    install,
    objects,
    plan_identity_initialization_sql,
)
from core.infrastructure.workbench_process_schema import workbench_process_contract_issues
from core.models.workbench_plan_reference import WorkbenchPlanLocator as Locator
from core.models.workbench_plan_reference import WorkbenchPlanReferenceError
from core.services.scheduler.workbench_plan_catalog import PlanCatalogLocator, build_plan_catalog
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository
from tests.workbench.plan_catalog_support import END, START, history, scenario, seed_operation, selection
from tests.workbench.plan_identity_support import (
    IDENTITY_TABLES,
    all_refs,
    dynamic_scale,
    exec_plan_objects,
    foreign_keys_off,
    installed_case,
    legacy_schema,
    load_v23_schema,
    load_v24_schema,
    plan_rows,
    replace_row,
    seed_plans,
    table_snapshot,
    use_legacy_process_triggers,
)
from tests.workbench.plan_persistent_identity_support import (
    assert_ignored_operation_conflicts,
    v26_identity_fixture,
)


@pytest.fixture(params=(False, True), ids=("fresh", "upgrade"))
def identity_case(request):
    conn = request.getfixturevalue("mem_conn" if request.param else "schema_conn")
    return installed_case(conn, legacy=request.param)


def test_upgrade_preserves_every_existing_table_field_and_is_idempotent(mem_conn):
    schema_conn = load_v23_schema(mem_conn)
    seed_plans(schema_conn)
    before = table_snapshot(schema_conn)
    ddl = schema_conn.execute("SELECT name, sql FROM sqlite_master WHERE type = 'table' ORDER BY name").fetchall()
    assert v24.run(schema_conn) == MigrationOutcome.APPLIED
    assert table_snapshot(schema_conn, IDENTITY_TABLES) == before
    assert [tuple(row) for row in ddl] == [tuple(row) for row in schema_conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type = 'table' AND name NOT IN (?, ?, ?) ORDER BY name", IDENTITY_TABLES)]
    refs = all_refs(schema_conn)
    after = table_snapshot(schema_conn)
    assert not contract_issues(schema_conn)
    assert v24.run(schema_conn) == MigrationOutcome.APPLIED
    assert table_snapshot(schema_conn) == after and all_refs(schema_conn) == refs


def test_refs_survive_reopen_and_queries_are_select_only(identity_case, tmp_path):
    conn, repo, _ = identity_case
    before = all_refs(conn)
    snapshot = table_snapshot(conn)
    lookups = [(key, value, plan_rows(conn, key)) for key, value in before.items() if key != "operations"]
    statements = []
    conn.set_trace_callback(statements.append)
    for locator, (ref, tasks), rows in lookups:
        assert repo.resolve_plan(ref) == locator
        assert repo.get_plan_ref(locator) == ref
        assert repo.get_task_refs(ref, rows) == tasks
    assert repo.get_operation_refs(before["operations"]) == before["operations"]
    assert repo.read_revision() > 0
    conn.set_trace_callback(None)
    submitted = [sql for sql in statements if not sql.startswith("--")]
    assert submitted and all(sql.lstrip().upper().startswith("SELECT") for sql in submitted)
    assert table_snapshot(conn) == snapshot
    conn.commit()
    with sqlite3.connect(str(tmp_path / "identity.sqlite")) as copy:
        conn.backup(copy)
    with sqlite3.connect(str(tmp_path / "identity.sqlite")) as reopened:
        reopened.row_factory = sqlite3.Row
        reopened.execute("PRAGMA query_only = ON")
        assert all_refs(reopened) == before


def test_plan_aliases_never_share_plan_or_task_refs(identity_case):
    conn, repo, ids = identity_case
    refs = all_refs(conn)
    public = []
    for locator, value in refs.items():
        if locator == "operations":
            continue
        ref, tasks = value
        public.extend([ref] + list(tasks.values()))
        assert repo.resolve_plan(ref) == locator
        assert repo.get_plan_ref(PlanCatalogLocator(locator.version, locator.plan_role, locator.scenario_id)) == ref
    assert len(public) == len(set(public))
    assert all(re.fullmatch("[0-9a-f]{48}", ref) for ref in public)
    assert repo.get_operation_refs(ids) == refs["operations"]
    assert len(set(repo.get_operation_refs([ids[0]]).values())) == 1


def test_summary_head_changes_do_not_create_a_new_business_plan(identity_case):
    conn, repo, _ = identity_case
    locator = Locator(2, "adopted")
    ref = repo.get_plan_ref(locator)
    tasks = repo.get_task_refs(ref, plan_rows(conn, locator))
    revision = repo.read_revision()
    history(conn, 2, "failed", "{bad", time="2026-09-09 12:00:00")
    head_id = conn.execute("SELECT max(id) FROM ScheduleHistory").fetchone()[0]
    history(conn, 2, "partial", time="2026-09-09 13:00:00")
    assert repo.get_plan_ref(locator) == ref and repo.resolve_plan(ref) == locator
    assert repo.get_task_refs(ref, plan_rows(conn, locator)) == tasks
    assert build_plan_catalog(conn)[0].completeness == "partial"
    assert repo.read_revision() > revision
    conn.execute("DELETE FROM ScheduleHistory WHERE id > ?", (head_id,))
    assert repo.get_plan_ref(locator) == ref
    assert build_plan_catalog(conn)[0].completeness == "invalid"


@pytest.mark.parametrize("recursive", (0, 1))
def test_history_replace_and_version_move_never_rebind_version_refs(schema_conn, recursive):
    conn, repo, _ = installed_case(schema_conn)
    conn.execute(f"PRAGMA recursive_triggers = {recursive}")
    old = repo.get_plan_ref(Locator(2, "adopted"))
    row = conn.execute("SELECT * FROM ScheduleHistory WHERE version = 2").fetchone()
    replace_row(conn, "ScheduleHistory", row, result_status="failed")
    assert repo.get_plan_ref(Locator(2, "adopted")) == old
    replace_row(conn, "ScheduleHistory", row, version=3)
    with pytest.raises(WorkbenchPlanReferenceError):
        repo.resolve_plan(old)
    new = repo.get_plan_ref(Locator(3, "adopted"))
    conn.execute("UPDATE ScheduleHistory SET version = 4 WHERE version = 3")
    with pytest.raises(WorkbenchPlanReferenceError):
        repo.resolve_plan(new)
    history(conn, 2)
    assert repo.get_plan_ref(Locator(2, "adopted")) == old


def test_history_delete_last_then_restore_preserves_the_version_object(identity_case):
    conn, repo, _ = identity_case
    locator = Locator(2, "adopted")
    ref = repo.get_plan_ref(locator)
    rows = plan_rows(conn, locator)
    tasks = repo.get_task_refs(ref, rows)
    conn.execute("DELETE FROM ScheduleHistory WHERE version = 2")
    with pytest.raises(WorkbenchPlanReferenceError):
        repo.resolve_plan(ref)
    history(conn, 2)
    new = repo.get_plan_ref(locator)
    assert new == ref and repo.get_task_refs(new, rows) == tasks


@pytest.mark.parametrize("table,locator", [
    ("Schedule", Locator(2, "adopted")),
    ("ScheduleCandidateRows", Locator(1, "critical_best")),
    ("ScheduleAdjustmentScenarioRow", Locator(1, "adopted", "saved")),
])
@pytest.mark.parametrize("recursive", (0, 1))
def test_arrangement_update_delete_reinsert_replace(schema_conn, table, locator, recursive):
    conn, repo, _ = installed_case(schema_conn)
    conn.execute(f"PRAGMA recursive_triggers = {recursive}")
    ref = repo.get_plan_ref(locator)
    rows = plan_rows(conn, locator)
    row_id = rows[0]["schedule_id"]
    old = repo.get_task_refs(ref, rows)
    conn.execute(f'UPDATE "{table}" SET start_time = ? WHERE id = ?', ("2026-09-09 07:00:00", row_id))
    assert repo.get_task_refs(ref, rows) == old
    raw = conn.execute(f'SELECT * FROM "{table}" WHERE id = ?', (row_id,)).fetchone()
    replace_row(conn, table, raw)
    second = repo.get_task_refs(ref, rows)
    assert second != old
    conn.execute(f'DELETE FROM "{table}" WHERE id = ?', (row_id,))
    replace_row(conn, table, raw)
    assert repo.get_task_refs(ref, rows) not in (old, second)
    assert conn.execute("SELECT 1 FROM WorkbenchTaskRefs WHERE ref = ?", (old[row_id],)).fetchone()


@pytest.mark.parametrize("table,locator", [
    ("Schedule", Locator(2, "adopted")),
    ("ScheduleCandidateRows", Locator(1, "critical_best")),
    ("ScheduleAdjustmentScenarioRow", Locator(1, "adopted", "saved")),
])
def test_task_change_of_operation_is_a_new_arrangement(schema_conn, table, locator):
    conn, repo, ids = installed_case(schema_conn)
    ref = repo.get_plan_ref(locator)
    rows = plan_rows(conn, locator)
    old = repo.get_task_refs(ref, rows)
    conn.execute(f'UPDATE "{table}" SET op_id = ? WHERE id = ?', (ids[1], rows[0]["schedule_id"]))
    with pytest.raises(WorkbenchPlanReferenceError):
        repo.get_task_refs(ref, rows)
    assert repo.get_task_refs(ref, plan_rows(conn, locator)) != old


@pytest.mark.parametrize("recursive", (0, 1))
@pytest.mark.parametrize("conflict", ("id", "op_code", "composite"))
def test_operation_replace_retires_all_colliding_instances(schema_conn, recursive, conflict):
    conn, repo, ids = installed_case(schema_conn)
    foreign_keys_off(conn)
    conn.execute(f"PRAGMA recursive_triggers = {recursive}")
    old = repo.get_operation_refs(ids)
    raw = conn.execute("SELECT * FROM BatchOperations WHERE id = ?", (ids[1],)).fetchone()
    changes: Dict[str, Any] = {"id": 900}
    if conflict == "id":
        changes["id"] = ids[1]
    elif conflict == "composite":
        changes["op_code"] = "different-code"
    replace_row(conn, "BatchOperations", raw, **changes)
    target = changes["id"]
    assert repo.get_operation_refs([target])[target] not in old.values()
    inactive = conn.execute("SELECT active FROM WorkbenchPlanSourceRefs WHERE ref = ?", (old[ids[1]],)).fetchone()
    assert inactive[0] == 0
    assert repo.get_operation_refs([ids[0]])[ids[0]] == old[ids[0]]


def test_operation_rename_preserves_instance_but_rebuild_never_rebinds_old_task(identity_case):
    conn, repo, ids = identity_case
    old = repo.get_operation_refs([ids[0]])[ids[0]]
    conn.execute("UPDATE BatchOperations SET op_code = 'renamed', seq = 10 WHERE id = ?", (ids[0],))
    assert repo.get_operation_refs([ids[0]])[ids[0]] == old
    foreign_keys_off(conn)
    raw = conn.execute("SELECT * FROM BatchOperations WHERE id = ?", (ids[0],)).fetchone()
    conn.execute("DELETE FROM BatchOperations WHERE id = ?", (ids[0],))
    replace_row(conn, "BatchOperations", raw)
    assert repo.get_operation_refs([ids[0]])[ids[0]] != old
    locator = Locator(2, "adopted")
    ref = repo.get_plan_ref(locator)
    conn.execute("UPDATE Schedule SET lock_status = 'unlocked' WHERE version = 2")
    with pytest.raises(WorkbenchPlanReferenceError) as caught:
        repo.get_task_refs(ref, plan_rows(conn, locator))
    assert caught.value.code == "task_binding_invalid"


@pytest.mark.parametrize("action", ("update", "delete", "replace"))
@pytest.mark.parametrize("recursive", (0, 1))
def test_selection_lifetime_does_not_retarget_old_ref(schema_conn, action, recursive):
    conn, repo, _ = installed_case(schema_conn)
    conn.execute(f"PRAGMA recursive_triggers = {recursive}")
    locator = Locator(1, "baseline_best")
    old = repo.get_plan_ref(locator)
    row = conn.execute("SELECT * FROM ScheduleCandidateSelection WHERE role = 'baseline_best'").fetchone()
    if action == "update":
        target = conn.execute("SELECT candidate_id FROM ScheduleCandidateSelection WHERE role = 'critical_best'").fetchone()[0]
        conn.execute("UPDATE ScheduleCandidateSelection SET candidate_id = ?, source_table = 'candidate_rows' WHERE id = ?", (target, row["id"]))
    else:
        if action == "delete":
            conn.execute("DELETE FROM ScheduleCandidateSelection WHERE id = ?", (row["id"],))
        replace_row(conn, "ScheduleCandidateSelection", row)
    new = repo.get_plan_ref(locator)
    assert new != old
    with pytest.raises(WorkbenchPlanReferenceError):
        repo.resolve_plan(old)
    assert repo.get_task_refs(new, plan_rows(conn, locator))


@pytest.mark.parametrize("recursive", (0, 1))
def test_scenario_replace_by_unique_draft_cannot_reuse_old_plan_or_rows(schema_conn, recursive):
    conn, repo, _ = installed_case(schema_conn)
    foreign_keys_off(conn)
    conn.execute(f"PRAGMA recursive_triggers = {recursive}")
    locator = Locator(1, "adopted", "saved")
    old = repo.get_plan_ref(locator)
    rows = plan_rows(conn, locator)
    raw = conn.execute("SELECT * FROM ScheduleAdjustmentScenario WHERE scenario_id = 'saved'").fetchone()
    replace_row(conn, "ScheduleAdjustmentScenario", raw, scenario_id="new")
    with pytest.raises(WorkbenchPlanReferenceError):
        repo.resolve_plan(old)
    replacement = repo.get_plan_ref(Locator(1, "adopted", "new"))
    assert replacement != old
    with pytest.raises(WorkbenchPlanReferenceError):
        repo.get_task_refs(replacement, rows)


def test_scenario_publish_keeps_identity_delete_rebuild_does_not(identity_case):
    conn, repo, _ = identity_case
    locator = Locator(1, "adopted", "saved")
    old = repo.get_plan_ref(locator)
    conn.execute("UPDATE ScheduleAdjustmentScenario SET status = 'published', published_version = 2")
    assert repo.resolve_plan(old) == locator and repo.get_plan_ref(locator) == old
    raw = conn.execute("SELECT * FROM ScheduleAdjustmentScenario").fetchone()
    conn.execute("DELETE FROM ScheduleAdjustmentScenario")
    replace_row(conn, "ScheduleAdjustmentScenario", raw)
    assert repo.get_plan_ref(locator) != old


@pytest.mark.parametrize("damage", ("cross_version", "alias", "candidate_replaced", "scenario_base"))
def test_bad_bindings_fail_closed_without_writing(schema_conn, damage):
    conn, repo, _ = installed_case(schema_conn)
    foreign_keys_off(conn)
    locator = Locator(1, "baseline_best")
    if damage == "cross_version":
        conn.execute("UPDATE ScheduleCandidate SET version = 20 WHERE candidate_key = 'adopted'")
    elif damage == "alias":
        conn.execute("UPDATE ScheduleCandidateSelection SET candidate_id = "
                     "(SELECT id FROM ScheduleCandidate WHERE candidate_key = 'critical_best') WHERE role = 'baseline_best'")
    elif damage == "candidate_replaced":
        raw = conn.execute("SELECT * FROM ScheduleCandidate WHERE candidate_key = 'adopted'").fetchone()
        replace_row(conn, "ScheduleCandidate", raw)
    else:
        conn.execute("UPDATE ScheduleAdjustmentScenario SET base_candidate_key = 'invented'")
        locator = Locator(1, "adopted", "saved")
    before = table_snapshot(conn)
    with pytest.raises(WorkbenchPlanReferenceError):
        repo.get_plan_ref(locator)
    assert table_snapshot(conn) == before


@pytest.mark.parametrize("missing", ("schema", "trigger", "plan", "operation", "task", "clock"))
def test_missing_identity_never_gets_backfilled_by_reads(v26_identity_case, missing):
    conn, repo, ids = v26_identity_case
    locator = Locator(2, "adopted")
    ref = repo.get_plan_ref(locator)
    rows = plan_rows(conn, locator)
    if missing == "schema":
        conn.execute("DROP TABLE WorkbenchTaskRefs")
    elif missing == "trigger":
        conn.execute("DROP TRIGGER wb_plan_schedule_row_insert")
    elif missing == "clock":
        conn.execute("DELETE FROM WorkbenchPlanIdentityClock")
    elif missing == "task":
        conn.execute("DELETE FROM WorkbenchTaskRefs WHERE plan_ref = ?", (ref,))
    else:
        kind = "official" if missing == "plan" else "operation"
        conn.execute("DELETE FROM WorkbenchPlanSourceRefs WHERE kind = ?", (kind,))
    before = table_snapshot(conn)
    with pytest.raises((RuntimeError, WorkbenchPlanReferenceError)):
        if missing == "operation":
            repo.get_operation_refs(ids)
        elif missing == "clock":
            repo.read_revision()
        else:
            repo.get_task_refs(ref, rows)
    assert table_snapshot(conn) == before


def test_empty_and_missing_schema_are_distinct(mem_conn, schema_conn):
    with pytest.raises(RuntimeError):
        WorkbenchPlanIdentityRepository(mem_conn).get_operation_refs([])
    assert not mem_conn.execute("SELECT name FROM sqlite_master").fetchall()
    install(schema_conn)
    repo = WorkbenchPlanIdentityRepository(schema_conn)
    assert repo.get_operation_refs([]) == {} and repo.read_revision() == 1
    with pytest.raises(WorkbenchPlanReferenceError):
        repo.get_plan_ref(Locator(1, "adopted"))


def test_migration_rolls_back_on_invalid_source_primary_key(mem_conn):
    before = list(mem_conn.iterdump())
    with pytest.raises(RuntimeError):
        v24.run(mem_conn)
    assert list(mem_conn.iterdump()) == before


def test_refs_do_not_certify_bad_plans_complete(schema_conn):
    seed_operation(schema_conn)
    history(schema_conn, 1, "success", "{bad")
    history(schema_conn, 2, "partial", "{}")
    history(schema_conn, 3, "failed", "{}")
    v24.run(schema_conn)
    repo = WorkbenchPlanIdentityRepository(schema_conn)
    before = table_snapshot(schema_conn)
    for entry in build_plan_catalog(schema_conn):
        assert repo.get_plan_ref(entry.locator)
        assert not entry.can_view and entry.completeness != "complete"
    assert table_snapshot(schema_conn) == before


@pytest.mark.parametrize("recursive", (0, 1))
@pytest.mark.parametrize("conflict", ("primary", "alternate", "both"))
def test_update_or_replace_operation_preserves_updating_instance_only(schema_conn, recursive, conflict):
    conn, repo, ids = installed_case(schema_conn)
    foreign_keys_off(conn)
    conn.execute(f"PRAGMA recursive_triggers = {recursive}")
    before = repo.get_operation_refs(ids)
    target = conn.execute("SELECT * FROM BatchOperations WHERE id = ?", (ids[1],)).fetchone()
    assignment, params = [], []
    if conflict in ("primary", "both"):
        assignment.append("id = ?")
        params.append(ids[1])
    if conflict in ("alternate", "both"):
        assignment.append("op_code = ?")
        params.append(target["op_code"])
    conn.execute("UPDATE OR REPLACE BatchOperations SET " + ", ".join(assignment) + " WHERE id = ?", params + [ids[0]])
    surviving_id = ids[1] if conflict in ("primary", "both") else ids[0]
    assert repo.get_operation_refs([surviving_id])[surviving_id] == before[ids[0]]
    assert conn.execute("SELECT active FROM WorkbenchPlanSourceRefs WHERE ref = ?", (before[ids[1]],)).fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM BatchOperations").fetchone()[0] == 1


@pytest.mark.parametrize("recursive", (0, 1))
def test_update_or_replace_role_alias_retires_displaced_binding(schema_conn, recursive):
    conn, repo, _ = installed_case(schema_conn)
    conn.execute(f"PRAGMA recursive_triggers = {recursive}")
    old_refs = [repo.get_plan_ref(Locator(1, role)) for role in ("baseline_best", "critical_best")]
    conn.execute("UPDATE OR REPLACE ScheduleCandidateSelection SET role = 'baseline_best' WHERE role = 'critical_best'")
    new = repo.get_plan_ref(Locator(1, "baseline_best"))
    assert new not in old_refs
    for old in old_refs:
        with pytest.raises(WorkbenchPlanReferenceError):
            repo.resolve_plan(old)


@pytest.mark.parametrize("recursive", (0, 1))
def test_insert_or_ignore_and_update_or_ignore_never_rotate_identities(schema_conn, recursive):
    conn, repo, ids = installed_case(schema_conn)
    conn.execute(f"PRAGMA recursive_triggers = {recursive}")
    assert_ignored_operation_conflicts(conn, repo, ids)


def test_failed_backfill_rolls_back_schema_and_all_identity_rows(mem_conn):
    conn = load_v23_schema(mem_conn)
    seed_plans(conn)
    conn.execute("INSERT INTO ScheduleAdjustmentScenario(scenario_id, source_draft_id, base_version, "
                 "base_plan_role, base_source_table, validation_status) VALUES (NULL, 'bad-draft', 1, 'adopted', 'schedule', 'valid')")
    conn.commit()
    before = list(conn.iterdump())
    with pytest.raises(RuntimeError, match="missing source key"):
        v24.run(conn)
    assert list(conn.iterdump()) == before


def test_bulk_refs_reject_partial_maps_and_wrong_versions(identity_case):
    conn, repo, ids = identity_case
    ref = repo.get_plan_ref(Locator(2, "adopted"))
    rows = plan_rows(conn, Locator(2, "adopted"))
    for bad_ids in ([ids[0], True], [ids[0], 999], [ids[0], 1.0]):
        with pytest.raises(WorkbenchPlanReferenceError):
            repo.get_operation_refs(bad_ids)
    for extra in ({"schedule_id": 999, "op_id": ids[0], "version": 2},
                  {"schedule_id": rows[0]["schedule_id"], "op_id": ids[0], "version": 1},
                  {"schedule_id": rows[0]["schedule_id"], "op_id": ids[1], "version": 2}):
        with pytest.raises(WorkbenchPlanReferenceError):
            repo.get_task_refs(ref, rows + [extra])


def test_install_does_not_depend_on_history_before_schedule_insert(schema_conn):
    install(schema_conn)
    op_id = seed_operation(schema_conn)
    schema_conn.execute("INSERT INTO Schedule(version, op_id, start_time, end_time) VALUES (1, ?, ?, ?)", (op_id, START, END))
    history(schema_conn, 1)
    repo = WorkbenchPlanIdentityRepository(schema_conn)
    ref = repo.get_plan_ref(Locator(1, "adopted"))
    assert repo.get_task_refs(ref, plan_rows(schema_conn, Locator(1, "adopted")))


def test_ten_thousand_dynamic_versions_and_distinct_operations_avoid_quadratic_writes(schema_conn):
    elapsed, steps = dynamic_scale(schema_conn)
    assert steps < 100000000
    assert schema_conn.execute("SELECT count(*) FROM WorkbenchTaskRefs").fetchone()[0] == 30000
    repo = WorkbenchPlanIdentityRepository(schema_conn)
    for role in ("adopted", "baseline_best", "critical_best"):
        ref = repo.get_plan_ref(Locator(10000, role))
        assert repo.get_task_refs(ref, [{"schedule_id": 10000, "op_id": 10001, "version": 10000}])
    assert len(repo.get_operation_refs(range(1, 10002))) == 10001
    print(f"dynamic scale: versions=10000 operations=10001 tasks=30000 seconds={elapsed:.3f} vm_steps<{steps}")


def test_ten_thousand_versions_backfill_and_deep_reads_are_indexed(mem_conn):
    conn = load_v23_schema(mem_conn)
    op_id = seed_operation(conn)
    conn.executemany("INSERT INTO ScheduleHistory(version, strategy, schedule_time, result_summary) VALUES (?, 'scale', ?, '{}')",
                     ((version, START) for version in range(1, 10001)))
    conn.executemany("INSERT INTO Schedule(version, op_id, start_time, end_time) VALUES (?, ?, ?, ?)",
                     ((version, op_id, START, END) for version in range(1, 10001)))
    conn.commit()
    started = time.perf_counter()
    v24.run(conn)
    install_seconds = time.perf_counter() - started
    assert conn.execute("SELECT count(*) FROM WorkbenchTaskRefs").fetchone()[0] == 10000
    repo = WorkbenchPlanIdentityRepository(conn)
    steps = []
    conn.set_progress_handler(lambda: steps.append(1) or 0, 1000)
    started = time.perf_counter()
    for version in (10000, 5000, 1):
        locator = Locator(version, "adopted")
        ref = repo.get_plan_ref(locator)
        assert repo.resolve_plan(ref) == locator
        assert repo.get_task_refs(ref, [{"schedule_id": version, "op_id": op_id, "version": version}])
    query_seconds = time.perf_counter() - started
    conn.set_progress_handler(None, 0)
    assert len(steps) < 100
    assert len(objects()) > 20 and not contract_issues(conn)
    print(f"plan identity scale: versions=10000 rows=10000 install={install_seconds:.3f}s "
          f"deep_reads={query_seconds:.4f}s vm_steps<{(len(steps) + 1) * 1000} sqlite={sqlite3.sqlite_version}")


@pytest.mark.parametrize("initializer", (initialize_plan_identity, install))
def test_direct_objects_need_one_strict_clock_initialization(mem_conn, initializer):
    conn = load_v23_schema(mem_conn)
    exec_plan_objects(conn)
    assert contract_issues(conn) == ["missing_workbench_plan_clock_state"]
    before = table_snapshot(conn)
    with pytest.raises(RuntimeError, match="clock"):
        WorkbenchPlanIdentityRepository(conn).read_revision()
    assert table_snapshot(conn) == before
    initializer(conn)
    assert not contract_issues(conn)
    assert WorkbenchPlanIdentityRepository(conn).read_revision() == 1
    conn.commit()
    conn.execute("PRAGMA query_only = ON")
    before = table_snapshot(conn), conn.total_changes
    initializer(conn)
    assert (table_snapshot(conn), conn.total_changes) == before


def test_direct_ddl_and_exported_seed_work_without_install(mem_conn, monkeypatch):
    conn = load_v23_schema(mem_conn)
    monkeypatch.setattr(v24, "run", lambda *args, **kwargs: pytest.fail("v24 must not be called"))
    exec_plan_objects(conn)
    conn.execute(plan_identity_initialization_sql())
    seed_plans(conn)
    expected = all_refs(conn)
    before = table_snapshot(conn), conn.total_changes
    conn.execute(plan_identity_initialization_sql())
    assert (table_snapshot(conn), conn.total_changes) == before
    conn.commit()
    conn.execute("PRAGMA query_only = ON")
    assert WorkbenchPlanIdentityRepository(conn).read_revision() > 1
    assert all_refs(conn) == expected


def test_real_fresh_startup_fast_forwards_without_migration(tmp_path, monkeypatch, schema_path):
    from core.infrastructure import database, migration_state

    def migration_forbidden(*args, **kwargs):
        pytest.fail("A fresh current schema must not run a legacy migration")

    monkeypatch.setattr(database, "_migrate_with_backup_impl", migration_forbidden)
    db_path = str(tmp_path / "fresh.sqlite")
    database.ensure_schema(db_path, schema_path=str(schema_path))
    with database.get_connection(db_path) as conn:
        assert migration_state.get_schema_version(conn) == migration_state.CURRENT_SCHEMA_VERSION
        assert migration_state.is_truly_empty_db(conn)
        assert not migration_state.current_schema_contract_issues(conn)
        assert WorkbenchPlanIdentityRepository(conn).read_revision() == 1
        seed_plans(conn)
        assert not migration_state.is_truly_empty_db(conn)
        expected = all_refs(conn)
    database.ensure_schema(db_path, schema_path=str(schema_path))
    with database.get_connection(db_path) as conn:
        conn.execute("PRAGMA query_only = ON")
        assert all_refs(conn) == expected


@pytest.mark.parametrize("damage", ("clock", "task_table"))
def test_real_startup_does_not_apply_fresh_seed_to_existing_damaged_database(tmp_path, schema_path, damage):
    from core.infrastructure import database, migration_state

    db_path = str(tmp_path / "used.sqlite")
    database.ensure_schema(db_path, schema_path=str(schema_path))
    with database.get_connection(db_path) as conn:
        conn.execute("UPDATE WorkbenchPlanIdentityClock SET revision = 2")
        assert not migration_state.is_truly_empty_db(conn)
        seed_plans(conn)
        if damage == "task_table":
            # Inject storage damage without deleting the current source maps.
            foreign_keys_off(conn)
        conn.execute("DELETE FROM WorkbenchPlanIdentityClock" if damage == "clock" else "DROP TABLE WorkbenchTaskRefs")
        conn.commit()
        before = list(conn.iterdump())
    with pytest.raises(migration_state.MigrationContractError):
        database.ensure_schema(db_path, schema_path=str(schema_path))
    with database.get_connection(db_path) as conn:
        assert list(conn.iterdump()) == before


@pytest.mark.parametrize("name", tuple(objects()))
def test_install_refuses_every_partial_schema_before_any_write(v26_identity_case, name):
    conn, _, _ = v26_identity_case
    kind = conn.execute("SELECT type FROM sqlite_master WHERE name = ?", (name,)).fetchone()[0]
    conn.execute('DROP ' + kind.upper() + ' "' + name + '"')
    before = list(conn.iterdump()), conn.total_changes
    with pytest.raises(RuntimeError, match="Partial"):
        install(conn)
    assert (list(conn.iterdump()), conn.total_changes) == before


@pytest.mark.parametrize("damage", ("task_row", "all_task_rows", "source_row", "all_source_rows", "clock"))
def test_complete_schema_with_lost_identity_rows_is_not_repaired(v26_identity_case, damage):
    conn, _, _ = v26_identity_case
    if damage == "clock":
        conn.execute("DELETE FROM WorkbenchPlanIdentityClock")
    elif damage in ("task_row", "all_task_rows"):
        conn.execute("DELETE FROM WorkbenchTaskRefs" +
                     (" WHERE ref = (SELECT ref FROM WorkbenchTaskRefs LIMIT 1)" if damage == "task_row" else ""))
    else:
        conn.execute("DELETE FROM WorkbenchPlanSourceRefs" +
                     (" WHERE kind = 'official' AND source_key = '2'" if damage == "source_row" else ""))
    before = list(conn.iterdump()), conn.total_changes
    with pytest.raises(RuntimeError):
        install(conn)
    assert (list(conn.iterdump()), conn.total_changes) == before


@pytest.mark.parametrize("initializer", (initialize_plan_identity, install))
def test_missing_used_clock_cannot_reset_even_after_business_sources_deleted(schema_conn, initializer):
    conn, repo, _ = installed_case(schema_conn)
    repo.read_revision()
    conn.execute("DELETE FROM ScheduleHistory")
    conn.execute("DELETE FROM ScheduleCandidate")
    conn.execute("DELETE FROM ScheduleAdjustmentScenario")
    conn.execute("DELETE FROM BatchOperations")
    conn.execute("DELETE FROM WorkbenchPlanIdentityClock")
    before = list(conn.iterdump()), conn.total_changes
    with pytest.raises(RuntimeError, match="existing source or identity"):
        initializer(conn)
    with pytest.raises(WorkbenchPlanReferenceError):
        repo.get_operation_refs([])
    assert (list(conn.iterdump()), conn.total_changes) == before


def test_exported_seed_aborts_instead_of_healing_lost_clock(schema_conn):
    conn, _, _ = installed_case(schema_conn)
    conn.execute("DELETE FROM WorkbenchPlanIdentityClock")
    before = table_snapshot(conn), conn.total_changes
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(plan_identity_initialization_sql())
    assert (table_snapshot(conn), conn.total_changes) == before


def test_existing_sources_without_any_identity_are_not_a_fresh_empty_schema(mem_conn):
    conn = load_v23_schema(mem_conn)
    seed_operation(conn)
    exec_plan_objects(conn)
    before = table_snapshot(conn), conn.total_changes
    for initializer in (initialize_plan_identity, install):
        with pytest.raises(RuntimeError, match="existing source or identity"):
            initializer(conn)
    assert (table_snapshot(conn), conn.total_changes) == before


def test_complete_identity_schema_with_bad_definition_is_not_repaired(schema_conn):
    conn, _, _ = installed_case(schema_conn)
    conn.execute("DROP TRIGGER wb_plan_history_delete")
    conn.execute("CREATE TRIGGER wb_plan_history_delete AFTER DELETE ON ScheduleHistory BEGIN SELECT 1; END")
    before = list(conn.iterdump()), conn.total_changes
    for initializer in (initialize_plan_identity, install):
        with pytest.raises(RuntimeError, match="bad_workbench_plan_identity"):
            initializer(conn)
    assert (list(conn.iterdump()), conn.total_changes) == before


def test_already_migrated_database_cannot_reinstall_an_entire_lost_identity_schema(mem_conn):
    from core.infrastructure import migration_state

    conn, _, _ = installed_case(load_v24_schema(mem_conn))
    migration_state.ensure_schema_version(conn)
    migration_state.set_schema_version(conn, 24)
    legacy_schema(conn)
    before = list(conn.iterdump()), conn.total_changes
    with pytest.raises(RuntimeError, match="already migrated"):
        install(conn)
    assert (list(conn.iterdump()), conn.total_changes) == before


@pytest.mark.parametrize("existing_plans", (False, True))
def test_v24_optimizes_legacy_process_triggers_before_plan_install_without_reallocating_refs(mem_conn, monkeypatch, existing_plans):
    conn = load_v24_schema(mem_conn)
    if existing_plans:
        installed_case(conn)
    else:
        legacy_schema(conn)
        seed_plans(conn)
    use_legacy_process_triggers(conn)
    conn.execute("INSERT INTO PartOperations(part_no, seq, op_type_name) VALUES ('CAT-P', 1, 'template')")
    conn.commit()
    before = table_snapshot(conn)
    previous_refs = all_refs(conn) if existing_plans else None
    assert workbench_process_contract_issues(conn)
    calls = []
    optimize, install_plan = v24.optimize_process_identity_triggers, v24.install_plan_identity

    def checked_optimize(connection):
        calls.append(("process", connection.in_transaction))
        optimize(connection)

    def checked_install(connection):
        calls.append(("plan", connection.in_transaction))
        assert not workbench_process_contract_issues(connection)
        install_plan(connection)

    monkeypatch.setattr(v24, "optimize_process_identity_triggers", checked_optimize)
    monkeypatch.setattr(v24, "install_plan_identity", checked_install)
    assert v24.run(conn) == MigrationOutcome.APPLIED
    assert calls == [("process", True), ("plan", True)]
    after = table_snapshot(conn)
    assert {table: after[table] for table in before} == before
    if previous_refs is not None:
        assert all_refs(conn) == previous_refs


def test_v24_plan_failure_rolls_back_the_preceding_process_trigger_optimization(mem_conn):
    conn, _, _ = installed_case(load_v24_schema(mem_conn))
    use_legacy_process_triggers(conn)
    conn.execute("DROP TABLE WorkbenchTaskRefs")
    conn.commit()
    before = list(conn.iterdump())
    with pytest.raises(RuntimeError, match="Partial"):
        v24.run(conn)
    assert list(conn.iterdump()) == before
    assert workbench_process_contract_issues(conn)


@pytest.mark.parametrize("damage,issue", [
    ("candidate_missing", "plan_binding_invalid"), ("candidate_bad_id", "plan_binding_invalid"),
    ("history_missing", "history_missing"), ("scenario_bad_version", "plan_binding_invalid"),
    ("identity_missing", "identity_missing"), ("identity_mismatch", "identity_invalid"),
    ("source_missing", "source_missing"),
])
def test_catalog_diagnostics_isolate_bad_bindings_and_keep_detail_resolution_strict(schema_conn, damage, issue):
    conn, repo, _ = installed_case(schema_conn)
    foreign_keys_off(conn)
    is_scenario = damage in ("history_missing", "scenario_bad_version", "source_missing")
    locator = Locator(1, "adopted", "saved") if is_scenario else Locator(1, "critical_best")
    old_ref = repo.get_plan_ref(locator)
    if damage == "candidate_missing":
        conn.execute("DELETE FROM ScheduleCandidate WHERE candidate_key = 'critical_best'")
    elif damage == "candidate_bad_id":
        conn.execute("UPDATE ScheduleCandidateSelection SET candidate_id = 'broken-id' WHERE role = 'critical_best'")
    elif damage == "history_missing":
        conn.execute("DELETE FROM ScheduleHistory WHERE version = 1")
    elif damage == "scenario_bad_version":
        conn.execute("UPDATE ScheduleAdjustmentScenario SET base_version = 'broken-version' WHERE scenario_id = 'saved'")
        version = conn.execute("SELECT base_version FROM ScheduleAdjustmentScenario WHERE scenario_id = 'saved'").fetchone()[0]
        locator = Locator(version, "adopted", "saved")
    elif damage == "identity_missing":
        conn.execute("DELETE FROM WorkbenchPlanSourceRefs WHERE ref = ?", (old_ref,))
    elif damage == "identity_mismatch":
        conn.execute("UPDATE WorkbenchPlanSourceRefs SET owner_key = 'wrong' WHERE ref = ?", (old_ref,))
    else:
        conn.execute("DELETE FROM ScheduleAdjustmentScenario WHERE scenario_id = 'saved'")
    expected_ref = old_ref
    if damage in ("candidate_bad_id", "scenario_bad_version"):
        kind = "scenario" if is_scenario else "selection"
        expected_ref = conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind = ? "
                                    "AND active = 1 AND plan_role = ?", (kind, locator.plan_role)).fetchone()[0]
        assert expected_ref != old_ref
    before = table_snapshot(conn), conn.total_changes
    conn.commit()
    conn.execute("PRAGMA query_only = ON")
    result = repo.get_catalog_reference(locator)
    assert not result.binding_valid and result.issues[0].code == issue
    assert result.plan_ref == (None if damage in ("identity_missing", "identity_mismatch", "source_missing") else expected_ref)
    with pytest.raises(WorkbenchPlanReferenceError):
        repo.get_plan_ref(locator)
    if result.plan_ref is not None:
        with pytest.raises(WorkbenchPlanReferenceError):
            repo.resolve_plan(result.plan_ref)
        with pytest.raises(WorkbenchPlanReferenceError):
            repo.get_task_refs(result.plan_ref, [])
    healthy = repo.get_catalog_reference(Locator(2, "adopted"))
    assert healthy.binding_valid and healthy.plan_ref == repo.get_plan_ref(Locator(2, "adopted"))
    assert (table_snapshot(conn), conn.total_changes) == before


def test_catalog_binding_diagnostic_is_not_a_completeness_claim(identity_case):
    conn, repo, _ = identity_case
    locator = Locator(2, "adopted")
    ref = repo.get_plan_ref(locator)
    conn.execute("UPDATE ScheduleHistory SET result_summary = '{bad' WHERE version = 2")
    before = table_snapshot(conn), conn.total_changes
    result = repo.get_catalog_reference(locator)
    assert result.plan_ref == ref and result.binding_valid and not result.issues
    assert not build_plan_catalog(conn)[0].can_view
    assert (table_snapshot(conn), conn.total_changes) == before


def test_catalog_reference_does_not_turn_storage_failure_into_a_disabled_item(identity_case):
    conn, repo, _ = identity_case
    repo.get_catalog_reference(Locator(2, "adopted"))
    conn.execute("DROP TABLE WorkbenchPlanIdentityClock")
    before = list(conn.iterdump())
    with pytest.raises(RuntimeError):
        repo.get_catalog_reference(Locator(2, "adopted"))
    assert list(conn.iterdump()) == before
