"""Replay the sample's real write contracts on an isolated production HTTP app."""

import json
import sqlite3
import threading
from datetime import date, timedelta

import pytest

from web.bootstrap.factory import create_app_core
from web.bootstrap.runtime_server import create_runtime_server
from web.bootstrap.sample_data import sample_blueprint
from web.bootstrap.sample_http import BASE, SampleAPIError, SampleClient, SampleProgress
from web.bootstrap.sample_injection import inject_sample, main


@pytest.fixture
def sample_server(tmp_path, monkeypatch):
    database = tmp_path / "db" / "aps.db"
    for key, value in (("APS_DB_PATH", database), ("APS_LOG_DIR", tmp_path / "logs"),
                       ("APS_BACKUP_DIR", tmp_path / "backups"), ("APS_EXCEL_TEMPLATE_DIR", tmp_path / "templates")):
        monkeypatch.setenv(key, str(value))
    monkeypatch.setenv("APS_ENV", "production")
    app = create_app_core(ui_mode="default", enable_secret_key=True, enable_security_headers=False,
                          enable_session_cookie_hardening=False)
    server = create_runtime_server(app, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        yield "http://127.0.0.1:" + str(server.server_port), database
    finally:
        server.shutdown()
        thread.join(timeout=10)
        server.server_close()


def _assert_saved_business(report, database, batches, operations):
    assert report["state"] == "seeded" and report["exercise_state"] == "not_run"
    assert report["counts"]["batches"] == batches
    assert report["counts"]["operations"] == batches * operations
    with sqlite3.connect(str(database)) as connection:
        assert connection.execute("SELECT count(*) FROM Batches").fetchone()[0] == batches
        assert connection.execute("SELECT count(*) FROM BatchOperations").fetchone()[0] == batches * operations
        assert connection.execute("SELECT count(*) FROM Schedule").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM ExternalGroups WHERE merge_mode='merged'").fetchone()[0] > 0
        assert connection.execute("SELECT count(*) FROM OperatorMachine").fetchone()[0] > 24
        assert connection.execute("SELECT count(*) FROM WorkbenchCommandReceipts").fetchone()[0] > batches
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()


def test_small_sample_saves_real_receipts_and_scoped_constraints(sample_server, tmp_path):
    base_url, database = sample_server
    output = tmp_path / "small-sample.json"
    report = inject_sample(base_url, output, batch_count=2, operation_count=12)
    _assert_saved_business(report, database, 2, 12)
    assert json.loads(output.read_text(encoding="utf-8"))["counts"] == report["counts"]
    client = SampleClient(base_url)
    for ref in report["refs"]["part"].values():
        assert client.get(BASE + "/entities/part/" + ref)["workflow"]["ready"]
    for ref in report["refs"]["batch"].values():
        detail = client.get(BASE + "/entities/batch/" + ref)
        assert len(detail["operations"]) == 12
        assert detail["template"]["complete"]
    night = client.get(BASE + "/entities/shift_profile/" + report["refs"]["shift_profile"]["CS-SHIFT-NIGHT"])
    work = next(day for day in night["fields"]["pattern"] if not day["is_rest"])
    assert work["periods"] == [{"start": "20:00", "end": "00:00", "day_offset": 0},
                               {"start": "00:30", "end": "04:30", "day_offset": 1}]
    with sqlite3.connect(str(database)) as connection:
        assert connection.execute("SELECT count(*) FROM BatchMaterialStages").fetchone()[0] == 2
        assert connection.execute("SELECT count(*) FROM BatchMaterialArrivals").fetchone()[0] == 2
        assert connection.execute("SELECT count(*) FROM MachineDowntimes WHERE status='active'").fetchone()[0] == 24
        assert connection.execute("SELECT count(*) FROM OperatorCalendar WHERE day_type='holiday'").fetchone()[0] == 16


@pytest.mark.perf
def test_full_sample_injects_five_thousand_operations(sample_server, tmp_path):
    base_url, database = sample_server
    report = inject_sample(base_url, tmp_path / "full-sample.json")
    _assert_saved_business(report, database, 100, 50)


def test_failed_receipt_is_preserved_without_retry(sample_server, tmp_path):
    base_url, database = sample_server
    client = SampleClient(base_url)
    progress = SampleProgress(tmp_path / "failure.json", client)
    with pytest.raises(SampleAPIError):
        progress.step("invalid-write", lambda: client.command(BASE + "/entities/op_type/create",
                       {"write_token": "expired"}, {"business_code": "NO-WRITE", "label": "不会保存", "fields": {}}))
    persisted = json.loads((tmp_path / "failure.json").read_text(encoding="utf-8"))
    assert persisted["state"] == "failed" and persisted["request_count"] == 1
    assert persisted["steps"][0]["response"]["committed"] is False
    with sqlite3.connect(str(database)) as connection:
        assert connection.execute("SELECT count(*) FROM OpTypes").fetchone()[0] == 0


def test_cli_refuses_formal_payload_before_reading_runtime(tmp_path):
    with pytest.raises(RuntimeError, match="正式数据"):
        main(tmp_path)
    assert not (tmp_path / "user-data").exists()


def test_default_dates_include_synthetic_history_and_future():
    blueprint = sample_blueprint(batch_count=2, operation_count=12)
    reference = date.today()
    anchor = reference - timedelta(days=14)
    while anchor.weekday() >= 5:
        anchor += timedelta(days=1)
    assert blueprint["metadata"]["anchor_date"] == anchor.isoformat()
    assert blueprint["metadata"]["synthetic_business_data"] is True
    assert blueprint["schedule_window"]["start_date"] < reference.isoformat() < blueprint["schedule_window"]["end_date"]
    assert len(blueprint["calendar_days"]) == 81
