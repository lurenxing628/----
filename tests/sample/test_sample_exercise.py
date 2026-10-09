"""Small real-HTTP sample compute/adoption/report flow on a disposable app."""

import copy
import json
import threading

import pytest

from web.bootstrap.factory import create_app_core
from web.bootstrap.launcher_runtime_lock import acquire_runtime_lock, release_runtime_lock
from web.bootstrap.runtime_server import create_runtime_server
from web.bootstrap.sample_constraint_checks import check_candidate
from web.bootstrap.sample_exercise import exercise_sample
from web.bootstrap.sample_injection import inject_sample
from web.bootstrap.workbench_run_runtime import install_workbench_run_runtime


@pytest.fixture
def sample_runtime(tmp_path, monkeypatch):
    database = tmp_path / "db" / "aps.db"
    for key, value in (("APS_DB_PATH", database), ("APS_LOG_DIR", tmp_path / "logs"),
                       ("APS_BACKUP_DIR", tmp_path / "backups"), ("APS_EXCEL_TEMPLATE_DIR", tmp_path / "templates")):
        monkeypatch.setenv(key, str(value))
    monkeypatch.setenv("APS_ENV", "production")
    app = create_app_core(ui_mode="default", enable_secret_key=True, enable_security_headers=False,
                          enable_session_cookie_hardening=False)
    scope = str(tmp_path / "launcher")
    lock = acquire_runtime_lock(scope, db_path=str(database))
    runtime = install_workbench_run_runtime(app, runtime_lock=lock)
    server = create_runtime_server(app, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        yield "http://127.0.0.1:" + str(server.server_port)
    finally:
        server.shutdown()
        thread.join(timeout=10)
        server.server_close()
        assert runtime.shutdown(timeout=30), runtime.status
        assert app.extensions["workbench_request_lifecycle"].shutdown(timeout=15)
        release_runtime_lock(scope, db_path=str(database))


def test_small_sample_exercises_real_worker_and_preserves_partial_actuals(sample_runtime, tmp_path):
    output = tmp_path / "exercise.json"
    seed = inject_sample(sample_runtime, output, batch_count=2, operation_count=8)
    assert seed["state"] == "seeded"
    report = exercise_sample(sample_runtime, seed, output)
    assert report["state"] == report["exercise_state"] == "complete"
    results = {row["name"]: row["result"] for row in report["steps"] if row["name"].startswith("exercise:")}
    checked = results["exercise:complete-candidate-constraints"]
    assert checked["task_count"] == 16
    assert checked["independent_checks"]["merged_external_cycles"] == 4
    assert checked["full_business_validation"]["can_adopt"]
    assert results["exercise:independent-conflict-trial"]["adoption_validation"]["can_adopt"] is False
    assert results["exercise:existing-formal-real-rerun"]["task_count"] == 16
    assert results["exercise:existing-formal-real-rerun"]["original_formal_plan_unchanged"] is True
    assert report["actual_report_count"] == 1
    assert results["exercise:partial-actual-replan-blocked"]["expected_rejection"] is True
    assert results["exercise:outside-partial-replan-blocked"]["expected_rejection"] is True
    assert results["exercise:outside-partial-replan-blocked"]["selected_operation_count"] == 8
    assert results["exercise:outside-partial-replan-blocked"]["new_job_or_receipt"] is False
    assert report["limitations"] and "不支持报工后再次排产" in report["limitations"][0]
    assert results["exercise:exact-csv-xlsx-exports"]["official"]["xlsx"]["rows"] == 16
    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert persisted["state"] == "complete" and persisted["official_plan_ref"] == report["official_plan_ref"]


def test_constraint_check_rejects_incomplete_public_scope():
    seed = {"blueprint": {}, "operation_refs": {"batch": {1: "expected"}}}
    workspace = {"tasks_complete": True, "tasks": [], "unplanned_operation_count": 1}
    with pytest.raises(RuntimeError, match="范围不一致"):
        check_candidate(workspace, seed, {"tasks": []})


def test_failed_real_run_is_preserved_and_not_marked_complete(tmp_path):
    from web.bootstrap.sample_exercise import exercise
    from web.bootstrap.sample_http import SampleAPIError, SampleProgress

    class FailedClient:
        base_url = "http://127.0.0.1:1"
        request_count = 0
        timeout = 120

        def post(self, path, value, status=200):
            self.request_count += 1
            raise SampleAPIError(path, 409, {"ok": False, "committed": False,
                                          "error": {"code": "snapshot_stale", "message": "真实测试拒绝"}})

    client = FailedClient()
    progress = SampleProgress(tmp_path / "failure.json", client)
    seed = {"state": "seeded", "steps": [], "schedule_window": {}, "refs": {"batch": {"B": "ref"}}}
    with pytest.raises(SampleAPIError):
        exercise(client, copy.deepcopy(seed), progress)
    saved = json.loads((tmp_path / "failure.json").read_text(encoding="utf-8"))
    assert saved["state"] == saved["exercise_state"] == "failed"
    assert saved["steps"][0]["response"]["error"]["code"] == "snapshot_stale"
    assert client.request_count == 1
