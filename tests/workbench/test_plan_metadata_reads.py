"""Catalog metadata stays streaming and retains exact persisted time semantics."""

import sqlite3

import pytest

from core.models.workbench_plan_scope import PlanCatalogScope
from core.services.workbench.plan.queries import WorkbenchPlanQueryService
from data.repositories.schedule_plan_query_repo import SchedulePlanQueryRepository
from data.repositories.workbench_plan_catalog_repo import WorkbenchPlanCatalogRepository
from tests.workbench.plan_read_support import plan_read_api  # noqa: F401


def _complete_capture_catalog(api, collection):
    """Keep the direct service call as an oracle for the HTTP catalog route."""
    with api.db() as conn:
        conn.execute("PRAGMA query_only=1")
        reader = WorkbenchPlanQueryService(conn)
        with reader.read_snapshot() as context:
            data, _ = reader.catalog_page(context, PlanCatalogScope(collection, 20), None)
            return data["plans"]


def test_catalog_streams_history_without_complete_capture(plan_api, monkeypatch):
    expected_history = _complete_capture_catalog(plan_api, "history")

    def no_full_capture(*args, **kwargs):
        pytest.fail("Catalog must not materialize complete plan arrangements")

    monkeypatch.setattr(SchedulePlanQueryRepository, "list_schedule_rows", no_full_capture)
    monkeypatch.setattr(SchedulePlanQueryRepository, "list_schedule_page", no_full_capture)
    history = plan_api.read(collection="history")["data"]["plans"]
    assert history == expected_history
    assert next(row for row in history if row["plan_ref"] == plan_api.ref())["capabilities"]["view"]
    assert not any("LEFT JOIN MACHINES" in sql.upper() for sql in plan_api.statements)


def test_metadata_time_scan_retains_raw_values_with_declared_datetime_converter(plan_api, monkeypatch):
    def converted_datetime(value):
        pytest.fail("Metadata time scan invoked the declared DATETIME converter")

    monkeypatch.setitem(sqlite3.converters, "DATETIME", converted_datetime)
    conn = sqlite3.connect(str(plan_api.path), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only=1")
        repo = WorkbenchPlanCatalogRepository(conn)
        span = repo.get_plan_time_span(version=3)
        assert span is not None and isinstance(span["start_time"], str) and isinstance(span["end_time"], str)
    finally:
        conn.close()
