"""Catalog metadata stays streaming and retains exact persisted time semantics."""

import sqlite3

import pytest

from core.models.workbench_plan_scope import PlanCatalogScope
from core.services.workbench.plan.point_query import PlanMetadataRepository, PointPlanCatalogRepository
from core.services.workbench.plan.queries import WorkbenchPlanQueryService
from core.services.workbench.plan.read_context import PlanReadContext
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


def test_catalog_streams_history_without_complete_capture(plan_api, monkeypatch):
    expected_history = _complete_capture_catalog(plan_api, "history")

    def no_full_capture(*args, **kwargs):
        pytest.fail("Catalog must not materialize complete plan arrangements")

    monkeypatch.setattr(PointPlanCatalogRepository, "source_rows", no_full_capture)
    history = plan_api.read(collection="history")["data"]["plans"]
    assert history == expected_history
    assert next(row for row in history if row["plan_ref"] == plan_api.ref())["capabilities"]["view"]
    assert not any('FROM "SCHEDULE" R' in sql.upper() for sql in plan_api.statements)


def test_metadata_time_scan_retains_raw_values_with_declared_datetime_converter(plan_api, monkeypatch):
    def converted_datetime(value):
        pytest.fail("Metadata time scan invoked the declared DATETIME converter")

    monkeypatch.setitem(sqlite3.converters, "DATETIME", converted_datetime)
    conn = sqlite3.connect(str(plan_api.path), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only=1")
        repo = PlanMetadataRepository(conn)
        span = repo.get_plan_time_span(version=3)
        assert span is not None and isinstance(span["start_time"], str) and isinstance(span["end_time"], str)
    finally:
        conn.close()
