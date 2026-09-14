"""Additional error, frozen-time, and capability boundaries for the new adapters."""

import ast
import csv
import io
from datetime import datetime
from pathlib import Path

import openpyxl
import pytest

from core.services.report.report_engine import ReportEngine
from core.services.workbench import report_facts
from tests.workbench.plan_catalog_support import history
from tests.workbench.plan_read_support import assert_error
from tests.workbench.report_api_support import event
from tests.workbench.report_api_support import report_api as _report_api
from web.routes.workbench import read_context


def test_snapshot_freezes_due_age_until_explicit_refresh(report_api, monkeypatch):
    class DayOne(datetime):
        @classmethod
        def now(cls):
            return cls(2026, 9, 2, 9, 10, 0)

    class DayTwo(datetime):
        @classmethod
        def now(cls):
            return cls(2026, 9, 3, 9, 10, 0)

    monkeypatch.setattr(read_context, "datetime", DayOne)
    first = report_api.read()
    assert first["data"]["summary"]["late_open"] == 0
    monkeypatch.setattr(read_context, "datetime", DayTwo)
    frozen = report_api.read(snapshot_ref=first["meta"]["snapshot_ref"])
    assert frozen["meta"]["as_of"] == first["meta"]["as_of"]
    assert frozen["data"]["summary"] == first["data"]["summary"]
    assert report_api.read()["data"]["summary"]["late_open"] == 21


@pytest.mark.parametrize("status", ["partial", "failed"])
def test_failed_latest_does_not_become_successful_history(report_api, status):
    with report_api.db() as conn:
        history(conn, 4, status)
    assert_error(report_api.get(), "plan_unavailable")
    assert_error(report_api.get(plan_ref=report_api.ref()), "plan_not_current_official")


def test_future_finish_is_invalid_not_completed(report_api):
    with report_api.db() as conn:
        event(conn, 3, "finish", "2099-09-02 09:00:00", quantity_done=1)
    result = report_api.read(query="OP-03")["data"]
    assert result["rows"][0]["execution_state"] == "invalid"
    assert result["rows"][0]["confirmed_finish"] is None
    assert result["summary"]["confirmed_due"] == 0
    response = report_api.client.get("/api/workbench/v1/reports/official-review/export", query_string={
        "query": "OP-03", "snapshot_ref": report_api.read(query="OP-03")["meta"]["snapshot_ref"]})
    assert response.status_code == 200
    workbook = openpyxl.load_workbook(io.BytesIO(response.data), read_only=True)
    cells = [value for row in workbook["计划和现场实际"].values for value in row]
    assert "未确认整道完工（记录时间异常）" in cells
    assert not any(isinstance(value, str) and "2099-09-02" in value for value in cells)
    workbook.close()


@pytest.mark.parametrize("topic", ["delivery", "records", "machines", "people", "quality"])
def test_empty_export_is_explicit(report_api, topic):
    first = report_api.read(topic=topic, query="no-such-operation")
    assert_error(report_api.get("/export", topic=topic, query="no-such-operation", snapshot_ref=first["meta"]["snapshot_ref"]), "empty_export", 422)


@pytest.mark.parametrize("name,limit", [("MAX_REPORT_OPERATIONS", 22), ("MAX_REPORT_EVENTS", 4)])
def test_read_capacity_never_truncates(report_api, monkeypatch, name, limit):
    monkeypatch.setattr(report_facts, name, limit)
    assert_error(report_api.get(), "query_too_large", 413)


@pytest.mark.parametrize("format_name", ["csv", "xlsx"])
def test_export_capacity_is_not_a_storage_failure(report_api, monkeypatch, format_name):
    first = report_api.read()
    monkeypatch.setattr(ReportEngine, "EXPORT_DIRECT_MAX_ROWS", 10)
    monkeypatch.setattr(ReportEngine, "EXPORT_STREAM_MAX_ROWS", 20)
    assert_error(report_api.get("/export", format=format_name, snapshot_ref=first["meta"]["snapshot_ref"]), "export_too_large", 413)


def test_range_limit_and_unassigned_plan_semantics(report_api):
    response = report_api.get(plan_finish_date_from="2026-01-01", plan_finish_date_to="2026-09-01")
    assert response.status_code == 422
    data = report_api.read(resource_type="machine", resource_ref="unassigned")["data"]
    assert all(row["execution_state"] != "unreported" for row in data["rows"])


def test_catalog_window_numbers_sort_and_staleness(report_api):
    path = "/api/workbench/v1/reports/downtime"
    first = report_api.client.get(path).get_json()
    assert len(first["data"]["rows"]) == 1
    assert first["data"]["rows"][0]["downtime_hours"] == .5
    assert "停机记录" in first["data"]["provenance"]
    query = {"snapshot_ref": first["meta"]["snapshot_ref"], "sort": "downtime_hours", "direction": "desc"}
    assert report_api.client.get(path, query_string=query).status_code == 200
    with report_api.db() as conn:
        conn.execute("UPDATE Machines SET name='改名设备' WHERE machine_id='M1'")
    assert_error(report_api.client.get(path + "/export", query_string=query), "snapshot_stale")


def test_formula_like_remark_is_literal_in_csv(report_api):
    with report_api.db() as conn:
        event(conn, 4, "start", "2026-09-02 08:00:00", remark="=1+1")
    first = report_api.read(topic="records")
    response = report_api.get("/export", topic="records", snapshot_ref=first["meta"]["snapshot_ref"])
    rows = list(csv.reader(io.StringIO(response.data.decode("utf-8-sig"))))
    column = rows[0].index("备注")
    operation_column = rows[0].index("工序")
    inserted = [row for row in rows[1:] if "OP-04" in row[operation_column]]
    assert len(inserted) == 1 and inserted[0][column] == "'=1+1"


def test_new_python_files_accept_python38_syntax():
    root = Path(__file__).resolve().parents[2]
    for pattern in ("core/models/workbench_report*.py", "core/services/workbench/report*.py", "core/services/workbench/review*.py", "web/routes/workbench/reports*.py"):
        for file in root.glob(pattern):
            ast.parse(file.read_text(encoding="utf-8"), filename=str(file), feature_version=(3, 8))
