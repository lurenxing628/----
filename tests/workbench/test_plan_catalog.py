"""Private catalog contract against isolated SQLite only, including corrupt rows."""

from dataclasses import FrozenInstanceError, fields

import pytest

from core.infrastructure.errors import AppError
from core.models.schedule_plan_identity import PlanIdentity
from core.models.schedule_plan_resolution import SchedulePlanRoleOption
from core.services.scheduler.workbench_plan_catalog import (
    PlanCatalogEntry,
    PlanCatalogIssue,
    PlanCatalogLocator,
    build_plan_catalog,
)
from tests.workbench.plan_catalog_support import candidate, history, scenario, seed_operation, selection


@pytest.fixture
def catalog_db(schema_conn):
    return schema_conn, seed_operation(schema_conn)


def test_empty_catalog_is_empty_list_without_initialization(schema_conn):
    before = list(schema_conn.iterdump())
    assert build_plan_catalog(schema_conn) == []
    assert list(schema_conn.iterdump()) == before


def test_shape_and_existing_identity_models_are_fixed(catalog_db):
    conn, op_id = catalog_db
    history(conn, 1, op_id=op_id)
    entries = build_plan_catalog(conn)
    assert type(entries) is list
    assert len(entries) == 1
    entry = entries[0]
    assert type(entry) is PlanCatalogEntry
    assert [field.name for field in fields(entry)] == [
        "locator", "kind", "display_name", "is_latest_version", "schedule_result_status", "completeness",
        "can_view", "blocked_reasons", "plan_identity", "role_option", "scenario_status", "published_version",
    ]
    assert [field.name for field in fields(PlanCatalogLocator)] == ["version", "plan_role", "scenario_id"]
    assert [field.name for field in fields(PlanCatalogIssue)] == ["code", "message"]
    assert entry.locator == PlanCatalogLocator(1, "adopted")
    assert type(entry.plan_identity) is PlanIdentity
    assert type(entry.role_option) is SchedulePlanRoleOption
    assert entry.kind == "official"
    assert entry.completeness == "complete" and entry.can_view
    assert entry.blocked_reasons == ()
    assert entry.plan_identity.is_current_executable_official_version
    assert entry.scenario_status is None and entry.published_version is None
    with pytest.raises(FrozenInstanceError):
        entry.can_view = False


@pytest.mark.parametrize("status,state", [("partial", "partial"), ("failed", "invalid")])
@pytest.mark.parametrize("has_detail", [True, False])
def test_latest_partial_or_failed_never_falls_back_to_old_success(catalog_db, status, state, has_detail):
    conn, op_id = catalog_db
    history(conn, 1, op_id=op_id)
    history(conn, 2, status, op_id=op_id if has_detail else None)
    latest, old = build_plan_catalog(conn)
    assert [latest.locator.version, old.locator.version] == [2, 1]
    assert latest.is_latest_version and not old.is_latest_version
    assert latest.schedule_result_status == status
    assert latest.completeness == (state if has_detail else "invalid")
    assert latest.can_view is has_detail
    assert latest.plan_identity is None or not latest.plan_identity.is_current_executable_official_version
    assert old.can_view and old.plan_identity.is_official
    assert old.plan_identity.is_superseded_by_newer_version
    assert not old.plan_identity.is_current_executable_official_version
    assert not old.plan_identity.can_write_feedback


def test_duplicate_history_uses_latest_record_per_version(catalog_db):
    conn, op_id = catalog_db
    history(conn, 1, op_id=op_id)
    history(conn, 1, "partial", time="2026-09-09 10:00:00")
    history(conn, 1, "failed", time="2026-09-09 10:00:00")
    entries = build_plan_catalog(conn)
    assert len(entries) == 1 and entries[0].schedule_result_status == "failed"
    assert not entries[0].plan_identity.is_current_executable_official_version


def test_representative_sharing_official_rows_remains_comparison(catalog_db):
    conn, op_id = catalog_db
    history(conn, 1, op_id=op_id)
    adopted_id = candidate(conn, 1, "adopted", source="schedule")
    selection(conn, 1, "baseline_best", adopted_id)
    candidate(conn, 1, "critical_best", op_id=op_id)
    official, shared, separate = build_plan_catalog(conn)
    assert [item.locator.plan_role for item in (official, shared, separate)] == [
        "adopted", "baseline_best", "critical_best",
    ]
    assert official.plan_identity.is_current_executable_official_version
    assert shared.plan_identity.source_row_id == official.plan_identity.source_row_id
    assert shared.plan_identity.source_table == "schedule"
    for item in (shared, separate):
        assert item.can_view and item.kind == "candidate"
        assert item.completeness == "unknown"
        assert item.plan_identity.requested_plan_role == item.locator.plan_role
        assert item.plan_identity.plan_resolution_status == "resolved_comparison"
        assert not item.plan_identity.is_official
        assert not item.plan_identity.can_dispatch and not item.plan_identity.can_write_feedback


@pytest.mark.parametrize("status", ["success", "partial", "failed"])
def test_candidate_and_scenario_do_not_inherit_official_completeness(catalog_db, status):
    conn, op_id = catalog_db
    history(conn, 1, status, op_id=op_id)
    adopted_id = candidate(conn, 1, "adopted", source="schedule")
    candidate(conn, 1, "baseline_best", op_id=op_id)
    scenario(conn, "active", 1, op_id=op_id, candidate_id=adopted_id, candidate_key="adopted")
    _, comparison, preview = build_plan_catalog(conn)
    for entry in (comparison, preview):
        assert entry.can_view and entry.completeness == "unknown"
        assert entry.schedule_result_status == status
        assert not entry.plan_identity.is_current_executable_official_version


def test_unselected_attempts_do_not_create_fictional_roles(catalog_db):
    conn, op_id = catalog_db
    history(conn, 1, op_id=op_id)
    conn.execute(
        "INSERT INTO ScheduleCandidate(version, candidate_key, candidate_label, candidate_kind, status) "
        "VALUES (1, 'attempt', 'Unselected attempt', 'baseline', 'failed')"
    )
    entries = build_plan_catalog(conn)
    assert [entry.locator for entry in entries] == [PlanCatalogLocator(1, "adopted")]


@pytest.mark.parametrize("saved,has_rows", [("no", False), ("yes", False), ("no", True)])
def test_missing_candidate_detail_is_listed_and_never_substituted(catalog_db, saved, has_rows):
    conn, op_id = catalog_db
    history(conn, 1, op_id=op_id)
    candidate(conn, 1, "adopted", source="schedule")
    candidate(conn, 1, "baseline_best", op_id=op_id if has_rows else None, saved=saved)
    official, missing = build_plan_catalog(conn)
    assert official.can_view
    assert missing.locator.plan_role == "baseline_best"
    assert missing.kind == "candidate" and not missing.can_view
    assert missing.plan_identity is None
    assert missing.role_option.detail_saved == saved
    assert missing.blocked_reasons[0].code == "plan_unavailable"
    assert "明细" in missing.blocked_reasons[0].message


def test_history_without_any_schedule_detail_stays_unavailable(schema_conn):
    history(schema_conn, 1)
    entry = build_plan_catalog(schema_conn)[0]
    assert not entry.can_view and entry.plan_identity is None
    assert entry.locator == PlanCatalogLocator(1, "adopted")
    assert "明细" in entry.blocked_reasons[0].message


@pytest.mark.parametrize("summary", ["{", "[]", '{"n": NaN}', '{"n": 1e999}'])
def test_bad_summary_is_explicit_and_does_not_poison_other_versions(catalog_db, summary):
    conn, op_id = catalog_db
    history(conn, 1, op_id=op_id)
    history(conn, 2, summary=summary, op_id=op_id)
    bad, old = build_plan_catalog(conn)
    assert bad.completeness == "invalid" and not bad.can_view
    assert bad.blocked_reasons[0].code == "summary_invalid"
    assert bad.plan_identity.result_summary_parse_failed
    assert not bad.plan_identity.can_dispatch
    assert old.can_view and old.completeness == "complete"
    assert not old.plan_identity.is_current_executable_official_version


@pytest.mark.parametrize("summary", [None, ""])
def test_missing_summary_is_unknown_not_complete(catalog_db, summary):
    conn, op_id = catalog_db
    history(conn, 1, summary=summary, op_id=op_id)
    entry = build_plan_catalog(conn)[0]
    assert entry.completeness == "unknown" and not entry.can_view
    assert entry.blocked_reasons[0].code == "summary_missing"
    assert not entry.plan_identity.is_current_executable_official_version


@pytest.mark.parametrize("damage", ["missing_candidate", "cross_version", "missing_adopted"])
def test_broken_role_relationship_is_not_hidden_or_repaired(catalog_db, damage):
    conn, op_id = catalog_db
    history(conn, 1, op_id=op_id)
    history(conn, 2, op_id=op_id)
    if damage != "missing_adopted":
        candidate(conn, 2, "adopted", source="schedule")
    target = candidate(conn, 2, "baseline_best", op_id=op_id)
    if damage != "missing_adopted":
        conn.commit()
        conn.execute("PRAGMA foreign_keys = OFF")
        if damage == "cross_version":
            conn.execute("UPDATE ScheduleCandidate SET version = 3 WHERE id = ?", (target,))
        else:
            conn.execute("DELETE FROM ScheduleCandidate WHERE id = ?", (target,))
    latest, bad, old = build_plan_catalog(conn)
    assert bad.locator == PlanCatalogLocator(2, "baseline_best")
    assert not bad.can_view and bad.completeness == "invalid"
    assert not latest.can_view and latest.plan_identity is None
    assert bad.blocked_reasons[0].message
    assert old.can_view


@pytest.mark.parametrize("status", ["failed", "skipped", "not_run"])
def test_unfinished_representative_is_not_viewable(catalog_db, status):
    conn, op_id = catalog_db
    history(conn, 1, op_id=op_id)
    candidate(conn, 1, "adopted", source="schedule")
    candidate(conn, 1, "baseline_best", op_id=op_id, status=status)
    entry = build_plan_catalog(conn)[1]
    assert entry.role_option.candidate_status == status
    assert not entry.can_view and entry.plan_identity is None


def test_comparison_cannot_claim_other_candidate_uses_official_rows(catalog_db):
    conn, op_id = catalog_db
    history(conn, 1, op_id=op_id)
    candidate(conn, 1, "adopted", source="schedule")
    candidate(conn, 1, "baseline_best", source="schedule")
    official, bad = build_plan_catalog(conn)
    assert official.can_view
    assert not bad.can_view and bad.plan_identity is None
    assert "正式采用候选" in bad.blocked_reasons[0].message


def test_adopted_binding_to_failed_candidate_is_not_healthy(catalog_db):
    conn, op_id = catalog_db
    history(conn, 1, op_id=op_id)
    candidate(conn, 1, "adopted", source="schedule", status="failed")
    entry = build_plan_catalog(conn)[0]
    assert not entry.can_view and entry.plan_identity is None
    assert entry.completeness == "invalid" and entry.blocked_reasons


@pytest.mark.parametrize("kind", ["official", "candidate", "scenario"])
def test_one_bad_time_row_cannot_hide_behind_valid_rows(catalog_db, kind):
    conn, op_id = catalog_db
    history(conn, 1, op_id=op_id)
    other_op = conn.execute(
        "INSERT INTO BatchOperations(op_code, batch_id, seq, op_type_name) "
        "VALUES ('CAT-OTHER', 'CAT-B', 2, 'Other op')"
    ).lastrowid
    if kind == "official":
        conn.execute(
            "INSERT INTO Schedule(version, op_id, start_time, end_time) VALUES (1, ?, 'bad', 'bad')", (other_op,),
        )
    elif kind == "candidate":
        candidate(conn, 1, "adopted", source="schedule")
        target = candidate(conn, 1, "baseline_best", op_id=op_id)
        conn.execute(
            "INSERT INTO ScheduleCandidateRows(version, candidate_id, op_id, start_time, end_time) "
            "VALUES (1, ?, ?, 'bad', 'bad')", (target, other_op),
        )
    else:
        scenario(conn, "bad-time", 1, op_id=op_id)
        conn.execute(
            "INSERT INTO ScheduleAdjustmentScenarioRow(scenario_id, source_table, op_id, start_time, end_time) "
            "VALUES ('bad-time', 'schedule', ?, 'bad', 'bad')", (other_op,),
        )
    entry = build_plan_catalog(conn)[-1]
    assert not entry.can_view and entry.plan_identity is None
    assert entry.completeness == "invalid"
    assert "无效时间" in entry.blocked_reasons[0].message


def test_active_scenario_and_published_official_have_distinct_identities(catalog_db):
    conn, op_id = catalog_db
    history(conn, 1, op_id=op_id)
    history(conn, 2, op_id=op_id)
    scenario(conn, "active", 1, op_id=op_id)
    scenario(conn, "published", 1, op_id=op_id, status="published", published_version=2)
    official, old, active, published = build_plan_catalog(conn)
    assert active.kind == "scenario" and active.can_view
    assert active.locator == PlanCatalogLocator(1, "adopted", "active")
    assert active.completeness == "unknown"
    assert active.plan_identity.is_preview and active.plan_identity.detail_saved
    assert not active.plan_identity.is_official and not active.plan_identity.can_write_feedback
    assert published.scenario_status == "published" and published.published_version == 2
    assert not published.can_view and published.plan_identity is None
    assert published.blocked_reasons[0].code == "scenario_not_active"
    assert official.plan_identity.is_current_executable_official_version
    assert old.plan_identity.is_superseded_by_newer_version


@pytest.mark.parametrize("status", ["discarded", "expired"])
def test_inactive_scenarios_do_not_preview(catalog_db, status):
    conn, op_id = catalog_db
    history(conn, 1, op_id=op_id)
    scenario(conn, status, 1, op_id=op_id, status=status)
    entry = build_plan_catalog(conn)[1]
    assert not entry.can_view and entry.scenario_status == status


@pytest.mark.parametrize("damage", ["no_rows", "bad_time", "missing_history", "bad_base"])
def test_unavailable_scenario_keeps_reason_and_never_falls_back(catalog_db, damage):
    conn, op_id = catalog_db
    history(conn, 1, op_id=op_id)
    scenario(conn, "broken", 9 if damage == "missing_history" else 1,
             op_id=None if damage == "no_rows" else op_id,
             source="candidate_rows" if damage == "bad_base" else "schedule")
    if damage == "bad_time":
        conn.execute("UPDATE ScheduleAdjustmentScenarioRow SET start_time = 'broken'")
    official, bad = build_plan_catalog(conn)
    assert official.can_view
    assert bad.kind == "scenario" and bad.locator.scenario_id == "broken"
    assert not bad.can_view and bad.plan_identity is None
    assert bad.completeness == "invalid" and bad.blocked_reasons[0].message


@pytest.mark.parametrize("summary", ["{}", "{broken"])
def test_repeated_reads_only_select_and_preserve_dump_and_caller_transaction(catalog_db, monkeypatch, summary):
    import sqlite3

    conn, op_id = catalog_db
    history(conn, 1, summary=summary, op_id=op_id)
    scenario(conn, "active", 1, op_id=op_id)
    assert conn.in_transaction
    before, changes = list(conn.iterdump()), conn.total_changes
    statements = []
    conn.set_trace_callback(statements.append)

    def forbidden(*args, **kwargs):
        pytest.fail("Catalog must not open another database")

    monkeypatch.setattr(sqlite3, "connect", forbidden)
    first = build_plan_catalog(conn)
    assert build_plan_catalog(conn) == first
    conn.set_trace_callback(None)
    assert statements and all(sql.lstrip().upper().startswith("SELECT") for sql in statements)
    assert conn.in_transaction and conn.total_changes == changes
    assert list(conn.iterdump()) == before
    conn.commit()
    conn.execute("PRAGMA query_only = ON")
    assert build_plan_catalog(conn) == first
    assert not conn.in_transaction


def test_missing_schema_raises_instead_of_returning_empty_or_creating_tables(mem_conn):
    with pytest.raises(AppError):
        build_plan_catalog(mem_conn)
    assert mem_conn.execute("SELECT name FROM sqlite_master").fetchall() == []
