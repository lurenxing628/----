"""Actual managed-host adoption, ordinary import protection and shutdown ordering."""

import threading
import time
from pathlib import Path

import pytest

from core.errors import BusinessError
from core.infrastructure.database import get_connection
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.process.part_service import PartService
from core.services.process.workflow_state import record_confirmation
from data.repositories.workbench_calibration_adoption_repo import WorkbenchCalibrationAdoptionRepository
from tests.workbench.calibration_adoption_host_support import (
    BASE,
    database_snapshot,
    prepare_calibration,
    preview_adoption,
)
from tests.workbench.calibration_adoption_support import assert_preserved
from tests.workbench.process_quota_protection_file_receipt_support import (
    QuotaFileAPI,
    assert_tables_preserved,
    file_rows,
    success,
)
from tests.workbench.run_entrypoint_support import EntryHarness
from tests.workbench.run_entrypoint_support import entrypoint_case as _case  # noqa: F401
from web.bootstrap.launcher_paths import db_scope_lock_path


def test_managed_host_calibration_lock_applies_to_ordinary_save_and_real_imports(job_case, tmp_path, monkeypatch):
    case = prepare_calibration(job_case)
    observed = {}

    def serve(app, *_):
        assert app.config["WORKBENCH_CALIBRATION_ADOPTION_ENABLED"] is True
        case.app = app
        client = app.test_client()
        body = preview_adoption(client, case, "host-calibration-adoption-0001")
        before = database_snapshot(case.db_path)
        result = success(client.post(BASE + case.template_ref + "/adopt", json=body))
        assert result["data"]["locked"] is True and result["data"]["effect_scope"] == "future_template_use_only"
        assert_preserved(before, database_snapshot(case.db_path))
        replay = success(client.post(BASE + case.template_ref + "/adopt", json=body))
        assert replay["replayed"] and replay["receipt_ref"] == result["receipt_ref"]
        assert success(client.get(BASE + case.template_ref + "/adopt/receipts/" + body["request_key"])) == replay
        with pytest.raises(WorkbenchCommandRejected) as caught:
            PartService(case.conn).update_internal_hours("P1", 1, 0, 99)
        assert caught.value.code == "calibration_quota_locked"

        api = QuotaFileAPI(case)
        rows = file_rows({"sequence": 1, "unit_hours": 99}, {"sequence": 2, "unit_hours": 8})
        mixed = api.preview(rows, fmt="xlsx")
        assert mixed["data"]["can_confirm"], mixed
        mixed_body = api.body(mixed, key="host-calibration-mixed-import-0001")
        mixed_result = success(api.confirm(mixed_body))
        assert mixed_result["result"] == "committed"
        assert mixed_result["data"]["skipped_refs"] == [case.template_ref]
        assert mixed_result["data"]["summary"]["update"] == 1
        assert dict(case.conn.execute("SELECT seq,unit_hours FROM PartOperations")) == {1: 3, 2: 8}
        assert api.receipt(mixed_body["request_key"])["data"] == mixed_result["data"]

        before_skip = database_snapshot(case.db_path)
        all_skip = api.preview(rows[:1], fmt="xlsx")
        skip_body = api.body(all_skip, key="host-calibration-skipped-import-0001")
        skip_result = success(api.confirm(skip_body))
        assert skip_result["result"] == "unchanged" and skip_result["data"]["skipped_count"] == 1
        assert_tables_preserved(before_skip, database_snapshot(case.db_path))
        assert api.receipt(skip_body["request_key"])["data"] == skip_result["data"]

        before_copy = database_snapshot(case.db_path)
        with pytest.raises(BusinessError):
            case.batch_service.create_batch_from_template("HOST-FUTURE", "P1", 10)
        assert database_snapshot(case.db_path) == before_copy
        with TransactionManager(case.conn).transaction():
            assert record_confirmation(case.conn, "P1", "hours", "Planner")["ready"]
        case.batch_service.create_batch_from_template("HOST-FUTURE", "P1", 10)
        copied = dict(case.conn.execute("SELECT seq,unit_hours FROM BatchOperations WHERE batch_id='HOST-FUTURE'"))
        assert copied == {1: 3, 2: 8}
        after_copy = database_snapshot(case.db_path)
        for table in ("Schedule", "ScheduleHistory", "WorkbenchProductionReports", "WorkbenchProductionReportRevisions",
                      "WorkbenchCalibrationAdoptions"):
            assert after_copy[table] == before_copy[table], table
        for row in before["BatchOperations"]:
            assert row in after_copy["BatchOperations"]
        observed["app"] = app

    harness = EntryHarness(job_case, tmp_path, monkeypatch, serve)
    try:
        assert harness.run() == 0
        assert observed["app"].config["WORKBENCH_CALIBRATION_ADOPTION_ENABLED"] is False
        with get_connection(str(job_case.path)) as conn:
            assert conn.execute("SELECT count(*) FROM WorkbenchCalibrationAdoptions").fetchone()[0] == 1
        harness.exit()
        assert not Path(db_scope_lock_path(str(job_case.path))).exists()
    finally:
        harness.cleanup()


def test_calibration_commit_drains_before_worker_shutdown_and_launcher_unlock(job_case, tmp_path, monkeypatch):
    case = prepare_calibration(job_case)
    entered, release = threading.Event(), threading.Event()
    threads, failures, receipts = [], [], []
    original = WorkbenchCalibrationAdoptionRepository.update_quota

    def update(repo, *args, **kwargs):
        entered.set()
        assert release.wait(10)
        return original(repo, *args, **kwargs)

    monkeypatch.setattr(WorkbenchCalibrationAdoptionRepository, "update_quota", update)

    def serve(app, *_):
        body = preview_adoption(app.test_client(), case, "host-calibration-drain-0001")
        gate = app.extensions["workbench_request_lifecycle"]
        runtime = app.extensions["workbench_run_runtime"]

        def write():
            try:
                receipts.append(success(app.test_client().post(BASE + case.template_ref + "/adopt", json=body)))
            except BaseException as exc:
                failures.append(exc)

        def finish_when_stopping():
            try:
                deadline = time.monotonic() + 5
                while gate.status["state"] == "accepting" and time.monotonic() < deadline:
                    time.sleep(.01)
                assert gate.status["state"] == "stopping" and gate.status["active"] >= 1
                assert not runtime.status["closed"]
                assert Path(db_scope_lock_path(str(job_case.path))).exists()
            except BaseException as exc:
                failures.append(exc)
            finally:
                release.set()

        writer = threading.Thread(target=write)
        threads.append(writer)
        writer.start()
        assert entered.wait(5)
        monitor = threading.Thread(target=finish_when_stopping)
        threads.append(monitor)
        monitor.start()

    harness = EntryHarness(job_case, tmp_path, monkeypatch, serve)
    try:
        assert harness.run() == 0
        for thread in threads:
            thread.join(timeout=5)
            assert not thread.is_alive()
        assert not failures and len(receipts) == 1
        with get_connection(str(job_case.path)) as conn:
            assert conn.execute("SELECT count(*) FROM WorkbenchCalibrationQuotaLocks").fetchone()[0] == 1
        assert Path(db_scope_lock_path(str(job_case.path))).exists()
        harness.exit()
        assert not Path(db_scope_lock_path(str(job_case.path))).exists()
    finally:
        release.set()
        for thread in threads:
            thread.join(timeout=5)
        harness.cleanup()
