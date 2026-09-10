"""Trace observations distinguish attempted SQL from committed defaults."""

import json
import sqlite3
from contextlib import closing

import pytest
from flask import Flask

from tests.workbench.final_master_config_trace_support import trace_schedule_config


@pytest.mark.parametrize("commit", [True, False])
def test_trace_binds_attempt_and_response_without_persisting_sql(tmp_path, monkeypatch, commit):
    (tmp_path / "db").mkdir()
    database = tmp_path / "db/aps-live.db"
    with closing(sqlite3.connect(str(database))) as conn:
        conn.execute("CREATE TABLE ScheduleConfig(id INTEGER PRIMARY KEY, config_key TEXT, config_value TEXT)")
        conn.commit()
    monkeypatch.setattr(sqlite3, "connect", sqlite3.connect)
    observer = trace_schedule_config(tmp_path)
    app = Flask(__name__)

    @app.post("/api/workbench/v1/calendar/upsert")
    def command():
        with closing(sqlite3.connect(str(database))) as conn:
            conn.execute("INSERT INTO ScheduleConfig VALUES (1, 'test', 'DO-NOT-RECORD-SQL-VALUE')")
            if commit:
                conn.commit()
            else:
                conn.rollback()
        return {}, 200 if commit else 409

    observer["attach"](app)
    response = app.test_client().post("/api/workbench/v1/calendar/upsert", json={"request_key": "trace-test"})
    assert response.status_code == (200 if commit else 409)
    observer["finish"]()
    files = list(tmp_path.glob("final-master-schedule-config-trace-*.json"))
    assert len(files) == 1
    raw = files[0].read_text(encoding="utf-8")
    result = json.loads(raw)
    assert result["completed"] and result["attempted_writes"] == 1
    assert result["before_requests"]["rows"] == 0
    assert len(result["requests"]) == 1
    observed = result["requests"][0]
    assert observed["request"] == {"method": "POST", "path": "/api/workbench/v1/calendar/upsert", "request_key": "trace-test"}
    assert observed["response_status"] == response.status_code
    assert observed["committed_config"]["rows"] == int(commit)
    assert "DO-NOT-RECORD-SQL-VALUE" not in raw
    assert result["first"]["stack"]


def test_restarted_observer_does_not_overwrite_first_mutation(tmp_path, monkeypatch):
    first = tmp_path / "final-master-first-schedule-config-write.json"
    first.write_text('{"old": true}\n', encoding="utf-8")
    monkeypatch.setattr(sqlite3, "connect", sqlite3.connect)
    observer = trace_schedule_config(tmp_path)
    with closing(sqlite3.connect(":memory:")) as conn:
        conn.execute("CREATE TABLE ScheduleConfig(value TEXT)")
        conn.execute("INSERT INTO ScheduleConfig VALUES ('new')")
    observer["finish"]()
    assert first.read_text(encoding="utf-8") == '{"old": true}\n'
    report = json.loads(next(tmp_path.glob("final-master-schedule-config-trace-*.json")).read_text(encoding="utf-8"))
    assert report["first"]["request"] is None
    assert report["attempted_writes"] == 1


def test_no_write_run_records_zero_attempts(tmp_path, monkeypatch):
    monkeypatch.setattr(sqlite3, "connect", sqlite3.connect)
    observer = trace_schedule_config(tmp_path)
    observer["finish"]()
    report = json.loads(next(tmp_path.glob("final-master-schedule-config-trace-*.json")).read_text(encoding="utf-8"))
    assert report["completed"] and report["attempted_writes"] == 0
    assert report["requests"] == [] and "first" not in report
