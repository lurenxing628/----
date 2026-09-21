"""The owned geometry fixture must publish complete permanent plan/task references."""

import sqlite3
from contextlib import closing

import pytest

from core.infrastructure.database import ensure_schema
from core.models.workbench_plan_reference import WorkbenchPlanLocator
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository
from tests._support.paths import REPO_ROOT
from tests.app_runtime.ui_geometry_fixture_support import _seed_geometry_database


@pytest.mark.parametrize("invalid_history", [False, True])
def test_seeded_geometry_plan_has_readable_persistent_task_refs(tmp_path, invalid_history):
    path = tmp_path / "geometry-seed.db"
    ensure_schema(str(path), logger=None, schema_path=str(REPO_ROOT / "schema.sql"), backup_dir=None)
    _seed_geometry_database(path, invalid_history=invalid_history)
    with closing(sqlite3.connect(str(path))) as conn:
        conn.row_factory = sqlite3.Row
        before = list(conn.iterdump())
        repository = WorkbenchPlanIdentityRepository(conn)
        plan_ref = repository.get_plan_ref(WorkbenchPlanLocator(1, "adopted"))
        rows = [dict(row) for row in conn.execute("SELECT id AS schedule_id, op_id, version FROM Schedule")]
        assert len(rows) == 1
        refs = repository.get_task_refs(plan_ref, rows)
        assert len(refs) == 1
        assert len(repository.get_operation_refs(row["op_id"] for row in rows)) == 1
        assert list(conn.iterdump()) == before, "Reference reads must never backfill fixture identities"
