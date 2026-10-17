"""Catalog metadata stays streaming and retains exact persisted time semantics."""

import sqlite3

import pytest

from core.models.workbench_plan_scope import PlanCatalogScope
from core.services.workbench.plan.point_query import PlanMetadataRepository, PointPlanCatalogRepository
from core.services.workbench.plan.queries import WorkbenchPlanQueryService
from core.services.workbench.plan.read_context import PlanReadContext
from tests.workbench.plan_catalog_support import scenario
from tests.workbench.plan_read_support import plan_read_api  # noqa: F401


def _complete_capture_catalog(api, collection):
    """Keep the complete-capture path as an oracle for the lean catalog reader."""
    with api.db() as conn:
        conn.execute("PRAGMA query_only=1")
        reader = WorkbenchPlanQueryService(conn)
        with reader.read_snapshot():
            context = PlanReadContext(conn, references=reader.references, entities=reader.entities)
            with context.read_scope():
                data, _ = reader._catalog_page(PlanCatalogScope(collection, 20), None, context)
                return data["plans"]


def test_catalog_streams_history_and_exact_scenario_keys_without_complete_capture(plan_api, monkeypatch):
    scenario_key = " PRIVATE-SPACED-SCENARIO "
    with plan_api.db() as conn:
        candidate_id = conn.execute("SELECT candidate_id FROM ScheduleCandidateSelection WHERE version=3 AND role='adopted'").fetchone()[0]
        op_id = conn.execute("SELECT op_id FROM Schedule WHERE version=3").fetchone()[0]
        scenario(conn, scenario_key, 3, op_id=op_id, candidate_id=candidate_id, candidate_key="adopted")
        conn.execute("UPDATE ScheduleAdjustmentScenario SET scenario_name='Spaced permanent key' WHERE scenario_id=?", (scenario_key,))
    ref = plan_api.ref(scenario_id=scenario_key)
    expected_history = _complete_capture_catalog(plan_api, "history")
    expected_scenarios = _complete_capture_catalog(plan_api, "scenario")

    def no_full_capture(*args, **kwargs):
        pytest.fail("Catalog must not materialize complete plan arrangements")

    monkeypatch.setattr(PointPlanCatalogRepository, "source_rows", no_full_capture)
    history = plan_api.read(collection="history")["data"]["plans"]
    scenarios = plan_api.read(collection="scenario")["data"]["plans"]
    assert history == expected_history and scenarios == expected_scenarios
    assert next(row for row in history if row["plan_ref"] == plan_api.ref())["capabilities"]["view"]
    assert next(row for row in scenarios if row["plan_ref"] == ref)["capabilities"]["view"]
    assert not any('FROM "SCHEDULE" R' in sql.upper() for sql in plan_api.statements)


@pytest.mark.parametrize("table,start,end,collection,role,scenario_id", [
    ("Schedule", "invalid", "2026-09-10T09:00:00", "history", "adopted", None),
    ("ScheduleCandidateRows", "2026-09-11T03:00:00", "2026-09-11T01:00:00", "history", "critical_best", None),
    ("ScheduleAdjustmentScenarioRow", "2026-09-12T23:00:00", "2026-09-12T23:00:00", "scenario", "adopted", "PRIVATE-ACTIVE"),
])
def test_catalog_metadata_keeps_invalid_time_and_unproven_point_disabled(plan_api, table, start, end, collection, role, scenario_id):
    ref = plan_api.ref(role=role, scenario_id=scenario_id)
    with plan_api.db() as conn:
        conn.execute("UPDATE " + table + " SET start_time=?,end_time=?", (start, end))
    expected = _complete_capture_catalog(plan_api, collection)
    plans = plan_api.read(collection=collection)["data"]["plans"]
    assert plans == expected
    selected = next(row for row in plans if row["plan_ref"] == ref)
    assert not selected["capabilities"]["view"] and not selected["capabilities"]["export"]
    assert selected["completeness"] == "invalid" and selected["blocked_reasons"]


def test_metadata_time_scan_retains_raw_values_with_declared_datetime_converter(plan_api, monkeypatch):
    def converted_datetime(value):
        pytest.fail("Metadata time scan invoked the declared DATETIME converter")

    monkeypatch.setitem(sqlite3.converters, "DATETIME", converted_datetime)
    conn = sqlite3.connect(str(plan_api.path), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only=1")
        repo = PlanMetadataRepository(conn)
        candidate_id = conn.execute("SELECT candidate_id FROM ScheduleCandidateSelection WHERE role='critical_best'").fetchone()[0]
        for source, candidate, scenario_id in (("schedule", None, None), ("candidate_rows", candidate_id, None),
                                               ("adjustment_scenario_rows", None, "PRIVATE-ACTIVE")):
            span = repo.get_plan_time_span(version=3, source_table=source, candidate_id=candidate, scenario_id=scenario_id)
            assert span is not None and isinstance(span["start_time"], str) and isinstance(span["end_time"], str)
    finally:
        conn.close()
