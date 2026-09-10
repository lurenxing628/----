"""The combined browser seed reaches real registered API routes without repairs."""

import importlib
import sqlite3
from pathlib import Path

from core.models.workbench_plan_reference import WorkbenchPlanLocator
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository


def test_combined_page_fixture_reads_exact_current_plan(app_client, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parent))
    seed = importlib.import_module("migration_pages_live_server").seed
    seed(app_client.application)
    path = app_client.application.config["DATABASE_PATH"]
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        ref = WorkbenchPlanIdentityRepository(conn).get_plan_ref(WorkbenchPlanLocator(3, "adopted"))
        before = list(conn.iterdump())
    base = "/api/workbench/v1"
    responses = {}
    for suffix in ("/plans", "/plans/" + ref + "/workspace", "/analytics", "/entities/part", "/entities/batch"):
        response = app_client.get(base + suffix)
        assert response.status_code == 200, (suffix, response.get_json())
        body = response.get_json()
        assert body["ok"] and body["meta"]["source"] == "production"
        responses[suffix] = body
    data = responses["/analytics"]["data"]
    assert data["summary"]["operations"] == 23
    assert data["summary"]["confirmed_due"] == 2
    assert data["summary"]["finish_late"] == 1
    assert data["summary"]["effective_processing_hours"] is None
    assert data["plan"]["plan_ref"] == ref
    assert responses["/entities/part"]["data"]["page"]["total"] == 69
    assert responses["/entities/batch"]["data"]["page"]["total"] == 2
    with sqlite3.connect(path) as conn:
        assert list(conn.iterdump()) == before
