"""Planned delivery contracts under the same read transaction as the workspace."""

import json
from dataclasses import replace

import pytest

from core.infrastructure.errors import AppError
from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.models.workbench_plan_reference import WorkbenchPlanReferenceError
from core.services.workbench.plan_delivery import read_plan_delivery
from tests.workbench.plan_delivery_support import (
    add_batch,
    add_operation,
    alias_official,
    allow_legacy_segments,
    assert_public,
    context,
    finish_event,
    read,
    readonly,
    seed_delivery,
    spaced_scenario_context,
)


@pytest.fixture
def delivery(schema_conn):
    return schema_conn, seed_delivery(schema_conn)


@pytest.mark.parametrize("finish,risk,hours", [
    ("2026-09-09 23:59:59", "on_time", 0),
    ("2026-09-10 00:00:00", "overdue", 0),
    ("2026-09-10 06:30:00", "overdue", 6.5),
    ("2026-09-11 00:00:00", "overdue", 24),
])
def test_due_day_includes_entire_day_and_next_midnight_is_exclusive(delivery, finish, risk, hours):
    conn, _ = delivery
    conn.execute("UPDATE Schedule SET end_time=? WHERE version=2", (finish,))
    conn.commit()
    public, facts = read(conn, context(conn))
    item = public["items"][0]
    assert item["risk"] == risk and item["is_overdue"] == (risk == "overdue")
    assert item["delay_hours"] == hours and item["delay_days"] == round(hours / 24, 2)
    assert item["delivery_deadline_exclusive"] == "2026-09-10T00:00:00"
    assert item["planned_finish"] == finish.replace(" ", "T")
    assert item["schedule_complete"] and item["completeness"] == "complete"
    assert facts["identity"]["version"] == 2
    assert_public(public)


@pytest.mark.parametrize("due,issue", [(None, "due_date_missing"), ("", "due_date_missing"),
                                        ("  ", "due_date_missing"), ("2026-02-30", "due_date_invalid"),
                                        ("bad", "due_date_invalid"), ("9999-12-31", "due_date_unspecified")])
def test_missing_invalid_and_sentinel_due_are_unknown_not_zero(delivery, due, issue):
    conn, _ = delivery
    conn.execute("UPDATE Batches SET due_date=? WHERE batch_id='CAT-B'", (due,))
    conn.commit()
    item = read(conn, context(conn))[0]["items"][0]
    assert item["risk"] == "unknown" and item["completeness"] == "unknown"
    assert item["is_overdue"] is None and item["delay_hours"] is None and item["delay_days"] is None
    assert item["planned_finish"] == "2026-09-09T09:00:00" and item["schedule_complete"]
    assert issue in item["issues"]


@pytest.mark.parametrize("due", ["2026/09/09", "2026-09-09T01:02:03"])
def test_due_parsing_reuses_existing_day_based_business_rule(delivery, due):
    conn, _ = delivery
    conn.execute("UPDATE Batches SET due_date=? WHERE batch_id='CAT-B'", (due,))
    conn.commit()
    assert read(conn, context(conn))[0]["items"][0]["delivery_deadline_exclusive"] == "2026-09-10T00:00:00"


def test_narrow_scope_selects_batches_but_completion_reads_full_plan(delivery):
    conn, _ = delivery
    add_operation(conn, start="2026-09-09 22:30:00", end="2026-09-10 06:30:00")
    add_batch(conn, "OUTSIDE", due="bad")
    conn.commit()
    ctx = context(conn, start="2026-09-09T08:00:00", end="2026-09-09T10:00:00")
    public, facts = read(conn, ctx)
    assert len(public["items"]) == 1
    item = public["items"][0]
    assert item["task_count"] == item["operation_count"] == 2
    assert item["planned_finish"] == "2026-09-10T06:30:00" and item["risk"] == "overdue"
    assert public["basis"]["completion_scope"] == "full_selected_plan"
    assert len(facts["tasks"]) == 3
    # An off-screen same-batch edit must invalidate the combined snapshot.
    conn.execute("UPDATE Schedule SET end_time='2026-09-10 07:00:00' WHERE version=2 AND end_time='2026-09-10 06:30:00'")
    conn.commit()
    newer = read(conn, ctx)
    assert input_fingerprint(facts) != input_fingerprint(newer[1])


@pytest.mark.parametrize("start,end", [("2026-09-09T09:00:00", "2026-09-09T10:00:00"),
                                       ("2026-09-09T07:00:00", "2026-09-09T08:00:00")])
def test_empty_half_open_scope_is_not_whole_plan_or_zero_delivery(delivery, start, end):
    conn, _ = delivery
    public, _ = read(conn, context(conn, start=start, end=end))
    assert public["items"] == [] and public["batch_count"] == 0
    assert public["items_complete"] and public["completeness"] == "unknown"
    assert "delay_hours" not in public


def test_missing_operation_not_hidden_by_completed_status_or_duplicate_tasks(delivery):
    conn, seed = delivery
    allow_legacy_segments(conn)
    missing = add_operation(conn, version=None)
    conn.execute("UPDATE BatchOperations SET status='completed' WHERE id=?", (missing,))
    conn.execute("INSERT INTO Schedule(version,op_id,start_time,end_time) VALUES (2,?,'2026-09-09 09:00:00','2026-09-09 10:00:00')", (seed["op"],))
    conn.commit()
    item = read(conn, context(conn))[0]["items"][0]
    assert item["task_count"] == 2 and item["scheduled_operation_count"] == 1 and item["operation_count"] == 2
    assert item["unscheduled_operation_count"] == 1 and item["completeness"] == "incomplete"
    assert item["planned_finish"] is None and item["partial_planned_finish"] == "2026-09-09T10:00:00"
    assert item["risk"] == "unknown" and item["delay_hours"] is None


def test_all_operation_segments_contribute_to_finish_without_double_count(delivery):
    conn, seed = delivery
    allow_legacy_segments(conn)
    add_operation(conn)
    conn.execute("INSERT INTO Schedule(version,op_id,start_time,end_time) VALUES (2,?,'2026-09-10 22:30:00','2026-09-11 06:30:00')", (seed["op"],))
    conn.execute("INSERT INTO Schedule(version,op_id,start_time,end_time) VALUES (2,?,'2026-09-10 22:30:00','2026-09-11 06:30:00')", (seed["op"],))
    conn.commit()
    item = read(conn, context(conn))[0]["items"][0]
    assert item["task_count"] == 4 and item["scheduled_operation_count"] == item["operation_count"] == 2
    assert item["planned_finish"] == "2026-09-11T06:30:00" and item["delay_hours"] == 30.5


@pytest.mark.parametrize("start,end", [("bad", "2026-09-09 10:00:00"), ("2026-09-09 08:00:00", "bad"),
                                       ("2026-09-09 09:00:00", "2026-09-09 08:00:00"),
                                       ("2026-09-09 08:00:00", "2026-09-09 08:00:00"),
                                       ("2026-09-09T08:00:00Z", "2026-09-09T09:00:00Z")])
def test_bad_time_anywhere_in_batch_invalidates_finish_even_outside_visible_window(delivery, start, end):
    conn, _ = delivery
    ctx = context(conn, start="2026-09-09T08:00:00", end="2026-09-09T09:00:00")
    add_operation(conn, start=start, end=end)
    conn.commit()
    item = read(conn, ctx)[0]["items"][0]
    assert item["planned_finish"] is None and item["risk"] == "unknown"
    assert item["invalid_task_count"] == 1 and "schedule_time_invalid" in item["issues"]
    assert item["completeness"] == "unknown" and item["delay_hours"] is None


def test_candidates_same_version_and_scenario_use_their_own_rows(delivery):
    conn, seed = delivery
    conn.execute("UPDATE ScheduleCandidateRows SET end_time='2026-09-10 01:00:00' WHERE candidate_id=?", (seed["baseline"],))
    conn.execute("UPDATE ScheduleCandidateRows SET end_time='2026-09-11 02:00:00' WHERE candidate_id=?", (seed["critical"],))
    conn.execute("UPDATE ScheduleAdjustmentScenarioRow SET end_time='2026-09-12 03:00:00'")
    conn.execute("UPDATE ScheduleHistory SET result_summary=? WHERE version=2",
                 (json.dumps({"incomplete_batches": {"count": 1, "items": [{"batch_id": "CAT-B"}]}}),))
    conn.commit()
    scopes = [("baseline_best", None, 1), ("critical_best", None, 26), ("baseline_best", "DELIVERY-SCENARIO", 51)]
    refs, fingerprints = set(), set()
    for role, scenario_id, hours in scopes:
        public, facts = read(conn, context(conn, role=role, scenario_id=scenario_id))
        assert public["items"][0]["delay_hours"] == hours
        assert "is_current_official" not in public and public["basis"]["kind"] == "planned_delivery"
        refs.add(public["plan_ref"])
        fingerprints.add(input_fingerprint(facts))
        assert_public(public)
    assert len(refs) == len(fingerprints) == 3


def test_shared_schedule_role_keeps_requested_ref_without_official_grant(delivery):
    conn, seed = delivery
    alias_official(conn, seed)
    candidate = read(conn, context(conn, role="baseline_best"))[0]
    official = read(conn, context(conn))[0]
    assert candidate["plan_ref"] != official["plan_ref"] and candidate["items"] == official["items"]
    assert "is_current_official" not in candidate


@pytest.mark.parametrize("changes", [{"candidate_id": -1}, {"source_table": "schedule"},
                                     {"effective_plan_role": "adopted"}, {"version": 1},
                                     {"plan_resolution_status": "fallback_to_adopted"}])
def test_mismatched_identity_is_rejected_without_fallback(delivery, changes):
    conn, _ = delivery
    scope, identity = context(conn, role="baseline_best")
    with pytest.raises(WorkbenchCommandRejected) as exc:
        read(conn, (scope, replace(identity, **changes)))
    assert exc.value.code == "plan_binding_invalid"


@pytest.mark.parametrize("status", ["published", "expired", "discarded"])
def test_inactive_scenario_never_becomes_base_or_published_plan(delivery, status):
    conn, _ = delivery
    ctx = context(conn, role="baseline_best", scenario_id="DELIVERY-SCENARIO")
    conn.execute("UPDATE ScheduleAdjustmentScenario SET status=?,published_version=2", (status,))
    conn.commit()
    with pytest.raises(WorkbenchCommandRejected) as exc:
        read(conn, ctx)
    assert exc.value.code == "plan_unavailable"


def test_stale_role_reference_never_rebinds_to_new_candidate(delivery):
    conn, seed = delivery
    ctx = context(conn, role="baseline_best")
    conn.execute("UPDATE ScheduleCandidateSelection SET candidate_id=? WHERE role='baseline_best'", (seed["critical"],))
    conn.commit()
    with pytest.raises(WorkbenchPlanReferenceError):
        read(conn, ctx)


@pytest.mark.parametrize("summary,completeness,issue", [
    ({"incomplete_batches": {"count": 1, "items": [{"batch_id": "CAT-B"}]}}, "incomplete", "saved_plan_incomplete"),
    ({"incomplete_batches": {"count": 2, "items": [{"batch_id": "OTHER"}]}}, "unknown", "completion_summary_sampled"),
    ({"counts": {"failed_ops": 1}}, "unknown", "completion_failures_unattributed"),
    ({"counts": {"failed_ops": "bad"}}, "unknown", "completion_summary_invalid"),
    ({"failure_details": [{"batch_id": "CAT-B", "code": "failed"}]}, "incomplete", "saved_plan_incomplete"),
])
def test_summary_cannot_turn_partially_failed_batches_into_healthy(delivery, summary, completeness, issue):
    conn, _ = delivery
    conn.execute("UPDATE ScheduleHistory SET result_summary=? WHERE version=2", (json.dumps(summary),))
    conn.commit()
    item = read(conn, context(conn))[0]["items"][0]
    assert item["completeness"] == completeness and issue in item["issues"]
    assert item["planned_finish"] is None and item["risk"] == "unknown" and item["delay_hours"] is None


def test_candidate_failures_are_read_from_exact_candidate_summary(delivery):
    conn, seed = delivery
    conn.execute("UPDATE ScheduleCandidate SET summary_json=? WHERE id=?", (json.dumps({"metrics": {"failed_ops": 1}}), seed["baseline"]))
    conn.commit()
    assert read(conn, context(conn, role="baseline_best"))[0]["items"][0]["risk"] == "unknown"
    assert read(conn, context(conn, role="critical_best"))[0]["items"][0]["risk"] == "on_time"


def test_scenario_row_count_mismatch_is_explicit_unknown(delivery):
    conn, _ = delivery
    ctx = context(conn, role="baseline_best", scenario_id="DELIVERY-SCENARIO")
    conn.execute("UPDATE ScheduleAdjustmentScenario SET row_count=2")
    conn.commit()
    item = read(conn, ctx)[0]["items"][0]
    assert item["risk"] == "unknown" and "scenario_rows_incomplete" in item["issues"]


def test_historical_batches_and_execution_events_remain_untouched_and_unmixed(delivery):
    conn, seed = delivery
    add_batch(conn, "HISTORICAL-ONLY", version=1)
    finish_event(conn, seed["op"])
    conn.execute("UPDATE Schedule SET end_time='2026-09-10 03:00:00' WHERE version=2")
    conn.commit()
    ctx = context(conn)
    before, changes = list(conn.iterdump()), conn.total_changes
    public, facts = read(conn, ctx)
    assert list(conn.iterdump()) == before and conn.total_changes == changes
    assert public["batch_count"] == 1 and public["items"][0]["delay_hours"] == 3
    assert public["basis"]["actual_completion"] == public["basis"]["actual_delivery"] == "not_evaluated"
    assert "actual_finish" not in public["items"][0] and "execution" not in facts
    historical = read(conn, context(conn, version=1))[0]
    assert historical["batch_count"] == 2 and historical["plan_ref"] != public["plan_ref"]


def test_refs_stable_and_live_batch_facts_participate_in_private_snapshot(delivery):
    conn, _ = delivery
    ctx = context(conn)
    first, facts = read(conn, ctx)
    conn.execute("UPDATE Batches SET due_date='2026-09-10',part_name='New part label' WHERE batch_id='CAT-B'")
    conn.commit()
    newer, newer_facts = read(conn, ctx)
    assert first["items"][0]["batch_ref"] == newer["items"][0]["batch_ref"]
    assert input_fingerprint(facts) != input_fingerprint(newer_facts)
    assert newer["items"][0]["part_label"] == "New part label"
    assert_public(newer)


def test_requires_callers_transaction_and_never_allocates_missing_ref(delivery):
    conn, _ = delivery
    scope, identity = context(conn)
    with pytest.raises(RuntimeError, match="caller-owned"):
        read_plan_delivery(conn, scope=scope, identity=identity)
    intact = list(conn.iterdump())
    tables = [row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name<>'WorkbenchEntityRefs'")]
    business = {name: list(conn.execute('SELECT * FROM "' + name + '"')) for name in tables}
    assert business["Batches"] and business["BatchOperations"] and business["Schedule"]
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    conn.execute("BEGIN")
    try:
        # Defer only this rollback-only corruption; keep dependent business rows.
        conn.execute("PRAGMA defer_foreign_keys=ON")
        conn.execute("DELETE FROM WorkbenchEntityRefs WHERE kind='batch'")
        before, changes = list(conn.iterdump()), conn.total_changes
        assert before != intact
        assert not conn.execute("SELECT 1 FROM WorkbenchEntityRefs WHERE kind='batch'").fetchall()
        assert business == {name: list(conn.execute('SELECT * FROM "' + name + '"')) for name in tables}
        conn.execute("PRAGMA query_only=ON")
        with pytest.raises(WorkbenchCommandRejected) as exc:
            read_plan_delivery(conn, scope=scope, identity=identity)
        assert exc.value.code == "identity_missing" and list(conn.iterdump()) == before
        assert conn.total_changes == changes and conn.in_transaction
    finally:
        conn.rollback()
        conn.execute("PRAGMA query_only=OFF")
    assert list(conn.iterdump()) == intact
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert conn.execute("PRAGMA defer_foreign_keys").fetchone()[0] == 0
    assert not conn.execute("PRAGMA foreign_key_check").fetchall()


def test_storage_error_propagates_instead_of_empty_delivery(delivery):
    conn, _ = delivery
    ctx = context(conn)
    conn.execute("ALTER TABLE Batches RENAME COLUMN due_date TO broken_due_date")
    conn.commit()
    with pytest.raises(AppError):
        read(conn, ctx)


def test_caller_can_reuse_transaction_without_module_commit_or_rollback(delivery):
    conn, _ = delivery
    scope, identity = context(conn)
    with readonly(conn):
        value, facts = read_plan_delivery(conn, scope=scope, identity=identity)
        assert conn.in_transaction
        assert read_plan_delivery(conn, scope=scope, identity=identity) == (value, facts)


@pytest.mark.parametrize("raw,issue", [(None, "completion_summary_missing"), ("broken-json", "completion_summary_invalid"),
                                      ('{"counts": {"failed_ops": NaN}}', "completion_summary_invalid"),
                                      ('{"incomplete_batches": []}', "completion_summary_invalid"),
                                      ('{"failure_details": [null]}', "completion_summary_invalid")])
def test_bad_or_missing_official_summary_never_claims_complete(delivery, raw, issue):
    conn, _ = delivery
    ctx = context(conn)
    conn.execute("UPDATE ScheduleHistory SET result_summary=? WHERE version=2", (raw,))
    conn.commit()
    item = read(conn, ctx)[0]["items"][0]
    assert item["planned_finish"] is None and item["delay_hours"] is None
    assert item["risk"] == "unknown" and issue in item["issues"]


def test_missing_batch_label_is_not_guessed_from_master_data(delivery):
    conn, _ = delivery
    conn.execute("UPDATE Batches SET part_name=NULL WHERE batch_id='CAT-B'")
    conn.commit()
    item = read(conn, context(conn))[0]["items"][0]
    assert item["part_label"] is None and item["completeness"] == "unknown"
    assert "part_label_missing" in item["issues"]


def test_all_invalid_times_still_select_batch_as_unknown_in_unrelated_range(delivery):
    conn, _ = delivery
    ctx = context(conn, start="2026-10-01T00:00:00", end="2026-10-02T00:00:00")
    conn.execute("UPDATE Schedule SET start_time='bad',end_time='bad' WHERE version=2")
    conn.commit()
    item = read(conn, ctx)[0]["items"][0]
    assert item["planned_finish"] is None and item["partial_planned_finish"] is None
    assert item["risk"] == "unknown" and item["invalid_task_count"] == 1


def test_permanent_scenario_key_is_not_trimmed_into_another_scenario(delivery):
    conn, seed = delivery
    public, facts = read(conn, spaced_scenario_context(conn, seed))
    assert public["items"][0]["delay_hours"] == 6.5
    assert facts["identity"]["scenario_id"] == " DELIVERY-SCENARIO "
    plain, _ = read(conn, context(conn, role="baseline_best", scenario_id="DELIVERY-SCENARIO"))
    assert plain["items"][0]["risk"] == "on_time" and plain["plan_ref"] != public["plan_ref"]
