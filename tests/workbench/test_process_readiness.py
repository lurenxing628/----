"""Real workflow counts, corruption boundaries, no writes and fixed SQL at scale."""

import copy
import importlib
import json
import sqlite3
from unittest.mock import patch

import pytest

from core.services.process.workflow_state import workflow_snapshot
from core.services.workbench.resource_queries import WorkbenchResourceQueryService
from tests.workbench.process_readiness_support import (
    enroll,
    process_item,
    seed_catalog_scale,
    seed_mixed_catalog,
    summary,
)
from tests.workbench.process_stage_api_support import BASE, stage_api_fixture, success
from tests.workbench.process_workflow_support import confirm_all, stored_state, workflow_database
from tests.workbench.resource_metrics_support import measured_read

MODULE = "core.services.workbench.resource_readiness"


@pytest.mark.parametrize("managed,stages,expected", [
    (False, (), "source"), (True, (), "route"), (True, ("route",), "source"),
    (True, ("route", "source"), "hours"), (True, ("route", "source", "hours"), "ready"),
])
def test_real_confirmations_not_populated_legacy_fields(workflow_conn, managed, stages, expected):
    if managed:
        enroll(workflow_conn, stages=stages)
    item = process_item(workflow_conn)
    counts = item["counts"]
    assert counts["total"] == counts[expected] == 1
    assert sum(counts[key] for key in ("route", "source", "hours", "ready")) == 1
    assert counts["legacy"] == int(not managed) and counts["managed"] == int(managed)
    assert counts["legacy_route_present"] == int(not managed)
    for name in ("route", "source", "hours"):
        assert counts[name + "_confirmed"] == int(name in stages)
    assert item["status"] == ("ready" if expected == "ready" else "pending")
    assert item["issues"] == []


def test_mixed_catalog_counts_stage_and_confirmation_separately(schema_conn):
    seed_mixed_catalog(schema_conn)
    item = process_item(schema_conn)
    assert item["counts"] == {"total": 7, "route": 3, "source": 2, "hours": 1, "ready": 1,
                              "legacy": 2, "managed": 5, "legacy_route_present": 1,
                              "route_confirmed": 3, "source_confirmed": 2, "hours_confirmed": 1}
    assert item["status"] == "pending"
    assert json.loads(json.dumps(item, allow_nan=False)) == item


@pytest.mark.parametrize("managed", (False, True))
def test_empty_route_is_not_confirmation_even_if_route_parsed_yes(schema_conn, managed):
    schema_conn.execute("INSERT INTO Parts(part_no,part_name,route_parsed) VALUES ('P1','empty','yes')")
    schema_conn.commit()
    if managed:
        enroll(schema_conn)
    counts = process_item(schema_conn)["counts"]
    assert counts["route"] == 1 and counts["ready"] == counts["route_confirmed"] == counts["legacy_route_present"] == 0


def test_empty_catalog_has_no_percentage_or_ready_claim(schema_conn):
    data = summary(schema_conn)
    item = data["readiness"]["items"]["process"]
    assert item["status"] == "zero" and set(item["counts"].values()) == {0}
    assert data["readiness"]["status"] == "unknown" and data["readiness"]["ratio"] is None


@pytest.mark.parametrize("statement,stage", [
    ("UPDATE Parts SET route_raw='changed' WHERE part_no='P1'", "route"),
    ("UPDATE PartOperations SET op_type_name='changed' WHERE seq=1", "route"),
    ("UPDATE Suppliers SET status='inactive' WHERE supplier_id='S'", "source"),
    ("UPDATE PartOperations SET unit_hours=2.5 WHERE seq=1", "hours"),
    ("UPDATE ExternalGroups SET merge_mode='merged',total_days=3", "source"),
    ("UPDATE WorkbenchProcessWorkflow SET hours_signature='" + "0" * 64 + "'", "hours"),
])
def test_real_content_changes_invalidate_summary_without_repair(workflow_conn, statement, stage):
    confirm_all(workflow_conn)
    reader = WorkbenchResourceQueryService(workflow_conn, "op_type")
    first = summary(workflow_conn, reader)
    assert first["readiness"]["items"]["process"]["counts"]["ready"] == 1
    workflow_conn.execute(statement)
    workflow_conn.commit()
    before, changes = stored_state(workflow_conn), workflow_conn.total_changes
    second = summary(workflow_conn, reader)
    counts = second["readiness"]["items"]["process"]["counts"]
    assert first["counts"] == second["counts"]
    assert counts["ready"] == 0 and counts[stage] == 1
    assert stored_state(workflow_conn) == before and workflow_conn.total_changes == changes


@pytest.mark.parametrize("statement", [
    "DROP TABLE WorkbenchProcessOperationConfirmations",
    "DROP INDEX idx_wb_process_confirmation_operation",
    "DELETE FROM WorkbenchEntityRefs WHERE kind='part'",
    "DELETE FROM WorkbenchEntityRefs WHERE kind='template_operation'",
])
def test_broken_storage_is_unavailable_not_zero_and_other_facts_survive(workflow_conn, statement, caplog):
    first = summary(workflow_conn)
    workflow_conn.execute("PRAGMA foreign_keys=OFF")
    workflow_conn.execute(statement)
    workflow_conn.commit()
    before, changes = stored_state(workflow_conn), workflow_conn.total_changes
    after = summary(workflow_conn)
    item = after["readiness"]["items"]["process"]
    assert item["status"] == "unavailable" and item["counts"]["total"] == 1
    assert all(value is None for key, value in item["counts"].items() if key != "total")
    assert item["issues"][0]["code"] == "process_workflow_unavailable"
    assert "读不出来" in item["issues"][0]["message"] and "no records were repaired" in caplog.text
    for key in ("counts", "metrics", "calendar"):
        assert after[key] == first[key]
    assert stored_state(workflow_conn) == before and workflow_conn.total_changes == changes


@pytest.mark.parametrize("mutate", [
    lambda snapshot: snapshot.clear(),
    lambda snapshot: snapshot["P1"].update(workflow=None),
    lambda snapshot: snapshot["P1"]["workflow"].update(stage="bogus"),
    lambda snapshot: snapshot["P1"]["workflow"].update(ready="true"),
    lambda snapshot: snapshot["P1"]["workflow"].update(origin="legacy"),
    lambda snapshot: snapshot["P1"]["workflow"]["hours"].update(state="locked"),
    lambda snapshot: snapshot["P1"]["workflow"]["hours"].update(confirmed_at=None),
    lambda snapshot: snapshot["P1"]["workflow"]["hours"].update(confirmed_by=42),
])
def test_invalid_domain_snapshot_is_explicit_and_never_partially_counted(workflow_conn, mutate, monkeypatch):
    confirm_all(workflow_conn)
    snapshot = copy.deepcopy(workflow_snapshot(workflow_conn))
    mutate(snapshot)
    monkeypatch.setattr(importlib.import_module(MODULE), "workflow_snapshot", lambda conn: snapshot)
    item = process_item(workflow_conn)
    assert item["status"] == "unavailable" and item["counts"]["ready"] is None


def test_summary_calls_bulk_snapshot_once_and_has_zero_writes(workflow_conn):
    confirm_all(workflow_conn)
    before, changes, writes = stored_state(workflow_conn), workflow_conn.total_changes, []

    def authorize(action, table, field, database, trigger):
        if action in (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE):
            writes.append(table)
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    workflow_conn.set_authorizer(authorize)
    try:
        with patch(MODULE + ".workflow_snapshot", wraps=workflow_snapshot) as bulk:
            assert process_item(workflow_conn)["counts"]["ready"] == 1
            bulk.assert_called_once_with(workflow_conn)
    finally:
        workflow_conn.set_authorizer(lambda *args: sqlite3.SQLITE_OK)
    assert not writes and stored_state(workflow_conn) == before and workflow_conn.total_changes == changes


def test_two_thousand_templates_keep_fixed_sql_and_preserve_all_tables(workflow_conn, record_property):
    confirm_all(workflow_conn)
    with measured_read(workflow_conn) as small:
        first = summary(workflow_conn)
    seed_catalog_scale(workflow_conn, 1999)
    before, changes = stored_state(workflow_conn), workflow_conn.total_changes
    workflow_conn.execute("PRAGMA query_only=ON")
    try:
        with measured_read(workflow_conn) as large:
            result = summary(workflow_conn)
    finally:
        workflow_conn.execute("PRAGMA query_only=OFF")
    counts = result["readiness"]["items"]["process"]["counts"]
    assert counts["total"] == 2000 and counts["ready"] == 1 and counts["legacy_route_present"] == counts["source"] == 1999
    select_count = lambda report: sum(sql.lstrip().upper().startswith(("SELECT", "PRAGMA")) for sql in report["statements"])
    assert select_count(small) == select_count(large)
    assert len(small["statements"]) == len(large["statements"])
    assert result["metrics"] == first["metrics"]
    assert stored_state(workflow_conn) == before and workflow_conn.total_changes == changes
    record_property("process_readiness_scale", {"parts": 2000, "small_reads": select_count(small),
                    "large_reads": select_count(large), "small_seconds": small["seconds"], "large_seconds": large["seconds"]})


def test_three_real_stage_saves_refresh_summary_and_snapshot_without_read_writes(stage_api):
    def read():
        before = stage_api.snapshot()
        result = success(stage_api.client.get(BASE + "/resources/summary"))
        assert stage_api.snapshot() == before
        assert result["data"]["readiness"]["ratio"] is None and result["data"]["readiness"]["status"] == "unknown"
        return result

    snapshots = [read()]
    assert snapshots[0]["data"]["readiness"]["items"]["process"]["counts"]["legacy"] == 5
    actions = [("route_confirm", lambda: {"route": stage_api.route(), "discard_group_refs": []}, "source"),
               ("source_confirm", stage_api.source, "hours"), ("hours_confirm", stage_api.hours, "ready")]
    for action, payload, stage in actions:
        result = stage_api.confirm(action, payload())
        assert result["result"] == "committed"
        current = read()
        counts = current["data"]["readiness"]["items"]["process"]["counts"]
        assert counts[stage] == (2 if stage == "source" else 1) and counts["legacy"] == 4
        assert current["meta"]["snapshot_ref"] != snapshots[-1]["meta"]["snapshot_ref"]
        snapshots.append(current)
    assert "静态资料不是排产检查" in snapshots[-1]["data"]["readiness"]["message"]
