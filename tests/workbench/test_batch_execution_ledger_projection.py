"""Batch progress and exact identity consume AJ's projection without rewriting it."""

import importlib
import sqlite3
from pathlib import Path

import pytest

from core.infrastructure.workbench_execution_ledger_schema import install_execution_ledger
from tests.workbench.batch_execution_ledger_support import batch_ledger_fixture, report
from tests.workbench.batch_support import BASE, batch_database, detail, list_data, post, state

_batch_fixture = batch_database
_ledger_fixture = batch_ledger_fixture


@pytest.mark.parametrize("quantity,expected,remaining", [(2, "partial", 3), (5, "complete", 0), (None, "partial", None), (0, "partial", 5)])
def test_report_progress_is_not_report_existence_or_unknown_zero(batch_ledger, quantity, expected, remaining):
    case = batch_ledger
    report(case, quantity)
    before = state(case.client)
    case.conn.execute("PRAGMA query_only=ON")
    entity = detail(case.client)["data"]
    op = entity["operations"][0]
    assert op["execution_state"] == expected and op["completed"] == (expected == "complete")
    assert op["execution"]["remaining_quantity"] == remaining
    assert op["execution"]["unknown_record_count"] == (1 if quantity is None else 0)
    assert op["execution"]["known_completed_quantity"] == (quantity if quantity is not None else 0)
    assert entity["relationships"]["completed_count"] == (1 if expected == "complete" else 0)
    assert entity["relationships"]["report_count"] == 1 and entity["protected"]
    rows = list_data(case.client, status="completed" if expected == "complete" else "processing")["data"]["entities"]
    assert case.batch_ref in [row["ref"] for row in rows]
    assert state(case.client) == before


@pytest.mark.parametrize("quantity", [None, 5])
def test_legal_old_finish_stays_complete_and_unknown_stays_null(batch_ledger, quantity):
    case = batch_ledger
    case.event(case.op_id, "start", version=7, batch_id="FREE-001")
    case.event(case.op_id, "finish", version=7, quantity=quantity, batch_id="FREE-001")
    op = detail(case.client)["data"]["operations"][0]
    assert op["completed"] and op["execution_state"] == "complete"
    assert op["data_quality"] == "legacy_incomplete"
    assert op["execution"]["completion_basis"] == "legacy_finish_event"
    assert op["execution"]["remaining_quantity"] == (None if quantity is None else 0)
    assert op["execution"]["reports"] == [] and len(op["execution"]["legacy_facts"]) == 2


@pytest.mark.parametrize("with_report", [False, True])
def test_stored_completion_is_not_reopened_by_incomplete_ledger(batch_ledger, with_report):
    case = batch_ledger
    if with_report:
        report(case)
    case.conn.execute("UPDATE BatchOperations SET status='completed' WHERE id=?", (case.op_id,))
    case.conn.commit()
    op = detail(case.client)["data"]["operations"][0]
    assert op["completed"] and op["status"] == "completed"
    assert op["execution_state"] == ("partial" if with_report else "unreported")
    assert any(gap["code"] == "completion_inconsistent" for gap in op["data_gaps"])
    assert post(case.client, "update", {"fields": {"quantity": 6}}).status_code == 409


def test_cross_version_refs_keep_reports_on_original_operation(batch_ledger):
    case = batch_ledger
    report(case)
    original = detail(case.client)["data"]["operations"][0]["execution"]
    case.plan(8, [case.op_id])
    current = detail(case.client)["data"]["operations"][0]["execution"]
    assert current["operation_ref"] == original["operation_ref"]
    assert current["current_task_ref"] != original["current_task_ref"]
    assert current["reports"][0]["recorded_against_task_ref"] == original["current_task_ref"]
    assert current["reports"][0]["recorded_against_plan_ref"] == original["plan_identity"]["plan_ref"]
    assert current["known_completed_quantity"] == 2


def test_quantity_reached_but_hours_missing_is_not_complete(batch_ledger):
    case = batch_ledger
    report(case, 5, effective_processing_hours=None)
    entity = detail(case.client)["data"]
    op = entity["operations"][0]
    assert op["execution"]["quantity_complete"] and not op["execution"]["records_complete"]
    assert op["execution_state"] == "partial" and not op["completed"]
    assert entity["relationships"]["completed_count"] == 0 and entity["protected"]
    assert op["execution"]["reports"][0]["effective_processing_hours"] is None


def test_real_combined_fixture_returns_two_of_twenty_three(app_client, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parent))
    importlib.import_module("migration_pages_live_server").seed(app_client.application)
    path = app_client.application.config["DATABASE_PATH"]
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("BEGIN")
        install_execution_ledger(conn)
        conn.commit()
        assert conn.execute("SELECT count(*) FROM OperationExecutionEvents WHERE batch_id='CAT-B' AND event_type='finish'").fetchone()[0] == 2
        assert conn.execute("SELECT count(*) FROM BatchOperations WHERE batch_id='CAT-B' AND status='completed'").fetchone()[0] == 0
        before = list(conn.iterdump())
    response = app_client.get(BASE)
    assert response.status_code == 200, response.get_json()
    entity = next(row for row in response.get_json()["data"]["entities"] if row["business_code"] == "CAT-B")
    assert entity["relationships"]["completed_count"] == 2
    assert entity["relationships"]["operation_count"] == 23
    assert entity["status"] == "processing" and not entity["all_operations_complete"]
    assert len([op for op in entity["operations"] if op["execution_state"] == "complete"]) == 2
    assert all(op["execution"]["completion_basis"] == "legacy_finish_event" for op in entity["operations"][:2])
    with sqlite3.connect(path) as conn:
        assert list(conn.iterdump()) == before
