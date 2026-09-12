"""Static readiness boundaries, compatible API and full-table read-only evidence."""

import json
import os
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from core.services.scheduler.calendar_service import CalendarService
from core.services.workbench.resource_queries import WorkbenchResourceQueryService
from tests.workbench.resource_metrics_support import metrics_database, stored_state


def project(conn):
    reader = WorkbenchResourceQueryService(conn, "op_type")
    with reader.read_snapshot():
        return reader.summary_projection(clock=lambda: datetime(2026, 9, 9, 12))


def test_original_counts_and_metrics_remain_compatible(metrics_conn):
    reader = WorkbenchResourceQueryService(metrics_conn, "op_type")
    expected_counts, expected_metrics = reader.summary(), reader.summary_metrics()
    data = project(metrics_conn)
    assert data["counts"] == expected_counts and data["metrics"] == expected_metrics
    readiness = data["readiness"]
    assert readiness["status"] == "unknown" and readiness["ratio"] is None
    assert readiness["items"]["op_int"]["counts"] == expected_metrics["groups"]["internal_op_type"]["counts"]
    assert readiness["items"]["op_ext"]["counts"]["available_suppliers"] == 2
    assert readiness["items"]["machine"]["counts"]["inactive"] == 1
    assert readiness["items"]["operator"]["counts"]["unknown"] == 1
    assert readiness["items"]["operator"]["counts"]["leave"] == 1


def test_no_parts_is_zero_not_vacuously_all_ready(schema_conn):
    data = project(schema_conn)
    readiness = data["readiness"]
    assert readiness["ratio"] is None and readiness["status"] == "unknown"
    assert readiness["items"]["process"]["status"] == "zero"
    assert readiness["items"]["process"]["counts"]["total"] == 0
    assert readiness["items"]["machine"]["status"] == "zero"
    assert readiness["items"]["material"]["status"] == "zero"
    assert readiness["items"]["calendar"]["status"] == "not_configured"
    schema_conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P','test')")
    schema_conn.commit()
    process = project(schema_conn)["readiness"]["items"]["process"]
    assert process["status"] == "pending" and process["counts"]["route"] == 1
    assert process["counts"]["ready"] == 0 and process["counts"]["legacy"] == 1


@pytest.mark.parametrize("statement,affected,unaffected", [
    ("UPDATE OperatorSkill SET op_type_id='X' WHERE operator_id='OK'", "op_int", "op_ext"),
    ("UPDATE Suppliers SET op_type_id='A' WHERE supplier_id='S1'", "op_ext", "op_int"),
    ("UPDATE WorkbenchMachineGroupMembers SET group_id='GHOST' WHERE machine_id='A1'", "machine", "op_ext"),
])
def test_bad_resource_relationship_only_invalidates_its_metric_item(metrics_conn, statement, affected, unaffected):
    before = project(metrics_conn)
    metrics_conn.execute("PRAGMA foreign_keys=OFF")
    metrics_conn.execute(statement)
    metrics_conn.commit()
    stored = stored_state(metrics_conn)
    after = project(metrics_conn)
    assert after["readiness"]["items"][affected]["status"] == "unavailable"
    assert after["readiness"]["items"][affected]["issues"]
    assert after["readiness"]["items"][unaffected] == before["readiness"]["items"][unaffected]
    assert after["calendar"] == before["calendar"]
    assert stored_state(metrics_conn) == stored


def test_bad_calendar_does_not_hide_resource_counts_or_promote_partial_days(metrics_conn):
    before = project(metrics_conn)
    metrics_conn.execute("INSERT INTO WorkCalendar(date,efficiency) VALUES ('2026-09-09','bad')")
    metrics_conn.commit()
    after = project(metrics_conn)
    assert after["counts"] == before["counts"] and after["metrics"] == before["metrics"]
    assert after["readiness"]["items"]["calendar"]["status"] == "unavailable"
    assert after["calendar"]["stats"]["effective_hours"] is None


def test_resource_status_changes_refresh_even_when_same_query_service_is_reused(metrics_conn):
    reader = WorkbenchResourceQueryService(metrics_conn, "op_type")
    with reader.read_snapshot():
        first = reader.summary_projection()
    metrics_conn.execute("UPDATE Machines SET status='inactive' WHERE machine_id='A1'")
    metrics_conn.execute("UPDATE Operators SET status='unclassified' WHERE operator_id='OK'")
    metrics_conn.commit()
    with reader.read_snapshot():
        second = reader.summary_projection()
    assert first["counts"] == second["counts"]
    assert second["readiness"]["items"]["machine"]["counts"]["inactive"] == 2
    assert second["readiness"]["items"]["operator"]["counts"]["unknown"] == 2
    assert second["readiness"]["ratio"] is None


def test_summary_route_is_readonly_with_sql_write_denied_and_no_metadata_repair(metrics_conn):
    from flask import Flask, g

    from web.routes.workbench.resources import resource_summary

    app = Flask(__name__)
    app.add_url_rule("/summary", view_func=resource_summary)

    @app.before_request
    def use_fixture_database():
        g.db = metrics_conn

    # Lost references must not be silently repaired even by the full summary route.
    metrics_conn.execute("DELETE FROM WorkbenchEntityRefs WHERE kind='machine'")
    metrics_conn.commit()
    before = stored_state(metrics_conn)
    writes = []

    def authorize(action, table, field, database, trigger):
        if action in (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE):
            writes.append((action, table))
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    metrics_conn.set_authorizer(authorize)
    try:
        response = app.test_client().get("/summary")
        assert response.status_code == 200, response.get_json()
        result = response.get_json()
        assert set(result["data"]) == {"counts", "metrics", "calendar", "readiness"}
        assert result["meta"]["source"] == "production" and result["meta"]["time_basis"] == "factory_local"
        assert result["data"]["calendar"]["factory_today"] == datetime.now().date().isoformat()
        assert result["data"]["readiness"]["ratio"] is None
        assert app.test_client().get("/summary?other=1").status_code == 400
    finally:
        metrics_conn.set_authorizer(lambda *args: sqlite3.SQLITE_OK)
    assert writes == []
    assert stored_state(metrics_conn) == before


def test_summary_storage_error_is_explicit_not_demo_or_success(schema_conn):
    from core.infrastructure.errors import AppError

    schema_conn.execute("DROP TABLE OperatorSkill")
    with pytest.raises(AppError):
        project(schema_conn)


def test_real_factory_api_keeps_all_tables_and_audit_unchanged_and_refreshes(app_client, tmp_path, monkeypatch):
    import importlib

    from core.infrastructure.database import get_connection

    module = importlib.import_module("core.services.workbench.resource_calendar_summary")
    monkeypatch.setattr(module, "factory_now", lambda: datetime(2026, 9, 9, 12))
    path = Path(app_client.application.config["DATABASE_PATH"])
    assert path.resolve().parent == tmp_path.resolve()
    conn = get_connection(str(path))
    try:
        conn.execute("INSERT INTO Machines(machine_id,name,status) VALUES ('RAIL-M','fixture','active')")
        conn.execute("DELETE FROM ScheduleConfig WHERE config_key='holiday_default_efficiency'")
        conn.commit()
        service = CalendarService(conn)
        service.upsert("2026-09-09", shift_start="22:30", shift_end="06:30", efficiency=.875)
        before = stored_state(conn)
        first = app_client.get("/api/workbench/v1/resources/summary")
        assert first.status_code == 200 and first.headers["Cache-Control"] == "no-store"
        data = first.get_json()["data"]
        assert data["calendar"]["days"][2]["explicit"] is True
        assert data["calendar"]["holiday_default_efficiency"]["status"] == "not_configured"
        assert stored_state(conn) == before
        conn.execute("UPDATE Machines SET status='inactive' WHERE machine_id='RAIL-M'")
        conn.commit()
        service.upsert("2026-09-09", shift_hours=6, efficiency=.5)
        after_write = stored_state(conn)
        second = app_client.get("/api/workbench/v1/resources/summary").get_json()
        assert second["ok"] is True
        assert second["data"]["readiness"]["items"]["machine"]["counts"]["inactive"] == 1
        assert second["data"]["calendar"]["days"][2]["effective"]["effective_hours"] == 3
        assert stored_state(conn) == after_write
    finally:
        conn.close()


def test_rail_chromium109_two_sizes_two_themes(metrics_conn, tmp_path):
    from tests.workbench.test_live_browser import runtime_tools

    service = CalendarService(metrics_conn)
    service.upsert("2026-09-09", shift_start="22:30", shift_end="06:30", efficiency=.875, allow_normal="no", allow_urgent="yes")
    service.upsert("2026-09-10", shift_hours=0, efficiency=1)
    metrics_conn.execute("INSERT INTO ScheduleConfig(config_key,config_value) VALUES ('holiday_default_efficiency','.625')")
    metrics_conn.commit()
    initial = project(metrics_conn)
    service.upsert("2026-09-12", shift_hours=6, efficiency=.5)
    metrics_conn.execute("UPDATE Machines SET status='inactive' WHERE machine_id='A1'")
    metrics_conn.commit()
    changed = project(metrics_conn)
    metrics_conn.execute("UPDATE WorkCalendar SET efficiency='broken' WHERE date='2026-09-09'")
    metrics_conn.commit()
    broken = project(metrics_conn)
    fixture = tmp_path / "rail-facts.json"
    fixture.write_text(json.dumps({"initial": initial, "changed": changed, "broken": broken}, ensure_ascii=False), encoding="utf-8")
    tools = runtime_tools()
    env = dict(os.environ, NODE_PATH=tools[2], WORKBENCH_BROWSER=tools[1])
    output = tmp_path / "rail-artifacts"
    command = [tools[0], str(Path(__file__).with_name("resource_rail_probe.cjs")), str(output), str(fixture)]
    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
    print(result.stdout)
    report = json.loads((output / "component-result.json").read_text(encoding="utf-8"))
    assert report["browser"].startswith("109.") and len(report["cases"]) == 8
    assert not report["errors"] and not report["external"]
