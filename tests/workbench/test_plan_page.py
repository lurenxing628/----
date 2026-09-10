"""Private bounded pages: real schema, strictly temporary SQLite, no app calls."""

import json
import platform
import sqlite3
from dataclasses import FrozenInstanceError, fields

import pytest

from core.infrastructure.errors import AppError
from core.services.scheduler import workbench_plan_catalog as catalog
from core.services.scheduler.workbench_plan_page import (
    MAX_PLAN_PAGE_SIZE,
    HistoryPlanPage,
    ScenarioPlanPage,
    build_history_plan_page,
    build_scenario_plan_page,
)
from data.repositories import schedule_time_sql
from data.repositories.schedule_plan_query_repo import SchedulePlanQueryRepository
from data.repositories.workbench_plan_catalog_repo import MAX_PLAN_VERSION
from tests.workbench.plan_catalog_support import candidate, history, scenario, seed_operation, selection
from tests.workbench.plan_page_support import create_scale_database, measure_page


@pytest.fixture
def page_db(schema_conn):
    return schema_conn, seed_operation(schema_conn)


def test_empty_frozen_shapes_and_defaults(schema_conn):
    history_page = build_history_plan_page(schema_conn)
    scenario_page = build_scenario_plan_page(schema_conn)
    assert history_page == HistoryPlanPage(20, (), (), False, None)
    assert scenario_page == ScenarioPlanPage(20, (), (), False, None)
    assert [field.name for field in fields(HistoryPlanPage)] == [
        "page_size", "versions", "entries", "has_more", "next_before_version",
    ]
    assert [field.name for field in fields(ScenarioPlanPage)] == [
        "page_size", "scenario_ids", "entries", "has_more", "next_after_scenario_id",
    ]
    with pytest.raises(FrozenInstanceError):
        history_page.has_more = True


@pytest.mark.parametrize("loader", [build_history_plan_page, build_scenario_plan_page])
@pytest.mark.parametrize("size", [0, -1, 51, True, False, 1.0, "20", None, 2 ** 64])
def test_page_size_is_strict_and_rejected_before_sql(schema_conn, loader, size):
    statements = []
    schema_conn.set_trace_callback(statements.append)
    with pytest.raises(ValueError):
        loader(schema_conn, page_size=size)
    assert statements == []


@pytest.mark.parametrize("boundary", [0, -1, True, 2.0, "2", MAX_PLAN_VERSION + 1])
def test_history_boundary_is_strict_and_sqlite_bounded(schema_conn, boundary):
    with pytest.raises(ValueError):
        build_history_plan_page(schema_conn, before_version=boundary)


@pytest.mark.parametrize("boundary", [1, False, 3.0, "", "s\x00x"])
def test_scenario_boundary_is_an_exact_nonempty_string(schema_conn, boundary):
    with pytest.raises(ValueError):
        build_scenario_plan_page(schema_conn, after_scenario_id=boundary)


def test_history_and_scenario_cursors_cannot_be_interchanged(schema_conn):
    with pytest.raises(TypeError):
        build_history_plan_page(schema_conn, after_scenario_id="S1")
    with pytest.raises(TypeError):
        build_scenario_plan_page(schema_conn, before_version=1)


def test_history_paginates_versions_not_roles_with_deterministic_heads(page_db):
    conn, op = page_db
    for version in (1, 3, 5, 7, 9):
        history(conn, version, op_id=op)
    history(conn, 9, "partial", time="2026-09-09 12:00:00")
    history(conn, 9, "failed", time="2026-09-09 12:00:00")
    adopted = candidate(conn, 9, "adopted", source="schedule")
    selection(conn, 9, "baseline_best", adopted)
    candidate(conn, 9, "critical_best", op_id=op)
    first = build_history_plan_page(conn, page_size=2)
    second = build_history_plan_page(conn, page_size=2, before_version=first.next_before_version)
    last = build_history_plan_page(conn, page_size=2, before_version=second.next_before_version)
    assert [first.versions, second.versions, last.versions] == [(9, 7), (5, 3), (1,)]
    assert len(first.entries) == 4 and first.entries[0].schedule_result_status == "failed"
    assert first.has_more and second.has_more and not last.has_more
    assert last.next_before_version is None
    assert first.entries + second.entries + last.entries == tuple(catalog.build_plan_catalog(conn))


def test_exact_page_boundary_and_missing_seek_positions_do_not_repeat_first_page(page_db):
    conn, op = page_db
    for version in (2, 4, 6, 8):
        history(conn, version, op_id=op)
    first = build_history_plan_page(conn, page_size=2)
    last = build_history_plan_page(conn, page_size=2, before_version=first.next_before_version)
    assert last.versions == (4, 2) and not last.has_more
    assert build_history_plan_page(conn, page_size=2, before_version=5).versions == (4, 2)
    assert build_history_plan_page(conn, before_version=2).entries == ()
    assert build_history_plan_page(conn, before_version=MAX_PLAN_VERSION).versions == (8, 6, 4, 2)


@pytest.mark.parametrize("status", ["partial", "failed"])
def test_latest_status_never_promotes_an_older_page(page_db, status):
    conn, op = page_db
    history(conn, 1, op_id=op)
    history(conn, 2, status)
    latest = build_history_plan_page(conn, page_size=1).entries[0]
    older = build_history_plan_page(conn, page_size=1, before_version=2).entries[0]
    assert latest.schedule_result_status == status and latest.is_latest_version
    assert not latest.can_view and latest.plan_identity is None
    assert older.can_view and not older.is_latest_version
    assert older.plan_identity.is_superseded_by_newer_version
    assert not older.plan_identity.is_current_executable_official_version


def test_candidate_aliases_keep_identity_and_share_span_work(page_db, monkeypatch):
    conn, op = page_db
    history(conn, 1, op_id=op)
    adopted = candidate(conn, 1, "adopted", source="schedule")
    selection(conn, 1, "baseline_best", adopted)
    selection(conn, 1, "critical_best", adopted)
    spans = []
    original = SchedulePlanQueryRepository.get_plan_time_span

    def counted(self, **kwargs):
        spans.append(kwargs)
        return original(self, **kwargs)

    monkeypatch.setattr(SchedulePlanQueryRepository, "get_plan_time_span", counted)
    page = build_history_plan_page(conn, page_size=1)
    assert len(spans) == 1 and len(page.entries) == 3
    official, *aliases = page.entries
    assert official.plan_identity.is_current_executable_official_version
    for entry in aliases:
        assert entry.can_view and entry.kind == "candidate"
        assert not entry.plan_identity.is_official and not entry.plan_identity.can_write_feedback
        assert entry.plan_identity.source_row_id == official.plan_identity.source_row_id


def test_scenario_pages_use_binary_key_order_and_keep_retired_states(page_db):
    conn, op = page_db
    history(conn, 1, op_id=op)
    history(conn, 2, op_id=op)
    for key, status in (("z", "expired"), ("A", "active"), ("b", "published"), ("a", "discarded")):
        scenario(conn, key, 1, op_id=op, status=status, published_version=2 if status == "published" else None)
    expected = {entry.locator.scenario_id: entry for entry in catalog.build_plan_catalog(conn) if entry.kind == "scenario"}
    first = build_scenario_plan_page(conn, page_size=2)
    last = build_scenario_plan_page(conn, page_size=2, after_scenario_id=first.next_after_scenario_id)
    assert first.scenario_ids == ("A", "a") and last.scenario_ids == ("b", "z")
    assert first.has_more and not last.has_more and last.next_after_scenario_id is None
    for entry in first.entries + last.entries:
        assert entry == expected[entry.locator.scenario_id]
    assert last.entries[0].published_version == 2 and not last.entries[0].can_view
    assert build_scenario_plan_page(conn, after_scenario_id="zz").entries == ()
    assert build_scenario_plan_page(conn, after_scenario_id="aa").scenario_ids == ("b", "z")


@pytest.mark.parametrize("kind", ["history", "scenario"])
def test_sql_limit_and_page_only_detail_validation(page_db, monkeypatch, kind):
    conn, op = page_db
    for version in range(1, 7):
        history(conn, version, op_id=op)
        conn.execute("UPDATE Schedule SET start_time = ? WHERE version = ?", (f"OFFPAGE-{version}", version))
        scenario(conn, f"S{version}", version, op_id=op)
        conn.execute("UPDATE ScheduleAdjustmentScenarioRow SET start_time = ? WHERE scenario_id = ?",
                     (f"SCENARIO-{version}", f"S{version}"))
    observed = []
    parse = schedule_time_sql.parse_dt_for_sql

    def track(value):
        observed.append(value)
        return parse(value)

    def forbidden(*args, **kwargs):
        pytest.fail("Page read attempted full catalog/history access")

    monkeypatch.setattr(schedule_time_sql, "parse_dt_for_sql", track)
    monkeypatch.setattr(catalog, "build_plan_catalog", forbidden)
    monkeypatch.setattr(SchedulePlanQueryRepository, "list_history_identity_rows", forbidden)
    statements = []
    conn.set_trace_callback(statements.append)
    if kind == "history":
        page = build_history_plan_page(conn, page_size=2, before_version=5)
        assert page.versions == (4, 3)
        assert set(value for value in observed if value.startswith("OFFPAGE")) == {"OFFPAGE-4", "OFFPAGE-3"}
        key_sql = next(sql for sql in statements if "SELECT DISTINCT version" in sql)
        assert "version < 5" in key_sql and "LIMIT 3" in key_sql
    else:
        page = build_scenario_plan_page(conn, page_size=2, after_scenario_id="S2")
        assert page.scenario_ids == ("S3", "S4")
        assert set(value for value in observed if value.startswith("OFFPAGE")) == {"OFFPAGE-3", "OFFPAGE-4"}
        key_sql = next(sql for sql in statements if "FROM ScheduleAdjustmentScenario " in sql)
        assert "BINARY > 'S2'" in key_sql and "LIMIT 3" in key_sql
    assert all("COUNT(" not in sql.upper() and "OFFSET" not in sql.upper() for sql in statements)
    assert len(statements) <= 2 + 16 * 2


def test_active_scenario_validates_selected_preview_rows_not_lookahead(page_db, monkeypatch):
    conn, op = page_db
    history(conn, 1, op_id=op)
    for key in ("A", "B", "C", "D"):
        scenario(conn, key, 1, op_id=op)
        conn.execute("UPDATE ScheduleAdjustmentScenarioRow SET start_time = ? WHERE scenario_id = ?",
                     (f"PREVIEW-{key}", key))
    parse = schedule_time_sql.parse_dt_for_sql
    observed = []

    def track(value):
        observed.append(value)
        return parse(value)

    monkeypatch.setattr(schedule_time_sql, "parse_dt_for_sql", track)
    page = build_scenario_plan_page(conn, page_size=2, after_scenario_id="A")
    assert page.scenario_ids == ("B", "C") and page.has_more
    assert not any(entry.can_view for entry in page.entries)
    assert set(value for value in observed if value.startswith("PREVIEW")) == {"PREVIEW-B", "PREVIEW-C"}


def test_inactive_scenario_page_reads_no_plan_details(page_db, monkeypatch):
    conn, op = page_db
    history(conn, 1, op_id=op)
    scenario(conn, "inactive", 1, status="published", published_version=2)

    def forbidden(value):
        pytest.fail("Inactive scenario must not validate base/preview detail")

    monkeypatch.setattr(schedule_time_sql, "parse_dt_for_sql", forbidden)
    statements = []
    conn.set_trace_callback(statements.append)
    page = build_scenario_plan_page(conn)
    assert not page.entries[0].can_view and len(statements) == 3
    assert not any("FROM Schedule " in sql or "FROM ScheduleAdjustmentScenarioRow" in sql for sql in statements)


def test_page_size_maximum_and_fresh_request_cache(page_db):
    conn, op = page_db
    for version in range(1, 53):
        history(conn, version, op_id=op)
    first = build_history_plan_page(conn, page_size=MAX_PLAN_PAGE_SIZE)
    assert len(first.versions) == 50 and first.next_before_version == 3
    history(conn, 53, "failed")
    second = build_history_plan_page(conn, page_size=1)
    assert second.versions == (53,) and not second.entries[0].can_view


def test_read_only_dump_query_only_and_caller_transaction(page_db, monkeypatch):
    conn, op = page_db
    history(conn, 1, summary="{broken", op_id=op)
    scenario(conn, "A", 1, op_id=op)
    assert conn.in_transaction
    before, changes = list(conn.iterdump()), conn.total_changes

    def forbidden(*args, **kwargs):
        pytest.fail("Page read must not open a database or app")

    monkeypatch.setattr(sqlite3, "connect", forbidden)
    for loader in (build_history_plan_page, build_scenario_plan_page):
        assert loader(conn) == loader(conn)
    assert conn.in_transaction and conn.total_changes == changes
    assert list(conn.iterdump()) == before
    conn.commit()
    conn.execute("PRAGMA query_only = ON")
    statements = []
    conn.set_trace_callback(statements.append)
    build_history_plan_page(conn)
    build_scenario_plan_page(conn)
    assert all(sql.lstrip().startswith("SELECT") for sql in statements)
    assert not conn.in_transaction


@pytest.mark.parametrize("loader", [build_history_plan_page, build_scenario_plan_page])
def test_missing_schema_is_not_an_empty_page(mem_conn, loader):
    with pytest.raises(AppError):
        loader(mem_conn)


def test_scale_ten_thousand_histories_half_million_details(tmp_path):
    path = tmp_path / "page-scale.db"
    conn = create_scale_database(path)
    try:
        measurements = {}
        cases = (
            ("history_first", build_history_plan_page, {}),
            ("history_middle", build_history_plan_page, {"before_version": 5001}),
            ("history_deep", build_history_plan_page, {"before_version": 101}),
            ("history_max", build_history_plan_page, {"page_size": 50}),
            ("scenario_first", build_scenario_plan_page, {}),
            ("scenario_deep", build_scenario_plan_page, {"after_scenario_id": "S001900"}),
        )
        for name, loader, kwargs in cases:
            result = measure_page(conn, loader, **kwargs)
            size = kwargs.get("page_size", 20)
            assert result["entries"] == [size] * 3
            assert max(result["sql_counts"]) <= 2 + 16 * size
            measurements[name] = result
        assert measurements["history_first"]["sql_counts"] == measurements["history_deep"]["sql_counts"]
        assert measurements["scenario_first"]["sql_counts"] == measurements["scenario_deep"]["sql_counts"]
        print("PLAN_PAGE_SCALE " + json.dumps({
            "python": platform.python_version(), "machine": platform.machine(), "sqlite": sqlite3.sqlite_version,
            "history_versions": 10000, "schedule_rows": 500000, "scenarios": 2000, "scenario_rows": 40000,
            "database_bytes": path.stat().st_size, "measurements": measurements,
        }, sort_keys=True))
    finally:
        conn.close()
