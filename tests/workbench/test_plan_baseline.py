"""Exact persisted baseline identity, complete comparison Scope and zero writes."""

import pytest

from core.errors import AppError
from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.services.workbench.plan_baseline import build_plan_baseline
from tests.workbench.plan_baseline_support import (
    MOVED_END,
    MOVED_START,
    NIGHT_END,
    NIGHT_START,
    BaselineCase,
    assert_public,
    connect,
    projection_trace,
)
from tests.workbench.plan_baseline_support import (
    baseline_fixture as baseline_fixture,
)


@pytest.mark.parametrize("role", ["adopted", "baseline_best", "critical_best"])
def test_ordinary_and_representative_plans_have_no_initial_snapshot(baseline_case, role):
    data, facts = baseline_case.read(role=role, scenario_id=None)
    assert data["state"] == "unavailable" and data["reason_code"] == "not_recorded"
    assert data["reason"] and not data["items_complete"] and data["items"] == []
    assert facts["outcome"] == data
    assert_public(data)


@pytest.mark.parametrize("key,role,source", [("saved", "adopted", "schedule"),
                                          ("alias", "baseline_best", "schedule"),
                                          ("candidate", "critical_best", "candidate_rows")])
def test_exact_scenario_base_source_role_and_permanent_tasks(baseline_case, key, role, source):
    data, facts = baseline_case.read(role=role, scenario_id=key)
    assert data["state"] == "available" and data["items_complete"]
    assert data["baseline_plan"]["plan_ref"] == baseline_case.ref(role, None)
    assert data["baseline_plan"]["kind"] == ("official" if role == "adopted" else "candidate")
    assert facts["scenario_header"]["base_source_table"] == source
    item = data["items"][0]
    assert item["change"] == "changed"
    assert item["before"]["operation_ref"] == item["after"]["operation_ref"] == item["operation_ref"]
    assert item["before"]["task_ref"] != item["after"]["task_ref"]
    assert item["before"]["start"] == (NIGHT_START if source == "schedule" else "2026-09-09T08:00:00")
    assert item["after"]["start"] == MOVED_START
    assert set(item["changed_fields"]) == {"start", "end", "machine_ref", "operator_ref"}
    assert_public(data)


@pytest.mark.parametrize("start,end,before,after", [
    (NIGHT_START, NIGHT_END, True, False),
    (MOVED_START, MOVED_END, False, True),
    ("2026-09-10T00:00:00", "2026-09-10T00:00:01", True, False),
])
def test_either_side_scope_keeps_moved_tasks_unclipped(baseline_case, start, end, before, after):
    data, _ = baseline_case.read(start=start, end=end)
    item = data["items"][0]
    assert data["item_count"] == 1
    assert (item["before_in_scope"], item["after_in_scope"]) == (before, after)
    assert item["change"] == "changed"
    assert (item["before"]["start"], item["before"]["end"]) == (NIGHT_START, NIGHT_END)
    assert (item["after"]["start"], item["after"]["end"]) == (MOVED_START, MOVED_END)
    assert item["before"]["machine_ref"] != item["after"]["machine_ref"]


@pytest.mark.parametrize("start,end", [(NIGHT_END, MOVED_START),
                                      ("2026-09-09T22:29:59", NIGHT_START),
                                      (MOVED_END, "2026-09-14T00:00:00")])
def test_half_open_boundaries_and_sparse_empty_scope(baseline_case, start, end):
    data, facts = baseline_case.read(start=start, end=end)
    assert data["state"] == "available" and data["items_complete"]
    assert data["items"] == [] and data["item_count"] == 0
    assert len(facts["complete_comparison"]["items"]) == 1


def test_true_add_remove_and_unchanged_not_range_movement(baseline_case):
    baseline_case.add_operations(1, base=False)
    baseline_case.add_operations(1, current=False)
    baseline_case.add_operations(1)
    data, _ = baseline_case.read(start=NIGHT_START, end=NIGHT_END)
    by_change = {item["change"]: item for item in data["items"]}
    assert set(by_change) == {"added", "removed", "unchanged", "changed"}
    assert by_change["added"]["before"] is None and by_change["removed"]["after"] is None
    assert by_change["unchanged"]["changed_fields"] == []


def test_resource_only_change_uses_both_persisted_arrangements(baseline_case):
    conn = baseline_case.conn
    conn.execute("UPDATE ScheduleAdjustmentScenarioRow SET start_time=?,end_time=? WHERE scenario_id='saved'",
                 (NIGHT_START, NIGHT_END))
    conn.commit()
    data, _ = baseline_case.read(start=NIGHT_START, end=NIGHT_END)
    item = data["items"][0]
    assert item["change"] == "changed" and item["changed_fields"] == ["machine_ref", "operator_ref"]
    assert item["before_in_scope"] and item["after_in_scope"]


def test_operation_alignment_stable_across_versions(baseline_case):
    conn = baseline_case.conn
    from tests.workbench.plan_catalog_support import scenario
    scenario(conn, "old", 1, op_id=1)
    conn.commit()
    old, _ = baseline_case.read(version=1, scenario_id="old")
    new, _ = baseline_case.read()
    assert old["items"][0]["operation_ref"] == new["items"][0]["operation_ref"]
    assert old["items"][0]["before"]["task_ref"] != new["items"][0]["before"]["task_ref"]


def test_real_draft_save_and_connection_restart(baseline_case):
    from core.services.scheduler.gantt_adjustment_scenario_service import GanttAdjustmentScenarioService
    from tests._support.gantt_scenario import _draft_with_change, _seed_base
    conn = baseline_case.conn
    _seed_base(conn)
    saved = GanttAdjustmentScenarioService(conn).save_scenario(draft_id=_draft_with_change(conn))
    first = baseline_case.read(version=5, scenario_id=saved.scenario_id)
    reopened = connect(baseline_case.path)
    try:
        second = BaselineCase(reopened, baseline_case.path).read(version=5, scenario_id=saved.scenario_id)
    finally:
        reopened.close()
    assert first == second
    assert first[0]["item_count"] == 3
    changed = [item for item in first[0]["items"] if item["change"] == "changed"]
    assert len(changed) == 1
    assert changed[0]["before"]["start"] == "2026-05-04T08:00:00"
    assert changed[0]["after"]["start"] == "2026-05-04T11:00:00"


@pytest.mark.parametrize("sql", [
    "UPDATE ScheduleAdjustmentScenario SET base_source_table='candidate_rows' WHERE scenario_id='saved'",
    "UPDATE ScheduleAdjustmentScenario SET base_candidate_key='wrong' WHERE scenario_id='saved'",
    "DELETE FROM ScheduleCandidateSelection WHERE role='adopted' AND version=3",
    "DELETE FROM ScheduleHistory WHERE version=3",
    "UPDATE WorkbenchPlanSourceRefs SET parent_ref=NULL WHERE kind='scenario' AND source_key='saved'",
    "UPDATE ScheduleAdjustmentScenario SET status='published' WHERE scenario_id='saved'",
    "UPDATE ScheduleHistory SET result_summary='broken' WHERE version=3",
    "UPDATE Schedule SET start_time='bad' WHERE version=3",
])
def test_bad_base_disables_comparison_without_fallback(baseline_case, sql):
    conn = baseline_case.conn
    conn.execute("BEGIN")
    inputs = baseline_case.inputs()
    conn.execute(sql)
    data, _ = build_plan_baseline(conn, **inputs)
    assert data["state"] == "unavailable" and data["reason"] and not data["items_complete"]
    assert data["baseline_plan"] is None and data["items"] == []
    assert_public(data)
    conn.rollback()


@pytest.mark.parametrize("table,where", [("ScheduleCandidate", "candidate_key='adopted'"),
                                        ("ScheduleAdjustmentScenario", "scenario_id='saved'"),
                                        ("BatchOperations", "id=1")])
def test_same_number_recreation_cannot_take_old_identity(baseline_case, table, where):
    conn = baseline_case.conn
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("BEGIN")
    inputs = baseline_case.inputs()
    row = dict(conn.execute("SELECT * FROM " + table + " WHERE " + where).fetchone())
    conn.execute("DELETE FROM " + table + " WHERE " + where)
    columns = ",".join('"' + column + '"' for column in row)
    conn.execute("INSERT INTO " + table + " (" + columns + ") VALUES (" + ",".join("?" for _ in row) + ")", tuple(row.values()))
    data, _ = build_plan_baseline(conn, **inputs)
    assert data["state"] == "unavailable" and data["items"] == []
    conn.rollback()


def test_history_summary_restore_preserves_immutable_version_identity(baseline_case):
    conn = baseline_case.conn
    before, _ = baseline_case.read()
    row = dict(conn.execute("SELECT * FROM ScheduleHistory WHERE version=3").fetchone())
    conn.execute("DELETE FROM ScheduleHistory WHERE version=3")
    columns = ",".join('"' + column + '"' for column in row)
    conn.execute("INSERT INTO ScheduleHistory (" + columns + ") VALUES (" + ",".join("?" for _ in row) + ")", tuple(row.values()))
    conn.commit()
    after, _ = baseline_case.read()
    assert before == after


def test_resource_identity_loss_is_explicit(baseline_case):
    baseline_case.conn.execute("UPDATE WorkbenchEntityRefs SET active=0 WHERE entity_key='PRIVATE-M1'")
    baseline_case.conn.commit()
    data, _ = baseline_case.read()
    assert data["state"] == "unavailable" and data["reason_code"] == "baseline_task_invalid"


def test_unrecorded_supplier_history_is_not_invented(baseline_case):
    conn = baseline_case.conn
    conn.execute("INSERT INTO Suppliers(supplier_id,name) VALUES ('PRIVATE-S1','Current supplier')")
    conn.execute("UPDATE BatchOperations SET supplier_id='PRIVATE-S1' WHERE id=1")
    conn.commit()
    data, _ = baseline_case.read()
    item = data["items"][0]
    assert item["before"]["supplier_ref"] == item["after"]["supplier_ref"]
    assert item["before"]["supplier_ref"] is not None
    assert "supplier_ref" not in data["compared_fields"]


def test_selected_subset_or_wrong_scope_is_rejected(baseline_case):
    conn = baseline_case.conn
    conn.execute("BEGIN")
    inputs = baseline_case.inputs()
    with pytest.raises(WorkbenchCommandRejected) as error:
        build_plan_baseline(conn, **dict(inputs, selected_rows=[]))
    assert error.value.code == "invalid_input"
    wrong = baseline_case.inputs(scenario_id="candidate", role="critical_best")
    with pytest.raises(WorkbenchCommandRejected) as error:
        build_plan_baseline(conn, **dict(inputs, scope=wrong["scope"]))
    assert error.value.code == "invalid_input"
    conn.rollback()


def test_requires_transaction_and_does_not_own_its_lifetime(baseline_case):
    conn = baseline_case.conn
    conn.execute("BEGIN")
    inputs = baseline_case.inputs()
    build_plan_baseline(conn, **inputs)
    assert conn.in_transaction
    conn.rollback()
    with pytest.raises(RuntimeError, match="caller-owned"):
        build_plan_baseline(conn, **inputs)


def test_select_only_zero_writes_all_tables_preserved(baseline_case):
    conn = baseline_case.conn
    before = list(conn.iterdump())
    changes = conn.total_changes
    conn.execute("PRAGMA query_only=ON")
    (_, _), statements = projection_trace(baseline_case)
    statements = [sql for sql in statements if not sql.startswith("-- ")]
    assert statements and all(sql.lstrip().upper().startswith(("SELECT", "WITH")) for sql in statements)
    assert conn.total_changes == changes and list(conn.iterdump()) == before


def test_schema_error_propagates_not_a_fake_unavailable(baseline_case):
    conn = baseline_case.conn
    intact = list(conn.iterdump())
    tables = [row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name<>'WorkbenchEntityRefs'")]
    business = {name: list(conn.execute('SELECT * FROM "' + name + '"')) for name in tables}
    assert business["Batches"] and business["BatchOperations"] and business["Schedule"]
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    conn.execute("BEGIN")
    try:
        inputs = baseline_case.inputs()
        # Let the real missing-table error reach the reader, then restore all rows.
        conn.execute("PRAGMA defer_foreign_keys=ON")
        conn.execute("DROP TABLE WorkbenchEntityRefs")
        before, changes = list(conn.iterdump()), conn.total_changes
        assert before != intact
        assert business == {name: list(conn.execute('SELECT * FROM "' + name + '"')) for name in tables}
        conn.execute("PRAGMA query_only=ON")
        with pytest.raises(AppError) as exc:
            build_plan_baseline(conn, **inputs)
        assert "no such table: WorkbenchEntityRefs" in str(exc.value.__cause__)
        assert conn.total_changes == changes and list(conn.iterdump()) == before
        assert conn.in_transaction
    finally:
        conn.rollback()
        conn.execute("PRAGMA query_only=OFF")
    assert list(conn.iterdump()) == intact
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert conn.execute("PRAGMA defer_foreign_keys").fetchone()[0] == 0
    assert not conn.execute("PRAGMA foreign_key_check").fetchall()


def test_private_snapshot_changes_for_moved_out_arrangement(baseline_case):
    first, first_facts = baseline_case.read(start=NIGHT_START, end=NIGHT_END)
    baseline_case.conn.execute("UPDATE ScheduleAdjustmentScenarioRow SET end_time='2026-09-13T03:00:00' WHERE scenario_id='saved'")
    baseline_case.conn.commit()
    second, second_facts = baseline_case.read(start=NIGHT_START, end=NIGHT_END)
    assert first["items"][0]["after"]["end"] != second["items"][0]["after"]["end"]
    assert input_fingerprint(first_facts) != input_fingerprint(second_facts)


@pytest.mark.parametrize("base,current", [(True, False), (False, True)])
def test_whole_plan_row_limit_even_for_tiny_scope(baseline_case, base, current):
    conn = baseline_case.conn
    conn.execute("BEGIN")
    inputs = baseline_case.inputs(start=NIGHT_START, end=NIGHT_END)
    conn.rollback()
    baseline_case.add_operations(10000, base=base, current=current)
    conn.execute("BEGIN")
    with pytest.raises(WorkbenchCommandRejected) as error:
        build_plan_baseline(conn, **inputs)
    assert error.value.code == "query_too_large" and error.value.status == 413
    conn.rollback()


def test_whole_baseline_byte_limit_not_just_visible_slice(baseline_case):
    conn = baseline_case.conn
    conn.execute("UPDATE BatchOperations SET op_type_name=? WHERE id=1", ("x" * (8 * 1024 * 1024),))
    conn.commit()
    with pytest.raises(WorkbenchCommandRejected) as error:
        baseline_case.read(start="2026-09-14T00:00:00", end="2026-09-14T01:00:00")
    assert error.value.code == "query_too_large"


def test_bounded_bulk_queries_no_per_task_or_history_scan(baseline_case):
    (_, _), small = projection_trace(baseline_case)
    baseline_case.add_operations(199)
    (data, _), medium = projection_trace(baseline_case)
    assert data["item_count"] == 200 and len(medium) == len(small)
    baseline_case.add_operations(800)
    (data, _), large = projection_trace(baseline_case)
    assert data["item_count"] == 1000
    assert len(large) == len(small) + 6  # Three identity bulk lookups, 400 IDs per chunk.
    assert not any("OFFSET" in sql.upper() for sql in large)
    assert sum("WITH plan_rows AS" in sql for sql in large) == 2
    print(f"baseline SELECT counts: 1={len(small)} 200={len(medium)} 1000={len(large)}")


def test_unrelated_history_does_not_expand_queries_or_replace_base(baseline_case):
    (before, _), small = projection_trace(baseline_case)
    conn = baseline_case.conn
    conn.executemany("INSERT INTO ScheduleHistory(version,strategy,result_status,result_summary) "
                     "VALUES (?,'noise','failed','{}')", ((v,) for v in range(4, 10004)))
    conn.commit()
    (after, _), large = projection_trace(baseline_case)
    assert len(small) == len(large)
    assert after["items"] == before["items"]
    assert after["baseline_plan"]["version"] == 3
    assert not after["baseline_plan"]["is_current_official"]
    assert before["baseline_plan"]["is_current_official"]
    print(f"baseline with 10000 unrelated failed versions: {len(large)} query traces")
